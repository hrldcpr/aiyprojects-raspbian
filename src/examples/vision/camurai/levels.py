import asyncio
import random

COLORS = [
    (255, 0, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
]
EMPTY_COLOR = (0, 0, 128)

NOTES = ['C4eE4q', 'E4eG4q', 'G4eC5q', 'C5eC6q']
FAIL_NOTES = 'E4e,A3q'

assert len(COLORS) == len(NOTES)
PROGRESS_DONE = len(COLORS)


class SimpleLevel:
    def __init__(self, order):
        self.order = order
        self.progress = 0

    def pristine(self):
        return self.progress == 0

    def get_order(self, camura):
        try:
            return self.order.index((camura.x, camura.y))
        except ValueError:
            pass

    def reset_camura(self, camura, lock=True):
        if camura.writer:
            order = self.get_order(camura)
            camura.write_color(EMPTY_COLOR if order is None else COLORS[order])
            if lock: camura.write_lock()

    def button_pressed(self, camura):
        """return True, False, or None"""
        order = self.get_order(camura)
        if order == self.progress:
            camura.write_lock()
            camura.write_buzzer(NOTES[order])
            self.progress += 1
            if self.progress == PROGRESS_DONE:
                return True
        else:
            camura.write_buzzer(FAIL_NOTES)
            return False


class Level1(SimpleLevel):
    def __init__(self, xys):
        # TODO limit to connected camuras
        super().__init__([(0, 0), (1, 1), (2, 2), (3, 3)])


class Level2(SimpleLevel):
    def __init__(self, xys):
        xys = list(xys)
        random.shuffle(xys)
        super().__init__(xys[:len(COLORS)])


class Level3(Level1):
    def reset_camura(self, camura):
        super().reset_camura(camura, lock=False)


class Level4(Level2):
    def reset_camura(self, camura):
        super().reset_camura(camura, lock=False)


LEVELS = [
    Level1,
    Level2,
    Level3,
    Level4,
]
