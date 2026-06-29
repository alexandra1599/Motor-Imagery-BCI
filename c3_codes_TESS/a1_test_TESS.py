import os
import sys
dirP = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
# #print(dirP + '/4_ref_other')
sys.path.append(os.getcwd() + '/z1_ref_other/0_lib')
sys.path.append(dirP + '/MS_codes/c2_codes_BCI/c2_Visual_interface/1_packages')
sys.path.append(dirP + '/MS_codes/c2_codes_BCI/c2_Visual_interface')
## Packages to import:
import time
sys.path.append(os.getcwd())
from rehamove import *

## LOAD STIMULATION CONFIGURATIONS
FES_freq = 30 	 # should be 30 Hz (Hertz)
chnName1 = 'red' # which channel to use
# 	For stim method 1 (FES):
pulseWidth = 100 	# in microseconds (usec)
# 	For stim method 2 (TESS):
# s1: ~20 mA
# s2: 14 mA
# s3: 
rampTime = 5 # in seconds
TESS_dur = 1 # in minutes
burst = 10
# Note: 50 usec equates to 10 kHz (since whole pulse cycle will be 100 usec)
# 		100 usec equates to 5 kHz (since whole pulse cycle will be 200 usec)

r = Rehamove("/dev/ttyUSB0")    # Open USB port (on Windows)
r.battery()   					# check battery level of device
# r.change_mode(0)                # Change to low-level mode (each pulse sent separately (already default))
while True:
	resp = int(input("Which stim type do you want to test, \n[1] Single-pulse FES every 30Hz or \n[2] 5kHz TESS pulses every 30Hz or \n[3] no 5kHz TESS pulses every 30Hz or \n[4] end this program?\nResponse: "))
	current = int(input("current (mA): "))
	pulsearray = []
	for i in range(10):
		if (i % 2) == 0: # even
			pulsearray.append([current, pulseWidth])
		else:            # odd
			pulsearray.append([-current, pulseWidth])

	if resp == 1:
		prevTime = time.time() 
		while (time.time() - prevTime)<=2: # test stimulation for 30 seconds
			r.pulse(chnName1, current , int(pulseWidth)) # Send a single pulse
			time.sleep(1/FES_freq) # pause pulse based on stimulation frequency

	elif resp == 2:
		prevTime = time.time()
		while (time.time() - prevTime)<=rampTime: # test stimulation for 30 seconds
			# pulseNew = np.transpose(np.array([pulsearray[:,0]*,pulsearray[:,1]]))
			# pulseNew = pulseNew.astype(int)
			# pulseNew = [list(pulseNew[i].astype(int)) for i in range(len(pulseNew))]
			# print(pulseNew)

			curr = current*(time.time() - prevTime)/(rampTime)	   	# in miiliamperes (mA)
			pulseNew = []
			for i in range(burst):
				if (i % 2) == 0: # even
					pulseNew.append([curr, pulseWidth])
				else:            # odd
					pulseNew.append([-curr, pulseWidth])
			print(pulseNew[0][0])
			r.custom_pulse(chnName1, pulseNew)
			time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency

		curr = current 	# in miiliamperes (mA)
		pulseNew = []
		for i in range(burst):
			if (i % 2) == 0: # even
				pulseNew.append([curr, pulseWidth])
			else:            # odd
				pulseNew.append([-curr, pulseWidth])

		print(pulseNew)
		prevTime = time.time()
		while (time.time() - prevTime)<=TESS_dur*60: # test stimulation for 30 seconds
			r.custom_pulse(chnName1, pulseNew)
			time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency

		prevTime = time.time()
		while (time.time() - prevTime)<=rampTime: # test stimulation for 30 seconds
			curr = current*(1-(time.time() - prevTime)/(rampTime))	   	# in miiliamperes (mA)
			pulseNew = []
			for i in range(burst):
				if (i % 2) == 0: # even
					pulseNew.append([curr, pulseWidth])
				else:            # odd
					pulseNew.append([-curr, pulseWidth])

			# pulseNew = np.transpose(np.array(pulsearray[:,0]*(1-(time.time() - prevTime)/(rampTime*60)),pulsearray[:,1]))
			print(pulseNew[0][0])
			r.custom_pulse(chnName1, pulseNew)
			time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency

	elif resp == 3:
		prevTime = time.time()
		while (time.time() - prevTime)<=rampTime: # test stimulation for 30 seconds
			# pulseNew = np.transpose(np.array([pulsearray[:,0]*,pulsearray[:,1]]))
			# pulseNew = pulseNew.astype(int)
			# pulseNew = [list(pulseNew[i].astype(int)) for i in range(len(pulseNew))]
			# print(pulseNew)

			curr = current*(time.time() - prevTime)/(rampTime)	   	# in miiliamperes (mA)
			pulseNew = []
			for i in range(2):
				if (i % 2) == 0: # even
					pulseNew.append([curr, pulseWidth])
				else:            # odd
					pulseNew.append([-curr, pulseWidth])
			print(pulseNew[0][0])
			r.custom_pulse(chnName1, pulseNew)
			time.sleep(1/FES_freq-pulseWidth*2/1000/1000) # pause pulses based on stimulation frequency

		curr = current 	# in miiliamperes (mA)
		pulseNew = []
		for i in range(2):
			if (i % 2) == 0: # even
				pulseNew.append([curr, pulseWidth])
			else:            # odd
				pulseNew.append([-curr, pulseWidth])

		print(pulseNew)
		prevTime = time.time()
		while (time.time() - prevTime)<=TESS_dur*60: # test stimulation for 30 seconds
			r.custom_pulse(chnName1, pulseNew)
			time.sleep(1/FES_freq-pulseWidth*2/1000/1000) # pause pulses based on stimulation frequency
		
		prevTime = time.time()
		while (time.time() - prevTime)<=rampTime: # test stimulation for 30 seconds
			curr = current*(1-(time.time() - prevTime)/(rampTime))	   	# in miiliamperes (mA)
			pulseNew = []
			for i in range(2):
				if (i % 2) == 0: # even
					pulseNew.append([curr, pulseWidth])
				else:            # odd
					pulseNew.append([-curr, pulseWidth])

			# pulseNew = np.transpose(np.array(pulsearray[:,0]*(1-(time.time() - prevTime)/(rampTime*60)),pulsearray[:,1]))
			print(pulseNew[0][0])
			r.custom_pulse(chnName1, pulseNew)
			time.sleep(1/FES_freq-pulseWidth*2/1000/1000) # pause pulses based on stimulation frequency

	elif resp == 4:
		print('Quitting program')
		break 
			
