
## Packages to import:
import serial
import sys
import os
from pathlib import Path
import numpy as np
dirP = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
# #print(dirP + '/4_ref_other')
sys.path.append(dirP + '/MS_codes/c2_codes_BCI/c2_Visual_interface/1_packages')
sys.path.append(dirP + '/MS_codes/c2_codes_BCI/c2_Visual_interface')

## Other Packages:
import pygame
import sys
import time
import random
from pygame.locals import *
import pyautogui
import math

## LOAD CONFIGURATIONS FOR THE TASK
from a0_configFile_LH_RH import *
import a0_config_TESS

## FES Rehamove Library
import time
import math 
from rehamove import * 	# Import rehamove library

# ## LSL + Serial Comm Packages
import socket
import UTIL_marker_stream_TESS
from pylsl import StreamInfo, StreamOutlet, StreamInlet, resolve_stream, local_clock


carrier = 2-int(sys.argv[1])
if carrier:
	burst = 10
	print('\n Stimulating with carrier frequency of 5kHz' )
else:
	burst = 2
	print('\n Stimulating without carrier frequency' )


black=(0,0,0)
white=(225,225,225)

pygame.init()
font = pygame.font.SysFont('helvetica',60)

# *************************************************************************************************
# Serial Comm Functions: (to and from LSL)
# #########################################

def send_udp_message(socket, ip, port, message):
    """
    Send a UDP message to the specified IP and port.
    Parameters:
        socket (socket.socket): The socket object for communication.
        ip (str): The target IP address.
        port (int): The target port.
        message (str): The message to send.
    """
    socket.sendto(message.encode('utf-8'), (ip, port))
    print(f"Sent UDP message to {ip}:{port}: {message}")


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


# Initial position of the bar in the middle of the rectangle:
initial_x = screen_width/2 - bar_width/2
initial_y = screen_height/2 - bar_height/2
centerOfScreen = (screen_width/2 , screen_height/2)


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
            	
            	
# Setup UDP
udp_marker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip = '127.0.0.1'
port = 12345
message1  = '55555'  # "TESS Start"
message2  = '50'   # "Stimulation start"
message3  = '51'    # "New Stimulation start"
message4  = '100'   # stimulus presentation
message5  = '101'   # correct response
message6  = '201'   # timeout
message7  = '52'   # Stim start 
message8  = '20'    # second rest period post stimulation
message9  = '21'    # rest
message10 = '32766'  # End of run

# Create LSL stream for markers
info   = StreamInfo('MarkerStream', 'Markers', 2, 0, 'float32', 'marker_stream_id')
outlet = StreamOutlet(info)


##################################
######## RUN STARTS HERE #########
##################################
send_udp_message(udp_marker, ip, port, message1) # send Event CUE: to indicate start of TESS
# Left hand and right HandArrows and up arrow
screen.fill(black)  # clear display
text = font.render('Rest - Eyes Open', True, white)
text_width, text_height = font.size("Rest - Eyes Open") #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()

# draw count-down bar
# sendTiD(10)  # send cue for second rest period post stimulation
# prevTime = time.time()
# while (time.time() - prevTime)<=inhibitionRestTime*60/2: 
# 	progress = (time.time() - prevTime)/(inhibitionRestTime*60/2)
# 	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
# 	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
# 	pygame.display.update()


# screen.fill(black)  # clear display
# text = font.render('Rest - Eyes Closed', True, white)
# text_width, text_height = font.size('Rest - Eyes Closed') #txt being whatever str you're rendering
# textRect = text.get_rect()
# textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

# screen.blit(text, textRect)
# pygame.display.update()
# time.sleep(3)
# # draw count-down bar
# sendTiD(11)  # send cue for second rest period post stimulation
# prevTime = time.time()
# while (time.time() - prevTime)<=inhibitionRestTime*60/2: 
# 	progress = (time.time() - prevTime)/(inhibitionRestTime*60/2)
# 	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
# 	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
# 	pygame.display.update()

# start with 2 minutes of resting
screen.fill(black)  # clear display

send_udp_message(udp_marker, ip, port, message2)  # send cue for stimulation start
pygame.draw.rect(screen, white, (
centerOfScreen[0] - bar_height / 3, centerOfScreen[1] - bar_height / 15, 2 * bar_height / 3, 2 * bar_height / 15),0)  # horizontal rectangle for cross cue
pygame.draw.rect(screen, white, (centerOfScreen[0] - bar_height / 15, centerOfScreen[1] - bar_height / 3, 2 * bar_height / 15, 2 * bar_height / 3),0)  # Vertical rectangle for cross cue
pygame.display.update()

