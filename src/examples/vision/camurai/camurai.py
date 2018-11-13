import asyncio
import logging

from gpiozero import Button
from aiy.vision.leds import Leds

import common

logging.basicConfig(level=logging.WARNING)

BUTTON_PIN = 23
SERVER_ADDRESS = '192.168.0.100'

async def led_loop(reader):
    leds = Leds()
    while True:
        r, g, b = await reader.readexactly(3)
        logging.info('{},{},{}'.format(r, g, b))
        if r == g == b == 0: leds.update(Leds.rgb_off())
        else: leds.update(Leds.rgb_on([r, g, b]))

async def button_loop(writer):
    button = Button(BUTTON_PIN)
    button.when_pressed = lambda: writer.write(bytes([1]))
    button.when_released = lambda: writer.write(bytes([0]))
    await asyncio.sleep(1.0)

async def main():
    reader, writer = await asyncio.open_connection(SERVER_ADDRESS, common.SERVER_PORT)
    await asyncio.gather(
        led_loop(reader),
        button_loop(writer),
    )

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()
