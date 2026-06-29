import os
import glob
import time
import socket
import numpy as np
from scipy.signal import butter, lfilter
from pylsl import StreamInlet, resolve_stream
from eog_checker import eog_checker
from build_decoder_riemann import _matrix_pow

from f3_Lapfilter import f3_lap_filter
from f5_featext import f5_feat_ext
from covar_extract import extract_covariance
from mdm_decoder import mdm_decoder

# --- UDP setup (receive trial events) ---
UDP_IP   = '127.0.0.1'
UDP_PORT = 12345

# --- UDP setup (send classifier probabilities to visual interface) ---
UDP_PROB_PORT = 12346   # separate port for sending probabilities

# --- LSL EEG stream name ---
LSL_STREAM_NAME = 'eegoSports 000126'   # EEG amplifier stream name


def ndf_main(sub_id: int, classifier: int, positive_feedback: bool = False):
    """
    Main online BCI loop — LSL for EEG input, UDP for trial event markers.

    Parameters
    ----------
    sub_id           : int  — subject ID
    classifier       : int  — 1 = LDA, 2 = Riemannian
    positive_feedback: bool — positive feedback mode (default: False)

    Class labels:
        +1 : RH  (cue 770)
        -1 : LH  (cue 769)
        -2 : BF  (cue 772)
        +2 : BH  (cue 771)
    """
    # --- EOG threshold differs between modes ---
    threshold_eog = 150 if positive_feedback else 280
    
    classifier_name = {1: 'LDA', 2: 'Rieman', 3: 'Rieman_shifted'}.get(classifier)
    if classifier_name is None:
    	raise ValueError(f'Unknown classifier: {classifier}. Use 1 (LDA), 2 (Rieman), or 3 (Rieman_shifted).')

    # --- Locate and load decoder ---
    decoder = _load_latest_decoder(sub_id, classifier_name)
    b_eog, a_eog = butter(2, [1, 10], btype='bandpass', fs=decoder['fs'])
    decoder['filter_eog_coeff'] = {'b': b_eog, 'a': a_eog}
    decoder['threshold_eog'] = threshold_eog

    # --- Precompute band info for LDA ---
    band_info = _compute_band_info(decoder) if classifier_name == 'LDA' else None

    # --- Connect to LSL EEG stream ---
    print(f'[LSL] Resolving stream "{LSL_STREAM_NAME}"...')
    streams = resolve_stream('name', LSL_STREAM_NAME)
    inlet = StreamInlet(streams[0])
    print(f'[LSL] Connected.\n')

    # --- Setup non-blocking UDP socket for receiving trial events ---
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((UDP_IP, UDP_PORT))
    udp_sock.setblocking(False)   # non-blocking so it doesn't stall the main loop
    print(f'[UDP] Listening for events on {UDP_IP}:{UDP_PORT}\n')

    # --- Setup UDP socket for sending probabilities to visual interface ---
    udp_prob_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f'[UDP] Sending probabilities to {UDP_IP}:{UDP_PROB_PORT}\n')

    # --- Initialise signal buffer ---
    n_ch_eeg  = decoder['num_ch_eeg']
    n_ch_bip  = decoder.get('num_ch_bip', 3)
    frame_size = int(decoder['fs'] * 0.0625)   # ~1/16 s default frame
    buf_size   = int(decoder['fs'] * decoder['session_details']['dur_epoch'])

    stream = {
        'eeg':       np.zeros((buf_size, n_ch_eeg)),
        'exg':       np.zeros((buf_size, n_ch_bip)),
        'posterior': np.zeros((1, len(decoder['classification']['model']['class_names']))),
        'frame_size':      frame_size,
        'num_channels':    n_ch_eeg,
        'num_bip_channels':n_ch_bip,
        'flags': {'init_filter': True, 'init_filter_eog': True},
        'filter': {}
    }

    # --- Loop state ---
    check_start        = False
    check_in_task      = False
    printed_decoding_time = False
    n_classes = len(decoder['classification']['model']['class_names'])
    prob          = np.full(n_classes, 0.5)
    current_class = 0

    print('[ndf] Receiving frames...\n')

    try:
        while True:
            # ---- Pull EEG frame from LSL ----
            t0 = time.time()
            eeg_sample, lsl_timestamp = inlet.pull_chunk(
                timeout=1.0, max_samples=frame_size
            )
            if not eeg_sample:
                continue
            eeg_frame = np.array(eeg_sample)           # (frame_size, n_ch)
            time_frame = 1000 * (time.time() - t0)

            # ---- Poll UDP for event marker (non-blocking) ----
            event = _receive_udp(udp_sock)

            # ---- Wait for run-start marker ----
            if (event is None or event != 32766) and not check_start:
                continue
            elif event == 32766 and not check_start:
                print('#################')
                print('## Run Started ##')
                print('#################\n')
                check_start = True

            # ---- Store signals into rolling buffer ----
            exg_frame = np.zeros((eeg_frame.shape[0], n_ch_bip))  # placeholder if BIP not in LSL
            stream = _store_signals(eeg_frame, exg_frame, stream, decoder, classifier_name)

            # ---- Trial start events ----
            if event in (7691, 7701, 7711, 7721):
                check_in_task = True
                prob = np.full(n_classes, 0.5)
                _update_stream(stream, prob)
                print('\n Detected Start of Trial')
                current_class = (
                    -1 * (event == 7691) +
                     1  * (event == 7701) +
                     2  * (event == 7711) +
                    -2  * (event == 7721)
                )

            # ---- Trial end events ----
            elif event in (7692, 7702, 7693, 7703, 7712, 7722, 7713, 7723):
                check_in_task = False
                prob = np.full(n_classes, 0.5)
                _update_stream(stream, prob)
                current_class = 0
                print('\n Detected End of Trial')

            new_data     = stream['eeg'].copy()
            new_data_bip = stream['exg'].copy()

            if not np.any(np.isnan(new_data)):
                t_decode = time.time()

                if printed_decoding_time:
                    print('\b' * 25, end='', flush=True)

                predicted_label, score = _classify(
                    new_data, decoder, classifier_name, band_info
                )

                # ---- Probability update ----
                if check_in_task:
                    if positive_feedback:
                        class_names = decoder['classification']['model']['class_names']
                        pred_idx = np.where(class_names == predicted_label)[0]
                        if (
                            predicted_label == current_class and
                            len(pred_idx) > 0 and
                            score[pred_idx[0]] >= abs(prob[pred_idx[0]])
                        ):
                            p_score = np.zeros(len(score))
                            p_score[pred_idx[0]] = score[pred_idx[0]]
                            if eog_checker(new_data_bip, threshold_eog) == 1:
                                prob = prob * 0.9 + p_score * 0.1
                    else:
                        if eog_checker(new_data_bip, threshold_eog) == 1:
                            prob = prob * 0.95 + score * 0.05

                    _update_stream(stream, prob)
                    # Send probabilities to visual interface via UDP
                    # Format: "LH_prob,RH_prob" e.g. "0.3200,0.6800"
                    prob_msg = ','.join([f'{p:.4f}' for p in prob])
                    udp_prob_sock.sendto(prob_msg.encode('utf-8'),
                                        (UDP_IP, UDP_PROB_PORT))

                if positive_feedback:
                    print(np.fix(prob * 100))

                decode_ms = 1000 * (time.time() - t_decode)
                sign = '+' if predicted_label > 0 else '-'
                print(
                    f'Decoded as {sign}{abs(int(max(score) * 100)):03d}% '
                    f'in {int(decode_ms):03d}ms',
                    end='\r'
                )
                printed_decoding_time = True

            # ---- End of run ----
            if event == 32766 and check_start:
                print('\n End of run')
                break

    except Exception as e:
        print(f'[ndf] Exception: {e}')
        raise
    finally:
        _ndf_down(udp_sock, udp_prob_sock, inlet)


