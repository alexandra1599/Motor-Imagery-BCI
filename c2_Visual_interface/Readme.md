# Online BCI + FES Paradigm (TESS Motor Imagery)

Pygame-based visual display and FES delivery scripts for the **TESS online Motor Imagery BCI session**. This folder contains the full stimulus presentation layer: EOG calibration, offline FES training, and the online closed-loop paradigm where real-time classifier output from `ndf_main_adap.py` drives both the display and the Rehamove stimulator.

---

## Repository Structure

```
.
├── config_tess.py            # Master session config (change each session)
├── a0_configFile.py          # Trial timing and randomization
├── a0_configFileSTM.py       # FES stimulation intensities and pulse widths
├── a_calibration.py          # EOG calibration (eye movement + blink)
├── a1_offline_FES.py         # Offline FES training (time-based, no classifier)
├── a2_online_FES.py          # Online closed-loop BCI + FES display
└── UTIL_marker_stream_TESS.py # UDP→LSL marker bridge (run as a separate process)
```

---

## System Architecture

```
┌─────────────────────┐     UDP :12345      ┌──────────────────────────┐
│  a2_online_FES.py   │ ──── markers ──────▶ │ UTIL_marker_stream_TESS  │
│  (display + FES)    │                      │  (UDP → LSL bridge)      │
│                     │ ◀─── probs ────────  │                          │
│                     │     UDP :12347       └──────────────────────────┘
│                     │                               │ LSL MarkerStream
│                     │ ◀─── READY ────────           ▼
│                     │     UDP :12348       ┌──────────────────────────┐
└─────────────────────┘                      │    ndf_main_adap.py      │
                                             │  (EEG classifier)        │
         │ FES                               │  Riemannian / MDM        │
         ▼                                   └──────────────────────────┘
  Rehamove (USB)
```

**Startup handshake:** `a2_online_FES.py` waits on UDP port `12348` for a `READY` signal from `ndf_main_adap.py` before sending the run-start marker `32766`. This eliminates the timing race where the classifier could miss the first trial marker.

**Probability stream:** `ndf_main_adap.py` sends `[raw_rest, raw_move]` floats over UDP to port `12347` after each classification. `a2_online_FES.py` remaps these from classifier space `[0.5, 1.0]` → display space `[0.0, 1.0]` via `(raw - 0.5) * 2`. If no packet arrives, the display holds its last value.

---

## Script Descriptions

### `a_calibration.py` — EOG Calibration
Run at the start of each session before any EEG/BCI task. Displays fixation dots at four positions (top / bottom / left / right) in a randomized sequence to capture eye movement artifacts, followed by a green fixation cross for blink capture.

- `RUNS = 15` dot appearances total (evenly split across 4 positions)
- `BLINK_TIME = 10` s green cross phase for blink calibration
- Markers sent via UDP + LSL

### `a1_offline_FES.py` — Offline FES Training
Time-driven (no classifier) training paradigm used to pair motor imagery with FES before the online session. Each trial is either:
- **REST (trial = 0):** Circle fills progressively over `taskTime` seconds; no FES
- **MOVE (trial = 1):** Bar grows rightward over `taskTime` seconds; STS FES delivered at `FES_freq` Hz, switching to distal stimulation at the halfway point; MTS FES during result display

Loads trial order from `a0_configFile.py`. Always starts with a forced Move then Rest trial (`[1, 0, ...]`) before the randomized sequence.

### `a2_online_FES.py` — Online Closed-Loop BCI + FES
The primary online session script. Each trial runs through five phases:

1. **Rest** — blank screen, `restTime + U(0,1)` s
2. **Fixation** — cross displayed, `fixationCrossTime` s; `ndf_main_adap.py` uses this window to compute per-trial EEG baseline
3. **Cue** — imagery cue image shown for `cueTime` s
4. **Task window** — classifier probabilities received over UDP, display fills in real time, FES triggered proportional to confidence; ends on threshold crossing or `timeout`
5. **Result** — green (correct) or red (incorrect) feedback for `resultTime` s; MTS FES on correct Move trials

FES delivery during the task window is probability-gated:
- Both probs zero → proximal STS (baseline)
- Move prob dominant, below half-threshold → proximal STS
- Move prob dominant, above half-threshold → proximal + distal STS
- Rest prob dominant (symmetric logic)
- Correct Move detection → MTS proximal + distal throughout result display

### `UTIL_marker_stream_TESS.py` — UDP→LSL Marker Bridge
**Must be running as a separate process before any other script is started.** Listens on UDP port `12345`, validates incoming codes against a whitelist, pulls the current EEG timestamp from the LSL `EEG` stream, and pushes `[marker_value, eeg_timestamp]` as a 2-element float32 LSL sample. This gives all markers precise alignment to the EEG clock rather than system clock.

```bash
python UTIL_marker_stream_TESS.py
```

---

## Configuration

### `config_tess.py` — Master Session Config
**Edit this file at the start of every session.** Key parameters:

