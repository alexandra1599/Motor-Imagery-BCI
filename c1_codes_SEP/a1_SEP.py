## Packages to import:
import sys
import os
from pathlib import Path
import numpy as np
dirP = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
# #print(dirP + '/4_ref_other')
sys.path.append(dirP + '/z1_ref_other/0_lib')
sys.path.append(dirP + '/c1_codes_SEP/1_packages')

## Other Packages:
import pygame
import sys
import time
import random
from pygame.locals import *
import pyautogui
import math

## LOAD CONFIGURATIONS FOR THE TASK
from c0_config import *

## FES Rehamove Library
import time
import math 
from rehamove import * 	# Import rehamove library

from python_client import Trigger
import socket
import UTIL_marker_stream_TESS
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream, local_clock

# *************************************************************************************************
# Serial Comm Functions
# *************************************************************************************************
def send_udp_message(sock, ip, port, message):
    sock.sendto(message.encode('utf-8'), (ip, port))
    print(f"Sent UDP message to {ip}:{port}: {message}")


# Setup UDP
udp_marker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip   = '127.0.0.1'
port = 12345
message1  = '32766'  # start of Run
message2  = '101'    # SEP single pulse


# Create LSL stream for markers
info   = StreamInfo('MarkerStream', 'Markers', 2, 0, 'float32', 'marker_stream_id')
outlet = StreamOutlet(info)

black=(0,0,0)
white=(225,225,225)

pygame.init()
font = pygame.font.Font('freesansbold.ttf', 32)

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

print('hardwareTrigger = ' + str(hardwareTrigger))

##################################
######## RUN STARTS HERE #########
##################################
send_udp_message(udp_marker, ip, port, message1)   # indicate start of TESS
# Left hand and right HandArrows and up arrow
screen.fill(black)  # clear display
text = font.render('Rest', True, white)
text_width, text_height = font.size("Rest") #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()

FES = Rehamove("/dev/ttyUSB0")    # Open USB port (on Windows)

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
while stimCnt<=repetitions: 
	progress = (stimCnt)/(repetitions)
	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
	pygame.display.update()
	FES.custom_pulse(FES_channel, pulsearray)

	if hardwareTrigger:
		parallel.signal(101)

	send_udp_message(udp_marker, ip, port, message2)  # SEP single pulse
	time.sleep(restTime+0.5*random.random())
	stimCnt = stimCnt+1

# start with 2 minutes of resting
screen.fill(black)  # clear display


	
send_udp_message(udp_marker, ip, port, message1)  #  indicate start of TESS

logFile = sys.argv[1]
hand = sys.argv[2]
print(logFile)
f = open(logFile, "a+")

f.write("\nExperimentConfigureTime %f\r\n" % (ExperimentConfigureTime))
f.write("restTime %f\r\n" % (restTime))
f.write("FES_freq %f\r\n" % (FES_freq))
f.write("PPD_IPI %f\r\n" % (PPD_IPI))
f.write("repetitions %f\r\n" % (repetitions))
f.write("pulseWidth %f\r\n" % (pulseWidth))
f.write("sensoryIntensity %f\r\n" % (sensoryIntensity))
f.write("motorIntensity %f\r\n" % (motorIntensity))
f.write("stimulated hand %s\r\n" % (hand))
f.close()
