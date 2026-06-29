"""
ndf_main_adap.py
=================

Online adaptive MDM classifier for TESS pipeline.

Covariance pipeline (mirrors al0_builddecoder.py exactly):
  1. Trace-normalize + LW shrinkage
  2. Batch Riemannian whitening — using the FITTED whitener saved in the
     decoder (same reference mean as training → same whitened space)
  3. Sequential adaptive recentering — cold-starts at None each run,
     matching the Robot+FES pipeline (UPDATE_DURING_TRIAL controls whether
     recentering updates during trials or only between them)
  4. MDM classify against prototypes (which live in batch-whitened space)

This matches the Robot+FES runtime_common.py approach:
  - Training:  pyriemann Whitening.fit_transform → prototypes in whitened space
  - Online:    Whitening.transform (same fitted ref) → sequential recentering
               → compare to prototypes

Usage:
    python3 ndf_main_adap.py <subjectID> <sessionID> <recID> <decoderChoice>
    decoderChoice: 1=Offline, 2=Offline shifted, 3=Offline+Online, 4=Offline+Online shifted
"""

import sys
import os
import time
import socket
import pickle
import glob
import numpy as np
from datetime import datetime
from scipy.signal import butter, lfilter, lfilter_zi
from sklearn.covariance import LedoitWolf
from pyriemann.utils.geodesic import geodesic_riemann
from pyriemann.utils.base import invsqrtm

from ndf_shared import (
    connect_eeg_stream, connect_marker_stream,
    send_probabilities, StreamBuffer,
    make_eog_filter,
)
from functions.m0_initializeParams import initialize_params
from functions.EOG import eog_checker
from functions.adaptive_recenter import AdaptiveRecenter

import functions.config_tess as config

# =============================================================================
# Helpers
# =============================================================================

def _matrix_pow(A: np.ndarray, power: float) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(eigvals ** power) @ eigvecs.T


class LeakyIntegrator:
    """Smooth classifier scores into a running probability estimate."""
    def __init__(self, alpha: float = 0.85):
        self.alpha = alpha
        self.accumulated = 0.5

    def reset(self):
        self.accumulated = 0.5

    def update(self, new_prob: float) -> float:
        self.accumulated = self.alpha * self.accumulated + (1 - self.alpha) * new_prob
        return self.accumulated


def interpolate_fill(value: float) -> float:
    """Map probability to display fill [0, 1] between SHAPE_MIN and SHAPE_MAX."""
    return max(0.0, min(1.0,
        (value - config.SHAPE_MIN) / (config.SHAPE_MAX - config.SHAPE_MIN)
    ))


def calculate_fill_levels(running_avg: float, mode: int):
    """
    Return (fill_move, fill_rest) in display space [0, 1].
    Only the winning side fills — prevents both filling when near 0.5.
    mode 0 = Move trial, mode 1 = Rest trial.
    """
    if running_avg >= 0.5:
        fill_mi   = interpolate_fill(running_avg)
        fill_rest = 0.0
    else:
        fill_mi   = 0.0
        fill_rest = interpolate_fill(1.0 - running_avg)
    if mode == 1:
        return fill_rest, fill_mi
    return fill_mi, fill_rest


# =============================================================================
# Fixed base path
# =============================================================================
DECODER_BASE = '/home/alexandra-admin/Desktop/TESS/f2_subjectDecoders'

# =============================================================================
# Args
# =============================================================================
subject_id     = int(sys.argv[1]) if len(sys.argv) > 1 else 1
session_id     = int(sys.argv[2]) if len(sys.argv) > 2 else 1
rec_id         = int(sys.argv[3]) if len(sys.argv) > 3 else 1
decoder_choice = sys.argv[4]       if len(sys.argv) > 4 else '1'

subject_id_str = f'{subject_id:03d}'