# =============================================================================
# Communication helpers
# =============================================================================

def _receive_udp(sock: socket.socket):
    """
    Non-blocking UDP read. Returns integer event code or None.
    Sender is expected to send the event as a plain UTF-8 integer string e.g. b'7691'
    """
    try:
        data, _ = sock.recvfrom(1024)
        return int(data.decode('utf-8').strip())
    except BlockingIOError:
        return None   # no message waiting
    except ValueError:
        return None   # malformed message


def _update_stream(stream: dict, posterior: np.ndarray):
    """Roll the posterior buffer."""
    if stream['posterior'].shape[0] != 1:
        stream['posterior'][:-1] = stream['posterior'][1:]
    stream['posterior'][-1, :] = posterior


def _ndf_down(udp_sock: socket.socket, udp_prob_sock: socket.socket, inlet):
    """Cleanup: close LSL inlet and UDP sockets."""
    print('\n\n[ndf] Cleanup: closing connections')

    # Send 1000 end-of-run signal to visual interface so it can exit cleanly
    # (equivalent to sendTiC(repmat(1000,...)) in MATLAB ndf_down)
    try:
        end_msg = '1000.0,1000.0'
        udp_prob_sock.sendto(end_msg.encode('utf-8'), (UDP_IP, UDP_PROB_PORT))
        print('[ndf] Sent end-of-run signal (1000) to visual interface.')
    except Exception:
        pass

    try:
        inlet.close_stream()
    except Exception:
        pass
    udp_sock.close()
    udp_prob_sock.close()
    print('[ndf] Done.')


# =============================================================================
# Signal processing helpers
# =============================================================================

def _store_signals(eeg, exg, stream, decoder, classifier_name):
    fs = stream['frame_size']
    stream['eeg'][:-fs, :] = stream['eeg'][fs:, :]
    stream['exg'][:-fs, :] = stream['exg'][fs:, :]
    stream['eeg'][-fs:, :] = eeg[:fs, :n_ch(stream)]
    stream['exg'][-fs:, :] = exg[:fs, :]

    if classifier_name in ('Rieman', 'Rieman_shifted'):
        stream = _bandpass_filter_eeg(eeg, stream, decoder)
    stream = _bandpass_filter_eog(exg, stream, decoder['filter_eog_coeff'])
    return stream