| Parameter | Default | Description |
|---|---|---|
| `TRAINING_SUBJECT` | `3` | Subject ID |
| `FS` | `512` Hz | EEG sampling rate |
| `CLASSIFY_WINDOW` | `1000` ms | Classification window length |
| `STEP_SIZE` | `1/16` s | Classification step (≈62.5 ms) |
| `THRESHOLD_MI` | `0.60` | P(MOVE) required to trigger Move result |
| `THRESHOLD_REST` | `0.60` | P(REST) required to trigger Rest result |
| `SHAPE_MIN` | `0.45` | Probability at which display starts filling |
| `SHAPE_MAX` | `1.00` | Probability at which display is fully filled |
| `INTEGRATOR_ALPHA` | `0.85` | Leaky integrator smoothing (higher = smoother) |
| `MIN_PREDICTIONS` | `5` | Min classifications before early stop |
| `BASELINE_DURATION` | `2.0` s | Fixation window used for EEG baseline |
| `RECENTERING` | `True` | Enable online Riemannian recentering |
| `FES_toggle` | `1` | Enable (1) or disable (0) FES output |
| `THRESHOLD_EOG` | `inf` | EOG artifact gate (inf = disabled) |

### `a0_configFile.py` — Trial Timing and Randomization

| Parameter | Default | Description |
|---|---|---|
| `ExperimentConfigureTime` | `2` s | Delay after run-start marker |
| `fixationCrossTime` | `1` s | Fixation cross duration |
| `cueTime` | `1.5` s | Cue display duration |
| `taskTime` | `5` s | Maximum task window (offline) |
| `timeout` | `7` s | Maximum task window (online) |
| `resultTime` | `2` s | Result feedback duration |
| `restTime` | `1.5` s | Base rest duration (jitter added at runtime) |
| `n_Rest` | `5` | Rest trials |
| `n_Move` | `5` | Move trials |

Trial order is randomized at import time (without replacement), with two forced trials prepended: `[Move, Rest, ...randomized...]`.

### `a0_configFileSTM.py` — FES Stimulation Parameters

Defines sensory (STS) and motor (MTS) threshold intensities and pulse widths for proximal and distal channels, for both Move and Rest conditions. All intensities in mA, pulse widths in µs.

| Parameter | Default | Description |
|---|---|---|
| `FES_port` | `/dev/ttyUSB0` | Rehamove USB device path |
| `FES_freq` | `30` Hz | Stimulation frequency |
| `I_STS_distMove` | `2.5` mA | Sensory threshold, distal, Move |
| `I_MTS_distMove` | `7.5` mA | Motor threshold, distal, Move |
| `p_*` | `250` µs | Pulse width (all channels) |
| `I_*_Rest` | `0.0` mA | Rest-condition intensities (zeroed by default) |

---

## Marker Codes

All markers are sent via UDP to `127.0.0.1:12345` and bridged to LSL by `UTIL_marker_stream_TESS.py`.

| Code | Event |
|---|---|
| `32766` | Run start / end |
| `768` | Trial start (fixation onset) |
| `769` | Rest cue shown |
| `770` | Move cue shown |
| `1000` | Inter-trial rest period |
| `7691` | Rest task window start |
| `7701` | Move task window start |
| `7692` | Rest task — missed (timeout or wrong class) |
| `7702` | Move task — missed (timeout or wrong class) |
| `7693` | Rest task — correct detection |
| `7703` | Move task — correct detection |
| `1`–`13`, `20` | EOG calibration (fixation=1, dots=10–13, blink=20) |

---

## Usage

### Recommended Startup Order

```bash
# 1. Start the marker bridge (keep running throughout session)
python UTIL_marker_stream_TESS.py

# 2. (Optional) EOG calibration
python a_calibration.py

# 3. Offline FES training
python a1_offline_FES.py <logfile> <hand>

# 4. Start BCI classifier (separate terminal)
python ndf_main_adap.py <args>

# 5. Start online display (waits for READY from classifier)
python a2_online_FES.py <logfile> <hand> <move_threshold_pct> <rest_threshold_pct>
```

### Command-Line Arguments

**`a1_offline_FES.py`** and **`a_calibration.py`**:
```bash
python a1_offline_FES.py logs/sub003_run1.txt left
```

**`a2_online_FES.py`**:
```bash
python a2_online_FES.py logs/sub003_run2.txt left 65 65
# argv[1]: logfile path
# argv[2]: move detection threshold (integer percent, e.g. 65 → 0.65)
# argv[3]: rest detection threshold (integer percent)
```

Thresholds passed on the command line override `detectionThresholdMove/Rest` from `a0_configFile.py`.

---

## Dependencies

```
pygame
pyautogui
pylsl
rehamove
numpy
```

```bash
pip install pygame pyautogui pylsl numpy
```

`rehamove` and `python_client` are hardware-specific packages sourced from the Rehamove vendor SDK.

### Optional Assets
- `harmony_rest.png`, `harmony_move.png` — cue images displayed in the circle during trials; scripts fall back gracefully if not found
- `rest.wav`, `move.wav` — audio cues in `a1_offline_FES.py`; suppressed with a warning if missing

---

## Output Files

Each run appends to a `.txt` log file with all timing parameters, FES intensities, threshold values, and trial outcome counts (`nHitsBCI`, `missedCommands`, `closedCommands`). `a2_online_FES.py` additionally writes a `_probabilities_log.txt` file with per-classification-step `[time, raw_rest, raw_move]` values for offline analysis.

---

## Related

- `ndf_main_adap.py` — online EEG classifier (Riemannian MDM, adaptive recentering, pyriemann)
- `tess_visualize.py` — ERD/ERS visualization for post-session analysis
- SEP/PPD folder — somatosensory evoked potential and paired-pulse depression paradigms
