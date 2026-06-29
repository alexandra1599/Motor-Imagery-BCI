#	python3 a1_STMsetupMwave.py $subID $mode $sessionID $recID


from c0_config import *
from tkinter import *
import tkinter as tk

from datetime import datetime
# ## LOOP + Serial Comm Packages
import serial
import os
from pathlib import Path
dirP = os.path.abspath(os.getcwd())
dirP = dirP.split('/')
dirP = '/'.join(dirP[0:-1])

print(dirP)
# #print(dirP + '/4_ref_other')
sys.path.append(dirP + '/z1_ref_other/0_lib')
import cnbiloop
from cnbiloop import BCI, BCI_tid

sys.path.append(dirP + '/c1_codes/1_packages')
sys.path.append(dirP + '/c1_codes/1_packages/rehamoveLibrary')
from serialCommunication import SerialWriter

## Other Packages:
import pygame
import sys
import time
import random
from pygame.locals import *
import pyautogui
import numpy as np
from python_client import Trigger

import os
os.system("setserial /dev/ttyUSB1 low_latency")
os.system("setserial /dev/ttyUSB0 low_latency")
## LOAD CONFIGURATIONS FOR THE TASK 

## FES1 Rehamove Library
sys.path.append(dirP + '/rehamoveLibrary')
from rehamove import *          # Import our library
import time
import math 

FES_portNum = int(sys.argv[1])
FES_port = '/dev/ttyUSB' + str(FES_portNum)



bci = BCI_tid.BciInterface()

def sendTiD(Event_):
#    pass
	bci.id_msg_bus.SetEvent(Event_)
	bci.iDsock_bus.sendall(str.encode(bci.id_serializer_bus.Serialize()))
def receiveTiD():
    #pass
	data = None
	try:
		data = bci.iDsock_bus.recv(512).decode("utf-8")
		bci.idStreamer_bus.Append(data)
	except:
		nS = False
		dec = 0
		pass
	# deserialize ID message
	if (data):
		if (bci.idStreamer_bus.Has("<tobiid", "/>")):
			msg = bci.idStreamer_bus.Extract("<tobiid", "/>")
			bci.id_serializer_bus.Deserialize(msg)
			bci.idStreamer_bus.Clear()
			tmpmsg = int(round(float(bci.id_msg_bus.GetEvent())))
			# print("Received Message: ", tmpmsg)
			return tmpmsg

		elif bci.idStreamer_bus.Has("<tcstatus","/>"):
			MsgNum = bci.idStreamer_bus.Count("<tcstatus")
			for i in range(1,MsgNum-1):
				# Extract most of these messages and trash them
				msg_useless = bci.idStreamer_bus.Extract("<tcstatus","/>")


try:
	parallel = Trigger('USB2LPT') # if using hardware triggers through the arduino board, use 'ARDUINO'
	parallel.init(100)
	hardwareTrigger =1 	
except:
	hardwareTrigger =0 

if hardwareTrigger ==0: 
	try:
		parallel = Trigger('ARDUINO') # if using hardware triggers through the arduino board, use 'ARDUINO'
		parallel.init(100)
		hardwareTrigger =1 	
	except:
		hardwareTrigger =0 


print('Using Hardware Trigger=' + str(hardwareTrigger))
time.sleep(2)

FES1_port = FES_port


distalChannel_RH = 'red'
proximalChannel_RH = 'blue'
distalChannel_LH = 'black'
proximalChannel_LH = 'white'

#  NOTES:
# ********
# Class (+1): extension
# Class (-1): flexion

####################
## IMPORTANT NOTE ##
####################
# the following 17 lines must be the last 17 lines in this file!
# Not eeven empty lines shall be after them becasue another script reads the last 16 lines and modifies them based on the STM setup thresholds
FES_freq = 30.000000
I_STS_distRH = 6.500000
I_STS_proxRH = 6.000000
I_MTS_distRH = 10.00000
I_MTS_proxRH = 10.000000
I_STS_proxLH = 6.000000
I_STS_distLH = 5.500000
I_MTS_proxLH = 8.500000
I_MTS_distLH = 9.000000
p_STS_distRH = 200.000000
p_STS_proxRH = 200.000000
p_MTS_distRH = 200.000000
p_MTS_proxRH = 200.000000
p_STS_proxLH = 200.000000
p_STS_distLH = 200.000000
p_MTS_proxLH = 200.000000
p_MTS_distLH = 200.000000

