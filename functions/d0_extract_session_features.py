"""
d0_extract_session_features.py
================================

Loads XDF session data, performs EOG regression using calibration run,
epochs into sliding windows around task triggers, extracts features
(covariance matrices for Riemann, band power for LDA).

EOG channels: channels 33, 34, 35 in XDF (0-indexed: 32, 33, 34)
              placed on eye canthi and forehead
              ground + reference on mastoids
EOG removal:  linear regression method (same as MATLAB)
              eeg_clean = eeg - eog @ beta
              where beta = pinv(eog) @ eeg from calibration run

Folder structure expected:
    f1_data/Subject_001/
        Subject_001_Session_001_MI_Offline_BCI_LH_RH/
            calibrationData/
                Subject_001_MI_BCI_Calib_LH_RH_s001_r000_...xdf  ← EOG calibration
            Subject_001_MI_BCI_s001_r001_...xdf                   ← actual runs
"""

import os
import glob
import numpy as np
from scipy.signal import butter, lfilter

try:
    import pyxdf
except ImportError:
    raise ImportError('pyxdf not installed. Run: pip install pyxdf')


# =============================================================================
# Main function
# =============================================================================
def d0_extract_session_features(
    classifier: str,
    subject_id: int,
    mode: str,
    classes: str,
    selected_session: list,
    select_periods: list,
    selected_features: list,
    saving: bool,
    dur_considered: list,
    params: dict = None,
):
    """
    Load, EOG-correct, and epoch EEG data for a subject.

    Parameters
    ----------
    classifier       : str   — 'LDA' or 'Rieman'
    subject_id       : int
    mode             : str   — 'Visual' or 'STM'
    classes          : str   — '' or class string
    selected_session : list  — [offline_indices, online_indices]
                               [] = all sessions, [-1] = skip all
    select_periods   : list  — [rest, cue, task, result] booleans
    selected_features: list  — feature indices (for LDA)
    saving           : bool  — whether to save epoch to disk
    dur_considered   : list  — [offline_dur, online_dur] seconds
    params           : dict  — from a0_param_initialization

    Returns
    -------
    epoch : dict with keys:
        feature.task   : (n_ch, n_ch, n_epochs) for Riemann
                         (n_epochs, n_features)  for LDA
        label          : (n_epochs,)
        params         : params dict
        info           : session info
    """
    from a0_param_init import a0_param_initialization

    if params is None:
        params = a0_param_initialization(
            dur_considered=dur_considered,
            epoch_dur=1.0,
            step_size=1/16,
        )

    fs         = params['fs']
    epoch_dur  = params['epoch_dur']
    step_size  = params['step_size']           # samples
    ch_reject  = params['channels_to_reject']  # 1-indexed
    num_ch_eeg = params['num_ch_eeg']          # 32
    num_ch_bip = params['num_ch_bip']          # 3 EOG channels

    # Active EEG channels (0-indexed, after rejecting bad ones)
    all_ch = [i for i in range(num_ch_eeg) if (i + 1) not in ch_reject]
    n_ch   = len(all_ch)

    # EOG channel indices in XDF (AUX7, AUX8, AUX9 — NOT immediately after EEG)
    # Actual channel order confirmed via inspect_xdf_channels.py:
    #   [0-31]  EEG channels
    #   [32-34] AUX1-3 (unused)
    #   [35-37] AUX7-8-9 (EOG: eye canthi + forehead)
    #   [38]    TRIGGER
    eog_ch = [35, 36, 37]

    # Trigger codes
    trig_lh    = params['trig_lh']   # Rest:  [769, 7691, 7692, 7693]
    trig_rh    = params['trig_rh']   # Move:  [770, 7701, 7702, 7703]
    trig_start = {trig_lh[1], trig_rh[1]}       # task start
    trig_end   = {trig_lh[2], trig_lh[3],
                  trig_rh[2], trig_rh[3]}        # task end
    label_map  = {trig_lh[1]: -1, trig_rh[1]: 1}

    dur_off = dur_considered[0] if dur_considered else 3
    dur_on  = dur_considered[1] if len(dur_considered) > 1 else 5

    ep_samp   = int(epoch_dur * fs)
    step_samp = int(step_size)

    # Bandpass filter coefficients
    b_bp, a_bp = butter(
        params['filter_order'],
        [x / (fs / 2) for x in params['band_pass_filter_range']],
        btype='bandpass'
    )

    # EOG bandpass filter (1-10 Hz — same as MATLAB)
    b_eog, a_eog = butter(2, [1 / (fs / 2), 10 / (fs / 2)], btype='bandpass')

    # ── Find data root ────────────────────────────────────────────────────────
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_root  = os.path.join(script_dir, 'f1_data',
                              f'Subject_{subject_id:03d}')

    if not os.path.isdir(data_root):
        raise FileNotFoundError(f'No data folder at {data_root}')

    # All session folders
    all_sess_dirs = sorted([
        d for d in os.listdir(data_root)
        if os.path.isdir(os.path.join(data_root, d)) and 'Session' in d
    ])

    offline_dirs = [d for d in all_sess_dirs
                    if 'Offline' in d or 'offline' in d]
    online_dirs  = [d for d in all_sess_dirs
                    if ('Online' in d or 'online' in d)
                    and 'Offline' not in d]

    # Filter by mode
    if mode in ('Visual', 'visual'):
        offline_dirs = [d for d in offline_dirs
                        if 'Visual' in d or 'STM' not in d]
        online_dirs  = [d for d in online_dirs
                        if 'Visual' in d or 'STM' not in d]
    elif mode in ('STM', 'stm'):
        offline_dirs = [d for d in offline_dirs if 'STM' in d]
        online_dirs  = [d for d in online_dirs  if 'STM' in d]

    # Filter by classes
    if classes:
        offline_dirs = [d for d in offline_dirs if classes in d]
        online_dirs  = [d for d in online_dirs  if classes in d]

    # Session selection
    sel_off = selected_session[0] if selected_session else []
    sel_on  = selected_session[1] if len(selected_session) > 1 else [-1]

    def _pick(dirs, sel):
        """Select sessions by 1-indexed list, [] = all, [-1] = none."""
        if len(sel) == 1 and sel[0] == -1:
            return []
        if not sel:
            return dirs
        return [dirs[i - 1] for i in sel if 0 < i <= len(dirs)]

    sessions_to_use = (
        [(os.path.join(data_root, d), 'offline')
         for d in _pick(offline_dirs, sel_off)] +
        [(os.path.join(data_root, d), 'online')
         for d in _pick(online_dirs, sel_on)]
    )

    if not sessions_to_use:
        sessions_to_use = [
            (os.path.join(data_root, d), 'offline')
            for d in offline_dirs
        ]

    print(f'\n  Subject {subject_id:03d}: {len(sessions_to_use)} session(s)')

    # ── Process each session ──────────────────────────────────────────────────
    all_task_feats  = []
    all_task_labels = []
    all_rest_feats  = []
    all_task_runs   = []   # run-group id per task epoch — for LOGO CV
    global_run_id   = 0    # increments once per XDF run file across all sessions

    for sess_path, sess_type in sessions_to_use:
        dur_use = dur_off if sess_type == 'offline' else dur_on

        # ── Step 1: Load EOG calibration run ─────────────────────────────────
        calib_dir   = os.path.join(sess_path, 'calibrationData')
        # Case-insensitive glob: matches calib / Calib / CALIB etc.
        _all_xdf    = glob.glob(os.path.join(calib_dir, '*.xdf'))
        calib_files = sorted([f for f in _all_xdf
                               if 'calib' in os.path.basename(f).lower()])

        eog_beta = None   # regression coefficients (n_eog, n_eeg)

        if calib_files:
            print(f'  EOG calibration: {os.path.basename(calib_files[0])}')
            eeg_c, eog_c, _, _ = _load_xdf(calib_files[0],
                                            num_ch_eeg, eog_ch)
            if eeg_c is not None and eog_c is not None:
                # Bandpass filter EOG calibration data
                eog_f = lfilter(b_eog, a_eog, eog_c, axis=0)
                eeg_f = lfilter(b_bp,  a_bp,  eeg_c, axis=0)

                # Compute regression coefficients:
                # beta = pinv(eog) @ eeg  →  shape (n_eog, n_eeg)
                # eeg_clean = eeg - eog @ beta
                eog_beta = np.linalg.lstsq(eog_f, eeg_f, rcond=None)[0]
                print(f'    EOG regression coeff shape: {eog_beta.shape}')
        else:
            print(f'  [Warning] No calibration file in {calib_dir} — '
                  f'skipping EOG regression')

        # ── Step 2: Load actual run XDF files ─────────────────────────────────
        xdf_files = sorted(glob.glob(os.path.join(sess_path, '*.xdf')))
        xdf_files = [f for f in xdf_files
                     if 'Calib' not in f and 'calib' not in f]

        if not xdf_files:
            print(f'  [Warning] No run XDF files in {sess_path}')
            continue

        print(f'  {sess_type} session: {os.path.basename(sess_path)} '
              f'— {len(xdf_files)} run(s)')

        for run_idx, fpath in enumerate(xdf_files):
            eeg, eog, events, fs_file = _load_xdf(fpath, num_ch_eeg, eog_ch)
            if eeg is None:
                continue
            if fs_file and abs(fs_file - fs) > 1:
                fs        = fs_file
                ep_samp   = int(epoch_dur * fs)
                step_samp = int(epoch_dur * fs / 16)
                b_bp, a_bp = butter(
                    params['filter_order'],
                    [x / (fs / 2) for x in params['band_pass_filter_range']],
                    btype='bandpass')

            # ── Step 3: EOG regression ────────────────────────────────────────
            if eog_beta is not None and eog is not None:
                eog_f    = lfilter(b_eog, a_eog, eog, axis=0)
                eeg_clean = eeg - eog_f @ eog_beta   # (n_samp, n_eeg)
            else:
                eeg_clean = eeg

            # ── Step 4: Bandpass filter EEG ───────────────────────────────────
            if params.get('do_band_pass_filtering', True):
                eeg_clean = lfilter(b_bp, a_bp, eeg_clean, axis=0)

            # Select active channels
            eeg_ch_sel = eeg_clean[:, all_ch]   # (n_samp, n_ch)

            # ── Step 5: Task epochs ───────────────────────────────────────────
            if select_periods[2]:
                t_feats, t_labels = _epoch_task(
                    eeg_ch_sel, events,
                    trig_start, trig_end,
                    ep_samp, step_samp,
                    dur_use, fs,
                    label_map,
                    classifier, n_ch,
                )
                all_task_feats.extend(t_feats)
                all_task_labels.extend(t_labels)
                all_task_runs.extend([global_run_id] * len(t_labels))
                print(f'    {os.path.basename(fpath)}: '
                      f'{len(t_labels)} task epochs '
                      f'(Rest={t_labels.count(-1)}, Move={t_labels.count(1)})')

            # ── Step 6: Rest epochs ───────────────────────────────────────────
            if select_periods[0]:
                r_feats = _epoch_period(
                    eeg_ch_sel, events,
                    params['trig_rest'],
                    ep_samp, step_samp,
                    classifier, n_ch,
                )
                all_rest_feats.extend(r_feats)

            global_run_id += 1   # one run = one XDF file, used as LOGO group

    if not all_task_feats:
        raise RuntimeError(
            f'No task epochs found for Subject {subject_id}.\n'
            f'Check folder: {data_root}\n'
            f'Expected trigger codes: {list(trig_start)}')

    # ── Stack arrays ──────────────────────────────────────────────────────────
    if classifier == 'Rieman':
        task_arr = np.stack(all_task_feats, axis=2)   # (n_ch, n_ch, n_ep)
        rest_arr = (np.stack(all_rest_feats, axis=2)
                    if all_rest_feats
                    else np.zeros((n_ch, n_ch, 0)))
    else:
        task_arr = np.array(all_task_feats)            # (n_ep, n_feat)
        rest_arr = (np.array(all_rest_feats)
                    if all_rest_feats
                    else np.zeros((0, task_arr.shape[1])))

    labels_arr = np.array(all_task_labels)
    run_ids_arr = np.array(all_task_runs)

    print(f'\n  Task feature shape: {task_arr.shape}')
    print(f'  Labels:  {np.unique(labels_arr, return_counts=True)}')
    print(f'  Run IDs: {np.unique(run_ids_arr)} ({len(np.unique(run_ids_arr))} runs total)')

    epoch = {
        'subject':           subject_id,
        'label':             labels_arr,
        'run_ids':           run_ids_arr,   # per-epoch run-group id, for LOGO CV
        'selected_features': selected_features,
        'dur_considered':    dur_considered,
        'feature': {
            'task':   task_arr,
            'rest':   rest_arr,
            'cue':    np.zeros((n_ch, n_ch, 0)) if classifier == 'Rieman'
                      else np.zeros((0, task_arr.shape[1] if task_arr.ndim > 1 else 1)),
            'result': np.zeros((n_ch, n_ch, 0)) if classifier == 'Rieman'
                      else np.zeros((0, task_arr.shape[1] if task_arr.ndim > 1 else 1)),
        },
        'params': params,
        'info': {
            'sessions_used': [os.path.basename(s) for s, _ in sessions_to_use],
            'n_sessions':    len(sessions_to_use),
            'classifier':    classifier,
            'eog_regression': eog_beta is not None,
        }
    }

    return epoch