# =============================================================================
# Decoder path selection
# =============================================================================
print('\n=== Decoder Selection ===')
_paths = {
    '1': (f'Subject_{subject_id_str}_Offline',        'Rieman'),
    '2': (f'Subject_{subject_id_str}_Offline',        'Rieman_shifted'),
    '3': (f'Subject_{subject_id_str}_OfflineOnline',  'Rieman'),
    '4': (f'Subject_{subject_id_str}_OfflineOnline',  'Rieman_shifted'),
}
_labels = {
    '1': 'Offline only',
    '2': 'Offline only (shifted)',
    '3': 'Offline + Online',
    '4': 'Offline + Online (shifted)',
}
folder, rieman_sub = _paths.get(decoder_choice, _paths['1'])
decoder_path = os.path.join(DECODER_BASE, folder, rieman_sub)
print(f'  [{decoder_choice}] {_labels.get(decoder_choice, "Offline only")}')
print(f'  -> {decoder_path}')

# =============================================================================
# Select decoder file — most recent
# =============================================================================
all_decoders = sorted(
    glob.glob(os.path.join(decoder_path, '*.pkl')),
    key=lambda f: os.path.basename(f)
)
if not all_decoders:
    print(f'\n[ERROR] No .pkl decoders in: {decoder_path}')
    sys.exit(1)

decoder_file = all_decoders[-1]
print(f'\n  Using: {os.path.basename(decoder_file)}')
print('[ndf] pipeline: trace-norm + LW → batch whiten → sequential recenter → MDM')


# ── STARTUP CONFIG CHECK ───────────────────────────────────────
print(f'[STARTUP] SHAPE_MIN={config.SHAPE_MIN}  SHAPE_MAX={config.SHAPE_MAX}')
print(f'[STARTUP] THRESHOLD_MI={config.THRESHOLD_MI}  THRESHOLD_REST={config.THRESHOLD_REST}')
print(f'[STARTUP] INTEGRATOR_ALPHA={config.INTEGRATOR_ALPHA}')
print(f'[STARTUP] RECENTERING={config.RECENTERING}')
# ───────────────────────────────────────────────────────────────

# =============================================================================
# Load decoder
# =============================================================================
with open(decoder_file, 'rb') as f:
    decoder = pickle.load(f)

model_dict = decoder['classification']['model']
print(f' Epoch Counter = {model_dict.get("TestEpochCounter", 0)}')

# Prototypes (live in batch-whitened space)
prototypes = model_dict['parameters']
n_ch       = prototypes[0].shape[0]
decoder['numChEEG'] = n_ch
print(f' n_ch from prototype: {n_ch}')

# Load fitted pyriemann whitener (same object fitted at training time)
whitener = decoder.get('whitener', None)
if whitener is not None:
    print(f' Batch whitener: LOADED (pyriemann Whitening, metric=riemann)')
else:
    # Fallback: old-style fixed whitening via population mean
    population_mean = model_dict.get('populationMean', None)
    apply_whitening = model_dict.get('applyWhitening', False)
    if apply_whitening and population_mean is not None:
        pop_mean_inv_sqrt = _matrix_pow(population_mean, -0.5)
        print(f' Batch whitener: FALLBACK to pop_mean_inv_sqrt ({population_mean.shape})')
    else:
        pop_mean_inv_sqrt = None
        print(f' Batch whitener: DISABLED')

# Sequential adaptive recentering
# seed=None → cold start each run, matching Robot+FES pipeline
# (Prev_T=None, counter=0 at run start, same as runtime_common.py)
print(' AdaptiveRecenter: cold-start each run (seed=None, matches Robot+FES)')
recenter = AdaptiveRecenter(seed_reference=None)

# Band-pass filter
if 'spectralFilter' in decoder:
    b_bp = decoder['spectralFilter']['b']
    a_bp = decoder['spectralFilter']['a']
    print(f' Spectral filter: {decoder["spectralFilter"].get("range_hz","?")} Hz '
          f'order {decoder["spectralFilter"].get("order","?")}')
else:
    print(' [Warning] No spectralFilter in decoder — recomputing 8-30 Hz.')
    b_bp, a_bp = butter(4, [8/(config.FS/2), 30/(config.FS/2)], btype='band')

fs    = decoder['fs']
n_bip = 3

b_eog, a_eog = make_eog_filter(fs)
decoder['filterEOGCoeff'] = {'b': b_eog, 'a': a_eog}
decoder['thresholdEOG']   = config.THRESHOLD_EOG

