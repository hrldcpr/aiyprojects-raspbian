import asyncio
import collections
import logging
import math
import signal
import threading

from aiy.toneplayer import TonePlayer
from aiy.vision.inference import CameraInference
from aiy.vision.leds import Leds
from aiy.vision.models import face_detection
from gpiozero import Button
from picamera import PiCamera

import common

logging.basicConfig(level=logging.DEBUG)

BUZZER_PIN = 22
BUTTON_PIN = 23
JOY_SCORE_PEAK = 0.50 #0.85
JOY_SCORE_MIN = 0.10
ROI = 1 / 3
SERVER_ADDRESS = '192.168.0.100'

done = threading.Event()
writer = None

class MovingAverage(object):
    def __init__(self, size):
        self._window = collections.deque(maxlen=size)

    def next(self, value):
        self._window.append(value)
        return sum(self._window) / len(self._window)

def average_joy_score(faces):
    if faces:
        return sum([face.joy_score for face in faces]) / len(faces)
    return 0.0

def bounding_box_center(bounding_box):
    x, y, w, h = bounding_box
    return x + w/2, y + h/2

def bounding_box_center_distance(bounding_box, width, height):
    x, y = bounding_box_center(bounding_box)
    return math.hypot(x - width/2, y - height/2)

def bounding_box_weight(bounding_box, width, height):
    """varies from 1 at the center to 0 at a corner"""
    d = bounding_box_center_distance(bounding_box, width, height)
    return 1 - d / math.hypot(width / 2, height / 2)

def bounding_box_in_roi(bounding_box, roi, width, height, strict):
    left = width * (1 - roi) / 2
    top = height * (1 - roi) / 2
    right = width - left
    bottom = height - top
    x, y, w, h = bounding_box
    return (all if strict else any)((x > left, x + w < right, y > top, y + h < bottom))

def filter_faces_to_roi(faces, roi, width, height, strict=True):
    return [face for face in faces if bounding_box_in_roi(face.bounding_box, roi, width, height, strict)]

def stop():
    logging.info('Stopping...')
    done.set()

async def button_pressed(pressed):
    logging.info('pressed {}'.format(pressed))
    if not writer:
        logging.warning('no connection')
        return
    writer.write(common.BUTTON_PRESSED if pressed else common.BUTTON_RELEASED)

prev_joy = None
async def joy_detected(joy):
    global prev_joy
    joy = round(joy * 255)
    if joy == prev_joy: return
    prev_joy = joy

    logging.debug('joy {}'.format(joy))
    if not writer:
        logging.warning('no connection')
        return
    writer.write(common.JOY_KIND + bytes([joy]))

async def camera_loop():
    with PiCamera(sensor_mode=4, resolution=(1640, 1232)) as camera:
        joy_score_moving_average = MovingAverage(10)
        prev_joy_score = 0.0
        with CameraInference(face_detection.model()) as inference:
            logging.info('Model loaded.')
            for i, result in enumerate(inference.run()):
                faces = face_detection.get_faces(result)
                if faces:
                    weight = max(bounding_box_weight(face.bounding_box, result.width, result.height)
                                 for face in faces)
                    logging.debug(weight)
                    leds.update(Leds.rgb_on([0, weight*255, weight*255]))
                else:
                    leds.update(Leds.rgb_off())

                # faces = filter_faces_to_roi(faces, ROI, result.width, result.height, strict=False)

                joy_score = joy_score_moving_average.next(average_joy_score(faces))
                # await joy_detected(joy_score)

                # if joy_score > JOY_SCORE_PEAK > prev_joy_score:
                #     logging.info('joy detected')
                # elif joy_score < JOY_SCORE_MIN < prev_joy_score:
                #     logging.info('joy ended')

                prev_joy_score = joy_score

                if done.is_set(): break

                await asyncio.sleep(0)

leds = Leds()
async def listen(reader):
    buzzer = TonePlayer(BUZZER_PIN)
    while True:
        kind = await reader.readexactly(1)

        if kind == common.BUZZER_KIND:
            note = await reader.readexactly(3)
            logging.info('buzzer {}'.format(note))
            buzzer.play(note.decode())

        elif kind == common.LED_KIND:
            r, g, b = await reader.readexactly(3)
            logging.debug('led {},{},{}'.format(r, g, b))
            if r == g == b == 0: leds.update(Leds.rgb_off())
            else: leds.update(Leds.rgb_on([r, g, b]))

def setup_button(button, io_loop):
    button.when_pressed = lambda: asyncio.run_coroutine_threadsafe(button_pressed(True), io_loop)
    button.when_released = lambda: asyncio.run_coroutine_threadsafe(button_pressed(False), io_loop)

async def async_main():
    global writer
    reader, writer = await asyncio.open_connection(SERVER_ADDRESS, common.SERVER_PORT)
    await asyncio.gather(
        listen(reader),
        camera_loop()
    )

def main():
    signal.signal(signal.SIGINT, lambda signal, frame: stop())
    signal.signal(signal.SIGTERM, lambda signal, frame: stop())

    io_loop = asyncio.get_event_loop() # main thread's event loop

    button = Button(BUTTON_PIN) # keep in scope to avoid garbage-collection
    setup_button(button, io_loop)

    # camera_thread = threading.Thread(target=camera_loop, args=(io_loop,))
    # camera_thread.start()

    io_loop.run_until_complete(async_main())
    stop()
    camera_thread.join()

main()
