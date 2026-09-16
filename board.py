"""Puzzle grid + guaranteed-solvable generator.

Generation trick: build the board up one PIECE at a time, in a random
order. Each piece is a short, randomly-bent "snake" of cells (its body)
running tail-first to a head cell that keeps going straight off-board in
one direction; that straight lane from the head to the board edge must be
clear of every piece placed *so far*. Solving is then just that placement
order played backwards: the last piece placed has a clear lane against
everyone placed before it, so it's always the first one safe to fire, and
so on down the line. Every generated board is therefore solvable -- a
careless firing order can still dead-end a piece into a hit, exactly like
the original single-cell version, just with longer, twistier bodies now.
"""

import random
from enum import Enum


class Dir(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


DIRS = list(Dir)
DIR_FROM_DELTA = {d.value: d for d in DIRS}

MIN_FILL_RATIO = 0.85


class Piece:
    """A bent multi-cell arrow. `cells` runs tail-first to `cells[-1]`,
    the head, which keeps going straight off-board in `direction`."""

    __slots__ = ("cells", "direction")

    def __init__(self, cells, direction):
        self.cells = cells
        self.direction = direction

    @property
    def head(self):
        return self.cells[-1]

    def local_direction(self, index):
        """Which way segment `index` visually points: toward the next
        cell in the body, or `direction` for the head itself."""
        if index == len(self.cells) - 1:
            return self.direction
        x, y = self.cells[index]
        nx, ny = self.cells[index + 1]
        return DIR_FROM_DELTA[(nx - x, ny - y)]


class Board:
    def __init__(self, size, max_piece_len=3):
        self.size = size
        self.max_piece_len = max_piece_len
        self.pieces = []
        self.cell_owner = {}  # (x, y) -> Piece
        self._generate()

    # -- generation ---------------------------------------------------

    def _lane_cells(self, head, direction):
        dx, dy = direction.value
        n = self.size
        x, y = head
        cx, cy = x + dx, y + dy
        cells = []
        while 0 <= cx < n and 0 <= cy < n:
            cells.append((cx, cy))
            cx += dx
            cy += dy
        return cells

    def _attempt_walk(self, start, occupied, length):
        n = self.size
        direction = random.choice(DIRS)
        cells = [start]
        visited = {start}

        for _ in range(length - 1):
            x, y = cells[-1]
            candidates = list(DIRS)
            random.shuffle(candidates)
            if random.random() < 0.55 and direction in candidates:
                candidates.remove(direction)
                candidates.insert(0, direction)
            moved = False
            for d in candidates:
                dx, dy = d.value
                nx, ny = x + dx, y + dy
                if (
                    0 <= nx < n
                    and 0 <= ny < n
                    and (nx, ny) not in visited
                    and (nx, ny) not in occupied
                ):
                    cells.append((nx, ny))
                    visited.add((nx, ny))
                    direction = d
                    moved = True
                    break
            if not moved:
                return None

        head = cells[-1]
        lane = self._lane_cells(head, direction)
        if any(c in occupied or c in visited for c in lane):
            return None
        return Piece(cells, direction)

    def _grow_piece(self, start, occupied):
        for length in range(self.max_piece_len, 1, -1):
            for _ in range(6):
                piece = self._attempt_walk(start, occupied, length)
                if piece is not None:
                    return piece

        # Guaranteed single-cell fallback, same as the original arrows.
        dirs = DIRS[:]
        random.shuffle(dirs)
        for d in dirs:
            lane = self._lane_cells(start, d)
            if not any(c in occupied for c in lane):
                return Piece([start], d)
        return None

    def _generate(self, max_attempts=60):
        n = self.size
        all_cells = [(x, y) for y in range(n) for x in range(n)]

        best_pieces = None
        best_fill = -1

        for _ in range(max_attempts):
            order = all_cells[:]
            random.shuffle(order)
            occupied = set()
            pieces = []

            for start in order:
                if start in occupied:
                    continue
                piece = self._grow_piece(start, occupied)
                if piece is None:
                    continue
                pieces.append(piece)
                occupied.update(piece.cells)

            if len(occupied) > best_fill:
                best_fill = len(occupied)
                best_pieces = pieces
            if best_fill >= MIN_FILL_RATIO * n * n:
                break

        self.pieces = best_pieces
        self.cell_owner = {c: p for p in best_pieces for c in p.cells}

    # -- queries / actions ----------------------------------------------

    def remaining(self):
        return len(self.pieces)

    def is_cleared(self):
        return not self.pieces

    def fire(self, cell):
        """Fire the piece at `cell`. Returns 'clear', 'hit', or None."""
        piece = self.cell_owner.get(cell)
        if piece is None:
            return None

        lane = self._lane_cells(piece.head, piece.direction)
        if any(c in self.cell_owner for c in lane):
            return "hit"

        for c in piece.cells:
            del self.cell_owner[c]
        self.pieces.remove(piece)
        return "clear"
