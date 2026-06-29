"""
al0_builddecoder.py
=========================
Merged decoder-building script combining:
  - run_script_Reimannian_mdm.py  (TESS pipeline)
  - a1_BuildDecoderRiemann.py / d0_computeModelRiemannSelectSessions.py
    (GeoLearning pipeline, session selector + geodesic shift)
  - pyriemann-style enhancements (trace-normalization, population whitening,
    dual-threshold calibration with reject option)

Covariance pipeline (must match ndf_main_adap.py exactly):
  1. Trace-normalize + LW shrinkage      (in _extract_covariance)
  2. Batch Riemannian whitening          (pyriemann Whitening, fitted here,
                                          saved in decoder, applied at test time)
  3. Sequential adaptive recentering     (online only — NOT applied here,
                                          so prototypes live in whitened space)
  4. MDM fit on whitened covariances

This matches the Robot+FES pipeline exactly:
  - Training:  batch Whitening.fit_transform → MDM prototypes in whitened space
  - Online:    Whitening.transform (same fitted ref) → sequential recentering
                → compare to prototypes

Usage:
    python3 al0_builddecoder.py
"""

import os
import glob
import pickle
import time
import numpy as np
from datetime import datetime
from scipy.signal import butter, lfilter

from pyriemann.preprocessing import Whitening

from functions.a0_param_init import a0_param_initialization
from functions.d1_initialize_decoder import d1_initialize_decoder
from functions.d0_extract_session_features import d0_extract_session_features

# =============================================================================
# *** CHANGE THESE EACH DAY ***
# =============================================================================
SUBJECT_ID = 3
EXPERIMENT = 'TESS'
MODE       = 'Visual'
CLASSES    = 'FES'
SAVE_DECODER = True

# Session selection
# offline: [] = all sessions, [0] = session 1 only, [0,1] = sessions 1 and 2
# online:  [] = skip all,     [0] = session 1 only, [0,1] = sessions 1 and 2
OFFLINE_SESSIONS = []
ONLINE_SESSIONS  = []

# Epoch parameters
DUR_CONSIDERED = [3, 5]
EPOCH_DUR      = 1.0
STEP_SIZE      = 1 / 16

# Covariance regularization
# Trace-normalize + LW done in _extract_covariance.
# Batch Riemannian whitening done here via pyriemann.
APPLY_WHITENING = True

# Decoder validation
MAKE_PLOTS = True

# =============================================================================
# Prompt: geodesic shift
# =============================================================================
print('\n' + '='*60)
print(f'  Building decoder for Subject {SUBJECT_ID:03d}')
print('='*60)
use_shift = input('\nApply geodesic shift to class prototypes? [y/n]: ').strip().lower() == 'y'
if use_shift:
    shifter_input = input('Shift percentage (default 15): ').strip()
    SHIFTER = float(shifter_input) if shifter_input else 15.0
    print(f'  Geodesic shift: {SHIFTER}%')
    CLASSIFIER_FOLDER = 'Rieman_shifted'
else:
    SHIFTER = 0.0
    print('  No geodesic shift.')
    CLASSIFIER_FOLDER = 'Rieman'

# =============================================================================
# Helpers: Riemannian math (used for geodesic shift + distance + MDM training)
# =============================================================================
def _matrix_pow(A: np.ndarray, power: float) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(eigvals ** power) @ eigvecs.T

def _matrix_log(A: np.ndarray) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(np.log(eigvals)) @ eigvecs.T

def _matrix_exp(A: np.ndarray) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eigh(A)
    return eigvecs @ np.diag(np.exp(eigvals)) @ eigvecs.T

def riemann_mean(covs: np.ndarray, max_iter: int = 50,
                 tol: float = 1e-7) -> np.ndarray:
    """covs: (n_ch, n_ch, n_trials)"""
    n_trials = covs.shape[2]
    mean_cov = covs.mean(axis=2)
    for _ in range(max_iter):
        inv_sqrt = _matrix_pow(mean_cov, -0.5)
        sqrt     = _matrix_pow(mean_cov,  0.5)
        S = np.zeros_like(mean_cov)
        for t in range(n_trials):
            S += _matrix_log(inv_sqrt @ covs[:, :, t] @ inv_sqrt)
        S /= n_trials
        update = sqrt @ _matrix_exp(S) @ sqrt
        if np.linalg.norm(update - mean_cov, 'fro') < tol:
            mean_cov = update
            break
        mean_cov = update
    return mean_cov

