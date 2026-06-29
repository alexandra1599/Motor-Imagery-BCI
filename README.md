# Motor-Imagery-BCI
Motor Imagery + Transcutaneous Electrical Spinal-Chord Stimulation BCI

# Riemannian MDM Decoder — Offline Training & Online Classification

Core BCI signal processing pipeline for the TESS Motor Imagery system. Covers offline decoder training, online adaptive classification, and all supporting utilities. The covariance pipeline is identical between training and online use — this is the central design constraint that everything else is built around.

---

## Repository Structure

```
.
├── config_tess.py                 # Master session config (thresholds, integrator, recentering)
│
├── — Offline Training —
├── a0_param_init.py               # Parameter initialization and EEG montage setup
├── d1_initialize_decoder.py       # Decoder dict scaffold from params
├── d0_extract_session_features.py # XDF session loader, EOG regression, covariance extraction
├── al0_builddecoder.py            # Main decoder training script
├── logo_validation.py             # Leave-one-run-out cross-validation
│
├── — Online Classification —
├── ndf_main_adap.py               # Online adaptive MDM classifier (main runtime)
├── ndf_shared.py                  # Shared utilities: LSL, UDP, ring buffer, decoder I/O
├── adaptive_recenter.py           # Sequential Riemannian recentering (stateful)
│
├── — Classifier Core —
├── mdm_decoder.py                 # MDM classifier: Riemannian distance + softmax
├── EOG.py                         # EOG artifact detection gate
```

---

## Covariance Pipeline

The same steps must be applied at training time and online — in the same order and with the same preprocessing. Any mismatch puts test covariances in a different space from the trained prototypes.

```
Raw EEG window (n_ch × n_samples)
    │
    ▼  Baseline correction
    │  Training: subtract mean of fixed 2 s pre-trial window (_epoch_task)
    │  Online:   subtract mean of fixation window (_compute_baseline, BASELINE_DURATION=2.0 s)
    │
    ▼  Step 1: Trace-normalize + Ledoit-Wolf shrinkage
    │          cov = X @ X.T                      [no /n_samples — cancelled by trace-norm]
    │          cov = cov / trace(cov)
    │          lam = LedoitWolf().fit(X).shrinkage_
    │          cov = (1-λ)·cov + λ·(tr/n)·I
    │
    ▼  Step 2: Batch Riemannian whitening
    │          Training: Whitening.fit_transform(covs) → save whitener in decoder
    │          Online:   whitener.transform(cov)        → same fitted reference
    │
    ▼  Step 3: Sequential adaptive recentering  (ONLINE ONLY)
    │          AdaptiveRecenter.update(cov)
    │          cold-starts per run (reset() on marker 32766)
    │
    ▼  Step 4: MDM classify
               Riemannian distance to each class prototype → exp(-d) softmax
```

Steps 1–2 are applied at training time in `al0_builddecoder.py`. The fitted `Whitening` object is saved inside the decoder `.pkl` so `ndf_main_adap.py` applies the exact same transform online. Step 3 is online-only — prototypes live in the whitened-but-not-recentered space.

**No demeaning is applied inside the covariance step** in either training or online. Both rely solely on the baseline subtraction step above to remove DC offsets.

---

## Script Descriptions

### `d0_extract_session_features.py` — XDF Session Loader

Loads XDF data, performs EOG regression, epochs into sliding windows, and returns covariance matrices ready for `al0_builddecoder.py`.

**Folder structure expected:**
```
f1_data/Subject_003/
    Subject_003_Session_001_MI_Offline_BCI_FES/
        calibrationData/
            Subject_003_MI_BCI_Calib_FES_s001_r000_...xdf   ← EOG calibration
        Subject_003_MI_BCI_s001_r001_...xdf                  ← run files
```

**Processing steps per session:**
1. Loads EOG calibration XDF and fits linear regression coefficients (`beta = pinv(eog) @ eeg`) on 1–10 Hz bandpass-filtered data
2. For each run XDF: applies EOG regression (`eeg_clean = eeg - eog @ beta`), then bandpass-filters EEG (8–30 Hz)
3. Rejects bad channels (from `params['channels_to_reject']`)
4. Extracts task epochs using sliding windows over the last `dur_considered` seconds of each trial
5. **Baseline correction:** subtracts the mean of the fixed 2 s window immediately before each trial onset (matches `config.BASELINE_DURATION = 2.0` online)
6. Computes trace-normalized + LW covariance per epoch via `_extract_covariance()`
7. Tracks run IDs per epoch for LOGO CV group assignment

