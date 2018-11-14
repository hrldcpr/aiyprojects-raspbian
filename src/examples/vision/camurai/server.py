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

writers = {}

def neighbors(x, y):
    return filter(None, [
        x > 0 and (x - 1, y),
        x + 1 < WIDTH and (x + 1, y),
        y > 0 and (x, y - 1),
        y + 1 < HEIGHT and (x, y + 1),
    ])

def write_buzzer(writer, note):
    writer.write(common.BUZZER_KIND + note.encode())

def write_led(writer, r, g, b):
    writer.write(common.LED_KIND + bytes([r, g, b]))

async def ripple(x0, y0):
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
                    writer = writers.get((x, y))
                    if not writer:
                        logging.warning(f'{x},{y} not connected')
                        continue
                    circle.append(writer)

        for writer in circle:
            write_led(writer, 255 // (d + 1)**2, 0, 0)
            write_buzzer(writer, NOTES[d])
        await asyncio.sleep(DELAY)
        for writer in circle:
            write_led(writer, 0, 0, 0)

async def button_loop(x, y, reader):
    while True:
        b, = await reader.readexactly(1)
        logging.info(f'{x},{y} sent {hex(b)}')
        if b: asyncio.create_task(ripple(x, y))

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

        write_led(writer, 0, 255, 255)

        await button_loop(x, y, reader)

    except asyncio.IncompleteReadError:
        logging.warning(f'{x},{y} disconnected')
        writers.pop((x, y), None)

async def main():
    server = await asyncio.start_server(connect, '0.0.0.0', common.SERVER_PORT)
    async with server:
        logging.info(f'listening')
        await server.serve_forever()

asyncio.run(main())