# Channel selection
ch_to_reject = decoder['preprocessing'].get('channels_to_reject', [])
all_channels = [i for i in range(32) if (i+1) not in ch_to_reject]
print(f' Channels after rejection: {len(all_channels)} (n_ch={n_ch})')
if len(all_channels) != n_ch:
    print(f' [Warning] Truncating all_channels to {n_ch}.')
    all_channels = all_channels[:n_ch]

stream = StreamBuffer(n_ch=n_ch, n_bip=n_bip,
                      buffer_seconds=config.CLASSIFY_WINDOW/1000 + config.BASELINE_DURATION + 1.0,
                      frame_size=int(fs * 0.02), fs=fs)
initialize_params(decoder, stream)

# =============================================================================
# Classification parameters
# =============================================================================
window_size_samples = int(config.CLASSIFY_WINDOW / 1000 * fs)
baseline_samples    = int(config.BASELINE_DURATION * fs)

class_names      = model_dict.get('ClassNames') or model_dict.get('class_names')
global_threshold = model_dict.get('globalThreshold', 0.5)
print(f' Class names: {class_names}, global threshold: {global_threshold:.3f}')
print(f' Window: {config.CLASSIFY_WINDOW}ms ({window_size_samples} samples), '
      f'Step: {config.STEP_SIZE*1000:.1f}ms')
print(f' THRESHOLD_MI={config.THRESHOLD_MI}, THRESHOLD_REST={config.THRESHOLD_REST}')
print(f' INTEGRATOR_ALPHA={config.INTEGRATOR_ALPHA}, SHAPE_MIN={config.SHAPE_MIN}')
print(f' RECENTERING={config.RECENTERING}, UPDATE_DURING_TRIAL={config.UPDATE_DURING_TRIAL}')

# =============================================================================
# Save path
# =============================================================================
online_save_dir = os.path.join(DECODER_BASE, f'Subject_{subject_id_str}_Online', 'Rieman')
os.makedirs(online_save_dir, exist_ok=True)
online_save_path = os.path.join(online_save_dir, f'decoder_run{rec_id:03d}.pkl')
print(f'\n Online decoder will be saved to: {online_save_path}')

# =============================================================================
# Connect streams
# =============================================================================
eeg_inlet    = connect_eeg_stream()
marker_inlet = connect_marker_stream()

TRIG_START = {7691, 7701, 7711, 7721}
TRIG_END   = {7692, 7702, 7693, 7703, 7712, 7722, 7713, 7723}

# =============================================================================
# Riemannian distance + MDM (exp-neg softmax)
# =============================================================================

def _riemann_dist(A: np.ndarray, B: np.ndarray) -> float:
    """Affine-invariant Riemannian distance between two SPD matrices."""
    inv_sqrt_A = _matrix_pow(A, -0.5)
    inner      = inv_sqrt_A @ B @ inv_sqrt_A
    eigvals    = np.linalg.eigvalsh(inner)
    eigvals    = np.maximum(eigvals, 1e-12)
    return float(np.sqrt(np.sum(np.log(eigvals) ** 2)))


def mdm_predict_proba(cov: np.ndarray, protos: list) -> np.ndarray:
    """
    Riemannian distances → probabilities via exp(-d) softmax.
    Closer prototype = higher probability.
    """
    dists = np.array([_riemann_dist(cov, p) for p in protos])
    print(f'[DEBUG MDM] raw_dists={np.round(dists, 4)}')
    dists_shifted = dists - dists.min()
    exp_neg = np.exp(-dists_shifted)
    score   = exp_neg / exp_neg.sum()
    print(f'[DEBUG MDM] score={np.round(score, 4)}')
    return score


# =============================================================================
# Per-frame IIR filter state
# =============================================================================
filter_zi_eeg = [lfilter_zi(b_bp, a_bp) * 0.0 for _ in range(n_ch)]
filter_zi_eog = [lfilter_zi(b_eog, a_eog) * 0.0 for _ in range(n_bip)]
filter_init   = True

# Rolling EEG buffer
_buf_size  = int((config.BASELINE_DURATION + config.CLASSIFY_WINDOW/1000 + 2.0) * fs)
_eeg_buf   = np.full((_buf_size, n_ch), np.nan)
_buf_ptr   = 0
_buf_count = 0

