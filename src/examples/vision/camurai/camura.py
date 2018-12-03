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

logging.basicConfig(level=logging.INFO)

BUZZER_PIN = 22
BUTTON_PIN = 23
SERVER_ADDRESS = '192.168.0.100'

CENTER_POWER = 5

class MovingAverage(object):
    def __init__(self, size):
        self._window = collections.deque(maxlen=size)

    def next(self, value):
        self._window.append(value)
        return sum(self._window) / len(self._window)

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

class Camura:
    def __init__(self):
        self.done = threading.Event()
        self.leds = Leds()
        self.color = None
        self.locked = False
        self.writer = None

    def stop(self):
        logging.info('Stopping...')
        self.done.set()

    async def button_pressed(self):
        if self.locked: return
        logging.info('button pressed')
        if not self.writer:
            logging.warning('no connection')
            return
        self.writer.write(common.BUTTON_PRESSED)

    async def camera_loop(self):
        with PiCamera(sensor_mode=4, resolution=(1640, 1232)) as camera:
            face_weight_moving_average = MovingAverage(10)
            with CameraInference(face_detection.model()) as inference:
                logging.info('Model loaded.')
                for i, result in enumerate(inference.run()):
                    if self.color and not self.locked:
                        faces = face_detection.get_faces(result)

                        weight = max((bounding_box_weight(face.bounding_box, result.width, result.height)
                                      for face in faces), default=0)
                        weight **= CENTER_POWER
                        weight = face_weight_moving_average.next(weight)

                        r, g, b = self.color
                        self.leds.update(Leds.rgb_on((r * weight, g * weight, b * weight)))

                    if self.done.is_set(): break
                    await asyncio.sleep(0)

    async def listen(self, reader):
        buzzer = TonePlayer(BUZZER_PIN)
        while True:
            kind = await reader.readexactly(1)
            length, = await reader.readexactly(1)
            data = await reader.readexactly(length)
            logging.info('received kind={} length={} data={}'.format(kind, length, data))

            if kind == common.BUZZER_KIND:
                buzzer.play(data.decode())

            elif kind == common.COLOR_KIND:
                self.color = data or None
                self.locked = False
                if not self.color: self.leds.update(Leds.rgb_off())

            elif kind == common.LOCK_KIND:
                self.locked = True
                if self.color: self.leds.update(Leds.rgb_on(self.color))

            elif kind == common.UNLOCK_KIND:
                self.locked = False

            else:
                logging.warning('unknown kind')

    async def async_main(self):
        reader, self.writer = await asyncio.open_connection(SERVER_ADDRESS, common.SERVER_PORT)
        await asyncio.gather(
            self.listen(reader),
            self.camera_loop()
        )

    def run(self):
        signal.signal(signal.SIGINT, lambda signal, frame: self.stop())
        signal.signal(signal.SIGTERM, lambda signal, frame: self.stop())

        io_loop = asyncio.get_event_loop() # main thread's event loop

        button = Button(BUTTON_PIN) # keep in scope to avoid garbage-collection
        button.when_pressed = lambda: asyncio.run_coroutine_threadsafe(self.button_pressed(), io_loop)

        io_loop.run_until_complete(self.async_main())
        self.stop()

Camura().run()
