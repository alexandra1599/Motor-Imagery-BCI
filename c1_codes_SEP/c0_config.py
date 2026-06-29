import random
import numpy as np
import sys
from itertools import repeat 
import numpy as np
# TIMING CONSTANTS:
# ***************20
ExperimentConfigureTime=0.5
restTime=2 # + - random(0-1)

inhibitionRestTime = 2 # in minutes

FES_freq = 30 	 # should be 30 Hz (Hertz)
FES_channel = 'red' # which channel to use

PPD_IPI = 100 # in milliseconds (msec)
repetitions = 25 # per modality

n_SEP = repetitions
n_PPD = repetitions

SEP_array = list(repeat(1, n_SEP))
PPD_array = list(repeat(2, n_PPD)) 
total = len(SEP_array) + len(PPD_array)
trials = np.zeros(total)
all_arrays = SEP_array + PPD_array

for i in range(0, total, 1):
    trials[i] = random.sample(all_arrays, 1)[0]
    all_arrays.remove(trials[i])

FES_pulseWidth = 200 # in microseconds (usec)

# do not change any line beneath this point
FES_port  = '/dev/ttyUSB0' 
pulseWidth = 200
sensoryIntensity = -6.0
motorIntensity = 5.0
