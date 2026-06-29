# *************************************************************************************************
# a2_online_FES.py
# Visual + FES interface for TESS online BCI session.
#
# Display filling mirrors runtime_common.py (Robot+FES pipeline):
#   - receiveTiC() returns [raw_rest, raw_move] from ndf_main_adap.py
#   - remap: display = (raw - 0.5) * 2  → [0, 1]
#   - prob holds its last value between packets (no reset on missing packet)
#   - bar/circle fill proportional to current probability
#   - threshold lines drawn at detectionThresholdMove / detectionThresholdRest
#   - trial ends when fill crosses threshold OR timeout expires
#
# Handshake:
#   - Waits for READY signal from ndf_main_adap.py on port 12348 before
#     sending run-start marker 32766, eliminating the timing race condition.
# *************************************************************************************************

import socket
import sys
import os
import time
import math
import random

import UTIL_marker_stream_TESS

from pathlib import Path
dirP = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
sys.path.append(dirP + '/z1_ref_other/0_lib')

import pygame
from pygame.locals import *
import pyautogui

from pylsl import StreamInfo, StreamOutlet

from a0_configFile import *
from a0_configFileSTM import *

from rehamove import *

import config_tess as config

# =============================================================================
# Pygame init
# =============================================================================
pygame.init()
pygame.mixer.init()

# =============================================================================
# UDP
# =============================================================================
def send_udp_message(sock, ip, port, message):
    sock.sendto(message.encode('utf-8'), (ip, port))
    print(f"Sent UDP message to {ip}:{port}: {message}")

udp_marker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip   = '127.0.0.1'
port = 12345

info   = StreamInfo('MarkerStream', 'Markers', 2, 0, 'float32', 'marker_stream_id')
outlet = StreamOutlet(info)

udp_prob_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_prob_sock.bind(('127.0.0.1', 12347))
udp_prob_sock.setblocking(False)


def receiveTiC():
    """
    Returns [raw_rest, raw_move] if a packet is available, else None.
    Returning None means prob holds its last value — bar stays filled.
    """
    try:
        data, _ = udp_prob_sock.recvfrom(1024)
        values = [float(x) for x in data.decode('utf-8').strip().split(',')]
        return values
    except BlockingIOError:
        return None
    except Exception:
        return None

# =============================================================================
# Thresholds from command line args
# =============================================================================
detectionThresholdRest = int(sys.argv[3]) / 100
detectionThresholdMove = int(sys.argv[2]) / 100
# Remap from [0.5,1] → [0,1] display space
detectionThresholdRest = (detectionThresholdRest - 0.5) / 0.5
detectionThresholdMove = (detectionThresholdMove - 0.5) / 0.5

fprob = open(sys.argv[1][0:-4] + '_probabilities_log.txt', "w+")
fprob.write('time \t Rest \t Move\n')

# =============================================================================
# FES (Rehamove)
# =============================================================================
FES = Rehamove(FES_port)
FES.change_mode(0)

def sts_distal_Rest():   FES.pulse('red', I_STS_distRest, int(p_STS_distRest))
def sts_proximal_Rest(): FES.pulse('red', I_STS_proxRest, int(p_STS_proxRest))
def sts_distal_Move():   FES.pulse('red', I_STS_distMove, int(p_STS_distMove))
def sts_proximal_Move(): FES.pulse('red', I_STS_proxMove, int(p_STS_proxMove))
def mts_distal_Rest():   FES.pulse('red', I_MTS_distRest, int(p_MTS_distRest))
def mts_proximal_Rest(): FES.pulse('red', I_MTS_proxRest, int(p_MTS_proxRest))
def mts_distal_Move():   FES.pulse('red', I_MTS_distMove, int(p_MTS_distMove))
def mts_proximal_Move(): FES.pulse('red', I_MTS_proxMove, int(p_MTS_proxMove))

# =============================================================================
# Screen layout
# =============================================================================
screen_size   = pyautogui.size()
screen_width  = int(screen_size[0])
screen_height = int(screen_size[1])
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('Motor Imagery Experiment')
pygame.mouse.set_visible(False)

spaceToBeLeft     = 2.5 * int(screen_width * 0.1)
rectWidth         = screen_width - spaceToBeLeft / 2
barHeight         = int(500 * 0.40)
offsetBarToCircle = 153

cx = screen_width  // 2
cy = screen_height // 2

circ_radius = 180
circ_center = (int(cx - rectWidth / 4), cy)
th_circ_radius = int(180 * math.sqrt(max(0, detectionThresholdRest)))

