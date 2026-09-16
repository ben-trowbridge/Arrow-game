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
        # A piece only needs a clear run of this many cells past its head,
        # not the literal board edge. Requiring a fully-clear lane all the
        # way across a large board makes the odds of any lane staying open
        # collapse exponentially as the board fills up (each extra cell in
        # the lane multiplies in another chance of a blocker), so above a
        # small board this cap is what keeps ~500-cell boards fillable at
        # all. Below it, min(size - 1, 8) just equals the true edge
        # distance, so nothing changes from the original edge-to-edge rule.
        self.exit_window = min(size - 1, 8)
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

    def _biased_direction(self, cell):
        """Pick a direction favoring whichever edge is nearest -- short
        exit lanes are far more likely to end up clear, which matters a
        lot once the board gets big."""
        weighted = [(d, 1.0 / (len(self._lane_cells(cell, d)) + 1) ** 2) for d in DIRS]
        total = sum(w for _, w in weighted)
        r = random.uniform(0, total)
        upto = 0.0
        for d, w in weighted:
            upto += w
            if upto >= r:
                return d
        return weighted[-1][0]

    def _walk(self, start, occupied):
        """One biased random walk from `start`, as long as possible up to
        `max_piece_len`. Returns (cells, path_dirs) where path_dirs[i] is
        the direction of the step from cells[i] to cells[i + 1]."""
        n = self.size
        direction = self._biased_direction(start)
        cells = [start]
        visited = {start}
        path_dirs = []

        for _ in range(self.max_piece_len - 1):
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
                    path_dirs.append(d)
                    direction = d
                    moved = True
                    break
            if not moved:
                break

        return cells, path_dirs

    def _grow_piece(self, start, occupied, tries=3):
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
                    dirs_to_try = sorted(DIRS, key=lambda d: (len(self._lane_cells(head, d)), random.random()))
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

    def _scan_order(self):
        """Process cells from the interior outward, ranked by distance to
        their own nearest edge. Every cell on a straight lane toward some
        edge is strictly closer to that edge than the cell behind it, so
        this ordering guarantees that when a cell is processed, the lane
        toward ITS nearest edge is still completely untouched -- that's
        what makes near-total fill possible at all (a fully random or
        raster order leaves the board full of isolated, unfillable holes
        by the time it's half full), and it naturally spreads all four
        exit directions across the board by geography instead of one
        direction dominating everything, which a single raster sweep
        does (every piece ends up pointing the same way, into whichever
        stretch the sweep hasn't reached yet)."""
        n = self.size
        cells = [(x, y) for y in range(n) for x in range(n)]

        def depth(cell):
            x, y = cell
            return min(x, n - 1 - x, y, n - 1 - y)

        return sorted(cells, key=lambda c: (-depth(c), random.random()))

    def _generate(self, max_attempts=20):
        n = self.size

        best_pieces = None
        best_fill = -1

        for _ in range(max_attempts):
            order = self._scan_order()
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
