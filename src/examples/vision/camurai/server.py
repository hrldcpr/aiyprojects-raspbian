import asyncio
import logging

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
    'C5q',
]
WIN_NOTES = 'C4eE4eG4eC5e'
LOSE_NOTES = 'E4qE4q'

LEVELS = [
    [(0, 0), (1, 1), (2, 2), (3, 3)],
    # TODO randomly choose four camuras for level 2
]

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

    def write_lock(self, locked=True):
        self.write(common.LOCK_KIND if locked else common.UNLOCK_KIND)

def reset_camura(x, y, camura, level):
    try:
        camura.order = level.index((x, y))
    except ValueError:
        camura.order = None
    if camura.writer:
        camura.write_color(camura.order is not None and COLORS[camura.order])
        camura.write_lock(False)

class Server:
    def __init__(self):
        self.camuras = {(x, y): Camura()
                        for x in range(WIDTH) for y in range(HEIGHT)}
        self.level = 0
        self.reset_level()

    def level_up(self):
        self.level = (self.level + 1) % len(LEVELS)
        reset_level()

    def reset_level(self):
        self.order = 0
        level = LEVELS[self.level]
        for (x, y), camura in self.camuras.items():
            reset_camura(x, y, camura, level)

    def order_up(self, camura):
        camura.write_buzzer(NOTES[camura.order])
        camura.write_lock()
        self.order += 1
        if self.order >= len(NOTES):
            camura.write_buzzer(WIN_NOTES)
            self.level_up()

    async def listen(self, x, y, reader, camura):
        while True:
            b = await reader.readexactly(1)
            if b == common.BUTTON_PRESSED:
                logging.info(f'{x},{y} sent button press')
                if camura.order == self.order:
                    self.order_up(camura)
                else:
                    camura.write_buzzer(LOSE_NOTES)
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

            reset_camura(x, y, camura, LEVELS[self.level])

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