FES1 = Rehamove(FES1_port)    # Open USB port (on Windows)

now = datetime.now()
date_time = now.strftime("%m_%d_%Y__%H_%M_%S")


# print(filename)

# f=open(filename, "a+")
# f.write("Stimulation Settings:\n")
# f.write("---------------------\n")

root = Tk()
root.title("Hands Stimulation")

RH_stsRed_i = DoubleVar()
LH_stsBlack_i = DoubleVar()
RH_stsBlue_i = DoubleVar()
LH_stsWhite_i = DoubleVar()
RH_stsRed_p = DoubleVar()
LH_stsBlack_p = DoubleVar()
RH_stsBlue_p = DoubleVar()
LH_stsWhite_p = DoubleVar()
RH_mtsRed_i = DoubleVar()
LH_mtsBlack_i = DoubleVar()
RH_mtsBlue_i = DoubleVar()
LH_mtsWhite_i = DoubleVar()
RH_mtsRed_p = DoubleVar()
LH_mtsBlack_p = DoubleVar()
RH_mtsBlue_p = DoubleVar()
LH_mtsWhite_p = DoubleVar()
freq = DoubleVar()

stsTime = 0.2;
mtsTime = 0.2;

global FES1_freq 
FES1_freq = 1

trialCnt = 0
trialCntS = 0
trialCntM = 0

def RH_LH_freqChange():
	global FES1_freq
	FES1_freq = int(freq.get())


## Sensory

def RH_LH_stsRed():
	global trialCntS
	trialCntS = trialCntS+1
	RH_LH_freqChange()
	prevTime=time.time() 
	pulsearray = []
	for i in range(2):
		if (i % 2) == 0: # even
			pulsearray.append([-RH_stsRed_i.get(), int(RH_stsRed_p.get())])
		else:            # odd
			pulsearray.append([0, int(RH_stsRed_p.get())])		

	print(pulsearray)
	FES1.custom_pulse('red', pulsearray)
	# f.write("Sensory trialCnt = %f\t" % (trialCntS))
	# f.write("pulseWidth = %f\t" % (int(RH_stsRed_p.get())))
	# f.write("current = %f mA\n" % (-RH_stsRed_i.get()))
	if hardwareTrigger:
		parallel.signal(101)
	sendTiD(101) 

