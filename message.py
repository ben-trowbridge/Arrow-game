"""Renders short uppercase text into a set of "on" cells using a tiny
5-row pixel font, for building a Board that spells out a fixed message
instead of a random puzzle -- see build_message_board().
"""

from board import Board, Dir, Piece

# Each glyph is 5 rows tall; row width varies (letters are 3 wide, the
# period and space are narrower). '#' = on, '.' = off.
FONT_5ROW = {
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "E": ["###", "#..", "##.", "#..", "###"],
    "M": ["#.#", "###", "#.#", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    ".": [".", ".", ".", ".", "#"],
    " ": ["..", "..", "..", "..", ".."],
}


def text_to_cells(lines, gap=1, line_gap=1):
    """Render uppercase text lines into a set of "on" (x, y) cells,
    left-aligned line by line, plus the overall (width, height)."""
    cells = set()
    max_width = 0
    y_offset = 0
    for line in lines:
        glyphs = [FONT_5ROW[ch] for ch in line]
        x_offset = 0
        for glyph in glyphs:
            for row_idx, row in enumerate(glyph):
                for col_idx, ch in enumerate(row):
                    if ch == "#":
                        cells.add((x_offset + col_idx, y_offset + row_idx))
            x_offset += len(glyph[0]) + gap
        max_width = max(max_width, x_offset - gap if glyphs else 0)
        y_offset += 5 + line_gap

    total_height = y_offset - line_gap if lines else 0
    return cells, max_width, total_height


def _run_piece(x, run_ys):
    """One vertical stroke: `run_ys` are the contiguous rows (ascending)
    of a single column's run. Piece.cells runs tail-first to the head,
    so bottom-to-top here (head = topmost cell, continuing UP off it)."""
    cells = [(x, y) for y in reversed(run_ys)]
    return Piece(cells, Dir.UP)


def build_message_board(lines):
    """A Board whose arrows spell out `lines` (each an uppercase string)
    instead of a random puzzle. Each letter's own vertical strokes come
    out as single multi-cell arrows -- e.g. "Y" is two 2-cell strokes and
    one 3-cell stroke, matching its shape -- rather than a scatter of
    independent 1-cell arrows, by grouping each column's "on" cells into
    maximal contiguous runs and giving each run one piece.

    All of them point UP. A run's own cells never block its exit (a run
    is maximal, so the cell right above its top is never part of it),
    but two *different* runs in the same column can still be close
    enough for one's exit lane to reach into the other -- so this isn't
    order-independent, just simple: clear top to bottom, column by
    column (independent columns can be done in any order relative to
    each other), and every run's lane is guaranteed already clear by
    the time you get to it.
    """
    cells, width, height = text_to_cells(lines)
    size = max(width, height)
    ox = (size - width) // 2
    oy = (size - height) // 2
    allowed_cells = {(x + ox, y + oy) for x, y in cells}

    board = Board(size, allowed_cells=allowed_cells, skip_generate=True)

    by_column = {}
    for x, y in allowed_cells:
        by_column.setdefault(x, []).append(y)

    pieces = []
    for x, ys in by_column.items():
        ys.sort()
        run = [ys[0]]
        for y in ys[1:]:
            if y == run[-1] + 1:
                run.append(y)
            else:
                pieces.append(_run_piece(x, run))
                run = [y]
        pieces.append(_run_piece(x, run))

    for piece in pieces:
        for c in piece.cells:
            board.cell_owner[c] = piece
    board.pieces = pieces
    return board
