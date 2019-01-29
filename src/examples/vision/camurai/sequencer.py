import asyncio
import logging

import mido

import common
import config

logging.basicConfig(level=logging.INFO)

ADDRESSES = {
    f'192.168.0.{200+k}': (k % config.WIDTH, k // config.HEIGHT)
    for k in range(config.WIDTH * config.HEIGHT)
}

ROW_COLORS = [
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
    (0, 0, 255),
]

ROW_NOTES = [
    60,  # 'C4e',
    62,  # 'D4e',
    64,  # 'E4e',
    67,  # 'G4e',
    69,  # 'A4e',
]


class Camura:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.writer = None

    def write(self, kind, data=b''):
        self.writer.write(kind + bytes((len(data), )) + data)

    def write_buzzer(self, notes):
        self.write(common.BUZZER_KIND, notes.encode())

    def write_color(self, color):
        self.write(common.COLOR_KIND,
                   bytes(map(round, color) if color else ()))

    def write_lock(self):
        self.write(common.LOCK_KIND)


class Server:
    def __init__(self):
        self.camuras = {
            Camura(x, y)
            for x in range(config.WIDTH) for y in range(config.HEIGHT)
        }
        self.enabled = set()
        self.midi = mido.open_output()

    def get_camura(self, x, y):
        camura, = (c for c in self.camuras if c.x == x and c.y == y)
        return camura

    def set_column(self, x, active):
        for y in range(config.HEIGHT):
            camura = self.get_camura(x, y)
            if not camura.writer: continue
            if (x, y) in self.enabled:
                self.midi.send(
                    mido.Message(('note_on' if active else 'note_off'),
                                 note=ROW_NOTES[y]))
            else:
                camura.write_color((128, 128, 128) if active else None)
                camura.write_lock()

    async def listen(self, camura, reader):
        while True:
            b = await reader.readexactly(1)
            logging.info(f'{camura.x},{camura.y} sent {b}')
            if b == common.BUTTON_PRESSED:
                xy = (camura.x, camura.y)
                if xy in self.enabled:
                    self.enabled.remove(xy)
                    self.midi.send(
                        mido.Message('note_off', note=ROW_NOTES[camura.y]))
                    camura.write_color(None)
                else:
                    self.enabled.add(xy)
                    camura.write_color(ROW_COLORS[camura.y])
                    camura.write_lock()
            else:
                logging.warning(f'unknown message')

    async def connect(self, reader, writer):
        camura = x = y = None
        try:
            address, port = writer.get_extra_info('peername')
            xy = ADDRESSES.get(address)
            if not xy:
                logging.warning(f'unknown address {address}')
                return
            x, y = xy
            camura = self.get_camura(x, y)

            if camura.writer:
                logging.warning(f'{x},{y} already connected')
            else:
                logging.info(f'{x},{y} connected')
            camura.writer = writer

            await self.listen(camura, reader)

        except asyncio.IncompleteReadError:
            logging.warning(f'{x},{y} disconnected')
            if camura: camura.writer = None

    async def animate(self):
        prev_x = None
        while True:
            for x in reversed(range(config.WIDTH)):
                if prev_x is not None: self.set_column(prev_x, False)
                self.set_column(x, True)
                prev_x = x
                await asyncio.sleep(0.2)

    async def run(self):
        server = await asyncio.start_server(self.connect, '0.0.0.0',
                                            common.SERVER_PORT)
        async with server:
            logging.info(f'listening')
            await asyncio.gather(
                server.serve_forever(),
                self.animate(),
            )


asyncio.run(Server().run())