_baseline_mean = None


def _push_samples(raw_chunk: np.ndarray):
    global filter_init, _buf_ptr, _buf_count, filter_zi_eeg

    n = raw_chunk.shape[0]
    if raw_chunk.shape[1] >= 64:
        eeg_raw = raw_chunk[:, all_channels]
    else:
        eeg_raw = raw_chunk[:, :n_ch]

    filtered = np.zeros((n, n_ch))
    for ch in range(n_ch):
        if filter_init or np.all(filter_zi_eeg[ch] == 0):
            filter_zi_eeg[ch] = lfilter_zi(b_bp, a_bp) * eeg_raw[0, ch]
        out, filter_zi_eeg[ch] = lfilter(b_bp, a_bp, eeg_raw[:, ch],
                                          zi=filter_zi_eeg[ch])
        filtered[:, ch] = out
    filter_init = False

    for i in range(n):
        _eeg_buf[_buf_ptr % _buf_size] = filtered[i]
        _buf_ptr   += 1
        _buf_count += 1


def _get_window(n_samples: int) -> np.ndarray:
    if _buf_count < n_samples:
        raise ValueError(f'Buffer has {_buf_count} samples, need {n_samples}')
    start = (_buf_ptr - n_samples) % _buf_size
    if start + n_samples <= _buf_size:
        window = _eeg_buf[start:start + n_samples]
    else:
        part1  = _eeg_buf[start:]
        part2  = _eeg_buf[:n_samples - len(part1)]
        window = np.vstack([part1, part2])
    return window.T   # (n_ch, n_samples)


def _get_baseline_corrected_window(n_samples: int) -> np.ndarray:
    window = _get_window(n_samples)
    if _baseline_mean is not None:
        window = window - _baseline_mean[:, np.newaxis]
    return window


def _compute_baseline():
    global _baseline_mean
    try:
        baseline_window = _get_window(baseline_samples)
        _baseline_mean  = baseline_window.mean(axis=1)
        print(f'[BASELINE] computed, mean norm={np.linalg.norm(_baseline_mean):.4f}')
    except ValueError:
        _baseline_mean = None
        print('[BASELINE] not enough samples — skipping')


def _classify_window(mode: int) -> float:
    """
    Full covariance pipeline matching al0_builddecoder.py:
      1. trace-normalize + LW
      2. batch whiten (pyriemann whitener from decoder)
      3. sequential recenter (AdaptiveRecenter, cold-start per run)
      4. MDM
    """
    window = _get_baseline_corrected_window(window_size_samples)

    # NaN guard
    if np.any(np.isnan(window)):
        print('[WARN] NaN in window — skipping')
        return 0.5

    # Step 1: Trace-normalize + LW (matches _extract_covariance in training)
    cov = window @ window.T
    tr  = np.trace(cov)
    if tr <= 0:
        tr = 1e-12
    cov = cov / tr

    lam = LedoitWolf().fit(window.T).shrinkage_
    n   = cov.shape[0]
    cov = (1 - lam) * cov + lam * (np.trace(cov) / n) * np.eye(n)

    print(f'[DEBUG COV] trace={np.trace(cov):.4f}  LW_shrinkage={lam:.4f}')

    # Step 2: Batch Riemannian whitening using FITTED whitener from decoder
    # This applies the SAME transform as training — critical for matching spaces.
    if whitener is not None:
        cov = whitener.transform(cov[np.newaxis])[0]
    elif pop_mean_inv_sqrt is not None:
        # Fallback for old decoders without saved whitener
        cov = pop_mean_inv_sqrt @ cov @ pop_mean_inv_sqrt.T

    # Step 3: Sequential adaptive recentering
    # Cold-starts at Prev_T=None per run (recenter.reset() on 32766),
    # matching runtime_common.py's _adaptive_recenter_cov behavior exactly.
    if config.RECENTERING:
        update_now = config.UPDATE_DURING_TRIAL or not check_in_task
        cov_w = recenter.update(cov, update_recentering=update_now)
    else:
        cov_w = cov

    # Step 4: MDM classify
    score = mdm_predict_proba(cov_w, prototypes)

    # class_names = [-1, 1]: index 0=REST(-1), index 1=MOVE(1)
    if mode == 0:
        return float(score[1])   # P(MOVE)
    else:
        return float(score[0])   # P(REST)


