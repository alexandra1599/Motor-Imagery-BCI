
# TESS Stimulation Tools

Hardware setup and stimulation delivery scripts for **Transcutaneous Electrical Spinal Stimulation (TESS)** sessions. This folder covers the full pre-session workflow: hardware threshold calibration, device testing, and the main 20-minute TESS protocol with embedded Psychomotor Vigilance Task (PVT).

---

## Repository Structure

```
.
├── config.py             # Master project config (EEG, decoder, networking, gaze — read-only for this folder)
├── a0_configFile.py      # Trial timing, randomization, and FES parameters for BCI sessions
├── a0_configFileSTM.py   # Per-channel FES intensities and pulse widths (simple format)
├── a0_config_TESS.py     # TESS-specific parameters (current, pulse shape, PVT timing)
├── STMsetup.py           # Tkinter GUI for live FES threshold calibration
├── a1_test_TESS.py       # Interactive CLI for testing FES/TESS pulse delivery
└── d1_TESS20min.py       # Main 20-minute TESS protocol with ramp up/down and PVT
```

---

## Typical Session Workflow

```
1. STMsetup.py        → set STS/MTS thresholds per channel, saves to RehamoveConfig_simple.json
2. a1_test_TESS.py    → verify pulse delivery and confirm subjective thresholds
3. d1_TESS20min.py    → run the full 20-minute TESS protocol
```

---

## Script Descriptions

### `STMsetup.py` — Threshold Calibration GUI
A **Tkinter GUI** for calibrating stimulation thresholds before each session. Provides sliders for current (0–30 mA) and pulse width (10–500 µs) for each Rehamove channel, with live test buttons for:

- **STS (Sensory Threshold Stimulation):** individual channels (red, blue, black, white) and paired combinations (red+blue for RH, black+white for LH)
- **MTS (Motor Threshold Stimulation):** same channel combinations
- **Full STS→MTS sequences:** ramps through distal-only → distal+proximal → MTS for each hand

All stimulation bursts are 2 s (STS) or 2 s (MTS) at the currently set frequency (adjustable via slider, default 30 Hz). Clicking **End** saves the calibrated values to `STM_interface/RehamoveConfig_simple.json` for consumption by downstream scripts.

Channel–hand mapping:

| Channel | Color | Hand |
|---|---|---|
| Distal | red | Right Hand (RH) |
| Proximal | blue | Right Hand (RH) |
| Distal | black | Left Hand (LH) |
| Proximal | white | Left Hand (LH) |

### `a1_test_TESS.py` — Interactive Pulse Tester
A command-line tool for verifying Rehamove pulse delivery. Prompts for stimulation type and current on each iteration:

| Option | Description |
|---|---|
| `1` | Single-pulse FES at 30 Hz for 2 s (standard monopolar) |
| `2` | 5 kHz TESS burst (`burst=10` pulses per cycle) with full ramp up → plateau → ramp down |
| `3` | TESS without carrier frequency (`burst=2`, biphasic only) with ramp up/down |
| `4` | Quit |

Ramp duration is `rampTime` seconds (default 5 s); plateau duration is `TESS_dur` minutes (default 1). Useful for subjectively confirming sensation and checking that the ramp produces smooth intensity transitions before the full protocol.

### `d1_TESS20min.py` — 20-Minute TESS Protocol
The main stimulation script. Runs a full TESS session with three phases:

**1. Ramp Up (`rampTime × 60` s)**
Current increases linearly from 0 → `current` mA. Progress bar displayed. Carrier frequency determined by command-line arg (`sys.argv[1]`):
- `0` → 5 kHz TESS (`burst=10` pulses per cycle)
- `1` → No carrier (`burst=2`, biphasic only)

**2. Plateau (20 min, `TESS_dur × 60` s)**
Constant stimulation at full `current`. Concurrently runs an embedded **Psychomotor Vigilance Task (PVT)**:
- Fixation cross displayed
- After a random ISI (`PVT_ISI ± PVT_ISI_var` s), the cross rotates 45° to signal a target
- Subject presses SPACE to respond; RT is measured
- Response window: `PVT_pt + PVT_rt` s total
- Correct response (in time) → green square feedback, marker `101`
- Timeout → red square feedback, marker `201`
- Overall session progress shown as a bottom progress bar

**3. Ramp Down (`rampTime × 60` s)**
Current decreases linearly from `current` → 0 mA.

**Post-stimulation rest:**
- Eyes-open rest for `inhibitionRestTime/2` minutes (marker `20`)
- Eyes-closed rest for `inhibitionRestTime/2` minutes (marker `21`)

---

## Configuration

### `a0_config_TESS.py` — TESS Session Parameters

