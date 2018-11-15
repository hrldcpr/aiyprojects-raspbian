import asyncio
import collections
import logging

from aiy.toneplayer import TonePlayer
from aiy.vision.inference import CameraInference
from aiy.vision.leds import Leds
from aiy.vision.models import face_detection
from gpiozero import Button
from picamera import PiCamera

import common

logging.basicConfig(level=logging.INFO)

BUZZER_PIN = 22
BUTTON_PIN = 23
SERVER_ADDRESS = '192.168.0.100'

writers = []

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

async def button_pressed(pressed):
    logging.info('pressed {}'.format(pressed))
    if not writers:
        logging.warning('no connection')
        return
    writers[0].write(common.BUTTON_PRESSED if pressed else common.BUTTON_RELEASED)

async def joy_detected(detected):
    logging.info('joy {}'.format(pressed))
    if not writers:
        logging.warning('no connection')
        return
    writers[0].write(common.JOY_DETECTED if detected else common.JOY_ENDED)

def camera_loop(io_loop):
    with PiCamera(sensor_mode=4, resolution=(1640, 1232)) as camera:
        joy_score_moving_average = MovingAverage(10)
        prev_joy_score = 0.0
        with CameraInference(face_detection.model()) as inference:
            logger.info('Model loaded.')
            for i, result in enumerate(inference.run()):
                faces = face_detection.get_faces(result)

                joy_score = joy_score_moving_average.next(average_joy_score(faces))
                animator.update_joy_score(joy_score)

                if joy_score > JOY_SCORE_PEAK > prev_joy_score:
                    asyncio.run_coroutine_threadsafe(joy_detected(True), io_loop)
                elif joy_score < JOY_SCORE_MIN < prev_joy_score:
                    asyncio.run_coroutine_threadsafe(joy_detected(False), io_loop)

                prev_joy_score = joy_score

async def listen(reader):
    leds = Leds()
    buzzer = TonePlayer(BUZZER_PIN)
    while True:
        kind = await reader.readexactly(1)

        if kind == common.BUZZER_KIND:
            note = await reader.readexactly(3)
            logging.info('buzzer {}'.format(note))
            buzzer.play(note.decode())

        elif kind == common.LED_KIND:
            r, g, b = await reader.readexactly(3)
            logging.info('led {},{},{}'.format(r, g, b))
            if r == g == b == 0: leds.update(Leds.rgb_off())
            else: leds.update(Leds.rgb_on([r, g, b]))

def setup_button(button, io_loop):
    button.when_pressed = lambda: asyncio.run_coroutine_threadsafe(button_pressed(True), io_loop)
    button.when_released = lambda: asyncio.run_coroutine_threadsafe(button_pressed(False), io_loop)

async def async_main():
    reader, writer = await asyncio.open_connection(SERVER_ADDRESS, common.SERVER_PORT)
    writers.append(writer)
    await listen(reader)

def main():
    io_loop = asyncio.get_event_loop() # main thread's event loop

    button = Button(BUTTON_PIN) # keep in scope to avoid garbage-collection
    setup_button(button, io_loop)

    camera_thread = new Thread(target=camera_loop, args=(io_loop,))
    camera_thread.start()

    io_loop.run_until_complete(main())
    camera_thread.join()

main()
