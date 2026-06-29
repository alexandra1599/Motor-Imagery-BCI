import numpy as np
from scipy.special import softmax


def distance_riemann(A: np.ndarray, B: np.ndarray) -> float:
    """
    Compute the Riemannian distance between two SPD covariance matrices.

    Parameters
    ----------
    A : np.ndarray, shape (n, n) — reference covariance matrix
    B : np.ndarray, shape (n, n) — covariance matrix to compare

    Returns
    -------
    float : Riemannian distance sqrt(sum(log(eig(A, B))^2))
    """
    eigenvalues = np.linalg.eigvals(
        np.linalg.solve(B, A)
    )  # generalised eigenvalues of (A, B)
    return float(np.sqrt(np.sum(np.log(eigenvalues.real) ** 2)))


def mdm_decoder(decoder: dict, eeg_covariance: np.ndarray):
    """
    Minimum Distance to Mean (MDM) classifier on the Riemannian manifold.

    Parameters
    ----------
    decoder : dict
        Must contain:
            decoder['classification']['model']['parameters']  : list of 2 mean covariance matrices
            decoder['classification']['model']['class_names'] : array of 2 class labels
    eeg_covariance : np.ndarray, shape (n_channels, n_channels)
        Covariance matrix of the current EEG epoch.

    Returns
    -------
    predicted_class : int/float
        The predicted class label.
    probability : np.ndarray, shape (2,)
        Class probabilities derived from softmax of squared Riemannian distances.
    """
    params = decoder["classification"]["model"]["parameters"]
    class_names = decoder["classification"]["model"]["class_names"]

    d1 = distance_riemann(params[0], eeg_covariance)
    d2 = distance_riemann(params[1], eeg_covariance)

    # probability = 1 - softmax([d1^2, d2^2])
    probability = 1 - softmax(np.array([d1**2, d2**2]))

    predicted_class = (
        class_names[0] if probability[0] >= probability[1] else class_names[1]
    )

    return predicted_class, probability
