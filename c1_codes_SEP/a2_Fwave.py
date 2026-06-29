
## Packages to import:
import serial
import sys
import os
from pathlib import Path
import numpy as np
dirP = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
# #print(dirP + '/4_ref_other')
sys.path.append(dirP + '/c2_codes_BCI/z1_ref_other/0_lib')
sys.path.append(dirP + '/c2_codes_BCI/c1_codes/1_packages')
sys.path.append(dirP + '/c5_codes_TMS_SICI')

from playsound import playsound
from a0_config_Fwave import *

## Other Packages:
import pygame
import sys
import time
import random
from pygame.locals import *
import pyautogui
import math

## LOAD CONFIGURATIONS FOR THE TASK

## FES Rehamove Library
import time
import math 
from rehamove import * 	# Import rehamove library

import cnbiloop
from cnbiloop import BCI, BCI_tid
from python_client import Trigger

from serialCommunication import SerialWriter


black=(0,0,0)
white=(225,225,225)

pygame.init()
font = pygame.font.SysFont('helvetica',60)

bci = BCI_tid.BciInterface()

def sendTiD(Event_):
#    pass
	bci.id_msg_bus.SetEvent(Event_)
	bci.iDsock_bus.sendall(str.encode(bci.id_serializer_bus.Serialize()))

screen = pyautogui.size();

screen_width = screen[0]
screen_height = screen[1]
scaling_factor = 1

# Normalize everything to the size of the bar as determined below
screen_width = int(screen_width / scaling_factor)
screen_height = int(screen_height / scaling_factor)
screen = pygame.display.set_mode((screen_width, screen_height))#,pygame.FULLSCREEN)  # Setting up the screen size 
pygame.mouse.set_visible(False)
pygame.display.set_caption('Motor Imagery Experiment')

spaceToBeLeft = 2.5 * int(screen_width * 0.1)  # space to be left at the edges of the rectangle to fit the
Bigger_rectangle_width = screen_width - 2 * spaceToBeLeft
bar_width = 0.5 * Bigger_rectangle_width

flexion_image = pygame.transform.flip(pygame.image.load('extension.png'), True, False)
image_scaling_flexion = spaceToBeLeft / flexion_image.get_rect().size[0]
flexion_image = pygame.transform.scale(flexion_image, (
int(spaceToBeLeft), int(flexion_image.get_rect().size[1] * image_scaling_flexion)))

bar_height = int(flexion_image.get_rect().size[1] * 0.2086701)  # make the height of the bar consistent with the size of wrist in the images

# setting the dimensions of the rectangle in which the bar moves right/left
Bigger_rectangle_height = bar_height
Bigger_rectangle_X = spaceToBeLeft
Bigger_rectangle_Y = screen_height / 2 - bar_height / 2 
Bigthickness = 3  # thickness of the edge lines for the rectangle and other shapes

white=(225,225,225)
FES_channel = 'red'
# Initial position of the bar in the middle of the rectangle:
initial_x = screen_width/2 - bar_width/2
initial_y = screen_height/2 - bar_height/2
centerOfScreen = (screen_width/2 , screen_height/2)

try:
	parallel = Trigger('USB2LPT') # if using hardware triggers through the arduino board, use 'ARDUINO'
	parallel.init(100)
	hardwareTrigger =1 	
except:
	hardwareTrigger =0 

if hardwareTrigger==0:
	try:
		parallel = Trigger('ARDUINO') # if using hardware triggers through the arduino board, use 'ARDUINO'
		parallel.init(100)
		hardwareTrigger =1 	
	except:
		hardwareTrigger =0 
	


print('Using Hardware Trigger=' + str(hardwareTrigger))
time.sleep(1)

##################################
######## RUN STARTS HERE #########
##################################


print('Welcome!')
t0 = time.time()
refresh = False
welcome = True
while welcome:
    if (time.time() - t0) < 1:
        t_rem = '5s'
        refresh = True
    elif ((time.time() - t0) > 1) & ((time.time() - t0) < 2):
        t_rem = '4s'
        refresh = True
    elif ((time.time() - t0) > 2) & ((time.time() - t0) < 3):
        t_rem = '3s'
        refresh = True
    elif ((time.time() - t0) > 3) & ((time.time() - t0) < 4):
        t_rem = '2s'
        refresh = True
    elif ((time.time() - t0) > 4) & ((time.time() - t0) < 5):
        t_rem = '1s'
        refresh = True
    elif (time.time() - t0) > 5:
    	refresh = True
    	welcome = False

    if refresh:
        text = font.render('Welcome, task starts in ' + t_rem + ' (press SPACE to skip)', True, white, black)
        textRect = text.get_rect()
        textRect.center = (screen_width/2, 200)
        screen.blit(text, textRect)
        pygame.display.update()
        refresh = False

    for event in pygame.event.get():
        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                pygame.quit;
                sys.exit();
            if event.key == K_SPACE:
            	welcome = False


sendTiD(32766)  # send Event CUE: 55555 to LOOP to indicate start of TESS
# Left hand and right HandArrows and up arrow
screen.fill(black)  # clear display
text = font.render('Rest', True, white)
text_width, text_height = font.size("Rest") #txt being whatever str you're rendering

textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()

playsound('RestStimulation.wav')

FES = Rehamove(FES_port)    # Open USB port (on Windows)

pulsearray = []
for i in range(2):
	if (i % 2) == 0: # even
		pulsearray.append([sensoryIntensity, pulseWidth])
	else:            # odd
		# aasd = 0
		pulsearray.append([0, pulseWidth])		
print(pulsearray)

# draw count-down bar
stimCnt = 1

screen.fill(black)  # clear display
pygame.display.update()

pygame.draw.rect(screen, white, (centerOfScreen[0] - bar_height / 3, centerOfScreen[1] - bar_height / 15, 2 * bar_height / 3,2 * bar_height / 15),0)  # horizontal rectangle for cross cue
pygame.draw.rect(screen, white, (centerOfScreen[0] - bar_height / 15, centerOfScreen[1] - bar_height / 3, 2 * bar_height / 15,2 * bar_height / 3),0)  # Vertical rectangle for cross cue
pygame.display.update()


screen.fill(black)  # clear display

for i in range(0, numTrials, 1):
	progress = (stimCnt)/(numTrials)
	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-5*text_width/2,centerOfScreen[1]-0.5*text_height,5*text_width*progress,2*text_height))
	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-5*text_width/2,centerOfScreen[1]-0.5*text_height,5*text_width,2*text_height), 4)
	pygame.display.update()

	
	FES.custom_pulse(FES_channel, pulsearray)
	if hardwareTrigger:
		parallel.signal(101)
	sendTiD(101)  # send Event CU

	time.sleep(restTime+random.random())
	stimCnt = stimCnt+1

# start with 2 minutes of resting
screen.fill(black)  # clear display

	
sendTiD(32766)  # send Event CUE: 55555 to LOOP to indicate start of TESS
logFile = sys.argv[1]
hand = sys.argv[2]
print(logFile)
f = open(logFile, "a+")

f.write("restTime %f\r\n" % (restTime))
f.write("numTrials %f\r\n" % (numTrials))
f.write("sensoryIntensity %f\r\n" % (sensoryIntensity))
f.write("motorIntensity %f\r\n" % (motorIntensity))
f.write("stimulated hand %s\r\n" % (hand))
f.write("FES_freq %f\r\n" % (FES_freq))
f.write("pulseWidth %f\r\n" % (pulseWidth))

f.close()

