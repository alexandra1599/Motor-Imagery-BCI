"""
logo_validation.py
====================
Leave-One-Group-Out (run-wise) cross-validation for the Riemannian MDM
decoder, matching the offline_train.py n-back study's XDAWN+XGBoost pattern
(choice == 3 block): run-wise OOF probabilities, a single GLOBAL threshold
chosen to maximize TPR×TNR, per-run breakdown at that threshold, and
ROC/PR curves from the OOF vector.

Unlike kfold_validation.py (random k-fold + dual ambiguity thresholds),
this module:
  - Splits by RUN (not random shuffling) — avoids leaking adjacent
    sliding-window epochs from the same trial/run across train/test.
  - Picks ONE global decision threshold (not a reject-option band).
  - Reports TPR x TNR product, matching tpr_tnr_product() from the
    reference n-back driver.
"""

import numpy as np
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    accuracy_score,
)


def _matrix_pow(A, power):
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(eigvals ** power) @ eigvecs.T


def _matrix_log(A):
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-12)
    return eigvecs @ np.diag(np.log(eigvals)) @ eigvecs.T


def _matrix_exp(A):
    eigvals, eigvecs = np.linalg.eigh(A)
    return eigvecs @ np.diag(np.exp(eigvals)) @ eigvecs.T


def riemann_mean_local(covs, max_iter=50, tol=1e-7):
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


def riemann_distance_local(C1, C2):
    eigvals, eigvecs = np.linalg.eigh(C1)
    eigvals = np.maximum(eigvals, 1e-12)
    C1_inv_sqrt = eigvecs @ np.diag(eigvals ** -0.5) @ eigvecs.T
    inner = C1_inv_sqrt @ C2 @ C1_inv_sqrt
    ev = np.linalg.eigvalsh(inner)
    ev = np.maximum(ev, 1e-12)
    return float(np.sqrt(np.sum(np.log(ev) ** 2)))


def mdm_predict_proba_local(covs, prototypes):
    """P(class 1) for a stack of covariances via distance-based softmax."""
    n_trials = covs.shape[2]
    scores = np.zeros(n_trials)
    for t in range(n_trials):
        d0 = riemann_distance_local(covs[:, :, t], prototypes[0])
        d1 = riemann_distance_local(covs[:, :, t], prototypes[1])
        s0, s1 = np.exp(-d0), np.exp(-d1)
        scores[t] = s1 / (s0 + s1)
    return scores


def tpr_tnr_from_labels(y_true, y_pred):
    """Matches tpr_tnr_from_labels() in the reference n-back driver."""
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    tnr = tn / (tn + fp) if (tn + fp) else 0.0
    return tpr, tnr, tpr * tnr


