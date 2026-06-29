import numpy as np
from scipy.signal import butter
from a0_param_init import a0_param_initialization, f4_eegc3_montage


def d1_initialize_decoder(
    subject_id: int, params: dict, mode: str, classes: str, eog_filt_coeff
) -> dict:
    """
    Initialize the decoder structure from params.

    Parameters
    ----------
    subject_id      : int   — subject ID
    params          : dict  — from a0_param_initialization()
    mode            : str   — 'Visual' or 'STM'
    classes         : str   — class string e.g. 'LH_RH'
    eog_filt_coeff  : array or None — EOG filter coefficients

    Returns
    -------
    decoder : dict
    """
    b, a = butter(
        params["filter_order"],
        [x / (params["fs"] / 2) for x in params["band_pass_filter_range"]],
        btype="bandpass",
    )

    decoder = {
        "subject_id": subject_id,
        "mode": mode,
        "classes": classes,
        "class_thresholds": params["class_thresholds"],
        "num_sessions": params["num_offline_sessions"],
        "session_details": {
            "num_runs": params["num_runs"],
            "num_trials": params["num_trials"],
            "dur_trial": params["dur_trial"],
            "dur_useful_trial_period": params["dur_considered"],
            "dur_epoch": params["epoch_dur"],
            "triggers": {
                "trig_run_start": params["trig_run_start"],
                "trig_trial_start": params["trig_trial_start"],
                "trig_lh": params["trig_lh"],
                "trig_rh": params["trig_rh"],
                "trig_bh": params["trig_bh"],
                "trig_bf": params["trig_bf"],
                "trig_rest": params["trig_rest"],
            },
            "trigger_labels": params["trig_labels"],
        },
        "eog_filt_coeff": eog_filt_coeff,
        "num_ch_eog": params["num_ch_eog"],
        "num_ch_bip": params["num_ch_bip"],
        "num_ch_eeg": params["num_ch_eeg"],
        "ch_labels": params["ch_labels"],
        "fs": params["fs"],
        "preprocessing": {
            "band_pass_filter": {
                "do_filter": params["do_band_pass_filtering"],
                "range": params["band_pass_filter_range"],
                "b": b,
                "a": a,
            },
            "spatial_filtering": {
                "montage": params["montage"],
                "laplacian_derivations": params["laplacian_derivations"],
            },
            "channels_to_reject": params["channels_to_reject"],
        },
        "feature_extraction": {
            "freq_bands": params["bands"],
            "window": params["window"],
            "overlap": params["overlap"],
        },
        "feature_selection": {
            "method": params["feature_selection"],
            "num_features": params["num_features"],
            "selected_features_indices": np.arange(
                1, params["num_ch_eeg"] * len(params["bands"]) + 1
            ),
        },
        "classification": {
            "method": params["classification_method"],
            "model": None,
            "evidence_accumulation_filter": params["evidence_accumulation_filter"],
        },
    }

    return decoder
