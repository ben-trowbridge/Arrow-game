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


def _vertical_piece(x, run_ys):
    """One vertical stroke: `run_ys` are the contiguous rows (ascending)
    of a single column's run. Piece.cells runs tail-first to the head,
    so bottom-to-top here (head = topmost cell, continuing UP off it)."""
    cells = [(x, y) for y in reversed(run_ys)]
    return Piece(cells, Dir.UP)


def _horizontal_piece(y, run_xs):
    """One horizontal stroke: `run_xs` are the contiguous columns
    (ascending) of a single row's run. Tail-first to the head means
    left-to-right, so the head (last cell, continuing UP off it) is the
    rightmost cell of the run."""
    cells = [(x, y) for x in run_xs]
    return Piece(cells, Dir.UP)


def _decompose_runs(allowed_cells):
    """Break the message's "on" cells into pieces. Horizontal runs of 2+
    cells are claimed first -- a flat stroke like the top of an "I" or
    the crossbar of an "A" reads as one clean bent piece exiting UP from
    its right end, rather than as isolated dots -- and each remaining
    cell is grouped into a vertical run by column, exiting UP from its
    topmost cell, exactly as before.

    Every piece here exits UP, and every piece's own body cells all sit
    at or below its own head's row: trivially true for a horizontal run
    (the whole body shares the head's row) and true by construction for
    a vertical run (the head is its topmost cell). That means sorting
    ALL pieces by head row ascending and firing in that order is always
    valid, regardless of whether a piece's body is a horizontal bar or a
    vertical stroke: anything sitting above a piece's head belongs to
    some other piece whose own head row is strictly smaller, so it always
    fires first. Clear top to bottom.
    """
    by_row = {}
    for x, y in allowed_cells:
        by_row.setdefault(y, []).append(x)

    claimed = set()
    pieces = []
    for y, xs in by_row.items():
        xs.sort()
        run = [xs[0]]
        for x in xs[1:]:
            if x == run[-1] + 1:
                run.append(x)
            else:
                if len(run) >= 2:
                    pieces.append(_horizontal_piece(y, run))
                    claimed.update((rx, y) for rx in run)
                run = [x]
        if len(run) >= 2:
            pieces.append(_horizontal_piece(y, run))
            claimed.update((rx, y) for rx in run)

    by_column = {}
    for x, y in allowed_cells - claimed:
        by_column.setdefault(x, []).append(y)

    for x, ys in by_column.items():
        ys.sort()
        run = [ys[0]]
        for y in ys[1:]:
            if y == run[-1] + 1:
                run.append(y)
            else:
                pieces.append(_vertical_piece(x, run))
                run = [y]
        pieces.append(_vertical_piece(x, run))

    return pieces


def build_message_board(lines):
    """A Board whose arrows spell out `lines` (each an uppercase string)
    instead of a random puzzle -- see _decompose_runs() for how the
    letters' cells become pieces."""
    cells, width, height = text_to_cells(lines)
    size = max(width, height)
    ox = (size - width) // 2
    oy = (size - height) // 2
    allowed_cells = {(x + ox, y + oy) for x, y in cells}

    board = Board(size, allowed_cells=allowed_cells, skip_generate=True)
    pieces = _decompose_runs(allowed_cells)
    for piece in pieces:
        for c in piece.cells:
            board.cell_owner[c] = piece
    board.pieces = pieces
    return board