**EOG channel mapping** (XDF stream, 0-indexed):
- `[35, 36, 37]` → AUX7, AUX8, AUX9 (eye canthi + forehead)
- `[0–31]` → EEG, `[32–34]` → AUX1–3 (unused), `[38]` → TRIGGER

**Returns** an `epoch` dict with:
- `feature.task`: `(n_ch, n_ch, n_epochs)` for Riemannian
- `label`: `(n_epochs,)` — `-1` = REST, `1` = MOVE
- `run_ids`: `(n_epochs,)` — run-group index for LOGO CV

---

### `al0_builddecoder.py` — Offline Decoder Training

Run once (or after new sessions) to build the `.pkl` decoder file.

**Steps performed:**
1. Prompts whether to apply a **geodesic shift** to class prototypes (shifts them further apart on the manifold by `SHIFTER`% along the geodesic)
2. Calls `a0_param_initialization()` to set filter, montage, and trigger params
3. Calls `d0_extract_session_features()` to load XDF data and extract baseline-corrected, trace-normalized + LW covariances
4. Fits `pyriemann.Whitening` on all training covariances and transforms them
5. Computes per-class Riemannian means (MDM prototypes) in the whitened space
6. Scores the training set and prints d′ (class separability)
7. Runs **Leave-One-Run-Out CV** (`logo_validation.py`) and picks a global threshold maximizing TPR×TNR
8. Saves decoder `.pkl` to `f2_subjectDecoders/Subject_XXX_Offline/Rieman[_shifted]/`

**Edit these at the top before each build:**

| Variable | Description |
|---|---|
| `SUBJECT_ID` | Subject number |
| `OFFLINE_SESSIONS` | List of 1-indexed session indices to include (`[]` = all) |
| `ONLINE_SESSIONS` | Online sessions to include (`[]` = skip all) |
| `DUR_CONSIDERED` | Epoch window(s) in seconds, e.g. `[3, 5]` |
| `APPLY_WHITENING` | Enable batch Riemannian whitening (should stay `True`) |
| `MAKE_PLOTS` | Show ROC/PR curves after LOGO CV |

```bash
python3 al0_builddecoder.py
# Prompts: Apply geodesic shift? [y/n]
# Prompts (if y): Shift percentage? (default 15)
```

**Output decoder path:**
```
f2_subjectDecoders/
└── Subject_003_Offline/
    └── Rieman/                     # or Rieman_shifted
        └── Subject_003_Off_all_YYYY_MM_DD_HH_MM_SS_.pkl
```

---

### `ndf_main_adap.py` — Online Adaptive Classifier

The runtime classifier. Runs as a background process during each BCI session, receiving EEG from LSL, classifying in real time, and streaming probabilities to the visual display (`a2_online_FES.py`) over UDP.

**Usage:**
```bash
python3 ndf_main_adap.py <subjectID> <sessionID> <recID> <decoderChoice>
```

| Arg | Description |
|---|---|
| `subjectID` | Integer subject ID |
| `sessionID` | Session number |
| `recID` | Recording/run number (used for output filename) |
| `decoderChoice` | `1` = Offline, `2` = Offline shifted, `3` = Offline+Online, `4` = Offline+Online shifted |

**Startup sequence:**
1. Loads the most recent `.pkl` from the selected decoder folder
2. Extracts whitener, prototypes, spectral filter, channel rejection list
3. Initializes `AdaptiveRecenter` (cold-start, `seed=None`)
4. Connects to LSL EEG stream (`eegoSports 000170`) and `MarkerStream`
5. Sends `READY` on UDP port `12348` → `a2_online_FES.py` unblocks and sends run-start marker `32766`

**Per-trial loop:**
- Marker `32766` → reset recenterer, start buffering
- Markers `7691`/`7701` → trial start: compute 2 s fixation baseline, reset leaky integrator
- Every `STEP_SIZE` seconds: run full covariance pipeline (baseline-correct → trace-norm+LW → whiten → recenter → MDM), update `LeakyIntegrator`, send `[raw_rest, raw_move]` on UDP port `12347`
- Markers `7692`/`7702`/`7693`/`7703` → trial end
- Second `32766` → save updated decoder, send `[1000.0, 1000.0]` as end-of-run signal, exit

**Probability encoding for UDP:**
```
fill ∈ [0, 1]  →  raw = fill/2 + 0.5  →  sent as "raw_rest,raw_move\n"
```
The visual driver inverts this: `fill = (raw - 0.5) * 2`. Values must be sent as raw floats in [0, 1], not percentages.

---

### `ndf_shared.py` — Shared Utilities

