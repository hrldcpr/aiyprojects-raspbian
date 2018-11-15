import asyncio
import logging

from gpiozero import Button
from aiy.vision.leds import Leds
from aiy.toneplayer import TonePlayer

import common

logging.basicConfig(level=logging.INFO)

BUZZER_PIN = 22
BUTTON_PIN = 23
SERVER_ADDRESS = '192.168.0.100'

writers = []
loop = asyncio.get_event_loop() # main thread's event loop

async def button_pressed(pressed=True):
    logging.info('pressed {}'.format(pressed))
    if not writers:
        logging.warning('no connection')
        return
    writers[0].write(bytes([1 if pressed else 0]))

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

def setup_button():
    button = Button(BUTTON_PIN)
    button.when_pressed = lambda: asyncio.run_coroutine_threadsafe(button_pressed(), loop)
    button.when_released = lambda: asyncio.run_coroutine_threadsafe(button_pressed(False), loop)

async def main():
    reader, writer = await asyncio.open_connection(SERVER_ADDRESS, common.SERVER_PORT)
    writers.append(writer)
    await listen(reader)

setup_button()
loop.run_until_complete(main())