# =============================================================================
# File loader
# =============================================================================
def _load_xdf(fpath: str, num_ch_eeg: int, eog_ch: list):
    """
    Load EEG, EOG, and events from an XDF file.

    Returns
    -------
    eeg    : (n_samp, num_ch_eeg)
    eog    : (n_samp, n_eog) or None
    events : list of (sample, marker_value)
    fs     : float
    """
    try:
        streams, _ = pyxdf.load_xdf(fpath)
    except Exception as e:
        print(f'  [Error] {fpath}: {e}')
        return None, None, None, None

    # Find EEG stream — must match type strictly first, since some files also
    # contain a per-sample marker stream whose NAME also contains "eego"
    # (e.g. 'eegoSports-000126_markers', type=Markers) which would otherwise
    # be mistakenly selected by a name-only check.
    eeg_stream = None
    for s in streams:
        stype = s['info']['type'][0].upper()
        if stype == 'EEG':
            eeg_stream = s
            break
    if eeg_stream is None:
        # Fallback: name match, but still exclude anything typed as Markers
        for s in streams:
            name = s['info']['name'][0]
            stype = s['info']['type'][0].upper()
            if 'eego' in name.lower() and stype != 'MARKERS':
                eeg_stream = s
                break

    if eeg_stream is None:
        print(f'  [Warning] No EEG stream in {os.path.basename(fpath)}')
        return None, None, None, None

    raw       = np.asarray(eeg_stream['time_series'], dtype=np.float64)   # (n_samp, n_total_ch)
    fs        = float(eeg_stream['info']['nominal_srate'][0])
    eeg_times = np.array(eeg_stream['time_stamps'])

    # EEG channels (first num_ch_eeg)
    if raw.shape[1] < num_ch_eeg:
        pad = np.zeros((raw.shape[0], num_ch_eeg - raw.shape[1]))
        raw = np.hstack([raw, pad])
    eeg = raw[:, :num_ch_eeg]                          # (n_samp, 32)

    # EOG channels (after EEG)
    eog = None
    if raw.shape[1] > max(eog_ch):
        eog = raw[:, eog_ch]                           # (n_samp, 3)
    else:
        print(f'  [Warning] EOG channels not found in {os.path.basename(fpath)} '
              f'(stream has {raw.shape[1]} channels, need up to {max(eog_ch)+1})')

    # Marker stream
    events = []
    for s in streams:
        if s['info']['name'][0] == 'MarkerStream':
            for ts, val in zip(s['time_stamps'], s['time_series']):
                try:
                    sample = int(np.searchsorted(eeg_times, ts))
                    events.append((sample, int(float(val[0]))))
                except Exception:
                    pass
            break

    return eeg, eog, events, fs