Imported by all `ndf_main_*.py` scripts. Provides:

- `connect_eeg_stream(stream_name)` — resolves and returns LSL `StreamInlet` for EEG
- `connect_marker_stream(stream_name)` — resolves LSL `MarkerStream` inlet
- `send_probabilities(prob, decoder)` — sends `[rest, move]` float array as comma-separated UDP to port `12347`
- `send_marker_udp(event_id)` — sends integer marker to port `12345`
- `StreamBuffer` — circular ring buffer with per-channel IIR filter state (replaces MATLAB global stream struct)
- `load_decoder(path)` — loads most recent `.pkl` from a directory
- `make_eog_filter(fs)` — returns 2nd-order Butterworth 1–10 Hz bandpass coefficients for EOG
- `update_reference(decoder, features, ...)` — legacy geodesic interpolation reference update (older pipeline; `AdaptiveRecenter` is preferred)
- `save_decoder_run(...)` — saves decoder at end of run and logs to `decoderLogHistory/`

---

### `adaptive_recenter.py` — Sequential Riemannian Recentering

Stateful online recentering. One instance per run, reset on run start.

**Algorithm (per classification step):**
```
if Prev_T is None:             # cold start
    Prev_T = cov
T_test     = geodesic(Prev_T, cov, 1/(counter+1))   # running Riemannian mean
T_invsqrtm = Prev_T^(-1/2)
cov_rec    = T_invsqrtm @ cov @ T_invsqrtm.T         # whiten with OLD ref
if update_recentering:
    Prev_T  = T_test           # advance AFTER whitening (no leakage)
    counter += 1
```

Key properties:
- Whitens using `Prev_T` **before** this sample — no self-whitening leakage
- Weight `1/(counter+1)` decays like a running mean: full weight on first sample, ~1/N afterward
- `update_recentering=False` freezes the reference (controlled by `UPDATE_DURING_TRIAL` in `config_tess.py`)
- Optional `seed_reference` allows initializing from the decoder's `populationMean` instead of cold-starting

```python
recenter = AdaptiveRecenter(seed_reference=None)  # cold start per run
recenter.reset()                                   # call at start of each run
cov_w = recenter.update(cov, update_recentering=True)
```

---

### `mdm_decoder.py` — MDM Classifier

Minimum Distance to Mean classifier on the Riemannian manifold.

```python
predicted_class, probability = mdm_decoder(decoder, eeg_covariance)
# probability: 1 - softmax([d1², d2²])
```

Note: `ndf_main_adap.py` uses its own inline `mdm_predict_proba()` which applies `exp(-d)` softmax (closer prototype = higher probability). `mdm_decoder.py` uses `1 - softmax(d²)`. Both are valid MDM variants but give different probability values for the same distances — ensure the same variant is used consistently within each pipeline.

---

### `logo_validation.py` — Leave-One-Run-Out Cross-Validation

Called by `al0_builddecoder.py` after training. Evaluates generalization using run boundaries as fold boundaries (avoids leaking adjacent sliding-window epochs across folds).

**Outputs:**
- OOF P(MOVE) probabilities across all trials
- Single global threshold maximizing TPR×TNR on the OOF vector
- Per-run breakdown at that threshold
- Overall ROC-AUC and PR-AUC
- Optionally: ROC and PR curve plots

Returns a `results` dict stored in `decoder['validation']` and accessible after loading any saved decoder.

---

### `a0_param_init.py` — Parameter Initialization

Centralizes all experiment parameters. Call once before building the decoder.

```python
params = a0_param_initialization(
    dur_considered=[3, 5],   # epoch window(s) in seconds
    epoch_dur=1.0,            # feature extraction window
    step_size=1/16,           # classification step (~62.5 ms at 512 Hz)
    fs=512,
)
```

Montage support: 5, 15, 32, 44, or 64 channels. For 32 ch, a 5×7 binary grid defines the Laplacian derivation layout via `f4_eegc3_montage()`.

Key channel rejection list (1-indexed, for 32-ch cap):
`[1, 2, 3, 13, 14, 18, 19, 30, 31, 32]` — removes edge electrodes before covariance estimation.

---

### `d1_initialize_decoder.py` — Decoder Dict Scaffold

Creates the empty decoder structure from `params`. The returned dict is the standard container passed through all pipeline stages and saved as `.pkl`.

**Top-level keys in a saved decoder:**

