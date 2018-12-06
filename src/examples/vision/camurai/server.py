import asyncio
import logging

import common
import config
import levels

logging.basicConfig(level=logging.INFO)

ADDRESSES = {
    f'192.168.0.{200+k}': (k % config.WIDTH, k // config.HEIGHT)
    for k in range(config.WIDTH * config.HEIGHT)
}


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
        self.write(common.COLOR_KIND, bytes(map(round, color) or ()))

    def write_lock(self):
        self.write(common.LOCK_KIND)


class Server:
    def __init__(self):
        self.camuras = {
            Camura(x, y)
            for x in range(config.WIDTH) for y in range(config.HEIGHT)
        }
        self.level_index = 0
        self.reset_level()

    def level_up(self):
        self.level_index = (self.level_index + 1) % len(levels.LEVELS)
        self.reset_level()

    def reset_level(self):
        xys = {(c.x, c.y) for c in self.camuras if c.writer}
        self.level = levels.LEVELS[self.level_index](xys)
        logging.info(f'level {self.level_index}')
        for camura in self.camuras:
            self.level.reset_camura(camura)

    async def listen(self, camura, reader):
        while True:
            b = await reader.readexactly(1)
            logging.info(f'{camura.x},{camura.y} sent {b}')
            if b == common.BUTTON_PRESSED:
                success = self.level.button_pressed(camura)
                if success is True:
                    await asyncio.sleep(1)
                    self.level_up()
                elif success is False:
                    self.reset_level()
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
            camura, = (c for c in self.camuras if c.x == x and c.y == y)

            if camura.writer:
                logging.warning(f'{x},{y} already connected')
            else:
                logging.info(f'{x},{y} connected')
            camura.writer = writer

            if self.level.pristine():
                self.level.reset_camura(camura)
            else:
                logging.warning(
                    'camura connected in middle of level, resetting level')
                self.reset_level()

            await self.listen(camura, reader)

        except asyncio.IncompleteReadError:
            logging.warning(f'{x},{y} disconnected')
            if camura: camura.writer = None

    async def run(self):
        server = await asyncio.start_server(self.connect, '0.0.0.0',
                                            common.SERVER_PORT)
        async with server:
            logging.info(f'listening')
            await server.serve_forever()


asyncio.run(Server().run())
