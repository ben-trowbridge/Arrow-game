"""Static config: window layout, sizing, and the retro color palette."""

# Reference ("design") pixel dimensions at 1.0x scale. The player's chosen
# window-size option (Game.ui_scale, adjustable from the title screen)
# multiplies these -- and every other fixed pixel value in main.py, via
# its S() helper -- at runtime, so the whole window/board/text/effects
# rescale together instead of just the board area.
DESIGN_WINDOW_WIDTH = 760
DESIGN_WINDOW_HEIGHT = 850
DESIGN_BOARD_AREA = 600
DESIGN_BOARD_TOP = 216
FPS = 60

# Default/min sized to comfortably fit inside a single 1920x1080 display
# with room for the taskbar -- the old 1.5x default (on top of an already
# fairly tall board) produced an 1584px-tall window, taller than a
# standard 1080p screen, which is why it wouldn't behave normally with
# window snapping/dragging.
DEFAULT_UI_SCALE = 1.0
MIN_UI_SCALE = 1.0
MAX_UI_SCALE = 2.0
UI_SCALE_STEP = 0.25

BASE_GRID_SIZE = 22
MAX_GRID_SIZE = 26
START_LIVES = 3

# A stopwatch that resets to 0:00 at the start of EVERY board (same as
# lives) and counts up from there; hitting the limit on the current
# board ends the game. Comfortably longer than any single board should
# take, with a deliberate "you get 5 minutes on this one" framing.
GAME_TIME_LIMIT = 300.0
GAME_TIME_WARNING = 270.0  # 4:30 -- clock turns red
GAME_TIME_PULSE_START = 290.0  # 4:50 -- clock starts pulsing, once per second

# A hit costs a heart AND adds time to the clock, pushing the 5:00 cutoff
# closer -- the penalty escalates across however many hearts you have,
# from MIN on the first hit this board to MAX on the last one.
MIN_HIT_PENALTY = 2.0
MAX_HIT_PENALTY = 10.0

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