# =============================================================================
# Epoch extraction helpers
# =============================================================================
def _extract_covariance(eeg: np.ndarray) -> np.ndarray:
    """
    Trace-normalized + Ledoit-Wolf regularized covariance (n_samp, n_ch) -> (n_ch, n_ch).

    Matches the reference pipeline's compute_processed_covariances exactly:
      1. cov = (seg @ seg.T) / trace(seg @ seg.T)   [trace-norm inline]
      2. lam = LedoitWolf().fit(seg.T).shrinkage_    [exact LW from raw segment]
      3. cov = (1-lam)*cov + lam*(trace(cov)/n)*I

    LW is fitted on the raw segment (n_samp x n_ch) — this is the exact
    oracle shrinkage coefficient, not an approximation from the cov matrix.
    The raw segment is available here and discarded after, so this is the
    only place where exact LW can be computed.

    Riemannian whitening (step 3 in al0_builddecoder.py) is still applied
    centrally after all epochs are stacked.
    """
    from sklearn.covariance import LedoitWolf
    x   = eeg - eeg.mean(axis=0)           # demean (n_samp, n_ch)
    n   = x.shape[1]
    cov = x.T @ x / x.shape[0]             # sample covariance
    tr  = np.trace(cov)
    if tr > 0:
        cov = cov / tr                      # step 1: trace-normalize
    lam = LedoitWolf().fit(x).shrinkage_    # step 2: exact LW from raw segment
    mu  = np.trace(cov) / n
    return (1 - lam) * cov + lam * mu * np.eye(n)  # step 3: shrink