def evaluate_decoder_logo(
    covs, labels, run_ids,
    make_plots=True,
):
    """
    Leave-one-run-out CV evaluation of the Riemannian MDM decoder,
    matching the n-back study's XDAWN+XGBoost offline validation pattern.

    Parameters
    ----------
    covs       : (n_ch, n_ch, n_trials) — covariances (post trace-norm/
                 whitening, same as used for final training)
    labels     : (n_trials,) — original labels, e.g. [-1, 1]
    run_ids    : (n_trials,) — group id per epoch (one XDF run = one group)
    make_plots : bool — whether to generate ROC/PR matplotlib plots

    Returns
    -------
    results : dict — OOF metrics, chosen global threshold, per-run breakdown
    """
    labels  = np.asarray(labels)
    run_ids = np.asarray(run_ids)
    classes = np.sort(np.unique(labels))
    if len(classes) != 2:
        raise ValueError('evaluate_decoder_logo expects exactly 2 classes.')
    rest_label, move_label = classes[0], classes[1]
    n_trials = covs.shape[2]
    n_runs = len(np.unique(run_ids))

    print(f'\n🚀 Starting Leave-One-Run-Out CV ({n_runs} runs, MDM)...\n')

    logo = LeaveOneGroupOut()

    # Binary labels for sklearn-style metrics (0=rest, 1=move)
    y_bin = (labels == move_label).astype(int)

    oof_true  = y_bin.copy()
    oof_proba = np.empty(n_trials, dtype=float)

    per_run_argmax_acc = []

    for tr_idx, te_idx in logo.split(np.arange(n_trials), y_bin, run_ids):
        covs_tr, covs_te = covs[:, :, tr_idx], covs[:, :, te_idx]
        y_tr = labels[tr_idx]

        proto_rest = riemann_mean_local(covs_tr[:, :, y_tr == rest_label])
        proto_move = riemann_mean_local(covs_tr[:, :, y_tr == move_label])
        prototypes = [proto_rest, proto_move]

        scr_te = mdm_predict_proba_local(covs_te, prototypes)
        oof_proba[te_idx] = scr_te

        pred_argmax = (scr_te >= 0.5).astype(int)
        held_out_run = int(np.unique(run_ids[te_idx])[0])
        acc = accuracy_score(y_bin[te_idx], pred_argmax)
        per_run_argmax_acc.append((held_out_run, acc))
        print(f'✅ Run {held_out_run} (held out) Argmax Accuracy: {acc:.4f}')

    # ── Choose a single GLOBAL threshold to maximize TPR×TNR on OOF ─────────
    ths = np.unique(np.concatenate(([0.0, 1.0], oof_proba)))
    best_thr, best_prod = 0.5, -1.0
    for thr in ths:
        y_hat = (oof_proba >= thr).astype(int)
        _, _, prod = tpr_tnr_from_labels(oof_true, y_hat)
        if prod > best_prod:
            best_prod, best_thr = prod, float(thr)

    print(f'\nChosen GLOBAL threshold (OOF) = {best_thr:.2f}  '
          f'(TPR×TNR on OOF = {best_prod:.3f})')

    # ── Overall OOF metrics @ chosen threshold (matches reference's oof['ACC'] line) ──
    y_hat_global = (oof_proba >= best_thr).astype(int)
    overall_acc = accuracy_score(oof_true, y_hat_global)
    overall_tpr, overall_tnr, overall_prod = tpr_tnr_from_labels(oof_true, y_hat_global)
    print(f'OOF @thr: ACC={overall_acc:.3f}  TPR={overall_tpr:.3f}  TNR={overall_tnr:.3f}  '
          f'TPR×TNR={overall_prod:.3f}')

    # ── Per-run metrics at the chosen global threshold ───────────────────────
    print('\nPer-run metrics @ global threshold:')
    per_run_stats = []
    for r in np.unique(run_ids):
        m = run_ids == r
        y_true_r = oof_true[m]
        y_hat_r  = (oof_proba[m] >= best_thr).astype(int)
        acc = accuracy_score(y_true_r, y_hat_r)
        tpr, tnr, prod = tpr_tnr_from_labels(y_true_r, y_hat_r)
        print(f'  Run {int(r)}: Acc={acc:.3f}  TPR={tpr:.3f}  TNR={tnr:.3f}  TPR×TNR={prod:.3f}')
        per_run_stats.append({
            'run': int(r), 'acc': float(acc),
            'tpr': float(tpr), 'tnr': float(tnr), 'prod': float(prod),
        })

    # Run-wise CV TPR×TNR mean/std (matches reference's "Run-wise CV TPR×TNR: mean=... std=...")
    run_prods = [s['prod'] for s in per_run_stats]
    mean_prod = float(np.mean(run_prods))
    std_prod  = float(np.std(run_prods))
    print(f'Run-wise CV TPR×TNR: mean={mean_prod:.3f}  std={std_prod:.3f}')

    # ── AUCs from the same OOF vector ───────────────────────────────────────
    roc_auc = roc_auc_score(oof_true, oof_proba)
    pr_auc  = average_precision_score(oof_true, oof_proba)
    prevalence = float(oof_true.mean())

    print(f'\nOverall ROC-AUC = {roc_auc:.3f}')
    print(f'Overall PR-AUC  = {pr_auc:.3f}  (baseline={prevalence:.2f})')

    if make_plots:
        try:
            import matplotlib.pyplot as plt
            from sklearn.metrics import roc_curve, precision_recall_curve

            fpr, tpr_curve, _ = roc_curve(oof_true, oof_proba)
            plt.figure()
            plt.plot(fpr, tpr_curve, label=f'AUC={roc_auc:.3f}')
            plt.plot([0, 1], [0, 1], linestyle='--', label='Chance')
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title('ROC (OOF, Leave-One-Run-Out)')
            plt.legend()
            plt.tight_layout()
            plt.show()

            prec, rec, _ = precision_recall_curve(oof_true, oof_proba)
            plt.figure(figsize=(5, 4))
            plt.plot(rec, prec, label=f'PR (AP={pr_auc:.3f})')
            plt.hlines(prevalence, 0, 1, colors='gray', linestyles='--',
                       label=f'Baseline={prevalence:.2f}')
            plt.xlabel('Recall')
            plt.ylabel('Precision')
            plt.title('Precision-Recall (OOF, Leave-One-Run-Out)')
            plt.legend()
            plt.tight_layout()
            plt.show()
        except Exception as e:
            print(f'[Warning] Plotting failed (non-fatal): {e}')

    return {
        'method':            'logo',
        'n_runs':            n_runs,
        'global_threshold':  best_thr,
        'global_tpr_tnr_product': best_prod,
        'roc_auc':           roc_auc,
        'pr_auc':             pr_auc,
        'prevalence':         prevalence,
        'overall_accuracy':   float(overall_acc),
        'overall_tpr':        float(overall_tpr),
        'overall_tnr':        float(overall_tnr),
        'overall_tpr_tnr_product': float(overall_prod),
        'per_run_stats':      per_run_stats,
        'per_run_argmax_acc': [{'run': r, 'acc': float(a)} for r, a in per_run_argmax_acc],
        'mean_prod':          mean_prod,
        'std_prod':           std_prod,
        'n_trials':           n_trials,
        'oof_true':           oof_true.tolist(),
        'oof_proba':          oof_proba.tolist(),
    }