r = Rehamove("/dev/ttyUSB0")    # Open USB port (on Windows)


screen.fill(black)  # clear display
text = font.render('Stimulation Ramping Up ~ 1 min', True, white)
text_width, text_height = font.size("Stimulation Ramping Up ~ 1 min") #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()

prevTime = time.time()
while (time.time() - prevTime)<=rampTime*60: # test stimulation for 30 seconds
	progress = (time.time() - prevTime)/(rampTime*60)
	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
	pygame.display.update()
	# pulseNew = np.transpose(np.array([pulsearray[:,0]*,pulsearray[:,1]]))
	# pulseNew = pulseNew.astype(int)
	# pulseNew = [list(pulseNew[i].astype(int)) for i in range(len(pulseNew))]
	# print(pulseNew)

	curr = current*(time.time() - prevTime)/(rampTime*60)	   	# in miiliamperes (mA)
	pulseNew = []
	for i in range(burst):
		if (i % 2) == 0: # even
			pulseNew.append([curr, pulseWidth])
		else:            # odd
			pulseNew.append([-curr, pulseWidth])
	print(pulseNew)
	r.custom_pulse(chnName1, pulseNew)
	time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency
	for event in pygame.event.get():
		if event.type == QUIT:
			pygame.quit
			sys.exit()
		elif event.type == pygame.KEYDOWN:
			if event.key == pygame.K_ESCAPE:
				sys.exit() 

curr = current 	# in miiliamperes (mA)
pulseNew = []
for i in range(burst):
	if (i % 2) == 0: # even
		pulseNew.append([curr, pulseWidth])
	else:            # odd
		pulseNew.append([-curr, pulseWidth])

print(pulseNew)

send_udp_message(udp_marker, ip, port, message3)  # send cue for stimulation start
screen.fill(black)  # clear display
text = font.render('Stimulation for 20 min', True, white)
text_width, text_height = font.size("Stimulation for 20 min") #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()
white=(225,225,225)


########################################################