def _epoch_task(eeg, events, trig_start, trig_end,
                ep_samp, step_samp, dur_use, fs,
                label_map, classifier, n_ch):
    """
    Extract sliding-window epochs from task periods.
    Uses last dur_use seconds of each trial (matches MATLAB durConsidered).

    Baseline subtraction (matching reference pipeline):
      The mean of the 1 s pre-stimulus window is subtracted from every
      sliding-window epoch before covariance estimation.  If fewer than
      16 samples are available before the trial onset the window is not
      baselined (avoids subtracting near-zero means at the very start of
      a recording).
    """
    feats, labels = [], []
    baseline_samp = int(1.0 * fs)   # 1 s pre-stimulus baseline window

    for i, (samp, typ) in enumerate(events):
        if typ not in trig_start:
            continue

        # Find matching end trigger
        end_samp = samp + int(dur_use * fs)   # default if no end found
        for j in range(i + 1, min(i + 10, len(events))):
            if events[j][1] in trig_end:
                end_samp = events[j][0]
                break

        # Clamp to signal length
        task_end   = min(end_samp, eeg.shape[0])

        # Use last dur_use seconds
        task_start = max(samp, task_end - int(dur_use * fs))

        # Pre-stimulus baseline: all filtered EEG from recording start to
        # trial onset — matches reference pipeline's
        #   baseline = filtered_global[:, :baseline_end].mean(axis=1)
        # Longer window = more stable mean; falls back to zero if trial is
        # the very first event (fewer than 16 samples available).
        if samp >= 16:
            baseline = eeg[:samp, :].mean(axis=0, keepdims=True)
        else:
            baseline = np.zeros((1, eeg.shape[1]))

        pos = task_start
        while pos + ep_samp <= task_end:
            epoch_data = eeg[pos: pos + ep_samp, :] - baseline
            if classifier == 'Rieman':
                feats.append(_extract_covariance(epoch_data))
            else:
                feats.append(epoch_data.flatten())
            labels.append(label_map.get(typ, 0))
            pos += step_samp

    return feats, labels


def _epoch_period(eeg, events, trig_code,
                  ep_samp, step_samp, classifier, n_ch):
    """Extract epochs from rest/cue/result periods."""
    feats = []
    starts = [s for s, t in events if t == trig_code]
    ends   = []
    for i, (s, t) in enumerate(events):
        if t == trig_code and i + 1 < len(events):
            ends.append(events[i + 1][0])

    for start, end in zip(starts, ends):
        end = min(end, eeg.shape[0])
        pos = start
        while pos + ep_samp <= end:
            ep = eeg[pos: pos + ep_samp, :]
            if classifier == 'Rieman':
                feats.append(_extract_covariance(ep))
            else:
                feats.append(ep.flatten())
            pos += step_samp

    return feats
