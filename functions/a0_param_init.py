import numpy as np
from typing import Optional
from f4_eegc3_montage import f4_eegc3_montage


def a0_param_initialization(
    dur_considered=None,
    classes=None,
    epoch_dur=None,
    step_size=None,
    fs=None,
):
    """
    Initialize experiment parameters.

    Parameters
    ----------
    dur_considered : list, optional
        Duration windows to consider (default: [5, 7, 0])
    classes : str, optional
        Class labels (unused, kept for compatibility)
    epoch_dur : float, optional
        Duration in seconds for feature extraction (default: 1)
    step_size : float, optional
        Step size as a fraction of fs (default: 1/16)
    fs : int, optional
        Sampling rate in Hz (default: 512)

    Returns
    -------
    params : dict
        Dictionary of experiment parameters
    """
    params = {}

    # --- Experiment identity ---
    params["experiment"] = "TESS"
    params["mode"] = "Visual"
    params["classes"] = ""

    # --- Signal channels ---
    params["num_ch_eeg"] = 32
    params["num_ch_bip"] = 3
    params["num_ch_emg"] = 3
    params["num_ch_eog"] = 0

    # --- Preprocessing ---
    params["do_filter_eog"] = False
    params["band_pass_filter_range"] = [8, 30]
    params["do_band_pass_filtering"] = True
    params["filter_order"] = 2
    params["channels_to_reject"] = [
        1,
        2,
        3,
        13,
        14,
        18,
        19,
        30,
        31,
        32,
    ]  # for Riemannian

    # --- Feature extraction ---
    params["num_features"] = 10
    params["feature_selection"] = "fisherScore"
    params["bands"] = np.arange(4, 62, 2).reshape(-1, 1)  # (4:2:60)
    params["window"] = 0.50
    params["overlap"] = 0.50

    # --- Classification ---
    params["classification_method"] = "LDA"
    params["evidence_accumulation_filter"] = [0.9, 0.1]
    params["class_thresholds"] = [0.6, 0.6, 0.6, 0.6]

    # --- Session/trial structure ---
    params["num_online_sessions"] = 5
    params["num_offline_sessions"] = 1
    params["num_runs"] = 4
    params["num_trials"] = [20, 20]
    params["dur_trial"] = 5  # seconds
    params["timeout"] = 7  # seconds

    # --- Channel selection ---
    params["chosen_16_channels"] = [
        6,
        10,
        11,
        15,
        16,
        17,
        21,
        22,
        41,
        42,
        43,
        45,
        46,
        48,
        49,
    ]
    params["ch_labels"] = []

    # --- Event triggers ---
    params["trig_run_start"] = 32766
    params["trig_trial_start"] = 768
    params["trig_lh"] = [
        769,
        7691,
        7692,
        7693,
    ]  # LH cue, task start, timeout end, threshold end
    params["trig_rh"] = [770, 7701, 7702, 7703]  # RH same
    params["trig_bh"] = [771, 7711, 7712, 7713]  # Both Hands same
    params["trig_bf"] = [772, 7721, 7722, 7723]  # Both Feet same
    params["trig_rest"] = 1000
    params["trig_labels"] = [
    "Run Start",
    "Trial Start",
    "Cue Rest",           # was "Cue Flexion"
    "Task Start Rest",    # was "Task Start Flexion"
    "Task End Rest (timeout)",
    "Task End Rest (threshold hit)",
    "Cue Flexion",        # was "Cue Extension"
    "Task Start Flexion", # was "Task Start Extension"
    "Task End Flexion (timeout)",
    "Task End Flexion (threshold hit)",
    "Inter-trial Rest Started",
	]
    # --- Sampling rate ---
    params["fs"] = fs if fs is not None else 512

    # --- Step size ---
    if step_size is not None:
        params["step_size"] = int(params["fs"] * step_size)
    else:
        params["step_size"] = int(params["fs"] * 1 / 16)

    # --- Epoch duration ---
    params["epoch_dur"] = epoch_dur if epoch_dur is not None else 1

    # --- Duration considered ---
    params["dur_considered"] = (
        dur_considered if dur_considered is not None else [5, 7, 0]
    )

    # --- Laplacian montage & derivations ---
    params = _set_montage(params)

    return params


def _set_montage(params):
    """Set the EEG montage and compute Laplacian derivations based on numChEEG."""
    n = params["num_ch_eeg"]

    if n == 5:
        montage = np.ones((1, 5), dtype=int)

    elif n == 64:
        # Loaded externally in MATLAB from biosemi64.mat — placeholder here
        from scipy.io import loadmat

        mat = loadmat("/home/alexandra-admin/Desktop/TESS/biosemi64.mat")
        montage = mat["montage"]
        print("[Warning] 64-channel montage must be loaded from biosemi64 layout file.")

    elif n == 32:
        montage = np.array(
            [
                [1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 0, 1, 1, 1],
                [0, 1, 1, 1, 1, 1, 0],
            ],
            dtype=int,
        )

    elif n == 15:
        montage = np.array(
            [
                [0, 0, 1, 0, 0],
                [1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1],
                [1, 1, 0, 1, 1],
            ],
            dtype=int,
        )

    elif n == 44:
        montage = np.array(
            [
                [1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 1, 1, 1, 0, 1, 1, 1, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1],
            ],
            dtype=int,
        )

    else:
        montage = None
        print(f"[Warning] No montage defined for {n} EEG channels.")

    params["montage"] = montage

    if montage is not None:
        params["laplacian_derivations"] = f4_eegc3_montage(montage)
    else:
        params["laplacian_derivations"] = None

    return params
