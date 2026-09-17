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

# "M"'s crossbar sits in the middle of what would otherwise be two full
# 5-cell verticals -- merging it as a horizontal run splits each side into
# a lone top cell plus a shorter 3-run, which reads worse than just
# leaving it as two long strokes with a single dot between them. Letters
# in this set skip horizontal-run merging entirely.
VERTICAL_ONLY_LETTERS = {"M"}


def _glyph_cells(ch):
    return {
        (col, row)
        for row, line in enumerate(FONT_5ROW[ch])
        for col, v in enumerate(line)
        if v == "#"
    }


def _layout_glyphs(lines, gap=1, line_gap=1):
    """Compute each glyph's (char, x_offset, y_offset) placement across
    all lines, plus the overall (width, height) of the rendered block."""
    placements = []
    max_width = 0
    y_offset = 0
    for line in lines:
        x_offset = 0
        for ch in line:
            placements.append((ch, x_offset, y_offset))
            x_offset += len(FONT_5ROW[ch][0]) + gap
        if line:
            max_width = max(max_width, x_offset - gap)
        y_offset += 5 + line_gap

    total_height = y_offset - line_gap if lines else 0
    return placements, max_width, total_height


def text_to_cells(lines, gap=1, line_gap=1):
    """Render uppercase text lines into a flat set of "on" (x, y) cells,
    plus the overall (width, height). Kept for callers that just want
    the shape, not a piece decomposition."""
    placements, width, height = _layout_glyphs(lines, gap, line_gap)
    cells = {(x + xo, y + yo) for ch, xo, yo in placements for x, y in _glyph_cells(ch)}
    return cells, width, height


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


def _decompose_runs(cells, horizontal_merge=True):
    """Break a glyph's "on" cells into pieces. Horizontal runs of 2+
    cells are claimed first when `horizontal_merge` is set -- a flat
    stroke like the top of an "I" or the crossbar of an "A" reads as one
    clean bent piece exiting UP from its right end, rather than as
    isolated dots -- and each remaining cell is grouped into a vertical
    run by column, exiting UP from its topmost cell.

    Every piece here exits UP, and every piece's own body cells all sit
    at or below its own head's row: trivially true for a horizontal run
    (the whole body shares the head's row) and true by construction for
    a vertical run (the head is its topmost cell). That means sorting
    ALL pieces (across every glyph) by head row ascending and firing in
    that order is always valid, regardless of whether a piece's body is
    a horizontal bar or a vertical stroke: anything sitting above a
    piece's head belongs to some other piece whose own head row is
    strictly smaller, so it always fires first. Clear top to bottom.
    """
    claimed = set()
    pieces = []

    if horizontal_merge:
        by_row = {}
        for x, y in cells:
            by_row.setdefault(y, []).append(x)

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
    for x, y in cells - claimed:
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
    instead of a random puzzle. Each glyph is decomposed independently
    (see _decompose_runs()) so a letter like "M" can opt out of
    horizontal-run merging while the rest still get it, then every
    piece is shifted into its final position in the overall layout."""
    placements, width, height = _layout_glyphs(lines)
    size = max(width, height)
    ox = (size - width) // 2
    oy = (size - height) // 2

    pieces = []
    for ch, xo, yo in placements:
        local_cells = _glyph_cells(ch)
        horizontal_merge = ch not in VERTICAL_ONLY_LETTERS
        for piece in _decompose_runs(local_cells, horizontal_merge=horizontal_merge):
            shifted_cells = [(x + xo + ox, y + yo + oy) for x, y in piece.cells]
            pieces.append(Piece(shifted_cells, piece.direction))

    allowed_cells = {c for p in pieces for c in p.cells}
    board = Board(size, allowed_cells=allowed_cells, skip_generate=True)
    for piece in pieces:
        for c in piece.cells:
            board.cell_owner[c] = piece
    board.pieces = pieces
    # Presentation flags main.py checks for -- there's no time pressure
    # on a tribute board, and clearing it plays a longer, gentler
    # celebration (an angel rising) instead of the usual quick overlay.
    board.infinite_time = True
    board.tribute = True
    return board
