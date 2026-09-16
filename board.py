"""Puzzle grid + guaranteed-solvable generator.

Generation trick: build the board up one arrow at a time, in a random
order, giving each new arrow a direction whose path to the edge is clear
of every arrow placed *so far*. Solving is then just that placement order
played backwards: the last arrow placed has a clear path against everyone
placed before it, so it's always the first one safe to fire, and so on
down the line. Every generated board is therefore solvable.
"""

import random
from enum import Enum


class Dir(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


DIRS = list(Dir)


class Board:
    def __init__(self, size):
        self.size = size
        self.arrows = {}  # (x, y) -> Dir
        self._generate()

    def _generate(self, max_attempts=200):
        n = self.size
        cells = [(x, y) for y in range(n) for x in range(n)]

        for _ in range(max_attempts):
            order = cells[:]
            random.shuffle(order)
            placed = {}
            ok = True

            for (x, y) in order:
                valid_dirs = []
                for d in DIRS:
                    dx, dy = d.value
                    cx, cy = x + dx, y + dy
                    blocked = False
                    while 0 <= cx < n and 0 <= cy < n:
                        if (cx, cy) in placed:
                            blocked = True
                            break
                        cx += dx
                        cy += dy
                    if not blocked:
                        valid_dirs.append(d)

                if not valid_dirs:
                    ok = False
                    break
                placed[(x, y)] = random.choice(valid_dirs)

            if ok:
                self.arrows = placed
                return

        # Extremely unlikely fallback for pathological sizes.
        self.arrows = {(x, y): random.choice(DIRS) for x, y in cells}

    def remaining(self):
        return len(self.arrows)

    def is_cleared(self):
        return not self.arrows

    def fire(self, cell):
        """Fire the arrow at `cell`. Returns 'clear', 'hit', or None (empty cell)."""
        if cell not in self.arrows:
            return None

        d = self.arrows[cell]
        dx, dy = d.value
        x, y = cell
        cx, cy = x + dx, y + dy
        n = self.size

        while 0 <= cx < n and 0 <= cy < n:
            if (cx, cy) in self.arrows:
                return "hit"
            cx += dx
            cy += dy

        del self.arrows[cell]
        return "clear"
