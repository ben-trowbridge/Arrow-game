"""Puzzle grid + guaranteed-solvable generator.

Generation trick: build the board up one PIECE at a time, in a random
order. Each piece is a short, randomly-bent "snake" of cells (its body)
running tail-first to a head cell that keeps going straight in one
direction for a bounded "exit window" of cells; that stretch must be
clear of every piece placed *so far*. Solving is then just that placement
order played backwards: the last piece placed had a clear exit lane
against everyone placed before it, so it's always the first one safe to
fire, and so on down the line. Every generated board is therefore
solvable -- a careless firing order can still dead-end a piece into a
hit, exactly like the original single-cell version, just with longer,
twistier bodies now.

The exit window is deliberately a small, FIXED distance rather than the
literal board edge. A piece near the edge naturally needs only a short
clear run to get off the board, while a piece in the middle of a large
board would need a run of a dozen-plus clear cells -- so with an
edge-to-edge rule, cells near the border are trivially, permanently safe
(nothing can ever re-occupy a lane once the board starts getting
cleared), while the interior is nearly unplaceable. Capping the window
at a small constant makes every cell face the same-sized challenge
regardless of where it sits, so a solvable order is required everywhere
on the board, not just away from the edges.
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

MIN_FILL_RATIO = 0.75


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


EXIT_WINDOW = 4


class Board:
    def __init__(self, size, max_piece_len=3):
        self.size = size
        self.max_piece_len = max_piece_len
        self.exit_window = min(size - 1, EXIT_WINDOW)
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
        for _ in range(self.exit_window):
            if not (0 <= cx < n and 0 <= cy < n):
                break
            cells.append((cx, cy))
            cx += dx
            cy += dy
        return cells

    def _walk(self, start, occupied):
        """One biased random walk from `start`, as long as possible up to
        `max_piece_len`. Returns (cells, path_dirs) where path_dirs[i] is
        the direction of the step from cells[i] to cells[i + 1]. The
        initial direction is plain uniform-random -- NOT biased toward
        whichever edge is nearest -- so a piece's exit direction doesn't
        correlate with where it sits on the board; that correlation is
        exactly what made every arrow near a given edge the same color
        and trivially safe."""
        n = self.size
        direction = random.choice(DIRS)
        cells = [start]
        visited = {start}
        path_dirs = []

        for _ in range(self.max_piece_len - 1):
            x, y = cells[-1]
            candidates = list(DIRS)
            random.shuffle(candidates)
            if random.random() < 0.75 and direction in candidates:
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
                    path_dirs.append(d)
                    direction = d
                    moved = True
                    break
            if not moved:
                break

        return cells, path_dirs

    def _grow_piece(self, start, occupied, tries=8):
        best = None
        for _ in range(tries):
            cells, path_dirs = self._walk(start, occupied)

            # Backtrack from the full walk to the longest prefix whose
            # straight exit lane is clear (of other pieces and of its own
            # earlier body, in case the walk curled back on itself).
            candidate = None
            for length in range(len(cells), 0, -1):
                head = cells[length - 1]
                if length == 1:
                    dirs_to_try = DIRS[:]
                    random.shuffle(dirs_to_try)
                else:
                    dirs_to_try = [path_dirs[length - 2]]
                own_body = set(cells[:length])
                for d in dirs_to_try:
                    lane = self._lane_cells(head, d)
                    if not any(c in occupied or c in own_body for c in lane):
                        candidate = Piece(cells[:length], d)
                        break
                if candidate is not None:
                    break

            if candidate is not None and (best is None or len(candidate.cells) > len(best.cells)):
                best = candidate
            if best is not None and len(best.cells) == self.max_piece_len:
                break
        return best

    def _generate(self, max_attempts=20):
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
        self._prune_pointless_singles()

    def _prune_pointless_singles(self):
        """A lone 1-cell arrow only reads as intentional if it's actually
        part of the puzzle -- either something else has to be cleared
        before it can fire, or it's sitting in another piece's own exit
        lane. One that's already fireable AND blocks nothing is just
        leftover filler from a walk that failed to extend anywhere;
        pull it and leave the cell empty instead of cluttering the board
        with single cells that serve no purpose. Since this only removes
        pieces that nothing depends on, it can't affect any other
        piece's own validity."""
        other_lanes = [(other, set(self._lane_cells(other.head, other.direction))) for other in self.pieces]
        for piece in list(self.pieces):
            if len(piece.cells) != 1:
                continue
            cell = piece.cells[0]
            is_blocked = any(c in self.cell_owner for c in self._lane_cells(cell, piece.direction))
            if is_blocked:
                continue
            blocks_someone = any(other is not piece and cell in lane for other, lane in other_lanes)
            if blocks_someone:
                continue
            del self.cell_owner[cell]
            self.pieces.remove(piece)

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