flag_update = True
flag_newtrial = True
flag_intrial = False
flag_inresponse = False
t0 = time.time()
t_update = time.time()
PVT_T = TESS_dur*60
text_width = int(text_width/6)
while time.time() < t0 + PVT_T:
	r.custom_pulse(chnName1, pulseNew)
	time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency
	bar_progress = bar_width*(time.time()-t0)/PVT_T
	# set trial time
	if flag_newtrial:
		t_trial = time.time()
		t_isi = PVT_ISI + random.random()*PVT_ISI_var
		flag_newtrial = False

	# way to cancel measurement
	for event in pygame.event.get():
		if event.type == KEYDOWN:
			if event.key == K_ESCAPE:
				pygame.quit()
				sys.exit()
			if event.key == K_RETURN:
				# just for testing purposes!!
				screen.fill(black)
				pygame.draw.line(screen, (240,240,240), (centerOfScreen[0]-np.sqrt(2)/2*2*text_width/2,centerOfScreen[1]-np.sqrt(2)/2*2*text_width/2),(centerOfScreen[0]+np.sqrt(2)/2*2*text_width/2,centerOfScreen[1]+np.sqrt(2)/2*2*text_width/2),8)
				pygame.draw.line(screen, (240,240,240), (centerOfScreen[0]+np.sqrt(2)/2*2*text_width/2,centerOfScreen[1]-np.sqrt(2)/2*2*text_width/2),(centerOfScreen[0]-np.sqrt(2)/2*2*text_width/2,centerOfScreen[1]+np.sqrt(2)/2*2*text_width/2),8)
				pygame.display.update()

	# update continuously
	if time.time() - t_update > refreshTime:
		t_update = time.time()
		flag_update = True

	if flag_update:
		screen.fill(black)
		# draw cross
		pygame.draw.line(screen, (240,240,240), (centerOfScreen[0]-2*text_width/2,centerOfScreen[1]),(centerOfScreen[0]+2*text_width/2,centerOfScreen[1]),8)
		pygame.draw.line(screen, (240,240,240), (centerOfScreen[0],centerOfScreen[1]-2*text_width/2),(centerOfScreen[0],centerOfScreen[1]+2*text_width/2),8)
		# draw waitbar
		pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_width, bar_height), 5)
		pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_progress, bar_height))
		pygame.display.update()
		flag_update = False

	# trial
	if (time.time() > t_trial+t_isi) and not flag_intrial:
		# sending trial start message
		send_udp_message(udp_marker, ip, port, message4)  # stimulus presentation: 100
		t_stim = time.time()
		flag_intrial = True
		flag_update = True

	# time to provide response
	while flag_intrial:
		t_rt = PVT_pt + PVT_rt
		flag_inresponse = True
		while (time.time() < t_stim + PVT_pt + PVT_rt) and flag_inresponse:

			bar_progress = bar_width*(time.time()-t0)/PVT_T
			# rotate the bar
			if (time.time() < t_stim + PVT_pt) and flag_update:
				rot_x = math.sin(math.pi/2*(time.time()-t_stim)/PVT_pt)
				rot_y = math.cos(math.pi/2*(time.time()-t_stim)/PVT_pt)
				screen.fill(black)
				pygame.draw.line(screen, (240,240,240), (centerOfScreen[0]-rot_x*2*text_width/2,centerOfScreen[1]-rot_y*2*text_width/2),(centerOfScreen[0]+rot_x*2*text_width/2,centerOfScreen[1]+rot_y*2*text_width/2),8)
				pygame.draw.line(screen, (240,240,240), (centerOfScreen[0]+rot_y*2*text_width/2,centerOfScreen[1]-rot_x*2*text_width/2),(centerOfScreen[0]-rot_y*2*text_width/2,centerOfScreen[1]+rot_x*2*text_width/2),8)
				# draw waitbar
				pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_width, bar_height), 5)
				pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_progress, bar_height))
				pygame.display.update()

			# rotate back after 0.5 seconds (disengaged)
			if (time.time() > t_stim + PVT_pt) and flag_update:
				screen.fill(black)
				pygame.draw.line(screen, (240,240,240), (centerOfScreen[0]-2*text_width/2,centerOfScreen[1]),(centerOfScreen[0]+2*text_width/2,centerOfScreen[1]),8)
				pygame.draw.line(screen, (240,240,240), (centerOfScreen[0],centerOfScreen[1]-2*text_width/2),(centerOfScreen[0],centerOfScreen[1]+2*text_width/2),8)
				# draw waitbar
				pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_width, bar_height), 5)
				pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_progress, bar_height))
				pygame.display.update()
				flag_update = False

			for event in pygame.event.get():
				if event.type == KEYDOWN:
					if event.key == K_ESCAPE:
						print(response_table)
						pygame.quit()
						sys.exit()
					if event.key == K_SPACE:
						t_rt = time.time() - t_stim
						flag_intrial = False
						flag_inresponse = False

		flag_inresponse = False
		if t_rt < PVT_pt + PVT_rt:
			send_udp_message(udp_marker, ip, port, message5) # correct response: 101
			screen.fill(black)
			# RT_text = "{:.4f}".format(t_rt)
			# text = font.render('Reaction time = ' + RT_text + 's', white, white)
			# textRect = text.get_rect()
			# textRect.center = (centerOfScreen[0], centerOfScreen[1]+0.5*centerOfScreen[1])
			# screen.blit(text, textRect)

			# pygame.draw.circle(screen, (0,220,10), (centerOfScreen[0],centerOfScreen[1]), 4*text_width)
			# pygame.draw.circle(screen, black, (centerOfScreen[0],centerOfScreen[1]), 3.25*text_width)
			pygame.draw.rect(screen, (0,220,10), (centerOfScreen[0]-1.5*text_width,centerOfScreen[1]-1.5*text_width, 2*1.5*text_width, 2*1.5*text_width))
			pygame.draw.rect(screen, black, (centerOfScreen[0]-1.3*text_width,centerOfScreen[1]-1.3*text_width, 2*1.3*text_width, 2*1.3*text_width))
						# draw waitbar
			pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_width, bar_height), 5)
			pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_progress, bar_height))
			pygame.display.update()
			time.sleep(2)
			flag_update = True
			flag_intrial = False
			flag_newtrial = True
		else:
			send_udp_message(udp_marker, ip, port, message6)   # TimeOut: 201
			screen.fill(black)
			RT_text = "TimeOut"
			# text = font.render(RT_text, white, white)
			# textRect = text.get_rect()
			# textRect.center = (centerOfScreen[0], centerOfScreen[1]+0.5*centerOfScreen[1])
			# screen.blit(text, textRect)

			pygame.draw.rect(screen, (220,0,10), (centerOfScreen[0]-1.5*text_width,centerOfScreen[1]-1.5*text_width, 2*1.5*text_width, 2*1.5*text_width))
			pygame.draw.rect(screen, black, (centerOfScreen[0]-1.3*text_width,centerOfScreen[1]-1.3*text_width, 2*1.3*text_width, 2*1.3*text_width))
			# draw waitbar
			pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_width, bar_height), 5)
			pygame.draw.rect(screen, white, (centerOfScreen[0]-0.5*bar_width, centerOfScreen[1]+0.2*screen_height, bar_progress, bar_height))
			pygame.display.update()
			time.sleep(2)
			flag_update = True
			flag_intrial = False
			flag_newtrial = True









