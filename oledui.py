#!/usr/bin/python

from __future__ import unicode_literals

import requests
import os
import sys
import time
import json
import pycurl
import pprint
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

from time import *
from threading import Thread
from socketIO_client import SocketIO
from datetime import datetime
from io import BytesIO

# Imports for OLED display
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from modules.pushbutton import PushButton
from modules.rotaryencoder import RotaryEncoder
from modules.display import show_logo, load_font, StaticText, ScrollText

# Configuration Variables
volumio_host = 'localhost'
volumio_port = 3000
VOLUME_DT = 5  # Volume adjustment step
VERTICAL_FLIP = False  # Set to False to flip the display vertically

volumioIO = SocketIO(volumio_host, volumio_port)

STATE_NONE = -1
STATE_PLAYER = 0
STATE_PLAYLIST_MENU = 1
STATE_QUEUE_MENU = 2
STATE_VOLUME = 3
STATE_SHOW_INFO = 4
STATE_LIBRARY_MENU = 5
STATE_LIBRARY_INFO = 6

UPDATE_INTERVAL = 0.034
PIXEL_SHIFT_TIME = 120  # Time between picture position shifts in sec.

interface = spi(device=0, port=0)
oled = ssd1322(interface, rotate=2 if VERTICAL_FLIP else 0)

# Initialize OLED properties
oled.WIDTH = 256
oled.HEIGHT = 64
oled.state = 'stop'
oled.stateTimeout = 0
oled.timeOutRunning = False
oled.activeSong = ''
oled.activeArtist = 'VOLuMIO'
oled.playState = 'unknown'
oled.playPosition = 0
oled.modal = False
oled.queue = []
oled.volume = 100

font = load_font('Oxanium-Bold.ttf', 26)
font2 = load_font('Oxanium-Light.ttf', 12)
font3 = load_font('Oxanium-Regular.ttf', 22)

image = Image.new('RGB', (oled.WIDTH, oled.HEIGHT))

def display_update_service():
    """Update the OLED display at regular intervals."""
    while UPDATE_INTERVAL > 0:
        try:
            if oled.modal:
                image.paste("black", [0, 0, image.size[0], image.size[1]])
                oled.modal.DrawOn(image)
                oled.display(image)
        except AttributeError as e:
            print(f"Display error: {e}")
        sleep(UPDATE_INTERVAL)

def SetState(status):
    """Set the current OLED display state."""
    oled.state = status
    if oled.state == STATE_PLAYER:
        oled.modal = ScrollText(oled.HEIGHT, oled.WIDTH, f"{oled.activeArtist} - {oled.activeSong}", font3)
    elif oled.state == STATE_VOLUME:
        oled.modal = StaticText(oled.HEIGHT, oled.WIDTH, f"Volume: {oled.volume}", font)
    else:
        oled.modal = StaticText(oled.HEIGHT, oled.WIDTH, "No Data", font)

def onPushState(data):
    """Handle playback state updates from Volumio."""
    print("Received playback state:", data)
    if 'title' in data:
        oled.activeSong = data.get('title', '')
    if 'artist' in data:
        oled.activeArtist = data.get('artist', '')
    if 'status' in data:
        oled.playState = data.get('status', 'stop')

    SetState(STATE_PLAYER)

def ButtonA_PushEvent(hold_time):
    """Handle button A press events."""
    if hold_time < 3:  # Short press
        if oled.state == STATE_PLAYER and oled.playState != 'stop':
            volumioIO.emit('pause' if oled.playState == 'play' else 'play')
    else:  # Long press
        volumioIO.emit('shutdown')

def ButtonB_PushEvent(hold_time):
    """Handle button B press events."""
    if hold_time < 3:
        volumioIO.emit('stop')
    else:
        volumioIO.emit('listPlaylist')
        SetState(STATE_PLAYLIST_MENU)

# Initialize buttons
ButtonA_Push = PushButton(4, max_time=3)
ButtonA_Push.setCallback(ButtonA_PushEvent)
ButtonB_Push = PushButton(17, max_time=1)
ButtonB_Push.setCallback(ButtonB_PushEvent)

# Show startup logo
show_logo("volumio_logo.ppm", oled)
sleep(20)
SetState(STATE_PLAYER)

updateThread = Thread(target=display_update_service)
updateThread.daemon = True
updateThread.start()

def _receive_thread():
    volumioIO.wait()

receive_thread = Thread(target=_receive_thread)
receive_thread.daemon = True
receive_thread.start()

volumioIO.on('pushState', onPushState)
volumioIO.emit('getState')

try:
    while True:
        sleep(0.1)
except KeyboardInterrupt:
    print("Shutting down...")
    GPIO.cleanup()
