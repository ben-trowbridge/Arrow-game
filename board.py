"""Puzzle grid + guaranteed-solvable generator.

Generation trick: build the board up one PIECE at a time, in a random
order. Each piece is a short, randomly-bent "snake" of cells (its body)
running tail-first to a head cell that keeps going straight in one
direction, all the way to the board's edge; that entire run must be
clear of every piece placed *so far*. Solving is then just that placement
order played backwards: the last piece placed had a clear exit lane
against everyone placed before it, so it's always the first one safe to
fire, and so on down the line. Every generated board is therefore
solvable -- a careless firing order can still dead-end a piece into a
hit, exactly like the original single-cell version, just with longer,
twistier bodies now.

The exit lane runs the full remaining distance to the board's edge, not
some artificial shorter window -- what a player sees on screen (a clear
runway all the way off the board) is exactly what firing requires. That
does mean a piece deep in the interior needs a genuinely long clear run
in some direction to be placeable at all, which is a harder placement
constraint than a short fixed window would be; the generator compensates
by simply trying many random placement orders per board and keeping the
one that fills the most cells (see `_generate`'s `attempts` loop).
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

# Requiring a genuinely clear run all the way to the board's edge (see
# the module docstring) makes 0.75 unreachable in reasonable time on
# anything but the smallest boards -- generation would burn through
# every attempt without ever hitting it. 0.60 is comfortably achievable
# within a handful of attempts, keeping level load times well under a
# second instead of several.
MIN_FILL_RATIO = 0.60


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
    def __init__(
        self,
        size,
        max_piece_len=3,
        allowed_cells=None,
        min_fill_ratio=None,
        attempts=10,
        exit_window=None,
        prune=True,
        skip_generate=False,
    ):
        self.size = size
        self.max_piece_len = max_piece_len
        # `_lane_cells` stops the moment it steps off the board, so a
        # window this large always reaches the true edge from anywhere on
        # the grid -- `exit_window` stays overridable (e.g. tests) but
        # there's no reason to cap it below the board size any more.
        self.exit_window = size if exit_window is None else exit_window
        # Restricting placement to a specific cell set (rather than every
        # cell in the size x size square) is what lets a Board spell out a
        # fixed shape -- everything outside that set is simply never
        # attempted, so it stays permanently empty padding.
        self.allowed_cells = set(allowed_cells) if allowed_cells is not None else None
        self.min_fill_ratio = MIN_FILL_RATIO if min_fill_ratio is None else min_fill_ratio
        # Pruning drops any 1-cell arrow that doesn't block or get blocked
        # by anything -- exactly right for keeping a puzzle meaningful,
        # but wrong for a fixed shape: a sparse letter like "I" has pixels
        # that trivially don't interact with each other, and we want
        # every one of them drawn regardless.
        self.prune = prune
        self.pieces = []
        self.cell_owner = {}  # (x, y) -> Piece
        if not skip_generate:
            self._generate(max_attempts=attempts)

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
            # earlier body, in case the walk curled back on itself). Any
            # of the 4 directions is fair game at the truncation point,
            # not just the one the walk happened to already be heading --
            # bending once more right at the head lets a piece still fit
            # into a narrow, winding leftover gap where continuing dead
            # straight would immediately hit a wall.
            candidate = None
            for length in range(len(cells), 0, -1):
                head = cells[length - 1]
                dirs_to_try = DIRS[:]
                random.shuffle(dirs_to_try)
                if length > 1 and path_dirs[length - 2] in dirs_to_try:
                    dirs_to_try.remove(path_dirs[length - 2])
                    dirs_to_try.insert(0, path_dirs[length - 2])
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

    def _generate(self, max_attempts=10):
        n = self.size
        if self.allowed_cells is not None:
            all_cells = list(self.allowed_cells)
        else:
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
            if best_fill >= self.min_fill_ratio * len(all_cells):
                break

        self.pieces = best_pieces
        self.cell_owner = {c: p for p in best_pieces for c in p.cells}
        if self.prune:
            self._prune_pointless_singles()
        for _ in range(3):
            if not self._fill_remaining_gaps():
                break
            if self.prune:
                self._prune_pointless_singles()

    def _fill_remaining_gaps(self):
        """A second generation pass over whatever's still empty. New
        pieces are validated against the board as it stands right now,
        which is exactly the same rule the main pass used for every
        piece placed after the first -- so this is really just placing
        a few more pieces last in the same sequence, and reverse-order
        solving still works (fire these newest ones first). Because a
        gap sits between existing arrows, a new piece placed in it is
        much likelier to come out genuinely blocked by a neighbor, and
        since its body can land inside an EXISTING arrow's exit lane,
        that older arrow can end up newly blocked by this one too --
        real two-way interaction instead of isolated filler. Returns
        whether anything was added."""
        n = self.size
        occupied = set(self.cell_owner)
        if self.allowed_cells is not None:
            empty = [c for c in self.allowed_cells if c not in occupied]
        else:
            empty = [(x, y) for y in range(n) for x in range(n) if (x, y) not in occupied]
        random.shuffle(empty)
        added = False
        for start in empty:
            if start in occupied:
                continue
            piece = self._grow_piece(start, occupied)
            if piece is None:
                continue
            self.pieces.append(piece)
            occupied.update(piece.cells)
            for c in piece.cells:
                self.cell_owner[c] = piece
            added = True
        return added

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

    def lane_travel(self, piece):
        """How many cells `piece` can advance before either running off
        the board (lane fully clear) or slamming into the first occupied
        cell in its path -- used to animate a fire attempt (how far to
        slide) before/independent of actually resolving it via fire()."""
        lane = self._lane_cells(piece.head, piece.direction)
        for i, c in enumerate(lane):
            if c in self.cell_owner:
                return i
        return len(lane)

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