#######################################################3

# prevTime = time.time()
# while (time.time() - prevTime)<=TESS_dur*60: # test stimulation for 30 seconds
# 	progress = (time.time() - prevTime)/(TESS_dur*60)
# 	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
# 	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
# 	pygame.display.update()

# 	r.custom_pulse(chnName1, pulseNew)
# 	time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency
# 	for event in pygame.event.get():
# 		if event.type == QUIT:
# 			pygame.quit
# 			sys.exit()
# 		elif event.type == pygame.KEYDOWN:
# 			if event.key == pygame.K_ESCAPE:
# 				sys.exit() 

send_udp_message(udp_marker, ip, port, message7)  # send cue for stimulation start
screen.fill(black)  # clear display
text = font.render('Stimulation Fading Down ~ 1 min', True, white)
text_width, text_height = font.size("Stimulation Fading Down ~ 1 min") #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()
prevTime = time.time()

while (time.time() - prevTime)<=rampTime*60: # test stimulation for 30 seconds
	progress = (time.time() - prevTime)/(rampTime*60)
	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
	pygame.display.update()

	curr = current*(1-(time.time() - prevTime)/(rampTime*60))	   	# in miiliamperes (mA)
	pulseNew = []
	for i in range(burst):
		if (i % 2) == 0: # even
			pulseNew.append([curr, pulseWidth])
		else:            # odd
			pulseNew.append([-curr, pulseWidth])

	# pulseNew = np.transpose(np.array(pulsearray[:,0]*(1-(time.time() - prevTime)/(rampTime*60)),pulsearray[:,1]))
	print(pulseNew)
	r.custom_pulse(chnName1, pulseNew)
	time.sleep(1/FES_freq-pulseWidth*burst/1000/1000) # pause pulses based on stimulation frequency
	for event in pygame.event.get():
		if event.type == QUIT:
			pygame.quit
			sys.exit()
		elif event.type == pygame.KEYDOWN:
			if event.key == pygame.K_ESCAPE:
				sys.exit() 

screen.fill(black)  # clear display
text = font.render('Rest - Eyes Open', True, white)
text_width, text_height = font.size("Rest - Eyes Open") #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()

# draw count-down bar
send_udp_message(udp_marker, ip, port, message8)   # send cue for second rest period post stimulation
prevTime = time.time()
while (time.time() - prevTime)<=inhibitionRestTime*60/2: 
	progress = (time.time() - prevTime)/(inhibitionRestTime*60/2)
	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
	pygame.display.update()


screen.fill(black)  # clear display
text = font.render('Rest - Eyes Closed', True, white)
text_width, text_height = font.size('Rest - Eyes Closed') #txt being whatever str you're rendering
textRect = text.get_rect()
textRect.center = (centerOfScreen[0], centerOfScreen[1]-2*text_height)

screen.blit(text, textRect)
pygame.display.update()
time.sleep(3)
# draw count-down bar
send_udp_message(udp_marker, ip, port, message9)   # send cue for second rest period post stimulation
prevTime = time.time()
while (time.time() - prevTime)<=inhibitionRestTime*60/2: 
	progress = (time.time() - prevTime)/(inhibitionRestTime*60/2)
	pygame.draw.rect(screen, (255,255,255), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width*progress,2*text_height))
	pygame.draw.rect(screen, (128,128,128), pygame.Rect(centerOfScreen[0]-1.5*text_width/2,centerOfScreen[1]-0.5*text_height,1.5*text_width,2*text_height), 4)
	pygame.display.update()

# start with 2 minutes of resting
screen.fill(black)  # clear display
	
send_udp_message(udp_marker, ip, port, message1)  # send Event CUE: indicate start of TESS