def riemann_geodesic(C1: np.ndarray, C2: np.ndarray, t: float) -> np.ndarray:
    C1_inv_sqrt = _matrix_pow(C1, -0.5)
    C1_sqrt     = _matrix_pow(C1,  0.5)
    inner = C1_inv_sqrt @ C2 @ C1_inv_sqrt
    return (C1_sqrt @ _matrix_pow(inner, t) @ C1_sqrt).real

def riemann_distance(C1: np.ndarray, C2: np.ndarray) -> float:
    C1_inv_sqrt = _matrix_pow(C1, -0.5)
    inner = C1_inv_sqrt @ C2 @ C1_inv_sqrt
    eigvals = np.linalg.eigvalsh(inner)
    eigvals = np.maximum(eigvals, 1e-12)
    return float(np.sqrt(np.sum(np.log(eigvals) ** 2)))

# =============================================================================
# Initialise params and decoder
# =============================================================================
params = a0_param_initialization(
    dur_considered=DUR_CONSIDERED,
    epoch_dur=EPOCH_DUR,
    step_size=STEP_SIZE,
)
params['do_band_pass_filtering'] = True
params['feature_selection']      = 'shrinkageCovariance'
params['classification_method']  = 'Riemann'
params['band_pass_filter_range'] = [8, 30]
params['filter_order']           = 4

decoder = d1_initialize_decoder(
    SUBJECT_ID, params, MODE, CLASSES, eog_filt_coeff=None)

# =============================================================================
# Session selector
# =============================================================================
if not ONLINE_SESSIONS:
    selected_session = [OFFLINE_SESSIONS, [-1]]
else:
    selected_session = [OFFLINE_SESSIONS, ONLINE_SESSIONS]

print(f'\n  Offline sessions: {"all" if not OFFLINE_SESSIONS else OFFLINE_SESSIONS}')
print(f'  Online sessions:  {"none" if not ONLINE_SESSIONS else ONLINE_SESSIONS}')

# =============================================================================
# Extract features
# =============================================================================
epoch = d0_extract_session_features(
    'Rieman',
    SUBJECT_ID,
    MODE,
    CLASSES,
    selected_session=selected_session,
    select_periods=[0, 0, 1, 0],
    selected_features=[],
    saving=False,
    dur_considered=DUR_CONSIDERED,
    params=params,
)

# Fix shape mismatch
print(f'\n  Feature task shape: {epoch["feature"]["task"].shape}')
print(f'  Label shape:        {epoch["label"].shape}')
n_cov    = epoch['feature']['task'].shape[2]
n_labels = len(epoch['label'])
if n_cov != n_labels:
    step = n_labels // n_cov
    epoch['label'] = epoch['label'][::step][:n_cov]
    if 'run_ids' in epoch and len(epoch['run_ids']) == n_labels:
        epoch['run_ids'] = epoch['run_ids'][::step][:n_cov]
    print(f'  Resampled labels: {n_labels} → {len(epoch["label"])}')

decoder['info']      = epoch['info']
decoder['ch_labels'] = epoch['params'].get('ch_labels', [])

# =============================================================================
# Covariance pipeline
# Step 1: Trace-normalize + LW  (already done in _extract_covariance)
# Step 2: Batch Riemannian whitening via pyriemann
#         - Fitted on ALL training covariances
#         - Whitener saved in decoder so online script applies SAME transform
#         - Prototypes are built in this whitened space
# Step 3: NO sequential recentering here — that is done online only
# =============================================================================
covs_for_training = epoch['feature']['task']   # (n_ch, n_ch, n_trials)

# pyriemann expects (n_trials, n_ch, n_ch)
covs_T = covs_for_training.transpose(2, 0, 1)   # (n_trials, n_ch, n_ch)

population_mean = riemann_mean(covs_for_training)

whitener = None
if APPLY_WHITENING:
    print('\nStep 2: Batch Riemannian whitening (pyriemann)...')
    whitener = Whitening(metric='riemann')
    covs_T = whitener.fit_transform(covs_T)      # still (n_trials, n_ch, n_ch)
    print(f'  Done. Whitener fitted on {covs_T.shape[0]} covariances.')
    covs_for_training = covs_T.transpose(1, 2, 0)  # back to (n_ch, n_ch, n_trials)
else:
    print('\nStep 2: Whitening disabled.')
# =============================================================================
# Train MDM classifier
# =============================================================================
unique_labels   = np.sort(np.unique(epoch['label']))
n_classes       = len(unique_labels)
class_prototype = []

print('\nTraining Riemannian MDM classifier...')
t0 = time.time()

for label in unique_labels:
    mask       = epoch['label'] == label
    class_covs = covs_for_training[:, :, mask]
    prototype  = riemann_mean(class_covs)
    class_prototype.append(prototype)
    print(f'  Class {label}: {mask.sum()} epochs, prototype computed.')

