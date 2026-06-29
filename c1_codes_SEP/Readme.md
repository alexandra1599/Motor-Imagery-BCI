
# SEP / PPD Stimulation Paradigms

Pygame-based FES (Functional Electrical Stimulation) delivery scripts for eliciting **Somatosensory Evoked Potentials (SEPs)** and **Paired-Pulse Depression (PPD)** in the context of the TESS Motor Imagery BCI system. All scripts interface with the **Rehamove** stimulator over USB and emit event markers for EEG synchronization.

---

## Repository Structure

```
.
├── c0_config.py        # Shared configuration: timing, FES params, trial randomization
├── a1_SEP.py           # SEP-only paradigm (single pulses, LSL + UDP markers)
├── a1_PPD.py           # PPD-only paradigm (paired pulses, TiD/cnbiloop markers)
├── a1_SEP_PPD.py       # Combined SEP + PPD paradigm (interleaved, randomized)
└── a2_Fwave.py         # F-wave paradigm (single pulses, TiD markers, audio cue)
```

---

## Paradigm Overview

### SEP (`a1_SEP.py`)
Delivers **single FES pulses** at sensory intensity to evoke cortical somatosensory responses. Each pulse is timestamped via:
- **UDP socket** → marker code `101` sent to `127.0.0.1:12345`
- **LSL outlet** (`MarkerStream`, 2-channel float32)
- Optional **hardware trigger** via USB2LPT

Inter-stimulus interval: `restTime + U(0, 0.5)` seconds (jittered).

### PPD (`a1_PPD.py`)
Delivers **paired FES pulses** separated by `PPD_IPI` ms to measure **paired-pulse depression** of the SEP. Markers:
- `101` → first pulse of pair
- `201` → second pulse of pair

Marker delivery via **TiD/cnbiloop** (`sendTiD`) and optional hardware trigger. Inter-trial interval: `restTime + U(0, 1)` s.

### SEP + PPD Interleaved (`a1_SEP_PPD.py`)
The primary experimental script. Delivers a **randomized sequence** of SEP (single) and PPD (paired) trials as defined in `c0_config.py`. Trial types:
- `trials[i] == 1` → SEP: single pulse, marker `101`
- `trials[i] == 2` → PPD: paired pulses, markers `201` + `202` (separated by `PPD_IPI` ms)

Features a **countdown welcome screen** (5 s, spacebar-skippable), fixation cross display, audio cue (`RestStimulation.wav`), and fallback from USB2LPT → ARDUINO trigger. Markers via UDP + LSL.

### F-wave (`a2_Fwave.py`)
Single-pulse paradigm optimized for **F-wave** elicitation (supramaximal motor stimulation). Uses `playsound` for audio cueing and TiD/cnbiloop markers. Loads its own config from `a0_config_Fwave` (not included here). Progress bar displayed during stimulation loop.

---

## Configuration (`c0_config.py`)

All shared parameters are centralized here. Key values:

| Parameter | Default | Description |
|---|---|---|
| `restTime` | `2` s | Base ISI (jitter added at runtime) |
| `FES_freq` | `30` Hz | Stimulation frequency |
| `FES_channel` | `'red'` | Rehamove channel |
| `PPD_IPI` | `100` ms | Inter-pulse interval for PPD pairs |
| `repetitions` | `25` | Trials per condition (SEP and PPD each) |
| `pulseWidth` | `200` µs | FES pulse width |
| `sensoryIntensity` | `-6.0` mA | Sensory-level stimulation amplitude |
| `motorIntensity` | `5.0` mA | Motor-level stimulation amplitude (reserved) |
| `FES_port` | `/dev/ttyUSB0` | Rehamove USB device path |

Trial randomization in `c0_config.py` uses `random.sample` without replacement to interleave `n_SEP` single-pulse and `n_PPD` paired-pulse trials into a shuffled `trials` array.

---

## Marker Codes

| Code | Event |
|---|---|
| `32766` | Start / end of run |
| `101` | SEP pulse (single) OR first pulse of PPD pair |
| `201` | Second pulse of PPD pair (`a1_PPD.py`) / SEP pulse (`a1_SEP.py` — *note: see bug below*) |
| `202` | Second pulse of PPD pair (`a1_SEP_PPD.py`) |

---

## Dependencies

```
pygame
pyautogui
pylsl
rehamove
python_client   # for Trigger (USB2LPT / ARDUINO)
cnbiloop        # for TiD-based marker streaming (a1_PPD.py, a2_Fwave.py)
playsound       # a2_Fwave.py only
numpy
```

Install Python deps:
```bash
pip install pygame pyautogui pylsl numpy
```

The `rehamove`, `cnbiloop`, `python_client`, and `serialCommunication` packages are hardware-specific and must be sourced from their respective vendor SDKs.

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

The script appends experiment parameters to the log file at the end of each run.

Ensure the Rehamove device is connected at `/dev/ttyUSB0` (or update `FES_port` in `c0_config.py`) before launching.

---

## Hardware Trigger Fallback

All scripts attempt hardware trigger initialization in order:
1. `USB2LPT` (parallel port adapter)
2. `ARDUINO` (serial trigger board)
3. Software-only (no hardware trigger, markers via LSL/UDP/TiD only)

The active trigger mode is printed to stdout on startup.

---

## Known Issues / Notes

- `a1_SEP.py` contains a reference to `sendTiD(101)` which is undefined in that script (it uses UDP/LSL, not cnbiloop). This line should be replaced with the appropriate `send_udp_message(...)` call or removed.
- `a1_PPD.py` imports `serial` and `serialCommunication` but does not appear to use them; these can likely be removed.
- The `trials` array in `c0_config.py` is generated at import time, meaning it is fixed for the duration of one run but regenerated on each process start.
- Audio cue (`RestStimulation.wav`) in `a1_SEP_PPD.py` uses `pygame.mixer` with a `try/except` fallback; in `a2_Fwave.py` it uses `playsound` with no fallback.

---

## Related

- `ndf_main_adap.py` — online BCI classifier with Riemannian recentering and FES triggering
- `tess_visualize.py` — ERD/ERS visualization for TESS FES sessions
