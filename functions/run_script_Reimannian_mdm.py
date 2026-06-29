"""
Riemannian decoder-building script.
Equivalent of the MATLAB script that trains and saves a Riemannian MDM decoder.

Usage:
    python run_script_Reimannian_mdm.py
"""

import os
import pickle
import time
import numpy as np
from datetime import datetime


# =============================================================================
# Pure functions — safe to import from other modules
# =============================================================================

def _matrix_pow(A: np.ndarray, power: float) -> np.ndarray:
    """Compute matrix power A^power via eigendecomposition."""
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(eigvals ** power) @ eigvecs.T


def _matrix_log(A: np.ndarray) -> np.ndarray:
    """Compute matrix logarithm via eigendecomposition."""
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(np.log(eigvals)) @ eigvecs.T


def _matrix_exp(A: np.ndarray) -> np.ndarray:
    """Compute matrix exponential via eigendecomposition."""
    eigvals, eigvecs = np.linalg.eigh(A)
    return eigvecs @ np.diag(np.exp(eigvals)) @ eigvecs.T


def riemann_mean(covs: np.ndarray, max_iter: int = 50, tol: float = 1e-7) -> np.ndarray:
    """
    Compute the Riemannian (Fréchet) mean of a set of SPD covariance matrices
    using the fixed-point iteration (gradient descent on the manifold).

    Parameters
    ----------
    covs     : np.ndarray, shape (n_channels, n_channels, n_trials)
    max_iter : int
    tol      : float — convergence tolerance

    Returns
    -------
    mean_cov : np.ndarray, shape (n_channels, n_channels)
    """
    n_trials = covs.shape[2]
    mean_cov = covs.mean(axis=2)   # initialise with Euclidean mean

    for _ in range(max_iter):
        mean_cov_inv_sqrt = _matrix_pow(mean_cov, -0.5)
        mean_cov_sqrt     = _matrix_pow(mean_cov,  0.5)

        S = np.zeros_like(mean_cov)
        for t in range(n_trials):
            inner = mean_cov_inv_sqrt @ covs[:, :, t] @ mean_cov_inv_sqrt
            S    += _matrix_log(inner)
        S /= n_trials

        update = mean_cov_sqrt @ _matrix_exp(S) @ mean_cov_sqrt
        change = np.linalg.norm(update - mean_cov, "fro")
        mean_cov = update

        if change < tol:
            break

    return mean_cov


# =============================================================================
# Script entry point — only runs when executed directly, NOT on import
# =============================================================================

if __name__ == '__main__':

    import glob
    from a0_param_init import a0_param_initialization
    from d1_initialize_decoder import d1_initialize_decoder
    from extract_session_feat import d0_extract_session_features

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    SUBJECT_ID = 2
    EXPERIMENT = "TESS"
    MODE       = "Visual"
    CLASSES    = ""
    CLASSIFIER = "Rieman"

    RETRAIN        = False       # True  = offline + online session 2
                                 # False = offline only
    DUR_CONSIDERED = [3, 5]     # [offline_dur, online_dur] in seconds
    SAVE_DECODER   = True
    EPOCH_DUR      = 1.0        # seconds
    STEP_SIZE      = 1 / 16     # seconds

    # -------------------------------------------------------------------------
    # Initialise params and decoder
    # -------------------------------------------------------------------------
    params = a0_param_initialization(
        dur_considered=DUR_CONSIDERED,
        epoch_dur=EPOCH_DUR,
        step_size=STEP_SIZE,
    )
    params["do_band_pass_filtering"] = True   # required for Riemannian
    params["feature_selection"]      = "shrinkageCovariance"
    params["classification_method"]  = "Riemann"

    decoder = d1_initialize_decoder(SUBJECT_ID, params, MODE, CLASSES, eog_filt_coeff=None)

    # -------------------------------------------------------------------------
    # Extract features
    # -------------------------------------------------------------------------
    if RETRAIN:
        selected_session = [[], [-1, []]]   # offline: all | online: skip s1, take all s2
    else:
        selected_session = [[], [-1]]       # offline: all | online: skip all

    epoch = d0_extract_session_features(
        CLASSIFIER,
        SUBJECT_ID,
        MODE,
        CLASSES,
        selected_session=selected_session,
        select_periods=[0, 0, 1, 0],        # task period only
        selected_features=list(
            range(decoder["num_ch_eeg"] * len(decoder["feature_extraction"]["freq_bands"]))
        ),
        saving=False,
        dur_considered=DUR_CONSIDERED,
    )

    # Fix shape mismatch between covariance matrices and labels
    print("feature task shape:", epoch["feature"]["task"].shape)
    print("label shape:", epoch["label"].shape)
    n_cov    = epoch["feature"]["task"].shape[2]
    n_labels = len(epoch["label"])
    if n_cov != n_labels:
        step           = n_labels // n_cov
        epoch["label"] = epoch["label"][::step][:n_cov]
        print(f"Resampled labels from {n_labels} to {len(epoch['label'])} to match covariances")

    decoder["info"]      = epoch["info"]
    decoder["ch_labels"] = epoch["params"].get("ch_labels", [])

    # -------------------------------------------------------------------------
    # Train Riemannian MDM classifier
    # -------------------------------------------------------------------------
    unique_labels   = np.sort(np.unique(epoch["label"]))
    n_classes       = len(unique_labels)
    class_prototype = []

    print("\nTraining Riemannian MDM classifier...")
    t0 = time.time()

    for i, label in enumerate(unique_labels):
        trial_mask = epoch["label"] == label
        class_covs = epoch["feature"]["task"][:, :, trial_mask]
        prototype  = riemann_mean(class_covs)
        class_prototype.append(prototype)
        print(f"\t Class {label}: {trial_mask.sum()} trials, mean computed.")

    elapsed = time.time() - t0
    print(f"\t Time to train the classifier = {elapsed:.2f}s")

    # Store in decoder
    decoder["classification"]["model"] = {
        "parameters":      class_prototype,
        "class_names":     unique_labels,
        "distance_metric": "AIRM",
    }
    decoder["classification"]["method"]            = "Rieman"
    decoder["preprocessing"]["channels_to_reject"] = params["channels_to_reject"]

    # -------------------------------------------------------------------------
    # Save decoder
    # -------------------------------------------------------------------------
    if SAVE_DECODER:
        data_root    = os.getcwd()
        decoder_path = os.path.join(
            data_root,
            "f2_subjectDecoders",
            f"Subject_{SUBJECT_ID:03d}_OfflineOnline",
            CLASSIFIER,
        )
        os.makedirs(decoder_path, exist_ok=True)

        dt    = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        fname = (
            f"Subject_{SUBJECT_ID:03d}_Experiment_{EXPERIMENT}"
            f"_mode_{MODE}_classes_{CLASSES}_Decoder_{dt}_.pkl"
        )
        save_path = os.path.join(decoder_path, fname)

        with open(save_path, "wb") as f:
            pickle.dump(decoder, f)

        print("\n" + "=" * 74)
        print("\t  " + "*" * 53)
        print(f"\t\t  Subject-{SUBJECT_ID:03d} Decoder is READY")
        print("\t  " + "*" * 53)
        print("=" * 74 + "\n")
        print(f"Saved to: {save_path}")