| Parameter | Default | Description |
|---|---|---|
| `current` | `10` mA | Target stimulation current |
| `pulseWidth` | `100` µs | Half-cycle pulse width (5 kHz → 100 µs, no-carrier → see `a1_test_TESS.py`) |
| `FES_freq` | `30` Hz | Pulse delivery rate |
| `chnName1` | `'red'` | Rehamove channel |
| `rampTime` | `0.5` min | Ramp duration (up and down) |
| `TESS_dur` | `20` min | Plateau stimulation duration |
| `PVT_T` | `20 × 60` s | PVT total time (matches `TESS_dur`) |
| `PVT_ISI` | `30` s | Mean inter-stimulus interval |
| `PVT_ISI_var` | `10` s | ISI jitter (uniform ±) |
| `PVT_pt` | `1` s | Target presentation time |
| `PVT_rt` | `1` s | Response window after presentation |
| `refreshTime` | `0.5` s | Display update interval |
| `FES_port` | `/dev/ttyUSB0` | Rehamove USB device |

### `a0_configFile.py` — BCI Trial Parameters
Used by BCI session scripts (not `d1_TESS20min.py` directly). Defines timing constants, detection thresholds, and trial randomization for LH/RH motor imagery. Also contains the TESS-specific block at the bottom:

| Parameter | Default | Description |
|---|---|---|
| `n_LH_PAS` / `n_RH_PAS` | `35` each | Trials per hand for 20-min PAS protocol |
| `FES_pulseWidth` | `250` µs | Default FES pulse width |
| `current` | `14` mA | PAS stimulation current |
| `rampTime` | `0.5` min | Ramp time |
| `I_STS_RH_min/max` | `4.0` mA | Sensory threshold range, RH |
| `I_MTS_RH` | `6.5` mA | Motor threshold, RH |

> **Note:** The last 13 lines of `a0_configFile.py` (from `FES_freq = 30.000000` onward) are written programmatically by `STMsetup.py` / threshold calibration scripts. Do not add blank lines after them.

### `a0_configFileSTM.py` — Per-Channel FES Parameters
Simple flat file defining distal/proximal STS and MTS intensities and pulse widths for Move and Rest conditions. Consumed by `a2_online_FES.py` and related scripts.

### `config.py` — Master Project Config
Broad project-level configuration covering EEG acquisition, decoder backends, networking, gaze integration, robot control, ErrP pipeline, and display parameters. Most fields are not used by the TESS tools specifically but are imported transitively. **Machine-local overrides** (paths, ports, IP addresses) should be placed in `config_local.py` which is imported at the bottom of `config.py` if it exists.

---

## Marker Codes

All markers sent via UDP to `127.0.0.1:12345` and bridged to LSL by `UTIL_marker_stream_TESS.py`.

| Code | Event |
|---|---|
| `55555` | TESS session start / end |
| `50` | Stimulation ramp-up start |
| `51` | Plateau stimulation start (full current) |
| `52` | Ramp-down start |
| `100` | PVT target stimulus onset |
| `101` | PVT correct response (SPACE pressed in time) |
| `201` | PVT timeout (no response) |
| `20` | Post-stimulation eyes-open rest |
| `21` | Post-stimulation eyes-closed rest |
| `32766` | End of run |

---

## Usage

### Threshold Calibration
```bash
python STMsetup.py
```
Adjust sliders, test each channel, then click **End** to save to `RehamoveConfig_simple.json`.

### Device Test
```bash
python a1_test_TESS.py
```
Interactive prompts — enter stimulation type (1–4) and current (mA) each iteration.

### 20-Minute TESS Protocol
```bash
# With 5 kHz carrier frequency:
python d1_TESS20min.py 0

# Without carrier frequency (biphasic only):
python d1_TESS20min.py 1
```
No log file argument required. Markers are sent to `UTIL_marker_stream_TESS.py` for LSL recording. Ensure the marker bridge is running before starting.

---

## Dependencies

```
pygame
pyautogui
pylsl
rehamove
tkinter      # standard library (STMsetup.py)
numpy
```

```bash
pip install pygame pyautogui pylsl numpy
```

`rehamove` is a vendor SDK package from the Rehamove hardware library.

### Required Assets
- `extension.png` — wrist image used for display scaling in `d1_TESS20min.py`
- `STM_interface/RehamoveConfig_simple.json` — written by `STMsetup.py`, read by downstream BCI scripts
- `UTIL_marker_stream_TESS.py` — must be running as a separate process before any script is launched

---

## Notes

- The command-line arg in `d1_TESS20min.py` (`sys.argv[1]`) is `0` for carrier, `1` for no carrier — this is inverted from the internal `carrier` variable (`carrier = 2 - int(sys.argv[1])`), so passing `0` means "use carrier."
- `STMsetup.py` applies `setserial /dev/ttyUSB0 low_latency` at startup to minimize USB serial latency on Linux.
- The PVT in `d1_TESS20min.py` runs concurrently with stimulation inside the main loop — it shares the same `r.custom_pulse()` call timing, so PVT stimulus timing is subject to the FES cycle period (`1/FES_freq - pulseWidth*burst/1e6` s per iteration).

---

## Related

- `UTIL_marker_stream_TESS.py` — UDP→LSL marker bridge (required, in the online BCI folder)
- `a2_online_FES.py` — online closed-loop BCI display consuming thresholds from `a0_configFileSTM.py`
- `ndf_main_adap.py` — EEG classifier that runs alongside the online session
