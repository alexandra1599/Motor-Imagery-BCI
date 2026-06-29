# *************************************************************************************************
# Include needed packages
# ########################

# ## LSL + Serial Comm Packages
import socket
import sys
import os
import time
import math
import random

from pathlib import Path
dirP = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
sys.path.append(dirP + '/z1_ref_other/0_lib')

import pygame
from pygame.locals import *
import pyautogui

from pylsl import StreamInfo, StreamOutlet

## LOAD CONFIGURATIONS FOR THE TASK
from a0_configFile import *
from a0_configFileSTM import *

## FES Rehamove Library
from rehamove import *

# *************************************************************************************************
# Pygame init
# *************************************************************************************************
pygame.init()
pygame.mixer.init()

# Load sounds if available
try:
    sound_rest = pygame.mixer.Sound('rest.wav')
    sound_move = pygame.mixer.Sound('move.wav')
    has_sound  = True
except Exception:
    sound_rest = None
    sound_move = None
    has_sound  = False
    print('[Warning] Sound files not found — running without audio.')

# *************************************************************************************************
# UDP + LSL markers
# *************************************************************************************************
def send_udp_message(sock, ip, port, message):
    sock.sendto(message.encode('utf-8'), (ip, port))
    print(f"Sent UDP message to {ip}:{port}: {message}")

udp_marker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip   = '127.0.0.1'
port = 12345

message_run_start  = '32766'  # start/end of run
message_rest_end   = '1000'   # end of result view time
message_trial_start= '768'    # new trial start
message_flex_task  = '7691'   # start of flexion task
message_ext_task   = '7701'   # start of extension task
message_flex_end   = '7692'   # end of flexion task
message_ext_end    = '7702'   # end of extension task
message_flex_cue   = '769'    # flexion cue
message_ext_cue    = '770'    # extension cue

# LSL marker stream
info   = StreamInfo('MarkerStream', 'Markers', 2, 0, 'float32', 'marker_stream_id')
outlet = StreamOutlet(info)

# *************************************************************************************************
# Rehamove FES
# *************************************************************************************************
FES = Rehamove(FES_port)
FES.change_mode(0)

def sts_distal_Move():   FES.pulse('red', I_STS_distMove, int(p_STS_distMove))
def sts_proximal_Move(): FES.pulse('red', I_STS_proxMove, int(p_STS_proxMove))
def mts_distal_Move():   FES.pulse('red', I_MTS_distMove, int(p_MTS_distMove))
def mts_proximal_Move(): FES.pulse('red', I_MTS_proxMove, int(p_MTS_proxMove))

# *************************************************************************************************
# Build the interface
# *************************************************************************************************
screen_size   = pyautogui.size()
screen_width  = int(screen_size[0])
screen_height = int(screen_size[1])
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('Motor Imagery Experiment')
pygame.mouse.set_visible(False)

# Layout constants — match original PsychoPy proportions
rectWidth  = screen_width - (2.5 * int(screen_width * 0.1)) / 2
barHeight  = int(500 * 0.40)   # 200px — same as original
halfRectWidth = rectWidth / 2
offset     = rectWidth / 4

# Center of screen
cx = screen_width  // 2
cy = screen_height // 2

# Circle (left side — flexion feedback)
circ_radius     = 180
circ_center     = (int(cx - rectWidth / 4), cy)

# Horizontal rect (right side — extension feedback)
rect_x = int(cx - rectWidth / 4)   # left edge of the rect area
rect_w = int(rectWidth / 2)
rect_y = cy - barHeight // 2

# Colors (pygame 0-255)
black         = (0, 0, 0)
rectEdgeColor = (131, 58, 4)
rectFillColor = (198, 160, 131)
barColor      = rectEdgeColor
white         = (225, 225, 225)
greenColor    = (5, 170, 5)
redColor      = (134, 0, 0)
blueColor     = (10, 0, 134)

# Load harmony images
try:
    img_rest = pygame.image.load('harmony_rest.png')
    img_rest = pygame.transform.scale(img_rest, (220, 220))
    img_move = pygame.image.load('harmony_move.png')
    img_move = pygame.transform.scale(img_move, (220, 220))
    img_rest_x = circ_center[0] - 110 + 20
    img_rest_y = circ_center[1] - 110 - 20
    has_images = True
except Exception:
    has_images = False
    print('[Warning] harmony images not found — running without images.')

# Fixation cross dimensions
fix_hw = circ_radius // 3   # half-width of cross arm
fix_th = circ_radius // 10  # thickness


def draw_background():
    """Draw the base interface: rect + circle outlines."""
    screen.fill(black)
    # Horizontal rectangle
    pygame.draw.rect(screen, rectFillColor, (rect_x, rect_y, rect_w, barHeight))
    pygame.draw.rect(screen, rectEdgeColor, (rect_x, rect_y, rect_w, barHeight), 3)
    # Circle
    pygame.draw.circle(screen, rectFillColor, circ_center, circ_radius)
    pygame.draw.circle(screen, rectEdgeColor, circ_center, circ_radius, 8)


def draw_fixation():
    pygame.draw.rect(screen, white, (circ_center[0] - fix_hw, circ_center[1] - fix_th, 2 * fix_hw, 2 * fix_th))
    pygame.draw.rect(screen, white, (circ_center[0] - fix_th, circ_center[1] - fix_hw, 2 * fix_th, 2 * fix_hw))


