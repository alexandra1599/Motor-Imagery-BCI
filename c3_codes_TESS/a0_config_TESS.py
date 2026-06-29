current = int('10') 
checkMark=0
FES_freq = 30 	 # should be 30 Hz (Hertz)
chnName1 = 'red' # which channel to use
rampTime = 0.5 # in minutes (duration to ramp up and down with TESS)
TESS_dur = 20 # in minutes
# 	For stim method 1 (FES):
PVT_T = 20*60 # minutes * seconds
PVT_ISI = 30
PVT_ISI_var = 10
PVT_pt = 1
PVT_rt = 1
refreshTime = 0.5
tempCarrier = 1

import numpy as np

pulseWidth = 100 	# in microseconds (usec)
pulsearray = []
for i in range(10):
	if (i % 2) == 0: # even
		pulsearray.append([current, pulseWidth])
	else:            # odd
		pulsearray.append([-current, pulseWidth])

pulsearray = np.array(pulsearray)
print(pulsearray)

FES_port  = '/dev/ttyUSB0'
