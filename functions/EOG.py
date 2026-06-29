import numpy as np


def eog_checker(eog_signal: np.ndarray, threshold: float) -> int:
    """
    Check whether EOG signal exceeds a threshold (artifact detection).

    Parameters
    ----------
    eog_signal : np.ndarray, shape (n_samples, 3)
        EOG signal with 3 bipolar channels:
            col 0: horizontal EOG left
            col 1: horizontal EOG right
            col 2: vertical EOG
    threshold : float
        Artifact threshold in µV (e.g. 280)

    Returns
    -------
    int
        1 if signal is clean (no artifact), 0 if artifact detected
    """
    h_eog = eog_signal[:, 1] - eog_signal[:, 0]  # horizontal EOG
    v_eog = eog_signal[:, 2] - eog_signal[:, :2].mean(axis=1)  # vertical EOG
    a_eog = eog_signal.mean(axis=1)  # average EOG

    combined = np.abs(np.concatenate([h_eog, v_eog, a_eog]))

    return 0 if combined.max() > threshold else 1