overall_mean = riemann_mean(covs_for_training)
elapsed = time.time() - t0
print(f'  Training time: {elapsed:.2f}s')

rejection_prototypes = [p.copy() for p in class_prototype]

# =============================================================================
# Score distribution analysis
# =============================================================================
import matplotlib.pyplot as plt
from mdm_predict import mdm_predict_proba

n_trials    = covs_for_training.shape[2]
scores_move = []
true_labels = []

for t in range(n_trials):
    cov   = covs_for_training[:, :, t]
    score = mdm_predict_proba(cov, class_prototype)
    scores_move.append(score[1])
    true_labels.append(epoch['label'][t])

scores_move = np.array(scores_move)
true_labels = np.array(true_labels)
unique      = np.unique(true_labels)

print('\n=== Score distribution summary (whitened, no recentering) ===')
for label in unique:
    mask = true_labels == label
    print(f'  True class {label} ({mask.sum()} epochs):')
    print(f'    P(MOVE) mean={scores_move[mask].mean():.3f}  '
          f'std={scores_move[mask].std():.3f}  '
          f'min={scores_move[mask].min():.3f}  '
          f'max={scores_move[mask].max():.3f}')

mask0   = true_labels == unique[0]
mask1   = true_labels == unique[1]
d_prime = abs(scores_move[mask1].mean() - scores_move[mask0].mean()) / \
          np.sqrt(0.5 * (scores_move[mask1].std()**2 +
                         scores_move[mask0].std()**2))
print(f"\n  d' (separation): {d_prime:.3f}  "
      f"({'good' if d_prime > 1.0 else 'marginal' if d_prime > 0.5 else 'POOR'})")

fig, ax = plt.subplots(figsize=(8, 4))
for label in unique:
    mask = true_labels == label
    ax.hist(scores_move[mask], bins=30, alpha=0.6, label=f'True class {label}')
ax.axvline(0.5, color='black', linestyle='--', linewidth=1.5, label='chance (0.5)')
ax.set_xlabel('P(MOVE)')
ax.set_ylabel('Count')
ax.set_title(f'Subject {SUBJECT_ID:03d} — P(MOVE) distribution (batch whitened)')
ax.legend()
plt.tight_layout()
plt.savefig(f'Subject_{SUBJECT_ID:03d}_score_distribution.png', dpi=150)
plt.show()
print(f'  Plot saved: Subject_{SUBJECT_ID:03d}_score_distribution.png')

# =============================================================================
# Geodesic shift (optional)
# =============================================================================
if use_shift and n_classes == 2:
    shifted = list(class_prototype)
    shifted[1] = riemann_geodesic(class_prototype[0],
                                   class_prototype[1],
                                   1 + SHIFTER / 100)
    shifted[0] = riemann_geodesic(class_prototype[1],
                                   class_prototype[0],
                                   1 + SHIFTER / 100)
    d_prev = riemann_distance(class_prototype[0], class_prototype[1])
    d_new  = riemann_distance(shifted[0],          shifted[1])
    print(f'\n  Geodesic shift ({SHIFTER}%):')
    print(f'    Distance {d_prev:.4f} → {d_new:.4f} '
          f'(+{100*(d_new-d_prev)/d_prev:.1f}%)')
    class_prototype = shifted

# =============================================================================
# Decoder validation (Leave-One-Run-Out CV)
# =============================================================================
from logo_validation import evaluate_decoder_logo

d_prev = riemann_distance(rejection_prototypes[0], rejection_prototypes[1])
d_new  = riemann_distance(class_prototype[0], class_prototype[1]) if use_shift else d_prev

print(f'\n  Riemannian distance between prototypes: {d_prev:.4f}'
      + (f' → {d_new:.4f} (post-shift)' if use_shift else ''))

if 'run_ids' not in epoch or len(np.unique(epoch['run_ids'])) < 2:
    if 'run_ids' in epoch:
        print(f'\n  [Debug] run_ids: {np.unique(epoch["run_ids"])} '
              f'(len={len(epoch["run_ids"])})')
    print('\n  [Warning] Fewer than 2 distinct runs — skipping LOGO CV.')
    logo_results     = None
    global_threshold = 0.5
else:
    logo_results = evaluate_decoder_logo(
        covs       = covs_for_training,
        labels     = epoch['label'],
        run_ids    = epoch['run_ids'],
        make_plots = MAKE_PLOTS,
    )
    global_threshold = logo_results['global_threshold']

