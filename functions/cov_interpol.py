import numpy as np
from run_script_Reimannian_mdm import _matrix_pow


def covariance_interpolation(C1: np.ndarray, C2: np.ndarray, t: float) -> np.ndarray:
    """
    Geodesic interpolation between two SPD covariance matrices on the
    Riemannian manifold.

    Implements:
        C(t) = C1^{1/2} @ (C1^{-1/2} @ C2 @ C1^{-1/2})^t @ C1^{1/2}

    At t=0 returns C1, at t=1 returns C2.

    Parameters
    ----------
    C1 : np.ndarray, shape (n, n) — start covariance (SPD)
    C2 : np.ndarray, shape (n, n) — end covariance (SPD)
    t  : float in [0, 1]          — interpolation parameter

    Returns
    -------
    C : np.ndarray, shape (n, n)
    """
    C1_inv_sqrt = _matrix_pow(C1, -0.5)
    C1_sqrt = _matrix_pow(C1, 0.5)
    inner = _matrix_pow(C1_inv_sqrt @ C2 @ C1_inv_sqrt, t)
    return C1_sqrt @ inner @ C1_sqrt