def n_ch(stream):
    return stream['num_channels']


def _bandpass_filter_eeg(eeg, stream, decoder):
    b = decoder['preprocessing']['band_pass_filter']['b']
    a = decoder['preprocessing']['band_pass_filter']['a']
    fs = stream['frame_size']
    if stream['flags']['init_filter']:
        stream['flags']['init_filter'] = False
        stream['filter']['zf'] = np.zeros((max(len(a), len(b)) - 1, stream['num_channels']))
    for ch in range(stream['num_channels']):
        filtered, stream['filter']['zf'][:, ch] = lfilter(
            b, a, eeg[:, ch], zi=stream['filter']['zf'][:, ch]
        )
        stream['eeg'][-fs:, ch] = filtered
    return stream


def _bandpass_filter_eog(exg, stream, coeff):
    b, a = coeff['b'], coeff['a']
    fs = stream['frame_size']
    if stream['flags']['init_filter_eog']:
        stream['flags']['init_filter_eog'] = False
        stream['filter']['zf2'] = np.zeros((max(len(a), len(b)) - 1, stream['num_bip_channels']))
    for ch in range(stream['num_bip_channels']):
        filtered, stream['filter']['zf2'][:, ch] = lfilter(
            b, a, exg[:, ch], zi=stream['filter']['zf2'][:, ch]
        )
        stream['exg'][-fs:, ch] = filtered
    return stream


def _classify(new_data, decoder, classifier_name, band_info):
    if classifier_name == 'LDA':
        filtered = f3_lap_filter(
            new_data,
            decoder['preprocessing']['spatial_filtering']['laplacian_derivations']
        )
        features = f5_feat_ext(
            filtered, decoder['fs'], band_info,
            decoder['feature_extraction']['window'],
            decoder['feature_extraction']['overlap']
        )
        features = features[decoder['feature_selection']['selected_features_indices']]
        predicted_label, score = decoder['classification']['model'].predict(features.reshape(1, -1))
        return predicted_label[0], score[0]
    elif classifier_name in ('Rieman', 'Rieman_shifted'):#elif classifier_name == 'Rieman':
        ch_indices = np.arange(decoder['num_ch_eeg'])
        ch_indices = np.delete(ch_indices, decoder['preprocessing']['channels_to_reject'])
        features = extract_covariance(new_data[:, ch_indices])

        # --- Rebiasing: apply affine transformation using stored reference ---
        # Equivalent to Affine_transformation(cov, reference) in MATLAB:
        #   C_rebiased = R^{-1/2} @ C @ R^{-1/2}
        reference = decoder['classification']['model'].get('reference')
        if reference is not None:
            ref_inv_sqrt = _matrix_pow(reference, -0.5)
            features = ref_inv_sqrt @ features @ ref_inv_sqrt

        return mdm_decoder(decoder, features)


def _compute_band_info(decoder):
    from scipy.signal import welch
    fs       = decoder['fs']
    dur_epoch = decoder['session_details']['dur_epoch']
    window   = decoder['feature_extraction']['window']
    overlap  = decoder['feature_extraction']['overlap']
    freq_bands = decoder['feature_extraction']['freq_bands']
    num_ch   = decoder['num_ch_eeg']
    _, frq = welch(
        np.random.rand(int(dur_epoch * fs)), fs=fs,
        nperseg=int(fs * window), noverlap=int(fs * window * overlap)
    )
    indx_bands = np.intersect1d(frq, freq_bands, return_indices=True)[1]
    band_info = np.zeros((len(frq), num_ch), dtype=bool)
    for ch in range(num_ch):
        band_info[indx_bands, ch] = True
    return band_info


def _load_latest_decoder(sub_id, classifier_name):
    import pickle
    current_path = os.getcwd()
    # Decoder is stored inside the TESS project folder, not parent
    decoder_path = os.path.join(
        current_path, 'f2_subjectDecoders',
        f'Subject_{sub_id:03d}_OfflineOnline', classifier_name
    )
    all_decoders = sorted(glob.glob(os.path.join(decoder_path, f'*Subject_{sub_id}*')))
    if not all_decoders:
        raise FileNotFoundError(f'No decoders found for subject {sub_id} at {decoder_path}')
    latest = all_decoders[-1]
    name   = os.path.basename(latest)
    print(f'\n Decoder Updated on:')
    print(f'\tDate (YYYY-MM-DD): {name[-24:-14]}')
    print(f'\t\t\tTime (HH-MM-SS):   {name[-12:-5]}\n')
    print(f'\n Decoder Name: \t {name}\n')
    with open(latest, 'rb') as f:
        return pickle.load(f)


# =============================================================================
# Entry point
# =============================================================================
if __name__ == '__main__':
    import sys
    sub_id            = int(sys.argv[1])
    classifier        = int(sys.argv[2])
    positive_feedback = len(sys.argv) > 3 and sys.argv[3] == 'positive'
    ndf_main(sub_id, classifier, positive_feedback=positive_feedback)
