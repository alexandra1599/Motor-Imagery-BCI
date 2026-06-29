"""
ndf_shared.py
==============
Shared utilities for all ndf_main_*.py online classifier scripts.

Replaces MATLAB cnbiloop (TiD/TiC, ndf_read, stream buffers) with:
  - pylsl StreamInlet  — reads EEG frames
  - UDP socket         — sends probabilities to visual interface
  - numpy ring buffer  — replaces global stream struct
"""

import os
import sys
import time
import socket
import pickle
import numpy as np
from scipy.signal import butter, lfilter
from pylsl import StreamInlet, local_clock
try:
    from pylsl import resolve_stream  # pylsl < 1.16
except ImportError:
    from pylsl import resolve_byprop as resolve_stream  # pylsl >= 1.16

from covar_extract import extract_covariance
from cov_interpol import covariance_interpolation
from stabilizer import stabiliser
from mdm_decoder import mdm_decoder
from EOG import eog_checker


# =============================================================================
# LSL EEG stream connection
# =============================================================================
def connect_eeg_stream(stream_name: str = 'eegoSports 000170') -> StreamInlet:
    print(f'[ndf] Resolving EEG stream: {stream_name}...')
    streams = resolve_stream('name', stream_name)
    inlet   = StreamInlet(streams[0])
    print('[ndf] EEG stream connected.')
    return inlet


def connect_marker_stream(stream_name: str = 'MarkerStream'):
    print(f'[ndf] Resolving marker stream: {stream_name}...')
    try:
        streams = resolve_stream('name', stream_name)
        inlet   = StreamInlet(streams[0])
        print('[ndf] Marker stream connected.')
        return inlet
    except Exception:
        print('[ndf] No marker stream found — using UDP only.')
        return None


# =============================================================================
# UDP probability sender  (replaces sendTiC / TiC protocol)
# =============================================================================
_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_UDP_IP   = '127.0.0.1'
_UDP_PORT_PROB = 12347   # probabilities → visual interface


def send_probabilities(prob: np.ndarray, decoder: dict = None):
    """
    Send class probabilities as a comma-separated UTF-8 string on UDP
    port 12346, matching the visual/FES driver's receiveTiC() exactly:

        values = [float(x) for x in data.decode('utf-8').strip().split(',')]

    CRITICAL: values must be sent RAW in [0, 1], NOT as percentages.
    The visual driver applies its own scaling:
        prob[0] = max(0, (prob[0] - 0.5) * 2)   # rest
        prob[1] = max(0, (prob[1] - 0.5) * 2)   # move
    which assumes prob is already in [0, 1] -- sending percentages (0-100)
    here would blow that formula up to values like 59-139 instead of [0, 1],
    breaking the circle/bar fill, the FES probability-based triggering, and
    the detectionThresholdRest/Move comparisons (also defined in [0, 1]
    after the driver's own (x/100 - 0.5)/0.5 normalization of the CLI args).

    Also: the visual driver detects END OF RUN by checking
    `int(message[0]) != 1000`. Sending prob=[1000.0, 1000.0] (e.g. from
    ndf_main_adap.py's shutdown path) MUST arrive as literal 1000s on the
    wire -- do not scale here.
    """
    msg = ','.join([f'{p:.6f}' for p in prob])
    _udp_sock.sendto(msg.encode('utf-8'), (_UDP_IP, _UDP_PORT_PROB))


def send_marker_udp(event_id: int):
    """Send a marker on UDP port 12345."""
    _udp_sock.sendto(str(int(event_id)).encode('utf-8'), (_UDP_IP, 12345))


