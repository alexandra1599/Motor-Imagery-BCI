import numpy as np
from scipy.linalg import sqrtm, inv

def stabiliser(data: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Shift covariance matrices on the Riemannian manifold.
    
    Applies the affine transformation:
        transformed = R^{-1/2} * data * R^{-1/2T}
    
    where R = reference (the recentering matrix).

    Parameters
    ----------
    data : np.ndarray
        Single covariance matrix (n_channels, n_channels)
        or stack of matrices (n_channels, n_channels, n_trials).
    reference : np.ndarray, shape (n_channels, n_channels)
        Affine transformation matrix (e.g. Riemannian mean of reference set).

    Returns
    -------
    transformed_data : np.ndarray
        Recentered covariance matrix/matrices, same shape as input.
    """
    # Compute R^{-1/2}
    ref_invsqrt = inv(sqrtm(reference))

    if data.ndim == 2:
        # Single matrix
        return ref_invsqrt @ data @ ref_invsqrt.conj().T
    elif data.ndim == 3:
        # Stack of matrices (n_ch, n_ch, n_trials)
        n_trials = data.shape[2]
        transformed = np.zeros_like(data)
        for t in range(n_trials):
            transformed[:, :, t] = ref_invsqrt @ data[:, :, t] @ ref_invsqrt.conj().T
        return transformed
    else:
        raise ValueError(f"data must be 2D or 3D, got shape {data.shape}")