bar_start_x = circ_center[0] + offsetBarToCircle
bar_max_w   = int(rectWidth / 2 - offsetBarToCircle)
bar_y       = cy - barHeight // 2
th_line_x   = int(bar_start_x + bar_max_w * detectionThresholdMove)

rect_x = int(cx - rectWidth / 4)
rect_w = int(rectWidth / 2)
rect_y = cy - barHeight // 2

black         = (0,   0,   0)
rectEdgeColor = (131, 58,  4)
rectFillColor = (198, 160, 131)
barColor      = rectEdgeColor
white         = (225, 225, 225)
rightRed      = (134, 0,   0)
greenColor    = (5,   170, 5)

try:
    img_rest = pygame.image.load('harmony_rest.png')
    img_rest = pygame.transform.scale(img_rest, (220, 220))
    img_move = pygame.image.load('harmony_move.png')
    img_move = pygame.transform.scale(img_move, (220, 220))
    img_x    = circ_center[0] - 110 + 20
    img_y    = circ_center[1] - 110 - 20
    has_images = True
except Exception:
    has_images = False
    print('[Warning] harmony images not found.')

fix_hw = circ_radius // 3
fix_th = circ_radius // 10


def draw_background():
    screen.fill(black)
    pygame.draw.rect(screen, rectFillColor, (rect_x, rect_y, rect_w, barHeight))
    pygame.draw.rect(screen, rectEdgeColor, (rect_x, rect_y, rect_w, barHeight), 3)
    pygame.draw.circle(screen, rectFillColor, circ_center, circ_radius)
    pygame.draw.circle(screen, rectEdgeColor, circ_center, circ_radius, 8)


def draw_thresholds():
    if th_circ_radius > 0:
        pygame.draw.circle(screen, rightRed, circ_center, th_circ_radius, 3)
    pygame.draw.line(screen, rightRed,
                     (th_line_x, bar_y + 3),
                     (th_line_x, bar_y + barHeight - 3), 4)


def draw_fixation():
    pygame.draw.rect(screen, white,
                     (circ_center[0] - fix_hw, circ_center[1] - fix_th,
                      2 * fix_hw, 2 * fix_th))
    pygame.draw.rect(screen, white,
                     (circ_center[0] - fix_th, circ_center[1] - fix_hw,
                      2 * fix_th, 2 * fix_th))


def draw_image(trial_class):
    if not has_images:
        return
    if trial_class == 0:
        screen.blit(img_rest, (img_x, img_y))
    elif trial_class == 1:
        screen.blit(img_move, (img_x, img_y))


def draw_prob_bars(prob_rest, prob_move):
    """
    Fill circle (rest) and bar (move) proportional to display-space probability.
    prob_rest, prob_move are in [0, 1] — already remapped from raw classifier output.
    Mirrors runtime_common draw_ball_fill / draw_arrow_fill.
    """
    # Circle fill — rest probability
    fill_r = int(circ_radius * math.sqrt(max(0, prob_rest)))
    if fill_r > 0:
        pygame.draw.circle(screen, rectEdgeColor, circ_center, fill_r)
    # Bar fill — move probability
    bar_w = int(bar_max_w * prob_move)
    if bar_w > 0:
        pygame.draw.rect(screen, barColor, (bar_start_x, bar_y, bar_w, barHeight))


# =============================================================================
# Wait for READY signal from ndf_main_adap.py
# ndf_main_adap sends READY from inside its main loop once the marker inlet
# is active — only then do we send 32766 so it cannot be missed.
# =============================================================================
draw_background()
pygame.display.update()

udp_ready_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_ready_sock.bind(('127.0.0.1', 12348))
udp_ready_sock.setblocking(False)
print('[Visual] Waiting for BCI Controller READY signal...')
ready_received = False
t_ready_start  = time.time()

while not ready_received:
    for event in pygame.event.get():
        if event.type == QUIT: pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()
    draw_background()
    pygame.display.update()
    try:
        data, _ = udp_ready_sock.recvfrom(1024)
        print(f'[Visual] BCI Controller READY: {data.decode()}')
        ready_received = True
    except BlockingIOError:
        pass
    if time.time() - t_ready_start > 120:
        print('[Visual] Timeout waiting for READY — continuing anyway.')
        break
    time.sleep(0.05)
udp_ready_sock.close()

# =============================================================================
# RUN STARTS HERE
# =============================================================================
send_udp_message(udp_marker, ip, port, '32766')
outlet.push_sample([32766.0, 32766.0])
print('[Visual] Run start marker 32766 sent.')

time.sleep(ExperimentConfigureTime)

correctBCICommand = 0
missedCommands    = 0
closedCommands    = 0

