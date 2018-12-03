import asyncio
import logging
import random

import common

logging.basicConfig(level=logging.INFO)

WIDTH = 4
HEIGHT = 4
ADDRESSES = {f'192.168.0.{200+k}': (k % WIDTH, k // HEIGHT)
             for k in range(WIDTH * HEIGHT)}

COLORS = [
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
]
NOTES = [
    'C4q',
    'E4q',
    'G4q',
    'C5q'
]
FAIL_NOTES = 'E4e,A3q'

LEVELS = [
    lambda camuras: [(0, 0), (1, 1), (2, 2), (3, 3)],
    lambda camuras: shuffled([xy for xy, camura in camuras.items() if camura.writer])[:len(NOTES)],
]

def shuffled(xs):
    random.shuffle(xs)
    return xs

class Camura:
    def __init__(self):
        self.order = None
        self.writer = None

    def write(self, kind, data=b''):
        self.writer.write(kind + bytes((len(data),)) + data)

    def write_buzzer(self, notes):
        self.write(common.BUZZER_KIND, notes.encode())

    def write_color(self, color):
        self.write(common.COLOR_KIND, bytes(color or ()))

    def write_lock(self):
        self.write(common.LOCK_KIND)

class Server:
    def __init__(self):
        self.camuras = {(x, y): Camura()
                        for x in range(WIDTH) for y in range(HEIGHT)}
        self.level_index = 0
        self.reset_level()

    def reset_camura(self, x, y, camura):
        try:
            camura.order = self.level.index((x, y))
        except ValueError:
            camura.order = None
        if camura.writer:
            camura.write_color(camura.order is not None and COLORS[camura.order])

    def level_up(self):
        self.level_index = (self.level_index + 1) % len(LEVELS)
        self.reset_level()

    def reset_level(self):
        self.level = LEVELS[self.level_index](self.camuras)
        logging.info(f'level {self.level_index}: {self.level}')
        self.order = 0
        for (x, y), camura in self.camuras.items():
            self.reset_camura(x, y, camura)

    async def listen(self, x, y, reader, camura):
        while True:
            b = await reader.readexactly(1)
            if b == common.BUTTON_PRESSED:
                logging.info(f'{x},{y} sent button press')
                if camura.order == self.order:
                    camura.write_lock()
                    camura.write_buzzer(NOTES[camura.order])
                    self.order += 1
                    if self.order >= len(NOTES):
                        await asyncio.sleep(1)
                        self.level_up()
                else:
                    camura.write_buzzer(FAIL_NOTES)
                    self.reset_level()
            else:
                logging.warning(f'{x},{y} sent unknown kind {b}')

    async def connect(self, reader, writer):
        camura = x = y = None
        try:
            address, port = writer.get_extra_info('peername')
            xy = ADDRESSES.get(address)
            if not xy:
                logging.warning(f'unknown address {address}')
                return
            x, y = xy
            camura = self.camuras[(x, y)]

            if camura.writer:
                logging.warning(f'{x},{y} already connected')
            else:
                logging.info(f'{x},{y} connected')
            camura.writer = writer

            if self.order == 0:
                self.reset_camura(x, y, camura)
            else:
                logging.warning('camura connected in middle of level, resetting level')
                self.reset_level()

            await self.listen(x, y, reader, camura)

        except asyncio.IncompleteReadError:
            logging.warning(f'{x},{y} disconnected')
            if camura: camura.writer = None

    async def run(self):
        server = await asyncio.start_server(self.connect, '0.0.0.0', common.SERVER_PORT)
        async with server:
            logging.info(f'listening')
            await server.serve_forever()

asyncio.run(Server().run())