def draw_image(trial_class):
    if not has_images:
        return
    if trial_class == 0:   # rest/flexion
        screen.blit(img_rest, (img_rest_x, img_rest_y))
    elif trial_class == 1:  # move/extension
        screen.blit(img_move, (img_rest_x, img_rest_y))


##################################
######## RUN STARTS HERE #########
##################################
send_udp_message(udp_marker, ip, port, message_run_start)

draw_background()
pygame.display.update()
time.sleep(ExperimentConfigureTime)

resetCycleFES = 1
timeFES = time.time()

for trial in trials:

    trial = int(trial)
    print('Class of current trial: ', trial)

    # <<<<<< REST >>>>>>
    draw_background()
    pygame.display.update()
    send_udp_message(udp_marker, ip, port, message_rest_end)
    if sound_rest: sound_rest.play()
    time.sleep(restTime + random.random())

    # <<<<<< FIXATION CUE >>>>>>
    send_udp_message(udp_marker, ip, port, message_trial_start)
    if fixationCrossTime > 0:
        draw_background()
        draw_fixation()
        pygame.display.update()
        time.sleep(fixationCrossTime)

    # ================================================================
    # TRIAL == 0: REST / FLEXION — circle fills up over time
    # ================================================================
    if trial == 0:
        # Task cue
        draw_background()
        draw_image(0)
        pygame.display.update()
        send_udp_message(udp_marker, ip, port, message_flex_cue)
        if sound_move: sound_move.play()
        time.sleep(cueTime)

        # Task
        send_udp_message(udp_marker, ip, port, message_flex_task)
        t_start = time.time()
        while True:
            t_elapsed = time.time() - t_start
            if t_elapsed >= taskTime:
                break

            draw_background()
            # Fill circle proportional to time
            fill_r = int(circ_radius * math.sqrt(t_elapsed / taskTime))
            if fill_r > 0:
                pygame.draw.circle(screen, rectEdgeColor, circ_center, fill_r)
            draw_image(0)
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == QUIT: pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()

        # Result
        send_udp_message(udp_marker, ip, port, message_flex_end)
        draw_background()
        pygame.draw.circle(screen, greenColor, circ_center, circ_radius)
        pygame.draw.circle(screen, rectEdgeColor, circ_center, circ_radius, 8)
        draw_image(0)
        pygame.display.update()
        time.sleep(resultTime)

    # ================================================================
    # TRIAL == 1: MOVE / EXTENSION — bar grows rightward + FES
    # ================================================================
    elif trial == 1:
        # Task cue
        draw_background()
        draw_image(1)
        pygame.display.update()
        send_udp_message(udp_marker, ip, port, message_ext_cue)
        if sound_move: sound_move.play()
        time.sleep(cueTime)

        # Task
        send_udp_message(udp_marker, ip, port, message_ext_task)
        t_start = time.time()
        resetCycleFES = 1

        bar_max_w = int(rect_w - rect_w // 13)
        bar_start_x = rect_x + rect_w // 13

        while True:
            t_elapsed = time.time() - t_start
            if t_elapsed >= taskTime:
                break

            # FES timing
            if resetCycleFES:
                timeFES = time.time()
                resetCycleFES = 0
            if (time.time() - timeFES) > 1 / FES_freq:
                resetCycleFES = 1
                sts_proximal_Move()
                if t_elapsed > taskTime / 2:
                    sts_distal_Move()

            draw_background()
            step = int(bar_max_w * t_elapsed / taskTime)
            bar_x = bar_start_x
            pygame.draw.rect(screen, barColor, (bar_x, rect_y, step, barHeight))
            draw_image(1)
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == QUIT: pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()

        # Result — green bar + MTS FES
        send_udp_message(udp_marker, ip, port, message_ext_end)
        resetCycleFES = 1
        t_result = time.time()
        while time.time() - t_result < resultTime:
            if resetCycleFES:
                timeFES = time.time()
                resetCycleFES = 0
            if (time.time() - timeFES) > 1 / FES_freq:
                resetCycleFES = 1
                mts_distal_Move()
                mts_proximal_Move()

            draw_background()
            pygame.draw.rect(screen, greenColor, (bar_start_x, rect_y, bar_max_w, barHeight))
            pygame.draw.rect(screen, rectEdgeColor, (rect_x, rect_y, rect_w, barHeight), 3)
            draw_image(1)
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == QUIT: pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()

    for event in pygame.event.get():
        if event.type == QUIT: pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()

# End of run
send_udp_message(udp_marker, ip, port, message_run_start)
time.sleep(3)

logFile = sys.argv[1]
print(logFile)
f = open(logFile, "a+")
f.write("ExperimentConfigureTime %f\r\n" % ExperimentConfigureTime)
f.write("fixationCrossTime %f\r\n" % fixationCrossTime)
f.write("cueTime %f\r\n" % cueTime)
f.write("timeout %f\r\n" % timeout)
f.write("taskTime %f\r\n" % taskTime)
f.write("resultTime %f\r\n" % resultTime)
f.write("restTime %f\r\n" % restTime)
f.write("detectionThresholdRest %f\r\n" % detectionThresholdRest)
f.write("detectionThresholdMove %f\r\n" % detectionThresholdMove)
f.write("RightHanded %f\r\n" % 1)
f.close()
