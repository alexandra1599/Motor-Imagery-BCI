"""
config_tess.py
==============
Configuration for the TESS online BCI pipeline.
Mirrors the structure of the Robot+FES config.py so that
ndf_main_adap.py and a2_online_FES.py share the same values.

*** CHANGE THESE EACH SESSION ***
"""

# =============================================================================
# Subject / session
# =============================================================================
TRAINING_SUBJECT = 3      # subject ID (integer)

# =============================================================================
# EEG acquisition
# =============================================================================
FS              = 512      # sampling rate (Hz)
CLASSIFY_WINDOW = 1000     # classification window length (ms)
STEP_SIZE       = 1 / 16  # classification step size (seconds) = 62.5 ms

# =============================================================================
# Classification thresholds
# These mirror THRESHOLD_MI / THRESHOLD_REST in the Robot+FES config.
# P(MOVE) >= THRESHOLD_MI  → Move detected
# P(REST) >= THRESHOLD_REST → Rest detected  (i.e. P(MOVE) <= 1 - THRESHOLD_REST)
# Expressed as probabilities in [0, 1].
# =============================================================================
THRESHOLD_MI   = 0.60   # P(MOVE) must reach this to trigger Move result
THRESHOLD_REST = 0.60   # P(REST) must reach this to trigger Rest result

# =============================================================================
# Display fill scaling
# The leaky-integrated probability is mapped from [SHAPE_MIN, SHAPE_MAX]
# to display fill [0, 1].  Values outside this range clamp to 0 or 1.
# Set SHAPE_MIN = 0.5 and SHAPE_MAX = 1.0 to use the full range above chance.
# =============================================================================
SHAPE_MIN = 0.450   # probability at which bar/circle starts filling
SHAPE_MAX = 1.00   # probability at which bar/circle is completely full

# =============================================================================
# Leaky integrator
# Higher alpha = smoother but slower response.
# Lower alpha = faster but noisier.
# =============================================================================
INTEGRATOR_ALPHA = 0.85   # equivalent to UPDATE_RATE in old pipeline

# =============================================================================
# Early stopping
# Trial ends early when running_avg_confidence >= THRESHOLD after at least
# MIN_PREDICTIONS classifications have been made.
# =============================================================================
MIN_PREDICTIONS = 5   # minimum classifications before early stop is allowed

# =============================================================================
# Baseline
# Duration (seconds) of the fixation period used to compute per-channel
# baseline mean that is subtracted from each classification window.
# =============================================================================
BASELINE_DURATION = 2.0   # seconds of fixation EEG to use as baseline

# =============================================================================
# Adaptive recentering
# =============================================================================
RECENTERING         = True   # enable online adaptive recentering
UPDATE_DURING_TRIAL = True   # update reference during trials (not just between)

# =============================================================================
# EOG
# =============================================================================
THRESHOLD_EOG = float('inf')   # inf = accept all (EOG gating disabled)

# =============================================================================
# FES
# =============================================================================
FES_toggle = 1   # 1 = enabled, 0 = disabled

# =============================================================================
# Colours (RGB) — used by a2_online_FES.py display
# =============================================================================
black  = (0,   0,   0)
white  = (225, 225, 225)
red    = (134, 0,   0)
green  = (5,   170, 5)
orange = (255, 165, 0)
blue   = (0,   0,   200)
