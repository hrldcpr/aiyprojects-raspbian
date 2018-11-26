import asyncio
import collections
import logging
import signal
import threading

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
JOY_SCORE_PEAK = 0.50 #0.85
JOY_SCORE_MIN = 0.10
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
        camera.zoom = (0.25, 0.25, 0.5, 0.5)
        joy_score_moving_average = MovingAverage(10)
        prev_joy_score = 0.0
        with CameraInference(face_detection.model()) as inference:
            logging.info('Model loaded.')
            for i, result in enumerate(inference.run()):
                faces = face_detection.get_faces(result)

                joy_score = joy_score_moving_average.next(average_joy_score(faces))
                await joy_detected(joy_score)

                # if joy_score > JOY_SCORE_PEAK > prev_joy_score:
                #     logging.info('joy detected')
                # elif joy_score < JOY_SCORE_MIN < prev_joy_score:
                #     logging.info('joy ended')

                prev_joy_score = joy_score

                if done.is_set(): break

                await asyncio.sleep(0)

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