# =============================================================================
# Ring-buffer stream  (replaces MATLAB global stream struct)
# =============================================================================
class StreamBuffer:
    """
    Circular buffer for EEG + optional EOG/BIP channels.
    Replaces MATLAB global stream with explicit parameter passing.
    """
    def __init__(self, n_ch: int, n_bip: int, buffer_seconds: float,
                 frame_size: int, fs: float):
        n_buf = int(buffer_seconds * fs)
        self.fs         = float(fs)   # was missing -- needed by initialize_params()
        self.eeg        = np.zeros((n_buf, n_ch))
        self.exg        = np.zeros((n_buf, n_bip)) if n_bip > 0 else None
        self.posterior  = np.zeros((1, 2))
        self.frame_size = frame_size
        self.num_channels    = n_ch
        self.num_BIPchannels = n_bip
        self.filter_zi_eeg   = [None] * n_ch
        self.filter_zi_exg   = [None] * n_bip
        self.init_filter     = True
        self.init_filter_eog = True

    def push_eeg(self, eeg_frame: np.ndarray, b, a):
        """Shift buffer and append new frame with IIR filtering."""
        n = eeg_frame.shape[0]
        self.eeg[:-n, :] = self.eeg[n:, :]
        # Apply bandpass filter with state
        filtered = np.zeros_like(eeg_frame)
        for ch in range(self.num_channels):
            if self.init_filter or self.filter_zi_eeg[ch] is None:
                from scipy.signal import lfilter_zi
                zi = lfilter_zi(b, a) * eeg_frame[0, ch]
                self.filter_zi_eeg[ch] = zi
            out, self.filter_zi_eeg[ch] = lfilter(b, a, eeg_frame[:, ch],
                                                   zi=self.filter_zi_eeg[ch])
            filtered[:, ch] = out
        self.init_filter = False
        self.eeg[-n:, :] = filtered

    def push_exg(self, exg_frame: np.ndarray, b, a):
        """Shift EOG buffer and append new filtered frame."""
        if self.exg is None:
            return
        n = exg_frame.shape[0]
        self.exg[:-n, :] = self.exg[n:, :]
        filtered = np.zeros_like(exg_frame)
        for ch in range(self.num_BIPchannels):
            if self.init_filter_eog or self.filter_zi_exg[ch] is None:
                from scipy.signal import lfilter_zi
                zi = lfilter_zi(b, a) * exg_frame[0, ch]
                self.filter_zi_exg[ch] = zi
            out, self.filter_zi_exg[ch] = lfilter(b, a, exg_frame[:, ch],
                                                   zi=self.filter_zi_exg[ch])
            filtered[:, ch] = out
        self.init_filter_eog = False
        self.exg[-n:, :] = filtered


# =============================================================================
# Decoder loading
# =============================================================================
def load_decoder(decoder_path: str) -> dict:
    """Load most recent .pkl decoder from a directory."""
    import glob
    files = sorted(glob.glob(os.path.join(decoder_path, '*.pkl')),
                   key=os.path.getmtime)
    if not files:
        raise FileNotFoundError(f'No .pkl decoders in {decoder_path}')
    path = files[-1]
    print(f'\n Decoder Name: {os.path.basename(path)}')
    with open(path, 'rb') as f:
        decoder = pickle.load(f)
    return decoder, path


# =============================================================================
# EOG filter setup
# =============================================================================
def make_eog_filter(fs: float):
    b, a = butter(2, [1/(fs/2), 10/(fs/2)], btype='bandpass')
    return b, a


# =============================================================================
# Decoder session ID check
# =============================================================================
def check_session_id(decoder_name: str, session_id: int) -> bool:
    """Verify decoder filename ends with the correct session ID."""
    try:
        name_session = int(decoder_name[-5])   # matches MATLAB end-4 index
        if name_session != session_id:
            print('!' * 69)
            print('*** decoder ID not matching with session ID ***')
            print('!' * 69)
            return False
    except (ValueError, IndexError):
        pass
    return True


# =============================================================================
# Reference update  (online rebiasing)
# =============================================================================
def update_reference(decoder: dict, new_features: np.ndarray,
                     check_in_task: bool, eog_ok: bool) -> dict:
    """
    Update running reference covariance using geodesic interpolation.
    Initialises on first valid task epoch.
    """
    m = decoder['classification']['model']
    counter = m['TestEpochCounter']

    if counter == 1 and check_in_task and eog_ok:
        m['reference'] = new_features.copy()
        m['TestEpochCounter'] = 2
        print(f'Epoch Counter: 2, checkInTask: {check_in_task}')

    elif counter > 1 and check_in_task and eog_ok:
        m['reference'] = covariance_interpolation(
            m['reference'], new_features, 1.0 / counter)
        m['TestEpochCounter'] = counter + 1
        print(f'Epoch Counter: {counter+1}, checkInTask: {check_in_task}')

    return decoder


# =============================================================================
# Save decoder on run end
# =============================================================================
def save_decoder_run(decoder: dict, decoder_path: str,
                     decoder_name: str, session_id: int,
                     rec_id: int, classifier_type: str = '',
                     previous_dir: str = ''):
    """Save updated decoder at end of run."""
    from datetime import datetime
    dt = datetime.now().strftime('%d%m%y%H%M')

    # Save to Adapt folder
    out1 = os.path.join(decoder_path, decoder_name)
    with open(out1, 'wb') as f:
        pickle.dump(decoder, f)
    print(f'Saved decoder to {out1}')

    # Save to log history
    if previous_dir and classifier_type:
        log_dir = os.path.join(previous_dir, 'decoderLogHistory',
                               classifier_type,
                               f'Subject_{decoder["subjectID"]:03d}')
        os.makedirs(log_dir, exist_ok=True)
        stem = os.path.splitext(decoder_name)[0]
        log_name = (f'{stem}_Session_{session_id}_Online_'
                    f'Run_{rec_id}__{dt}.pkl')
        with open(os.path.join(log_dir, log_name), 'wb') as f:
            pickle.dump(decoder, f)
