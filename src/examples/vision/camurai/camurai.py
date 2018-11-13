import asyncio
import logging

from gpiozero import Button
from aiy.vision.leds import Leds

import common

logging.basicConfig(level=logging.INFO)

BUTTON_PIN = 23
SERVER_ADDRESS = '192.168.0.100'

writers = []

def when_pressed(pressed):
    logging.info('pressed {}'.format(pressed))
    if not writers:
        logging.warning('no connection')
        return
    writers[0].write(bytes([1 if pressed else 0]))

async def led_loop(reader):
    leds = Leds()
    while True:
        r, g, b = await reader.readexactly(3)
        logging.info('{},{},{}'.format(r, g, b))
        if r == g == b == 0: leds.update(Leds.rgb_off())
        else: leds.update(Leds.rgb_on([r, g, b]))

async def main():
    reader, writer = await asyncio.open_connection(SERVER_ADDRESS, common.SERVER_PORT)
    writers.append(writer)
    await asyncio.gather(
        led_loop(reader),
        # TODO button_loop(writer),
    )

# TODO something more async / more threadsafe than this...
button = Button(BUTTON_PIN)
button.when_pressed = lambda: when_pressed(1)
button.when_released = lambda: when_pressed(0)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
