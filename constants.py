"""Static config: window layout, sizing, and the retro color palette."""

# Single knob for the whole UI's pixel scale -- every fixed pixel value in
# main.py (fonts, HUD/title/game-over layout, borders, insets) is derived
# from this via the S() helper, so bumping this one number rescales the
# entire window/board/text/etc. together instead of just the board area.
UI_SCALE = 1.5

WINDOW_WIDTH = round(900 * UI_SCALE)
WINDOW_HEIGHT = round(1056 * UI_SCALE)
FPS = 60

BOARD_AREA = round(800 * UI_SCALE)
BOARD_LEFT = (WINDOW_WIDTH - BOARD_AREA) // 2
BOARD_TOP = round(216 * UI_SCALE)

BASE_GRID_SIZE = 22
MAX_GRID_SIZE = 26
START_LIVES = 3
LEVEL_TIME_BASE = 10.0
LEVEL_TIME_PER_PIECE = 1.0
HIT_TIME_PENALTY = 2.0

BASE_SNAKE_LEN = 10
MAX_SNAKE_LEN = 10

# NES-ish palette
BLACK = (10, 10, 16)
WHITE = (244, 244, 244)
BG = (18, 14, 36)
PANEL_BG = (28, 22, 52)
GRID_BG = (34, 28, 64)
GRID_LINE = (58, 48, 96)
BORDER = (90, 76, 150)

UP_COLOR = (248, 96, 96)       # red
RIGHT_COLOR = (120, 224, 120)  # green
DOWN_COLOR = (96, 176, 248)    # blue
LEFT_COLOR = (248, 216, 88)    # yellow

ACCENT = (248, 176, 40)
HEART_FULL = (248, 88, 120)
HEART_EMPTY = (70, 40, 56)
TEXT_DIM = (150, 140, 190)
