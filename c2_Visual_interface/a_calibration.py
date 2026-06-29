# *************************************************************************************************
# EOG Calibration Script
# Shows dots at top/bottom/left/right for eye movements, then green cross for blinking
# *************************************************************************************************

import pygame
import random
import time
import pyautogui
import socket
from pylsl import StreamInfo, StreamOutlet

# *************************************************************************************************
# UDP + LSL markers
# *************************************************************************************************
def send_udp_message(sock, ip, port, message):
    sock.sendto(message.encode('utf-8'), (ip, port))
    print(f"Sent UDP message to {ip}:{port}: {message}")

udp_marker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
ip   = '127.0.0.1'
port = 12345

info   = StreamInfo('MarkerStream', 'Markers', 2, 0, 'float32', 'marker_stream_id')
outlet = StreamOutlet(info)

# Marker codes
MARKER_START     = '32766'
MARKER_FIXATION  = '1'     # fixation cross shown
MARKER_DOT_TOP   = '10'    # dot at top
MARKER_DOT_BOT   = '11'    # dot at bottom
MARKER_DOT_LEFT  = '12'    # dot at left
MARKER_DOT_RIGHT = '13'    # dot at right
MARKER_BLINK     = '20'    # blink phase start
MARKER_END       = '32766'

# *************************************************************************************************
# Pygame init
# *************************************************************************************************
pygame.init()

screen_tmp    = pyautogui.size()
screen_width  = screen_tmp[0]
screen_height = screen_tmp[1]

BACKGROUND_COLOR  = (0, 0, 0)
GREEN_CROSS_COLOR = (0, 255, 0)
CROSS_COLOR       = (255, 255, 255)
DOT_COLOR         = (255, 255, 255)
CROSS_SIZE        = 20
DOT_RADIUS        = 10
FIXATION_TIME     = 1    # seconds between fixation cross and dot
DOT_TIME          = 1    # seconds dot is shown
RUNS              = 15   # total number of dot appearances
BLINK_TIME        = 10   # seconds for blink phase

CENTER = (screen_width // 2, screen_height // 2)
DOT_POSITIONS = {
    MARKER_DOT_TOP:   (CENTER[0], CENTER[1] - 400),
    MARKER_DOT_BOT:   (CENTER[0], CENTER[1] + 400),
    MARKER_DOT_LEFT:  (CENTER[0] - 400, CENTER[1]),
    MARKER_DOT_RIGHT: (CENTER[0] + 400, CENTER[1]),
}

screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("EOG Calibration")
pygame.mouse.set_visible(False)
clock = pygame.time.Clock()


def draw_fixation_cross(color):
    pygame.draw.line(screen, color, (CENTER[0] - CROSS_SIZE, CENTER[1]),
                     (CENTER[0] + CROSS_SIZE, CENTER[1]), 3)
    pygame.draw.line(screen, color, (CENTER[0], CENTER[1] - CROSS_SIZE),
                     (CENTER[0], CENTER[1] + CROSS_SIZE), 3)


def draw_dot(position):
    pygame.draw.circle(screen, DOT_COLOR, position, DOT_RADIUS)


def check_events():
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            send_udp_message(udp_marker, ip, port, MARKER_END)
            pygame.quit(); exit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            send_udp_message(udp_marker, ip, port, MARKER_END)
            pygame.quit(); exit()


# *************************************************************************************************
# Run
# *************************************************************************************************
send_udp_message(udp_marker, ip, port, MARKER_START)

# Build randomised dot sequence with marker codes
markers   = list(DOT_POSITIONS.keys())
num_each  = RUNS // len(markers)
sequence  = markers * num_each
random.shuffle(sequence)

for marker in sequence:
    position = DOT_POSITIONS[marker]

    # Fixation cross
    screen.fill(BACKGROUND_COLOR)
    draw_fixation_cross(CROSS_COLOR)
    pygame.display.flip()
    send_udp_message(udp_marker, ip, port, MARKER_FIXATION)
    time.sleep(FIXATION_TIME)
    check_events()

    # Dot
    screen.fill(BACKGROUND_COLOR)
    draw_dot(position)
    pygame.display.flip()
    send_udp_message(udp_marker, ip, port, marker)
    time.sleep(DOT_TIME)
    check_events()

# Blink phase — green fixation cross
screen.fill(BACKGROUND_COLOR)
draw_fixation_cross(GREEN_CROSS_COLOR)
pygame.display.flip()
send_udp_message(udp_marker, ip, port, MARKER_BLINK)
time.sleep(BLINK_TIME)
check_events()

send_udp_message(udp_marker, ip, port, MARKER_END)
pygame.quit()