for trial in trials:

    trial = int(trial)
    print('Class of current trial: ', trial)

    # ── REST period ──────────────────────────────────────────────────────────
    draw_background()
    pygame.display.update()
    send_udp_message(udp_marker, ip, port, '1000')
    time.sleep(restTime + random.random())

    # ── FIXATION CUE (baseline collection window) ────────────────────────────
    send_udp_message(udp_marker, ip, port, '768')
    if fixationCrossTime > 0:
        draw_background()
        draw_fixation()
        pygame.display.update()
        time.sleep(fixationCrossTime)
    # ndf_main_adap.py computes baseline from the EEG accumulated during this
    # fixation period when it receives the trial-start marker below.

    # prob in display space [0,1] — holds value between UDP packets
    prob  = [0.0, 0.0]
    check = -1

    # ── TASK CUE ─────────────────────────────────────────────────────────────
    if trial == 0:
        send_udp_message(udp_marker, ip, port, '769')
        t_cue = time.time()
        while time.time() - t_cue < cueTime:
            draw_background()
            draw_image(0)
            pygame.display.update()
            for event in pygame.event.get():
                if event.type == QUIT: pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()
        send_udp_message(udp_marker, ip, port, '7691')
        outlet.push_sample([7691.0, 7691.0])
        fprob.write('%d\t%d\t%d\n' % (7691, 7691, 7691))

    elif trial == 1:
        send_udp_message(udp_marker, ip, port, '770')
        t_cue = time.time()
        while time.time() - t_cue < cueTime:
            draw_background()
            draw_image(1)
            pygame.display.update()
            for event in pygame.event.get():
                if event.type == QUIT: pygame.quit(); sys.exit()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()
        send_udp_message(udp_marker, ip, port, '7701')
        outlet.push_sample([7701.0, 7701.0])
        fprob.write('%d\t%d\t%d\n' % (7701, 7701, 7701))

    # ── TASK WINDOW ───────────────────────────────────────────────────────────
    t_task        = time.time()
    resetCycleFES = 1
    timeFES       = time.time()

    while True:
        # Receive probability — None means no new packet, keep last value
        message = receiveTiC()

        if resetCycleFES:
            timeFES       = time.time()
            resetCycleFES = 0

        if message is not None:
            raw_rest = message[0]
            raw_move = message[1]

            fprob.write('%07.3f\t' % (time.time() - t_task))
            fprob.write('%05.4f\t%05.4f\t' % (raw_rest * 100, raw_move * 100))
            fprob.write('\n')

            # Remap classifier space [0.5, 1.0] → display space [0.0, 1.0]
            # ndf_main_adap already packs fill values as raw = fill/2 + 0.5
            # so this remap recovers the fill directly.
            prob[0] = max(0.0, (raw_rest - 0.5) * 2)
            prob[1] = max(0.0, (raw_move - 0.5) * 2)
            print(f'[UDP RECV] raw=[{raw_rest:.3f},{raw_move:.3f}] '
                  f'display=[{prob[0]:.3f},{prob[1]:.3f}]')

        # Draw
        draw_background()
        draw_prob_bars(prob[0], prob[1])
        draw_thresholds()
        draw_image(trial)
        pygame.display.update()

        # FES — probability-based (unchanged from original)
        if (time.time() - timeFES) > 1 / FES_freq:
            resetCycleFES = 1
            if prob[1] == 0 and prob[0] == 0:
                if trial == 0:   sts_proximal_Move()
                elif trial == 1: sts_proximal_Rest()
            elif prob[1] >= detectionThresholdMove / 2 and prob[1] >= prob[0]:
                sts_distal_Move(); sts_proximal_Move()
            elif 0 <= prob[1] < detectionThresholdMove / 2 and prob[1] >= prob[0]:
                sts_proximal_Move()
            elif 0 <= prob[0] < detectionThresholdRest / 2 and prob[0] >= prob[1]:
                sts_proximal_Rest()
            elif prob[0] >= detectionThresholdRest / 2 and prob[0] >= prob[1]:
                sts_distal_Rest(); sts_proximal_Rest()

        # Threshold check (display space)
        if prob[0] >= detectionThresholdRest: check = 0
        if prob[1] >= detectionThresholdMove: check = 1

        if (time.time() - t_task >= timeout) or check in [0, 1]:

            if check == trial:
                correctBCICommand += 1
                if trial == 0:
                    send_udp_message(udp_marker, ip, port, '7693')
                    outlet.push_sample([7693.0, 7693.0])
                    fprob.write('%d\t%d\t%d\n' % (7693, 7693, 7693))
                    draw_background()
                    pygame.draw.circle(screen, greenColor, circ_center, circ_radius)
                    pygame.draw.circle(screen, rectEdgeColor, circ_center, circ_radius, 8)
                    draw_image(0)
                    pygame.display.update()
                    time.sleep(resultTime)

                elif trial == 1:
                    send_udp_message(udp_marker, ip, port, '7703')
                    outlet.push_sample([7703.0, 7703.0])
                    fprob.write('%d\t%d\t%d\n' % (7703, 7703, 7703))
                    closedCommands += 1
                    t_result = time.time()
                    while time.time() - t_result < resultTime:
                        draw_background()
                        pygame.draw.rect(screen, greenColor,
                                         (bar_start_x, bar_y, bar_max_w, barHeight))
                        pygame.draw.rect(screen, rectEdgeColor,
                                         (rect_x, rect_y, rect_w, barHeight), 3)
                        draw_image(1)
                        pygame.display.update()
                        mts_proximal_Move()
                        mts_distal_Move()
                        time.sleep(1 / FES_freq)

            else:
                missedCommands += 1
                if trial == 0:
                    send_udp_message(udp_marker, ip, port, '7692')
                    outlet.push_sample([7692.0, 7692.0])
                    fprob.write('%d\t%d\t%d\n' % (7692, 7692, 7692))
                    draw_background()
                    pygame.draw.circle(screen, rightRed, circ_center, circ_radius)
                    pygame.draw.circle(screen, rectEdgeColor, circ_center, circ_radius, 8)
                    draw_image(0)
                    pygame.display.update()
                    time.sleep(resultTime)

                elif trial == 1:
                    send_udp_message(udp_marker, ip, port, '7702')
                    outlet.push_sample([7702.0, 7702.0])
                    fprob.write('%d\t%d\t%d\n' % (7702, 7702, 7702))
                    draw_background()
                    pygame.draw.rect(screen, rightRed,
                                     (bar_start_x, bar_y, bar_max_w, barHeight))
                    pygame.draw.rect(screen, rectEdgeColor,
                                     (rect_x, rect_y, rect_w, barHeight), 3)
                    draw_image(1)
                    pygame.display.update()
                    time.sleep(resultTime)

            check = -1
            break

        for event in pygame.event.get():
            if event.type == QUIT: pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: sys.exit()