decoder['validation'] = {
    'method':                      'logo',
    'riemann_distance_pre_shift':  d_prev,
    'riemann_distance_post_shift': d_new,
    'trace_normalize':             True,
    'ledoit_wolf':                 True,
    'apply_whitening':             APPLY_WHITENING,
    'apply_recentering_online':    True,   # recentering done online only
    'global_threshold':            global_threshold,
    'logo_results':                logo_results,
}

# =============================================================================
# Store in decoder
# =============================================================================
decoder['classification']['model'] = {
    'parameters':          class_prototype,       # prototypes in batch-whitened space
    'rejectionParameters': rejection_prototypes,  # pre-whitening (reference)
    'class_names':         unique_labels,
    'ClassNames':          unique_labels.tolist(),
    'originalClasses':     unique_labels.tolist(),
    'distance_metric':     'AIRM',
    'distanceMetric':      'AIRM',
    'overallMean':         overall_mean,
    'populationMean':      population_mean,        # pre-whitening mean (saved for reference)
    'TestEpochCounter':    1,
    'reference':           overall_mean.copy(),
    'traceNormalize':      True,
    'ledoitWolf':          True,
    'applyWhitening':      APPLY_WHITENING,
    'applyRecentering':    True,                   # sequential recentering done online
    'globalThreshold':     global_threshold,
}
decoder['classification']['method']            = 'Rieman'
decoder['preprocessing']['channels_to_reject'] = params['channels_to_reject']

# Save the FITTED whitener so online script applies the SAME transform
# (same reference mean, same scaling) — this is the key to matching
# training and online covariance spaces.
decoder['whitener'] = whitener   # None if APPLY_WHITENING=False

# =============================================================================
# Save spectral filter coefficients
# =============================================================================
from scipy.signal import butter as _butter_for_save
_bp_b, _bp_a = _butter_for_save(
    params['filter_order'],
    [params['band_pass_filter_range'][0] / (params['fs'] / 2),
     params['band_pass_filter_range'][1] / (params['fs'] / 2)],
    btype='band',
)
decoder['spectralFilter'] = {
    'b':        _bp_b,
    'a':        _bp_a,
    'range_hz': params['band_pass_filter_range'],
    'order':    params['filter_order'],
}

# =============================================================================
# Save decoder
# =============================================================================
if SAVE_DECODER:
    data_root = os.getcwd()

    n_off = len(OFFLINE_SESSIONS) if OFFLINE_SESSIONS else 'all'
    n_on  = len(ONLINE_SESSIONS)  if ONLINE_SESSIONS  else 0
    dt    = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')

    if n_on > 0:
        decoder_path = os.path.join(
            data_root, 'f2_subjectDecoders',
            f'Subject_{SUBJECT_ID:03d}_OfflineOnline',
            CLASSIFIER_FOLDER,
        )
        fname = f'Subject_{SUBJECT_ID:03d}_Off{n_off}_On{n_on}_{dt}_.pkl'
    else:
        decoder_path = os.path.join(
            data_root, 'f2_subjectDecoders',
            f'Subject_{SUBJECT_ID:03d}_Offline',
            CLASSIFIER_FOLDER,
        )
        fname = f'Subject_{SUBJECT_ID:03d}_Off{n_off}_{dt}_.pkl'

    os.makedirs(decoder_path, exist_ok=True)
    save_path = os.path.join(decoder_path, fname)

    with open(save_path, 'wb') as f:
        pickle.dump(decoder, f)

    print('\n' + '='*74)
    print(f'\t  Subject-{SUBJECT_ID:03d} Decoder is READY')
    print(f'\t  Folder:          {CLASSIFIER_FOLDER}')
    print(f'\t  Filter:          {params["band_pass_filter_range"]} Hz, '
          f'order {params["filter_order"]}')
    print(f'\t  Trace-norm + LW: in _extract_covariance (per epoch)')
    print(f'\t  Whitening:       {"batch pyriemann (saved in decoder)" if APPLY_WHITENING else "disabled"}')
    print(f'\t  Recentering:     online sequential (NOT applied at training)')
    print(f'\t  Shift:           {SHIFTER}% ({"applied" if use_shift else "none"})')
    if logo_results is not None:
        print(f'\t  Global threshold:{global_threshold:.3f} '
              f'(TPR×TNR={logo_results["global_tpr_tnr_product"]:.3f})')
        print(f'\t  ROC-AUC:         {logo_results["roc_auc"]:.3f}')
    print(f'\t  Offline sessions:{"all" if not OFFLINE_SESSIONS else OFFLINE_SESSIONS}')
    print(f'\t  Online sessions: {"none" if not ONLINE_SESSIONS else ONLINE_SESSIONS}')
    print('='*74)
    print(f'\nSaved to: {save_path}')
