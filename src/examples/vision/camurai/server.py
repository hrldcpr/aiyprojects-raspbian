import asyncio
import logging

import common

logging.basicConfig(level=logging.INFO)

WIDTH = 4
HEIGHT = 4
DELAY = 0.2 # seconds
NOTES = ['C4q', 'D4q', 'E4q', 'F4q', 'G4q', 'A5q', 'B5q', 'C5q']

ADDRESSES = {f'192.168.0.{200+k}': (k % WIDTH, k // HEIGHT)
             for k in range(WIDTH * HEIGHT)}

class Camura:
    def __init__(self, writer):
        self.writer = writer

    def write_buzzer(self, note):
        self.writer.write(common.BUZZER_KIND + note.encode())

    def write_led(self, r, g, b):
        self.writer.write(common.LED_KIND + bytes([r, g, b]))

class Server:
    def __init__(self):
        self.camuras = {}

    async def ripple(self, x0, y0):
        for d in range(WIDTH + HEIGHT):
            circle = []
            for dx in range(d + 1):
                dy = d - dx
                for dx in {-dx, dx}:
                    x = x0 + dx
                    if x < 0 or x >= WIDTH: continue
                    for dy in {-dy, dy}:
                        y = y0 + dy
                        if y < 0 or y >= HEIGHT: continue
                        camura = self.camuras.get((x, y))
                        if not camura:
                            logging.warning(f'{x},{y} not connected')
                            continue
                        circle.append(camura)

            for camura in circle:
                camura.write_led(255 // (d + 1)**2, 0, 0)
                camura.write_buzzer(NOTES[d])
            await asyncio.sleep(DELAY)
            for camura in circle:
                camura.write_led(0, 0, 0)

    async def listen(self, x, y, reader, camura):
        while True:
            b = await reader.readexactly(1)
            if b == common.BUTTON_PRESSED:
                logging.info(f'{x},{y} sent button press')
                asyncio.create_task(self.ripple(x, y))
            elif b == common.BUTTON_RELEASED:
                logging.info(f'{x},{y} sent button release')
            elif b == common.JOY_KIND:
                joy, = await reader.readexactly(1)
                logging.debug(f'{x},{y} sent joy {joy}')
                camura.write_led(0, joy, joy)
            else:
                logging.warning(f'{x},{y} sent unknown kind {b}')

    async def connect(self, reader, writer):
        x = y = None
        try:
            address, port = writer.get_extra_info('peername')
            xy = ADDRESSES.get(address)
            if not xy:
                logging.warning(f'unknown address {address}')
                return
            x, y = xy

            if (x, y) in self.camuras:
                logging.warning(f'{x},{y} already connected')
            logging.info(f'{x},{y} connected')
            camura = Camura(writer)
            self.camuras[(x, y)] = camura

            camura.write_led(0, 255, 255)

            await self.listen(x, y, reader, camura)

        except asyncio.IncompleteReadError:
            logging.warning(f'{x},{y} disconnected')
            self.camuras.pop((x, y), None)

    async def run(self):
        server = await asyncio.start_server(self.connect, '0.0.0.0', common.SERVER_PORT)
        async with server:
            logging.info(f'listening')
            await server.serve_forever()

asyncio.run(Server().run())