def RH_LH_stsBlack():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('black',LH_stsBlack_i.get(), int(LH_stsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_stsBlue():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('blue',RH_stsBlue_i.get(), int(RH_stsBlue_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_stsWhite():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('white',LH_stsWhite_i.get(), int(LH_stsWhite_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_stsRedBlue():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('red',RH_stsRed_i.get(), int(RH_stsRed_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('blue',RH_stsBlue_i.get(), int(RH_stsBlue_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_stsBlackWhite():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('black',LH_stsBlack_i.get(), int(LH_stsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('white',LH_stsWhite_i.get(), int(LH_stsWhite_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

## Motor

def RH_LH_mtsRed():
	global trialCntM
	trialCntM = trialCntM+1
	RH_LH_freqChange()
	prevTime=time.time() 
	pulsearray = []
	for i in range(2):
		if (i % 2) == 0: # even
			pulsearray.append([RH_mtsRed_i.get(), int(RH_mtsRed_p.get())])
		else:            # odd
			pulsearray.append([0, int(RH_mtsRed_p.get())])		

	print(pulsearray)
	FES1.custom_pulse('red', pulsearray)
	# f.write("Motor trialCnt = %f\t" % (trialCntM))
	# f.write("pulseWidth = %f\t" % (int(RH_mtsRed_p.get())))
	# f.write("current = %f mA\n" % (RH_mtsRed_i.get()))
	if hardwareTrigger:
		parallel.signal(100)
	sendTiD(100) 

def RH_LH_mtsBlack():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=mtsTime:
		FES1.pulse('black',LH_mtsBlack_i.get(), int(LH_mtsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_mtsBlue():
	global trialCnt
	trialCnt = trialCnt+1
	RH_LH_freqChange()
	prevTime=time.time() 
	pulsearray = []
	for i in range(2):
		if (i % 2) == 0: # even
			pulsearray.append([RH_mtsBlue_i.get(), int(RH_mtsBlue_p.get())])
		else:            # odd
			# aasd = 0
			pulsearray.append([0, int(RH_mtsBlue_p.get())])		
	print(pulsearray)
	FES1.custom_pulse('blue', pulsearray)
	# f.write("trialCnt = %f\t" % (trialCnt))
	# f.write("current = %f mA\n" % (RH_mtsBlue_i.get()))
	if hardwareTrigger:
		parallel.signal(200)
	sendTiD(200)  # send Event CUE: 32766 to LOOP to indicate start of the run
	# while (time.time() - prevTime)<=mtsTime:
	# 	FES1.pulse('blue',RH_mtsBlue_i.get(), int(RH_mtsBlue_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
	# 	time.sleep(1/FES1_freq)

def RH_LH_mtsWhite():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=mtsTime:
		FES1.pulse('white',LH_mtsWhite_i.get(), int(LH_mtsWhite_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_mtsRedBlue():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=mtsTime:
		FES1.pulse('red',RH_mtsRed_i.get(), int(RH_mtsRed_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('blue',RH_mtsBlue_i.get(), int(RH_mtsBlue_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_mtsBlackWhite():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=mtsTime:
		FES1.pulse('black',LH_mtsBlack_i.get(), int(LH_mtsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('white',LH_mtsWhite_i.get(), int(LH_mtsWhite_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

# Full Sequence STS/MTS

def RH_LH_redBlueseq():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('red',RH_stsRed_i.get(), int(RH_stsRed_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('red',RH_stsRed_i.get(), int(RH_stsRed_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('blue',RH_stsBlue_i.get(), int(RH_stsBlue_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)		
	prevTime=time.time() 
	while (time.time() - prevTime)<=mtsTime:
		FES1.pulse('red',RH_mtsRed_i.get(), int(RH_mtsRed_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('blue',RH_mtsBlue_i.get(), int(RH_mtsBlue_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def RH_LH_blackWhiteseq():
	RH_LH_freqChange()
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('black',LH_stsBlack_i.get(), int(LH_stsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)
	prevTime=time.time() 
	while (time.time() - prevTime)<=stsTime:
		FES1.pulse('black',LH_stsBlack_i.get(), int(LH_stsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('white',LH_stsWhite_i.get(), int(LH_stsWhite_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)	
	prevTime=time.time() 
	while (time.time() - prevTime)<=mtsTime:
		FES1.pulse('black',LH_mtsBlack_i.get(), int(LH_mtsBlack_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		FES1.pulse('white',LH_mtsWhite_i.get(), int(LH_mtsWhite_p.get())) # 3 250+int(((t_passed - t_init)/STS_duration[0])*250)
		time.sleep(1/FES1_freq)

def updateRedIntensityM(values):
	# print(RH_stsRed_i.get())
	round((RH_stsRed_i.get() * 2) / 2)
	RH_mtsRed_i.set(round(((RH_stsRed_i.get()/1.2) * 2) / 2))
	RH_mtsRed_p.set(RH_stsRed_p.get())

def updateRedIntensityS(values):
	RH_stsRed_i.set(round((1.2*RH_mtsRed_i.get() * 2) / 2))
	RH_stsRed_p.set(RH_mtsRed_p.get())
	# print(RH_mtsRed_i.get())

def endSetup():
	sendTiD(32766)  # send Event CUE: 32766 to LOOP to indicate start of the run
	if hardwareTrigger:
		parallel.signal(255)
	
	# write into the c0_config file
	with open("c0_config.py") as f1:
		lines = f1.readlines()
	f1.close()
	with open("c0_config.py", 'w') as f2:
		f2.writelines(lines[:-4])
	f2.close()

	f2=open("c0_config.py", "a+")
	f2.write("FES_port  = '%s' \n" % (FES_port))
	f2.write("pulseWidth = %i\n" % (RH_stsRed_p.get()))
	f2.write("sensoryIntensity = %.1f\n" % (-RH_stsRed_i.get()))
	f2.write("motorIntensity = %.1f\n" % (RH_mtsRed_i.get()))
	f2.close()
	sys.exit()


###########################################################################################################
#### SENSORY-THRESHOLD ####
###########################
tempL = Label(root, text="Stimulation Frequency").grid(row = 0, column = 0)
freqSlider = Scale( root, variable = freq , from_ = 1, to = 500, length = 300, resolution = 1, orient = HORIZONTAL)
freqSlider.set(30)
freqSlider.grid(row = 0,column=1)

shiftCol = 2;

fspace = tk.Frame(root)
tempL = Label(fspace)
fspace.grid(row = shiftCol +0,column=1, sticky="nsew")
tempL.pack(pady = 20)

tempL = Label(root, text="Sensory-Threshold Stimulation").grid(row = shiftCol + 0, column = 0)
current = Label(root, text = 'Current').grid(row = shiftCol + 0, column = 1)
pulseWidth = Label(root, text = 'Pulse Width').grid(row = shiftCol + 0, column = 2)


buttonReds = Button(root, text = " STS @ red (RH)", command = RH_LH_stsRed).grid(row = shiftCol +1,column=0)
redChannel_sts_i = Scale( root, variable = RH_stsRed_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL, command = updateRedIntensityM).grid(row = shiftCol + 1,column=1)
redChannel_sts_p = Scale( root, variable = RH_stsRed_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL, command = updateRedIntensityM)
redChannel_sts_p.set(FES_pulseWidth)
redChannel_sts_p.grid(row = shiftCol +1,column=2)
buttonBlues = Button(root, text = "STS @ blue (RH)", command = RH_LH_stsBlue).grid(row = shiftCol +2,column=0)
blueChannel_sts_i = Scale( root, variable = RH_stsBlue_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL).grid(row = shiftCol +2,column=1)
blueChannel_sts_p = Scale( root, variable = RH_stsBlue_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL)
blueChannel_sts_p.set(FES_pulseWidth)
blueChannel_sts_p.grid(row = shiftCol +2,column=2)

f1 = tk.Frame(root)
buttonRedBlues = Button(f1, text = "STS @ red & blue", command = RH_LH_stsRedBlue)
f1.grid(row = shiftCol +3,column=1, sticky="nsew")
buttonRedBlues.pack(anchor = CENTER)

buttonBlacks = Button(root, text = "STS @ black (LH) ", command = RH_LH_stsBlack).grid(row = shiftCol +4,column=0)
blackChannel_sts_i = Scale( root, variable = LH_stsBlack_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL).grid(row = shiftCol +4,column=1)
blackChannel_sts_p = Scale( root, variable = LH_stsBlack_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL)
blackChannel_sts_p.set(FES_pulseWidth)
blackChannel_sts_p.grid(row = shiftCol +4,column=2)
buttonWhites = Button(root, text = "STS @ white (LH)", command = RH_LH_stsWhite).grid(row = shiftCol +5,column=0)
whiteChannel_sts_i = Scale( root, variable = LH_stsWhite_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL).grid(row = shiftCol +5,column=1)
whiteChannel_sts_p = Scale( root, variable = LH_stsWhite_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL)
whiteChannel_sts_p.set(FES_pulseWidth)
whiteChannel_sts_p.grid(row = shiftCol +5,column=2)

f2 = tk.Frame(root)
buttonBlackWhites = Button(f2, text = "STS @ black & white", command = RH_LH_stsBlackWhite)
f2.grid(row = shiftCol +6,column=1, sticky="nsew")
buttonBlackWhites.pack(anchor = CENTER)

fspace = tk.Frame(root)
tempL = Label(fspace)
fspace.grid(row = shiftCol +8,column=1, sticky="nsew")
tempL.pack(pady = 20)

###########################################################################################################
#### MOTOR-THRESHOLD ####
#########################

fspace = tk.Frame(root)
tempL = Label(fspace)
fspace.grid(row = shiftCol +10,column=1, sticky="nsew")
tempL.pack(pady = 20)

tempL = Label(root, text="Motor-Threshold Stimulation").grid(row = shiftCol + 10, column = 0)
current = Label(root, text = 'Current').grid(row = shiftCol + 10, column = 1)
pulseWidth = Label(root, text = 'Pulse Width').grid(row = shiftCol + 10, column = 2)


buttonRedm = Button(root, text = " MTS @ red (RH)", command = RH_LH_mtsRed).grid(row = shiftCol +11,column=0)
redChannel_mts_i = Scale( root, variable = RH_mtsRed_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL, command = updateRedIntensityS).grid(row = shiftCol +11,column=1)
redChannel_mts_p = Scale( root, variable = RH_mtsRed_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL, command = updateRedIntensityS)
redChannel_mts_p.set(FES_pulseWidth)
redChannel_mts_p.grid(row = shiftCol +11,column=2)

buttonBlackm = Button(root, text = "MTS @ blue (RH)", command = RH_LH_mtsBlue).grid(row = shiftCol +12,column=0)
blueChannel_mts_i = Scale( root, variable = RH_mtsBlue_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL).grid(row = shiftCol +12,column=1)
blueChannel_mts_p = Scale( root, variable = RH_mtsBlue_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL)
blueChannel_mts_p.set(FES_pulseWidth)
blueChannel_mts_p.grid(row = shiftCol +12,column=2)


f1 = tk.Frame(root)
buttonRedBluem = Button(f1, text = "MTS @ red & blue", command = RH_LH_mtsRedBlue)
f1.grid(row = shiftCol +13,column=1, sticky="nsew")
buttonRedBluem.pack(anchor = CENTER)

buttonBlackm = Button(root, text = "MTS @ black (LH)", command = RH_LH_mtsBlack).grid(row = shiftCol +14,column=0)
blackChannel_mts_i = Scale( root, variable = LH_mtsBlack_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL).grid(row = shiftCol +14,column=1)
blackChannel_mts_p = Scale( root, variable = LH_mtsBlack_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL)
blackChannel_mts_p.set(FES_pulseWidth)
blackChannel_mts_p.grid(row = shiftCol +14,column=2)

buttonWhitem = Button(root, text = "MTS @ white (LH)", command = RH_LH_stsWhite).grid(row = shiftCol +15,column=0)
whiteChannel_mts_i = Scale( root, variable = LH_mtsWhite_i , from_ = 0, to = 30, length = 300, resolution = 0.5, orient = HORIZONTAL).grid(row = shiftCol +15,column=1)
whiteChannel_mts_p = Scale( root, variable = LH_mtsWhite_p , from_ = 1, to = 500, length = 600, resolution = 1, orient = HORIZONTAL)
whiteChannel_mts_p.set(FES_pulseWidth)
whiteChannel_mts_p.grid(row = shiftCol +15,column=2)


f2 = tk.Frame(root)
buttonBlackWhitem = Button(f2, text = "MTS @ black & white", command = RH_LH_mtsBlackWhite)
f2.grid(row = shiftCol +16,column=1, sticky="nsew")
buttonBlackWhitem.pack(anchor = CENTER)

fspace = tk.Frame(root)
tempL = Label(fspace)
fspace.grid(row = shiftCol +17,column=1, sticky="nsew")
tempL.pack(pady = 20)

buttonRedBlueseq = Button(root, text = "Red/Blue Sequence", command = RH_LH_redBlueseq).grid(row = shiftCol +18,column=0)
buttonBlackWhiteseq = Button(root, text = "Black/White Sequence", command = RH_LH_blackWhiteseq).grid(row = shiftCol +18,column=1)
buttonEnd = Button(root, text = "End", command = endSetup).grid(row = shiftCol +18,column=2)

sendTiD(32766)  # send Event CUE: 32766 to LOOP to indicate start of the run
if hardwareTrigger:
	parallel.signal(255)

root.mainloop() 
