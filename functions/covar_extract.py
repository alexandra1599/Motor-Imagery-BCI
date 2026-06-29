import numpy as np


def extract_covariance(eeg_data: np.ndarray) -> np.ndarray:
    """
    Compute trace-normalised regularised covariance matrix of EEG data.

    Parameters
    ----------
    eeg_data : np.ndarray, shape (n_samples, n_channels)
        Raw EEG segment.

    Returns
    -------
    covariance_matrix : np.ndarray, shape (n_channels, n_channels)
        Shrinkage-regularised covariance matrix.
    """
    norm_factor = np.sqrt(np.trace(eeg_data.T @ eeg_data))
    normalised = eeg_data / norm_factor
    return cov1para(normalised)


def cov1para(x: np.ndarray, shrink: float = -1) -> np.ndarray:
    """
    Ledoit-Wolf shrinkage covariance estimator (one-parameter target).

    Shrinks the sample covariance towards a scaled identity matrix
    (equal variances, zero covariances).

    Parameters
    ----------
    x      : np.ndarray, shape (n_samples, n_channels)
        Zero-mean or raw observations (de-meaning is applied internally).
    shrink : float, optional
        Fixed shrinkage coefficient in [0, 1].
        Pass -1 (default) to estimate it analytically from the data.

    Returns
    -------
    sigma : np.ndarray, shape (n_channels, n_channels)
        Regularised covariance matrix.
    shrinkage : float
        Shrinkage coefficient that was applied.
    """
    t, n = x.shape

    # --- De-mean ---
    x = x - x.mean(axis=0)

    # --- Sample covariance ---
    sample = (x.T @ x) / t

    # --- Prior: scaled identity (equal variances, no covariance) ---
    mean_var = np.diag(sample).mean()
    prior = mean_var * np.eye(n)

    # --- Estimate shrinkage analytically if not provided ---
    if shrink == -1:
        y = x**2
        phi_mat = (y.T @ y) / t - 2 * (x.T @ x) * sample / t + sample**2
        phi = phi_mat.sum()

        gamma = np.linalg.norm(sample - prior, "fro") ** 2
        kappa = phi / gamma
        shrinkage = float(np.clip(kappa / t, 0, 1))
    else:
        shrinkage = float(shrink)

    # --- Shrinkage estimator ---
    sigma = shrinkage * prior + (1 - shrinkage) * sample

    return sigma
