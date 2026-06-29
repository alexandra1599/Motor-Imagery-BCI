# SEP / PPD Stimulation Paradigms

Pygame-based FES (Functional Electrical Stimulation) delivery scripts for eliciting **Somatosensory Evoked Potentials (SEPs)** and **Paired-Pulse Depression (PPD)** in the context of the TESS Motor Imagery BCI system. All scripts interface with the **Rehamove** stimulator over USB and emit event markers via UDP for EEG synchronization.

---

## Repository Structure

```
.
├── c0_config.py        # Shared configuration: timing, FES params, trial randomization
├── a1_SEP.py           # SEP-only paradigm (single pulses)
├── a1_PPD.py           # PPD-only paradigm (paired pulses)
├── a1_SEP_PPD.py       # Combined SEP + PPD paradigm (interleaved, randomized)
└── a2_Fwave.py         # F-wave paradigm (single pulses, separate config)
```

---

## Paradigm Overview

### SEP (`a1_SEP.py`)
Delivers **single FES pulses** at sensory intensity to evoke cortical somatosensory responses. Marker `101` is sent via UDP and LSL on each pulse. Inter-stimulus interval: `restTime + U(0, 0.5)` s (jittered).

### PPD (`a1_PPD.py`)
Delivers **paired FES pulses** separated by `PPD_IPI` ms to measure paired-pulse depression of the SEP. Markers:
- `201` → first pulse of pair
- `202` → second pulse of pair

Inter-trial interval: `restTime + U(0, 1)` s.

### SEP + PPD Interleaved (`a1_SEP_PPD.py`)
The primary experimental script. Delivers a **randomized sequence** of SEP and PPD trials as defined in `c0_config.py`. Trial types:
- `trials[i] == 1` → SEP: single pulse, marker `101`
- `trials[i] == 2` → PPD: paired pulses, markers `201` + `202` (separated by `PPD_IPI` ms)

Features a **countdown welcome screen** (5 s, spacebar-skippable), fixation cross display, and audio cue (`RestStimulation.wav`).

### F-wave (`a2_Fwave.py`)
Single-pulse paradigm for **F-wave** elicitation. Loads its own config from `a0_config_Fwave` (not included here). Sends marker `101` per pulse. Progress bar displayed during the stimulation loop. Audio cue via `pygame.mixer`.

---

## Marker Codes

All scripts send markers via UDP to `127.0.0.1:12345`. Codes are harmonized across all scripts:

| Code | Variable | Event |
|---|---|---|
| `32766` | `MSG_RUN` | Start / end of run |
| `101` | `MSG_SEP` / `MSG_FWAVE` | SEP single pulse or F-wave pulse |
| `201` | `MSG_PPD_1` | First pulse of PPD pair |
| `202` | `MSG_PPD_2` | Second pulse of PPD pair |

`a1_SEP.py` and `a1_SEP_PPD.py` additionally push markers to an **LSL outlet** (`MarkerStream`, 2-channel float32).

---

## Configuration (`c0_config.py`)

All shared parameters for `a1_SEP.py`, `a1_PPD.py`, and `a1_SEP_PPD.py`:

| Parameter | Default | Description |
|---|---|---|
| `restTime` | `2` s | Base ISI (jitter added at runtime) |
| `FES_freq` | `30` Hz | Stimulation frequency |
| `FES_channel` | `'red'` | Rehamove channel |
| `PPD_IPI` | `100` ms | Inter-pulse interval for PPD pairs |
| `repetitions` | `25` | Trials per condition (SEP and PPD each) |
| `pulseWidth` | `200` µs | FES pulse width |
| `sensoryIntensity` | `-6.0` mA | Sensory-level stimulation amplitude |
| `motorIntensity` | `5.0` mA | Motor-level amplitude (reserved) |
| `FES_port` | `/dev/ttyUSB0` | Rehamove USB device path |

Trial randomization uses `random.sample` without replacement to interleave `n_SEP` single-pulse and `n_PPD` paired-pulse trials into a shuffled `trials` array. This runs at import time and is fixed for the duration of one process.

`a2_Fwave.py` uses a separate `a0_config_Fwave.py` with the same parameter conventions.

---

## Dependencies

```
pygame
pyautogui
pylsl
rehamove
python_client   # for Trigger (USB2LPT / ARDUINO)
numpy
```

Install Python deps:
```bash
pip install pygame pyautogui pylsl numpy
```

The `rehamove` and `python_client` packages are hardware-specific and must be sourced from their respective vendor SDKs.

---

## Usage

All scripts take two positional arguments:

```bash
python a1_SEP_PPD.py <logfile_path> <hand>
# e.g.:
python a1_SEP_PPD.py logs/sub001_run1.txt left
```

- `logfile_path`: path to `.txt` log file (opened in append mode)
- `hand`: `left` or `right` (logged for reference)

The script appends all experiment parameters to the log file at the end of each run. Ensure the Rehamove device is connected at `/dev/ttyUSB0` (or update `FES_port` in `c0_config.py`) before launching.

---

## Hardware Trigger Fallback

All scripts attempt hardware trigger initialization in order:
1. `USB2LPT` (parallel port adapter)
2. `ARDUINO` (serial trigger board)  
3. Software-only (UDP/LSL markers only)

The active trigger mode is printed to stdout on startup.

---

## Notes

- The `trials` array in `c0_config.py` is generated at import time — it is fixed per run but re-randomized on each process start.
- Audio cue (`RestStimulation.wav`) uses `pygame.mixer` with a `try/except` fallback in all scripts that play audio.

---

## Related

- `ndf_main_adap.py` — online BCI classifier with Riemannian recentering and FES triggering
- `tess_visualize.py` — ERD/ERS visualization for TESS FES sessions
