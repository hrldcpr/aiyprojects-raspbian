import asyncio
import logging

import common

logging.basicConfig(level=logging.INFO)

WIDTH = 4
HEIGHT = 4

ADDRESSES = {f'192.168.0.{200+k}': (k % WIDTH, k // HEIGHT) for k in range(16)}

writers = {}

def neighbors(x, y):
    return filter(None, [
        x > 0 and (x - 1, y),
        x + 1 < WIDTH and (x + 1, y),
        y > 0 and (x, y - 1),
        y + 1 < HEIGHT and (x, y + 1),
    ])

async def leds_loop():
    while True:
        for y in range(HEIGHT):
            for x in range(WIDTH):
                writer = writers.get((x, y))
                if not writer:
                    logging.warning(f'{x},{y} not connected')
                    await asyncio.sleep(1.0)
                    continue
                logging.info(f'{x},{y}')
                writer.write(bytes([0, 255, 255]))
                await asyncio.sleep(1.0)
                writer.write(bytes([0, 0, 0]))

async def button_loop(reader):
    while True:
        b, = await reader.readexactly(1)
        logging.info(f'{x},{y} sent {hex(b)}')

async def connect(reader, writer):
    x = y = None
    try:
        address, port = writer.get_extra_info('peername')
        xy = ADDRESSES.get(address)
        if not xy:
            logging.warning(f'unknown address {address}')
            return
        x, y = xy

        if (x, y) in writers:
            logging.warn(f'{x},{y} already connected')
            return
        logging.info(f'{x},{y} connected')
        writers[(x, y)] = writer

        await button_loop(reader)

    except asyncio.IncompleteReadError:
        logging.warning(f'{x},{y} disconnected')
        writers.pop((x, y), None)

async def main():
    server = await asyncio.start_server(connect, '0.0.0.0', common.SERVER_PORT)
    async with server:
        logging.info(f'listening')
        await asyncio.gather(
            server.serve_forever(),
            leds_loop(),
        )

asyncio.run(main())
