"""
adaptive_recenter.py
======================
Online adaptive recentering for the TESS Riemannian MDM decoder, work with 
decoder['classification']['model']
numpy-prototype format (the same dict al0_builddecoder.py produces).

Math :
    if counter == 0 or Prev_T is None:
        Prev_T = cov                                    # cold start
    T_test     = geodesic_riemann(Prev_T, cov, 1/(counter+1))
    T_invsqrtm = invsqrtm(Prev_T)
    cov_rec    = T_invsqrtm @ cov @ T_invsqrtm.T          # whiten with OLD ref
    if update_recentering:
        Prev_T  = T_test                                  # THEN advance ref
        counter += 1
    return cov_rec

Key properties:
  - Whitens using Prev_T from BEFORE this sample (no leakage).
  - Reference updates on EVERY call by default (update_recentering=True) --
    no check_in_task gating. Pass update_recentering=False to freeze the
    reference (e.g. during periods you don't want to drift it).
  - Weight is 1/(counter+1), so the very first sample is whitened against
    itself (cov_rec = I) and the reference update has full weight 1 on
    sample 1, decaying ~1/N afterward -- a running Riemannian mean.
  - Cold-starts at Prev_T=None -- call reset() at the start of each
    recording/run to match how an online session always starts fresh.

Usage:
    from adaptive_recenter import AdaptiveRecenter

    recenter = AdaptiveRecenter()
    # at the start of each run:
    recenter.reset()
    # per classification tick:
    cov_w = recenter.update(cov, update_recentering=True)
"""

import numpy as np


def _matrix_pow(A: np.ndarray, power: float) -> np.ndarray:
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(eigvals ** power) @ eigvecs.T


def invsqrtm(A: np.ndarray) -> np.ndarray:
    """A^(-1/2) -- matches pyriemann.utils.base.invsqrtm."""
    return _matrix_pow(A, -0.5)


def geodesic_riemann(C1: np.ndarray, C2: np.ndarray, alpha: float) -> np.ndarray:
    """
    Geodesic interpolation from C1 to C2 at parameter alpha.
    Matches pyriemann.utils.geodesic.geodesic_riemann exactly:
        C1^(1/2) @ (C1^(-1/2) @ C2 @ C1^(-1/2))^alpha @ C1^(1/2)
    """
    C1_sqrt     = _matrix_pow(C1,  0.5)
    C1_inv_sqrt = _matrix_pow(C1, -0.5)
    inner = C1_inv_sqrt @ C2 @ C1_inv_sqrt
    return (C1_sqrt @ _matrix_pow(inner, alpha) @ C1_sqrt).real


class AdaptiveRecenter:
    """
    Stateful sequential Riemannian recentering, matching the robot driver's
    _adaptive_recenter_cov exactly. One instance per "band" if you ever run
    multi-band decoding (mu/beta) -- mirrors the mu/beta state separation in
    runtime_common.py (Prev_T vs Prev_T_beta).
    """

    def __init__(self, seed_reference=None):
        """
        Parameters
        ----------
        seed_reference : optional (n_ch, n_ch) covariance to start from
            instead of cold-starting at the first sample.  Pass the
            decoder's saved `populationMean` here if you want the online
            session to begin already centered near the offline-trained
            distribution, rather than drifting from a single noisy first
            sample.  Leave None to match the robot driver's behavior
            exactly (true cold start, Prev_T=None until first sample).
        """
        self._seed = None if seed_reference is None else seed_reference.copy()
        self.reset()

    def reset(self):
        """Call at the start of every run/recording -- matches the online
        driver's cold start (Prev_T=None, counter=0) at session start.
        If a seed_reference was provided, Prev_T starts there instead of
        None, and is NOT overwritten on the first update() call."""
        self.Prev_T  = None if self._seed is None else self._seed.copy()
        self.counter = 0
        self._seeded = self._seed is not None

    def update(self, cov, update_recentering=True):
        """
        Whiten one covariance using the current reference, then optionally
        advance the reference toward it.

        Parameters
        ----------
        cov : (n_ch, n_ch) trace-normalized + LW-shrunk covariance
        update_recentering : bool -- if False, whitens but does NOT advance
            the reference (matches robot driver's UPDATE_DURING_MOVE=False
            use case -- freeze the reference during a period you don't want
            to drift, e.g. while the subject is moving for real / FES active).

        Returns
        -------
        cov_recentered : (n_ch, n_ch)
        """
        # True cold start (no seed): first sample becomes its own reference,
        # matching the robot driver's `if counter==0 or Prev_T is None`.
        # Seeded start: Prev_T already holds the seed -- do NOT overwrite
        # it just because counter is still 0.
        if self.Prev_T is None or (self.counter == 0 and not self._seeded):
            self.Prev_T = cov.copy()

        T_test     = geodesic_riemann(self.Prev_T, cov, 1.0 / (self.counter + 1))
        T_invsqrtm = invsqrtm(self.Prev_T)
        cov_recentered = T_invsqrtm @ cov @ T_invsqrtm.T

        if update_recentering:
            self.Prev_T  = T_test
            self.counter += 1

        return cov_recentered