# =============================================================================
# End of run
# =============================================================================
send_udp_message(udp_marker, ip, port, '32766')
outlet.push_sample([32766.0, 32766.0])

# Wait for end signal [1000.0, 1000.0] from ndf_main_adap.py
message = receiveTiC()
while message is None or int(message[0]) != 1000:
    message = receiveTiC()

pygame.quit()

# Log file
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
f.write("detectionThresholdRest %f\r\n" % (0.5 + detectionThresholdRest * 0.5))
f.write("detectionThresholdMove %f\r\n" % (0.5 + detectionThresholdMove * 0.5))
f.write("nTrials %f\r\n" % (n_Move + n_Rest))
f.write("nHitsBCI %d\r\n" % correctBCICommand)
f.write("closedCommands %d\r\n" % closedCommands)
f.write("openCommands %d\r\n" % (correctBCICommand - closedCommands))
f.write("missedCommands %d\r\n" % missedCommands)
f.write("FES_freq= %f\n" % FES_freq)
f.write("I_STS_distMove= %f\n" % I_STS_distMove)
f.write("I_STS_proxMove= %f\n" % I_STS_proxMove)
f.write("I_MTS_distMove= %f\n" % I_MTS_distMove)
f.write("I_MTS_proxMove= %f\n" % I_MTS_proxMove)
f.write("I_STS_proxRest= %f\n" % I_STS_proxRest)
f.write("I_STS_distRest= %f\n" % I_STS_distRest)
f.write("I_MTS_proxRest= %f\n" % I_MTS_proxRest)
f.write("I_MTS_distRest= %f\n" % I_MTS_distRest)
f.write("p_STS_distMove= %f\n" % p_STS_distMove)
f.write("p_STS_proxMove= %f\n" % p_STS_proxMove)
f.write("p_MTS_distMove= %f\n" % p_MTS_distMove)
f.write("p_MTS_proxMove= %f\n" % p_MTS_proxMove)
f.write("p_STS_proxRest= %f\n" % p_STS_proxRest)
f.write("p_STS_distRest= %f\n" % p_STS_distRest)
f.write("p_MTS_proxRest= %f\n" % p_MTS_proxRest)
f.write("p_MTS_distRest= %f" % p_MTS_distRest)
f.close()