# =============================================================================
# Main loop
# =============================================================================
print('\n[ndf] Entering main loop...\n')

check_start   = False
check_in_task = False
ready_sent    = False

leaky         = LeakyIntegrator(alpha=config.INTEGRATOR_ALPHA)
trial_mode    = 0
n_predictions = 0
next_classify = 0.0

try:
    while True:
        # Pull EEG
        chunk, _ = eeg_inlet.pull_chunk(timeout=0.005, max_samples=32)

        # READY handshake (first iteration only)
        if not ready_sent:
            _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _s.sendto(b'READY', ('127.0.0.1', 12348))
            _s.close()
            ready_sent = True
            print('[ndf] Sent READY — waiting for 32766...')

        if chunk:
            _push_samples(np.array(chunk))

        # Markers
        event = None
        if marker_inlet:
            sample, _ = marker_inlet.pull_sample(timeout=0.0)
            if sample:
                try:
                    event = int(float(sample[0]))
                    print(f'[DEBUG] Marker: {event}')
                except Exception:
                    pass

        # Wait for run start
        if not check_start:
            if event == 32766:
                print('#################\n## Run Started ##\n#################\n')
                check_start = True
                # Cold-start recentering — Prev_T=None, counter=0
                # Matches Robot+FES runtime_common.py cold start behavior
                recenter.reset()
            continue

        # Trial start / end
        if event in TRIG_START:
            check_in_task = True
            trial_mode    = 0 if event in {7691, 7711} else 1
            _compute_baseline()
            leaky.reset()
            n_predictions = 0
            next_classify = time.time()
            print(f'\n Detected Start of Trial (mode={"Move" if trial_mode==0 else "Rest"})')

        elif event in TRIG_END:
            check_in_task = False
            leaky.reset()
            print('\n Detected End of Trial')

        # Classification step
        if check_in_task and _buf_count >= window_size_samples:
            now = time.time()
            if now >= next_classify:
                next_classify = now + config.STEP_SIZE

                try:
                    current_confidence = _classify_window(trial_mode)
                except ValueError:
                    current_confidence = 0.5

                running_avg = leaky.update(current_confidence)
                n_predictions += 1

                fill_move, fill_rest = calculate_fill_levels(running_avg, trial_mode)
                
                # ── DEBUG ──────────────────────────────────────────────────────
                print(f'[DEBUG FILL] running_avg={running_avg:.3f} '
                f'prob_inv={1-running_avg:.3f} '
                f'SHAPE_MIN={config.SHAPE_MIN} '
                f'fill_rest={fill_rest:.3f} fill_move={fill_move:.3f} '
                f'trial_mode={"Move" if trial_mode==0 else "Rest"}')



                raw_rest = fill_rest / 2.0 + 0.5
                raw_move = fill_move / 2.0 + 0.5
                send_probabilities(np.array([raw_rest, raw_move]), decoder)

                print(f'[CLASSIFY] conf={current_confidence:.3f} '
                      f'avg={running_avg:.3f} '
                      f'fill_move={fill_move:.3f} fill_rest={fill_rest:.3f} '
                      f'n={n_predictions}')

                threshold = config.THRESHOLD_MI if trial_mode == 0 else config.THRESHOLD_REST
                if n_predictions >= config.MIN_PREDICTIONS and running_avg >= threshold:
                    print(f'\n [EARLY STOP] {running_avg:.3f} >= {threshold:.3f} '
                          f'after {n_predictions} predictions')

        # End of run — second 32766 after run has started
        elif event == 32766 and check_start:
            print('\n End of run')
            with open(online_save_path, 'wb') as f:
                pickle.dump(decoder, f)
            print(f' Saved: {online_save_path}')
            break

except KeyboardInterrupt:
    print('\n[ndf] Interrupted.')
finally:
    send_probabilities(np.array([1000.0, 1000.0]), decoder)