| Key | Contents |
|---|---|
| `subject_id`, `mode`, `classes` | Session metadata |
| `fs` | Sampling rate |
| `preprocessing` | Bandpass filter coeffs, montage, channel rejection list |
| `classification.model.parameters` | Class prototype covariances (in batch-whitened space) |
| `classification.model.class_names` | e.g. `[-1, 1]` (REST, MOVE) |
| `classification.model.globalThreshold` | Threshold from LOGO CV |
| `classification.model.TestEpochCounter` | Recentering epoch count (updated online) |
| `whitener` | Fitted `pyriemann.Whitening` object (applied online at test time) |
| `spectralFilter` | Bandpass `{b, a, range_hz, order}` |
| `validation` | LOGO CV results dict |

---

### `EOG.py` — EOG Artifact Gate

Simple amplitude threshold check on 3-channel bipolar EOG. Returns `1` (clean) or `0` (artifact).

```python
clean = eog_checker(eog_signal, threshold=280)   # threshold in µV
```

In `ndf_main_adap.py`, `THRESHOLD_EOG = float('inf')` in `config_tess.py` disables EOG gating entirely (all epochs accepted).

---

## Decoder Directory Structure

```
f2_subjectDecoders/
├── Subject_003_Offline/
│   ├── Rieman/
│   │   └── Subject_003_Off_all_2025_06_01_10_30_00_.pkl
│   └── Rieman_shifted/
│       └── Subject_003_Off_all_2025_06_01_10_35_00_.pkl
├── Subject_003_OfflineOnline/
│   └── Rieman/
│       └── Subject_003_Off3_On2_2025_06_02_09_00_00_.pkl
└── Subject_003_Online/
    └── Rieman/
        └── decoder_run001.pkl       ← saved by ndf_main_adap.py after each run
```

`ndf_main_adap.py` always loads the **alphabetically last** `.pkl` from the selected folder.

---

## Session Workflow

```bash
# 1. Build decoder from offline XDF data
python3 al0_builddecoder.py
# → prompts for geodesic shift → saves to f2_subjectDecoders/

# 2. Start marker bridge (keep running)
python3 UTIL_marker_stream_TESS.py

# 3. Start online classifier (separate terminal)
python3 ndf_main_adap.py 3 1 1 1
# Blocks, sending READY and waiting for 32766 from visual display

# 4. Start visual display + FES (triggers READY handshake)
python3 a2_online_FES.py logs/sub003_run1.txt left 65 65
```

---

## Dependencies

```
numpy
scipy
scikit-learn
pyriemann          # Whitening, geodesic_riemann, invsqrtm
pyxdf              # XDF file loading (d0_extract_session_features.py)
pylsl              # LSL stream inlet
matplotlib         # LOGO CV plots (optional)
```

```bash
pip install numpy scipy scikit-learn pyriemann pyxdf pylsl matplotlib
```

### Internal Imports (must be on `sys.path`)

| Module | Used by |
|---|---|
| `f4_eegc3_montage` | `a0_param_init.py` — Laplacian derivation from montage grid |
| `covar_extract` | `ndf_shared.py` — covariance computation utility |
| `cov_interpol` | `ndf_shared.py` — covariance interpolation |
| `stabilizer` | `ndf_shared.py` — SPD matrix stabilization |
| `m0_initializeParams` | `ndf_main_adap.py` — runtime parameter init |
| `mdm_predict` | `al0_builddecoder.py` — score distribution analysis |

---

## Notes

- The `DECODER_BASE` path in `ndf_main_adap.py` is hardcoded to `/home/alexandra-admin/Desktop/TESS/f2_subjectDecoders`. Update this for each machine or move to `config_tess.py`.
- If a decoder was saved without a `whitener` key (older format), `ndf_main_adap.py` falls back to applying `pop_mean_inv_sqrt` (fixed whitening via population mean inverse square root). New decoders always include the fitted `Whitening` object.
- `LeakyIntegrator` in `ndf_main_adap.py` initializes at `0.5` and resets to `0.5` on each trial start. `INTEGRATOR_ALPHA=0.85` in `config_tess.py` gives roughly a 6-step memory (~375 ms at 62.5 ms step size).
- Session indices in `OFFLINE_SESSIONS` / `ONLINE_SESSIONS` in `al0_builddecoder.py` are **1-indexed** (matching `_pick()` in `d0_extract_session_features.py`). `[]` = all sessions, `[-1]` = skip all. Passing `[0]` silently returns no sessions.

---

## Related

- `a2_online_FES.py` — visual display and FES; receives probabilities on UDP port `12347`, sends markers on `12345`
- `UTIL_marker_stream_TESS.py` — UDP→LSL bridge; must be running before any script
- `config_tess.py` — master config shared by this folder and `a2_online_FES.py`
