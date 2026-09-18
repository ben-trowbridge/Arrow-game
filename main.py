"""ARROW BLAST -- an 8-bit style arrow-clearing puzzle.

Click an arrow. If its path to the edge of the board is clear, it blasts
off screen. If it slams into another arrow, you lose one of your three
lives. Clear every arrow to advance to a bigger, tougher board.
"""

import json
import math
import os
import random
import sys
from enum import Enum, auto

import pygame

from audio import SoundEngine
from board import DIR_FROM_DELTA, Board
from message import build_message_board
from constants import (
    ACCENT,
    BASE_GRID_SIZE,
    BASE_SNAKE_LEN,
    BG,
    BORDER,
    DEFAULT_UI_SCALE,
    DESIGN_BOARD_AREA,
    DESIGN_BOARD_TOP,
    DESIGN_WINDOW_HEIGHT,
    DESIGN_WINDOW_WIDTH,
    FPS,
    GAME_TIME_LIMIT,
    GAME_TIME_PULSE_START,
    GAME_TIME_WARNING,
    GRID_BG,
    GRID_LINE,
    HEART_EMPTY,
    HEART_FULL,
    MAX_GRID_SIZE,
    MAX_HIT_PENALTY,
    MAX_SNAKE_LEN,
    MAX_UI_SCALE,
    MIN_HIT_PENALTY,
    MIN_UI_SCALE,
    PANEL_BG,
    START_LIVES,
    TEXT_DIM,
    UI_SCALE_STEP,
    WHITE,
)
from sprites import ARROW_COLORS, Angel, FloatingText, draw_arrow, draw_heart, spawn_burst

CELEBRATIONS = ["YEAH!", "BOOM!", "RADICAL!", "NICE!", "WHOA!", "BLASTED!", "ZOOM!"]
SEED_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MESSAGE_SEEDS = {
    "SAMGARMN": ["YOU ARE", "MISSED."],
}

FIRE_CELLS_PER_SECOND = 18.0


def _path_point(path, t, exit_dir):
    """Continuous position along `path` (a list of grid cells) at
    fractional distance `t` cells from path[0] -- interpolating linearly
    between consecutive path cells, and extrapolating straight in
    `exit_dir` once `t` runs past the end of the recorded path (used once
    a segment has moved beyond the piece's own lane cells)."""
    last = len(path) - 1
    if t <= 0:
        return path[0]
    if t >= last:
        x1, y1 = path[last]
        extra = t - last
        return (x1 + exit_dir[0] * extra, y1 + exit_dir[1] * extra)
    idx0 = int(t)
    frac = t - idx0
    x0, y0 = path[idx0]
    x1, y1 = path[idx0 + 1]
    return (x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac)


def _path_direction(path, t, exit_dir):
    """Which way the segment sitting at path-position `t` is currently
    heading -- the step direction into the next path cell, or `exit_dir`
    once past the recorded path. Beyond the head's own bend, this is
    always `exit_dir` and never the body's approach direction into the
    head, since a piece's exit direction can differ from how its body
    happened to reach the head cell."""
    last = len(path) - 1
    idx0 = int(t)
    if idx0 >= last:
        return exit_dir
    x0, y0 = path[idx0]
    x1, y1 = path[idx0 + 1]
    return (x1 - x0, y1 - y0)


class FiringAnimation:
    """Purely visual: a fired piece slithers along its own body's path
    like classic Snake -- the head leads off the end of the piece's bent
    shape into its exit lane, and each trailing segment follows exactly
    the same route the segment ahead of it just took, straightening out
    through any corners rather than sliding sideways as a rigid block.

    A clear keeps going until the whole piece (including the tail) has
    passed the board's edge. A hit advances only as far as whatever
    blocked it, then retraces the identical path back to rest at the
    same speed. The actual game-logic outcome (score/lives/board state)
    is already resolved by the time this is created -- this only tracks
    how far along the animation is."""

    def __init__(self, piece, lane_cells, travel_distance, outcome):
        self.piece = piece
        self.outcome = outcome
        self.exit_dir = piece.direction.value
        self.path = list(piece.cells) + list(lane_cells)
        self.n = len(piece.cells)
        if outcome == "clear":
            # Every segment, including the tail, must pass the last lane
            # cell to be fully off the board -- the tail (segment 0)
            # reaches path-position `progress`, so progress needs to
            # reach the full path length for the whole piece to clear.
            self.forward_target = len(self.path)
        else:
            self.forward_target = max(travel_distance, 0.5)
        self.progress = 0.0
        self.phase = "forward"
        self.done = False

    def update(self, dt):
        step = FIRE_CELLS_PER_SECOND * dt
        if self.phase == "forward":
            self.progress = min(self.forward_target, self.progress + step)
            if self.progress >= self.forward_target:
                if self.outcome == "clear":
                    self.done = True
                else:
                    self.phase = "return"
        else:
            self.progress = max(0.0, self.progress - step)
            if self.progress <= 0.0:
                self.done = True
        return not self.done

    def segment_point(self, i):
        return _path_point(self.path, self.progress + i, self.exit_dir)

    def segment_direction(self, i):
        return _path_direction(self.path, self.progress + i, self.exit_dir)

SCOREBOARD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scoreboard.json")
SCOREBOARD_SIZE = 10
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def load_scoreboard():
    try:
        with open(SCOREBOARD_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (OSError, ValueError):
        pass
    return []


def save_scoreboard(entries):
    try:
        with open(SCOREBOARD_PATH, "w") as f:
            json.dump(entries, f, indent=2)
    except OSError:
        pass


def load_settings():
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_settings(settings):
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


class State(Enum):
    TITLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    LEVEL_CLEAR = auto()
    GAME_OVER = auto()
    SCOREBOARD = auto()
    SETTINGS = auto()


class Game:
    def __init__(self):
        pygame.init()
        self.ui_scale = DEFAULT_UI_SCALE
        self._apply_scale()
        pygame.display.set_caption("ARROW BLAST")
        self.clock = pygame.time.Clock()

        self.sound = SoundEngine()
        settings = load_settings()
        self.sound.apply_settings(
            settings.get("sfx_enabled", True),
            settings.get("sfx_volume", 0.8),
            settings.get("music_enabled", True),
            settings.get("music_volume", 0.5),
            settings.get("music_track", 0),
        )

        self.particles = []
        self.texts = []
        self.angel = None
        self.firing_animations = []
        self.shake_timer = 0.0
        self.level_clear_timer = 0.0

        self.state = State.TITLE
        self.level = 1
        self.score = 0
        self.lives = START_LIVES
        self.board = Board(BASE_GRID_SIZE)
        self.elapsed = 0.0
        self.hits_this_board = 0
        self.total_time = 0.0
        self.seed = None
        self.seed_input = ""

        self.pause_selection = 0
        self.pause_buttons = []
        self.scoreboard_button = None
        self.settings_button = None
        self.scoreboard = load_scoreboard()

        self.settings_selection = 0
        self.settings_rows = []
        self.settings_return_state = State.TITLE

    def S(self, px):
        """Scale a fixed pixel value (font size, layout offset, border
        width, ...) by the player's chosen window-size option, so every
        hardcoded position in this file grows or shrinks together with
        the window/board dimensions."""
        return round(px * self.ui_scale)

    def _apply_scale(self):
        """(Re)compute every scale-dependent dimension and resize the
        actual window/fonts/board surface to match -- called once at
        startup and again whenever the player changes the window-size
        option from the title screen."""
        self.window_width = round(DESIGN_WINDOW_WIDTH * self.ui_scale)
        self.window_height = round(DESIGN_WINDOW_HEIGHT * self.ui_scale)
        self.board_area = round(DESIGN_BOARD_AREA * self.ui_scale)
        self.board_top = round(DESIGN_BOARD_TOP * self.ui_scale)
        self.board_left = (self.window_width - self.board_area) // 2

        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        self.font_small = pygame.font.SysFont("couriernew", self.S(18), bold=True)
        self.font_med = pygame.font.SysFont("couriernew", self.S(26), bold=True)
        self.font_big = pygame.font.SysFont("couriernew", self.S(54), bold=True)
        self.board_surface = pygame.Surface((self.board_area, self.board_area))
        self.board_dirty = True

    def adjust_scale(self, delta):
        new_scale = max(MIN_UI_SCALE, min(MAX_UI_SCALE, round(self.ui_scale + delta, 2)))
        if new_scale != self.ui_scale:
            self.ui_scale = new_scale
            self._apply_scale()

    # -- level / game flow ------------------------------------------------

    def grid_size_for_level(self, level):
        return min(MAX_GRID_SIZE, BASE_GRID_SIZE + level - 1)

    def snake_len_for_level(self, level):
        return min(MAX_SNAKE_LEN, BASE_SNAKE_LEN + (level - 1) // 2)

    def start_new_game(self, seed=None):
        # The same seed always produces the same board, level after
        # level, because everything in board.py draws from this same
        # global `random` stream -- seeding it once here is enough to
        # make the whole run reproducible.
        seed = (seed or "".join(random.choices(SEED_CHARS, k=8))).upper()
        random.seed(seed)
        self.seed = seed
        self.seed_input = ""

        self.level = 1
        self.score = 0
        self.lives = START_LIVES
        self.elapsed = 0.0
        self.hits_this_board = 0
        self.total_time = 0.0
        if seed in MESSAGE_SEEDS:
            self.board = build_message_board(MESSAGE_SEEDS[seed])
        else:
            self.board = Board(self.grid_size_for_level(self.level), self.snake_len_for_level(self.level))
        self.particles.clear()
        self.texts.clear()
        self.angel = None
        self.firing_animations = []
        self.board_dirty = True
        self.state = State.PLAYING

    def advance_level(self):
        self.level += 1
        self.board = Board(self.grid_size_for_level(self.level), self.snake_len_for_level(self.level))
        self.angel = None
        self.firing_animations = []
        self.lives = START_LIVES
        self.elapsed = 0.0
        self.hits_this_board = 0
        self.board_dirty = True
        self.state = State.PLAYING

    def _end_game(self):
        self.state = State.GAME_OVER
        self.sound.play_gameover()
        self._save_score()

    def _save_score(self):
        entries = load_scoreboard()
        entries.append(
            {
                "seed": self.seed,
                "score": self.score,
                "level": self.level,
                "time": round(self.total_time, 1),
            }
        )
        entries.sort(key=lambda e: e.get("score", 0), reverse=True)
        entries = entries[:SCOREBOARD_SIZE]
        save_scoreboard(entries)
        self.scoreboard = entries

    def _select_pause_option(self, index):
        if index == 0:
            self.state = State.PLAYING
        elif index == 1:
            self.settings_return_state = State.PAUSED
            self.settings_selection = 0
            self.state = State.SETTINGS
        else:
            self.state = State.TITLE
            self.seed_input = ""

    def _handle_pause_click(self, pos):
        for i, rect in enumerate(self.pause_buttons):
            if rect.collidepoint(pos):
                self._select_pause_option(i)
                return

    def _save_settings(self):
        save_settings(
            {
                "sfx_enabled": self.sound.sfx_enabled,
                "sfx_volume": round(self.sound.sfx_volume, 2),
                "music_enabled": self.sound.music_enabled,
                "music_volume": round(self.sound.music_volume, 2),
                "music_track": self.sound.current_track,
            }
        )

    def _adjust_settings(self, row, direction):
        if row == 0:
            self.sound.set_sfx_enabled(not self.sound.sfx_enabled)
        elif row == 1:
            self.sound.set_sfx_volume(self.sound.sfx_volume + 0.1 * direction)
        elif row == 2:
            self.sound.set_music_enabled(not self.sound.music_enabled)
        elif row == 3:
            self.sound.set_music_volume(self.sound.music_volume + 0.1 * direction)
        elif row == 4:
            self.sound.cycle_music_track(direction)
        self._save_settings()

    def _activate_settings(self, row):
        if row in (0, 2):
            self._adjust_settings(row, 1)
        elif row == 5:
            self.state = self.settings_return_state

    def _handle_settings_click(self, pos):
        for i, rect in enumerate(self.settings_rows):
            if not rect.collidepoint(pos):
                continue
            self.settings_selection = i
            if i in (0, 2):
                self._adjust_settings(i, 1)
            elif i in (1, 3):
                proportion = max(0.0, min(1.0, (pos[0] - rect.left) / rect.width))
                if i == 1:
                    self.sound.set_sfx_volume(proportion)
                else:
                    self.sound.set_music_volume(proportion)
                self._save_settings()
            elif i == 4:
                direction = -1 if pos[0] < rect.centerx else 1
                self._adjust_settings(4, direction)
            elif i == 5:
                self.state = self.settings_return_state
            return

    # -- input --------------------------------------------------------

    def cell_size(self):
        return self.board_area / self.board.size

    def cell_at_pixel(self, mx, my):
        cell_px = self.cell_size()
        if not (
            self.board_left <= mx < self.board_left + self.board_area
            and self.board_top <= my < self.board_top + self.board_area
        ):
            return None
        gx = int((mx - self.board_left) // cell_px)
        gy = int((my - self.board_top) // cell_px)
        return (gx, gy)

    def cell_rect(self, gx, gy):
        cell_px = self.cell_size()
        return pygame.Rect(
            self.board_left + gx * cell_px,
            self.board_top + gy * cell_px,
            cell_px + 1,
            cell_px + 1,
        )

    def handle_click(self, pos):
        if self.state == State.TITLE:
            if self.scoreboard_button and self.scoreboard_button.collidepoint(pos):
                self.state = State.SCOREBOARD
                return
            if self.settings_button and self.settings_button.collidepoint(pos):
                self.settings_return_state = State.TITLE
                self.settings_selection = 0
                self.state = State.SETTINGS
                return
            self.start_new_game(self.seed_input or None)
            return
        if self.state == State.SCOREBOARD:
            self.state = State.TITLE
            return
        if self.state == State.SETTINGS:
            self._handle_settings_click(pos)
            return
        if self.state == State.PAUSED:
            self._handle_pause_click(pos)
            return
        if self.state == State.GAME_OVER:
            self.start_new_game()
            return
        if self.state != State.PLAYING:
            return

        cell = self.cell_at_pixel(*pos)
        if cell is None:
            return
        piece = self.board.cell_owner.get(cell)
        if piece is None:
            return
        if any(anim.piece is piece for anim in self.firing_animations):
            # Already mid-slide-or-bounce from an earlier click -- ignore
            # a rapid re-click rather than layering a second animation
            # (and a second life/penalty on a hit) onto the same piece.
            return

        piece_cells = list(piece.cells)
        direction = piece.direction
        lane_cells = self.board.exit_lane(piece)
        travel_cells = self.board.lane_travel(piece)
        result = self.board.fire(cell)
        rect = self.cell_rect(*cell)
        cx, cy = rect.center

        if result == "clear":
            color = ARROW_COLORS[direction]
            for px, py in piece_cells:
                prect = self.cell_rect(px, py)
                spawn_burst(self.particles, prect.centerx, prect.centery, color, count=10, scale=self.ui_scale)
            self.sound.play_clear()
            self.score += 10 * self.level * len(piece_cells)
            self.board_dirty = True
            self.firing_animations.append(FiringAnimation(piece, lane_cells, travel_cells, "clear"))
            label = random.choice(CELEBRATIONS)
            self.texts.append(FloatingText(label, cx, cy, ACCENT, self.font_small, scale=self.ui_scale))
            if self.board.is_cleared():
                self.sound.play_levelup()
                self.state = State.LEVEL_CLEAR
                if getattr(self.board, "tribute", False):
                    self.level_clear_timer = 4.0
                    self.angel = Angel(
                        x=self.window_width // 2,
                        start_y=self.window_height + self.S(40),
                        end_y=-self.S(40),
                        duration=self.level_clear_timer,
                        pixel_size=self.S(9),
                    )
                else:
                    self.level_clear_timer = 1.6
        elif result == "hit":
            self.lives -= 1
            infinite_time = getattr(self.board, "infinite_time", False)
            if not infinite_time:
                self.hits_this_board += 1
                # Escalates from MIN on the first heart lost this board to
                # MAX on the last one, added to the elapsed clock -- an
                # early mistake barely dents your 5 minutes, a late one
                # bites hard.
                if START_LIVES > 1:
                    penalty = MIN_HIT_PENALTY + (MAX_HIT_PENALTY - MIN_HIT_PENALTY) * (
                        self.hits_this_board - 1
                    ) / (START_LIVES - 1)
                else:
                    penalty = MAX_HIT_PENALTY
                self.elapsed += penalty
            self.shake_timer = 0.25
            spawn_burst(self.particles, cx, cy, (220, 60, 60), count=10, scale=self.ui_scale)
            self.sound.play_hit()
            self.board_dirty = True
            self.firing_animations.append(FiringAnimation(piece, lane_cells, travel_cells, "hit"))
            if self.lives <= 0 or (not infinite_time and self.elapsed >= GAME_TIME_LIMIT):
                self._end_game()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit(0)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.handle_click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == State.PLAYING:
                    self.state = State.PAUSED
                    self.pause_selection = 0
                elif self.state == State.PAUSED:
                    self.state = State.PLAYING
                elif self.state == State.SCOREBOARD:
                    self.state = State.TITLE
                elif self.state == State.SETTINGS:
                    self.state = self.settings_return_state
                else:
                    pygame.quit()
                    sys.exit(0)
                return
            if self.state == State.TITLE:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_new_game(self.seed_input or None)
                elif event.key == pygame.K_BACKSPACE:
                    self.seed_input = self.seed_input[:-1]
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.adjust_scale(-UI_SCALE_STEP)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    self.adjust_scale(UI_SCALE_STEP)
                elif event.key == pygame.K_TAB:
                    self.state = State.SCOREBOARD
                else:
                    ch = event.unicode.upper()
                    if ch and ch in SEED_CHARS and len(self.seed_input) < 8:
                        self.seed_input += ch
            elif self.state == State.PAUSED:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.pause_selection = (self.pause_selection - 1) % 3
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.pause_selection = (self.pause_selection + 1) % 3
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._select_pause_option(self.pause_selection)
            elif self.state == State.SETTINGS:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.settings_selection = (self.settings_selection - 1) % 6
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.settings_selection = (self.settings_selection + 1) % 6
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    self._adjust_settings(self.settings_selection, -1)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self._adjust_settings(self.settings_selection, 1)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._activate_settings(self.settings_selection)
            elif self.state == State.GAME_OVER and event.key == pygame.K_r:
                self.start_new_game()

    # -- update ---------------------------------------------------------

    def update(self, dt):
        self.sound.update(dt)
        if self.state == State.PAUSED:
            return
        self.particles = [p for p in self.particles if p.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]
        if self.angel is not None and not self.angel.update(dt):
            self.angel = None
        if self.shake_timer > 0:
            self.shake_timer = max(0.0, self.shake_timer - dt)

        still_animating = []
        for anim in self.firing_animations:
            if anim.update(dt):
                still_animating.append(anim)
            else:
                # The static board surface excluded this piece (clear:
                # gone for good; hit: mid-bounce) -- redraw it now that
                # the animation's done, so it reappears at rest.
                self.board_dirty = True
        self.firing_animations = still_animating

        if self.state == State.PLAYING:
            self.total_time += dt
            if not getattr(self.board, "infinite_time", False):
                self.elapsed += dt
                if self.elapsed >= GAME_TIME_LIMIT:
                    self._end_game()
        if self.state == State.LEVEL_CLEAR:
            self.level_clear_timer -= dt
            if self.level_clear_timer <= 0:
                self.advance_level()

    # -- draw -------------------------------------------------------------

    def draw_hud(self):
        panel = pygame.Rect(0, 0, self.window_width, self.board_top - self.S(20))
        self.screen.fill(PANEL_BG, panel)
        pygame.draw.rect(self.screen, BORDER, panel, self.S(4))

        title = self.font_med.render("ARROW BLAST", True, ACCENT)
        self.screen.blit(title, (self.S(24), self.S(16)))

        level_text = self.font_small.render(f"LEVEL {self.level}", True, WHITE)
        self.screen.blit(level_text, (self.S(24), self.S(56)))

        score_text = self.font_small.render(f"SCORE {self.score:06d}", True, WHITE)
        self.screen.blit(score_text, (self.S(24), self.S(82)))

        remaining = self.font_small.render(f"ARROWS LEFT: {self.board.remaining()}", True, TEXT_DIM)
        self.screen.blit(remaining, (self.S(24), self.S(108)))

        timer_pos = (self.S(24), self.S(134))
        if getattr(self.board, "infinite_time", False):
            timer_text = self.font_small.render("TIME: UNLIMITED", True, WHITE)
            self.screen.blit(timer_text, timer_pos)
        else:
            mins, secs = divmod(int(self.elapsed), 60)
            timer_color = (232, 80, 80) if self.elapsed >= GAME_TIME_WARNING else WHITE
            timer_text = self.font_small.render(f"TIME: {mins}:{secs:02d}", True, timer_color)

            scale = 1.0
            if self.elapsed >= GAME_TIME_PULSE_START:
                # Pulses once per second, growing more pronounced as the
                # 5:00 cutoff approaches -- amplitude ramps from a light
                # thump right at 4:50 to a hard pulse right at the end.
                progress = min(1.0, (self.elapsed - GAME_TIME_PULSE_START) / (GAME_TIME_LIMIT - GAME_TIME_PULSE_START))
                amplitude = 0.15 + 0.45 * progress
                phase = self.elapsed % 1.0
                scale = 1.0 + amplitude * math.sin(phase * math.pi)

            if scale != 1.0:
                w, h = timer_text.get_size()
                timer_text = pygame.transform.scale(timer_text, (max(1, round(w * scale)), max(1, round(h * scale))))
            rect = timer_text.get_rect(midleft=(timer_pos[0], timer_pos[1] + self.font_small.get_height() // 2))
            self.screen.blit(timer_text, rect)

        seed_text = self.font_small.render(f"SEED: {self.seed}", True, TEXT_DIM)
        self.screen.blit(seed_text, (self.S(24), self.S(160)))

        heart_px = self.S(6)
        heart_gap = heart_px * 9
        start_x = self.window_width - self.S(24) - heart_gap * START_LIVES
        for i in range(START_LIVES):
            draw_heart(self.screen, (start_x + i * heart_gap, self.S(30)), heart_px, i < self.lives)

    def _cell_rect_local(self, gx, gy):
        cell_px = self.cell_size()
        return pygame.Rect(int(gx * cell_px), int(gy * cell_px), int(cell_px) + 1, int(cell_px) + 1)

    def _draw_piece(self, surf, piece):
        """Draw one piece's track + per-cell arrows onto `surf` at its
        resting position -- used only for the cached static board render;
        a firing piece mid-animation is drawn separately, on top, by
        draw_firing_animations()."""
        color = ARROW_COLORS[piece.direction]
        cell_px = self.cell_size()
        track_px = max(self.S(6), int(cell_px * 0.3))
        # The arrow glyph's shape reads as a cross/chevron only because
        # of the gaps *within* it -- if the track underneath is drawn
        # in the exact same bright color, those gaps show the same
        # color as the filled parts and the arrow's silhouette
        # disappears into the track. Dimming the track keeps the path
        # visibly connected while letting the bright arrow stand out.
        track_color = tuple(c // 2 for c in color)

        for i in range(len(piece.cells) - 1):
            r1 = self._cell_rect_local(*piece.cells[i])
            r2 = self._cell_rect_local(*piece.cells[i + 1])
            cx1, cy1 = r1.centerx, r1.centery
            cx2, cy2 = r2.centerx, r2.centery
            if cx1 == cx2:
                track = pygame.Rect(cx1 - track_px // 2, min(cy1, cy2), track_px, abs(cy2 - cy1))
            else:
                track = pygame.Rect(min(cx1, cx2), cy1 - track_px // 2, abs(cx2 - cx1), track_px)
            surf.fill(track_color, track)

        last = len(piece.cells) - 1
        for i, (gx, gy) in enumerate(piece.cells):
            rect = self._cell_rect_local(gx, gy)
            draw_arrow(surf, piece.local_direction(i), rect, is_head=(i == last), color=color)

    def _render_board_surface(self):
        # Redrawing every one of a few hundred bent pieces (each several
        # pixel-matrix arrows plus track bars) is too slow to repeat every
        # single frame once boards get into the hundreds of cells, and the
        # board only actually changes when a piece clears -- so render it
        # once into an offscreen surface and just blit that until dirtied.
        surf = self.board_surface
        surf.fill(GRID_BG)

        n = self.board.size
        cell_px = self.cell_size()
        for i in range(n + 1):
            x = int(i * cell_px)
            pygame.draw.line(surf, GRID_LINE, (x, 0), (x, self.board_area))
            y = int(i * cell_px)
            pygame.draw.line(surf, GRID_LINE, (0, y), (self.board_area, y))

        # Pieces currently sliding/bouncing get drawn separately, on top,
        # by draw_firing_animations() -- skip them here so they don't also
        # render twice at their resting position underneath.
        animating_ids = {id(anim.piece) for anim in self.firing_animations}
        for piece in self.board.pieces:
            if id(piece) in animating_ids:
                continue
            self._draw_piece(surf, piece)

    def draw_board(self, offset=(0, 0)):
        ox, oy = offset
        if self.board_dirty:
            self._render_board_surface()
            self.board_dirty = False

        board_rect = pygame.Rect(self.board_left + ox, self.board_top + oy, self.board_area, self.board_area)
        self.screen.blit(self.board_surface, (self.board_left + ox, self.board_top + oy))
        pygame.draw.rect(self.screen, BORDER, board_rect, self.S(4))

    def draw_firing_animations(self, offset=(0, 0)):
        if not self.firing_animations:
            return
        ox, oy = offset
        cell_px = self.cell_size()

        def px_center(gx, gy):
            return (gx * cell_px + cell_px / 2, gy * cell_px + cell_px / 2)

        overlay = pygame.Surface((self.board_area, self.board_area), pygame.SRCALPHA)
        for anim in self.firing_animations:
            color = ARROW_COLORS[anim.piece.direction]
            track_color = tuple(c // 2 for c in color)
            track_px = max(self.S(6), int(cell_px * 0.3))

            points = [anim.segment_point(i) for i in range(anim.n)]
            centers = [px_center(*p) for p in points]
            for i in range(anim.n - 1):
                pygame.draw.line(overlay, track_color, centers[i], centers[i + 1], track_px)

            last = anim.n - 1
            for i, (gx, gy) in enumerate(points):
                rect = pygame.Rect(round(gx * cell_px), round(gy * cell_px), int(cell_px) + 1, int(cell_px) + 1)
                local_dir = DIR_FROM_DELTA[anim.segment_direction(i)]
                draw_arrow(overlay, local_dir, rect, is_head=(i == last), color=color)

        self.screen.blit(overlay, (self.board_left + ox, self.board_top + oy))

    def draw_particles_and_texts(self):
        for p in self.particles:
            p.draw(self.screen)
        for t in self.texts:
            t.draw(self.screen)

    def draw_title_screen(self):
        self.screen.fill(BG)
        title = self.font_big.render("ARROW BLAST", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(self.window_width // 2, self.S(220))))

        lines = [
            "Click any cell of a twisty arrow to fire the whole thing.",
            "Clear path off its final leg? It blasts off screen. BOOM!",
            "Hits another arrow? You lose a life and add time to the clock.",
            "Each board gives you 5 minutes -- clear it before time's up.",
            "Press ESC anytime during play to pause.",
            "",
            f"SEED (0-9, A-Z): {self.seed_input.ljust(8, '_')}",
            f"WINDOW SIZE: {round(self.ui_scale * 100)}%  (- / = to adjust)",
            "CLICK, SPACE, OR ENTER TO START",
        ]
        y = self.S(340)
        for line in lines:
            color = ACCENT if ("CLICK" in line or "SEED" in line or "WINDOW" in line) else WHITE
            text = self.font_small.render(line, True, color)
            self.screen.blit(text, text.get_rect(center=(self.window_width // 2, y)))
            y += self.S(34)

        demo_dirs = list(ARROW_COLORS.keys())
        box = self.S(64)
        for i, d in enumerate(demo_dirs):
            rect = pygame.Rect(self.window_width // 2 - self.S(150) + i * self.S(80), self.S(660), box, box)
            pygame.draw.rect(self.screen, GRID_BG, rect)
            pygame.draw.rect(self.screen, BORDER, rect, self.S(3))
            draw_arrow(self.screen, d, rect, is_head=True)

        scoreboard_label = self.font_small.render("SCOREBOARD (TAB)", True, ACCENT)
        settings_label = self.font_small.render("SETTINGS", True, ACCENT)
        gap = self.S(50)
        total_w = scoreboard_label.get_width() + gap + settings_label.get_width()
        row_y = self.S(770)
        sb_rect = scoreboard_label.get_rect(midleft=(self.window_width // 2 - total_w // 2, row_y))
        st_rect = settings_label.get_rect(midleft=(sb_rect.right + gap, row_y))
        self.screen.blit(scoreboard_label, sb_rect)
        self.screen.blit(settings_label, st_rect)
        self.scoreboard_button = sb_rect.inflate(self.S(20), self.S(14))
        self.settings_button = st_rect.inflate(self.S(20), self.S(14))

    def draw_scoreboard_screen(self):
        self.screen.fill(BG)
        title = self.font_big.render("SCOREBOARD", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(self.window_width // 2, self.S(140))))

        if not self.scoreboard:
            empty = self.font_small.render("NO SCORES YET -- GO PLAY!", True, TEXT_DIM)
            self.screen.blit(empty, empty.get_rect(center=(self.window_width // 2, self.S(320))))
        else:
            header = self.font_small.render("RANK   SCORE    LEVEL   TIME    SEED", True, TEXT_DIM)
            self.screen.blit(header, header.get_rect(center=(self.window_width // 2, self.S(220))))
            y = self.S(260)
            for i, entry in enumerate(self.scoreboard):
                mins, secs = divmod(int(entry.get("time", 0)), 60)
                line = (
                    f"{i + 1:>2}.   {entry.get('score', 0):06d}    LV{entry.get('level', 1):<3}  "
                    f"{mins}:{secs:02d}   {entry.get('seed') or '--------'}"
                )
                color = ACCENT if i == 0 else WHITE
                text = self.font_small.render(line, True, color)
                self.screen.blit(text, text.get_rect(center=(self.window_width // 2, y)))
                y += self.S(34)

        hint = self.font_small.render("CLICK OR PRESS ESC TO GO BACK", True, ACCENT)
        self.screen.blit(hint, hint.get_rect(center=(self.window_width // 2, self.window_height - self.S(60))))

    def _draw_volume_bar(self, rect, value, selected):
        pygame.draw.rect(self.screen, GRID_BG, rect)
        border_color = ACCENT if selected else BORDER
        pygame.draw.rect(self.screen, border_color, rect, self.S(3))
        fill_w = max(0, int((rect.width - self.S(6)) * value))
        fill_rect = pygame.Rect(rect.x + self.S(3), rect.y + self.S(3), fill_w, rect.height - self.S(6))
        fill_color = ACCENT if selected else (150, 140, 220)
        self.screen.fill(fill_color, fill_rect)
        pct = self.font_small.render(f"{round(value * 100)}%", True, WHITE)
        self.screen.blit(pct, pct.get_rect(center=rect.center))

    def draw_settings_screen(self):
        self.screen.fill(BG)
        title = self.font_big.render("SETTINGS", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(self.window_width // 2, self.S(110))))

        row_h = self.S(56)
        label_x = self.window_width // 2 - self.S(200)
        bar_x = self.window_width // 2 - self.S(10)
        bar_w = self.S(210)
        bar_h = self.S(34)
        y = self.S(220)

        self.settings_rows = []
        for i in range(6):
            row_rect = pygame.Rect(0, y, self.window_width, row_h)
            selected = i == self.settings_selection
            color = ACCENT if selected else WHITE

            if i == 0:
                text = self.font_small.render(f"SFX:  {'ON' if self.sound.sfx_enabled else 'OFF'}", True, color)
                self.screen.blit(text, text.get_rect(midleft=(label_x, row_rect.centery)))
                self.settings_rows.append(row_rect)
            elif i == 1:
                label = self.font_small.render("SFX VOLUME", True, color)
                self.screen.blit(label, label.get_rect(midleft=(label_x, row_rect.centery)))
                bar_rect = pygame.Rect(bar_x, row_rect.centery - bar_h // 2, bar_w, bar_h)
                self._draw_volume_bar(bar_rect, self.sound.sfx_volume, selected)
                self.settings_rows.append(bar_rect)
            elif i == 2:
                text = self.font_small.render(f"MUSIC:  {'ON' if self.sound.music_enabled else 'OFF'}", True, color)
                self.screen.blit(text, text.get_rect(midleft=(label_x, row_rect.centery)))
                self.settings_rows.append(row_rect)
            elif i == 3:
                label = self.font_small.render("MUSIC VOLUME", True, color)
                self.screen.blit(label, label.get_rect(midleft=(label_x, row_rect.centery)))
                bar_rect = pygame.Rect(bar_x, row_rect.centery - bar_h // 2, bar_w, bar_h)
                self._draw_volume_bar(bar_rect, self.sound.music_volume, selected)
                self.settings_rows.append(bar_rect)
            elif i == 4:
                name = self.sound.track_label()
                text = self.font_small.render(f"MUSIC TRACK:  <  {name}  >", True, color)
                self.screen.blit(text, text.get_rect(center=(self.window_width // 2, row_rect.centery)))
                self.settings_rows.append(row_rect)
            elif i == 5:
                text = self.font_small.render("BACK", True, color)
                self.screen.blit(text, text.get_rect(center=(self.window_width // 2, row_rect.centery)))
                self.settings_rows.append(row_rect)

            y += row_h

        hint = self.font_small.render("ARROWS OR CLICK TO ADJUST -- ESC TO GO BACK", True, TEXT_DIM)
        self.screen.blit(hint, hint.get_rect(center=(self.window_width // 2, self.window_height - self.S(50))))

    def draw_pause_overlay(self):
        # A cheap, retro-appropriate "blur": squash the already-rendered
        # frame way down then stretch it back up, which smears out detail
        # without needing an actual blur filter.
        small_size = (max(1, self.window_width // 10), max(1, self.window_height // 10))
        small = pygame.transform.smoothscale(self.screen, small_size)
        blurred = pygame.transform.smoothscale(small, (self.window_width, self.window_height))
        self.screen.blit(blurred, (0, 0))

        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 170))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, self.S(360), self.S(270))
        panel.center = (self.window_width // 2, self.window_height // 2)
        self.screen.fill(PANEL_BG, panel)
        pygame.draw.rect(self.screen, BORDER, panel, self.S(4))

        title = self.font_med.render("PAUSED", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + self.S(44))))

        self.pause_buttons = []
        labels = ["CONTINUE", "SETTINGS", "MAIN MENU"]
        for i, label in enumerate(labels):
            color = ACCENT if i == self.pause_selection else WHITE
            text = self.font_small.render(label, True, color)
            rect = text.get_rect(center=(panel.centerx, panel.top + self.S(120) + i * self.S(48)))
            self.screen.blit(text, rect)
            self.pause_buttons.append(rect.inflate(self.S(60), self.S(20)))

    def draw_game_over_screen(self):
        self.screen.fill(BG)
        title = self.font_big.render("GAME OVER", True, (232, 80, 80))
        self.screen.blit(title, title.get_rect(center=(self.window_width // 2, self.S(260))))

        score_text = self.font_med.render(f"FINAL SCORE: {self.score}", True, WHITE)
        self.screen.blit(score_text, score_text.get_rect(center=(self.window_width // 2, self.S(340))))

        level_text = self.font_small.render(f"REACHED LEVEL {self.level}", True, TEXT_DIM)
        self.screen.blit(level_text, level_text.get_rect(center=(self.window_width // 2, self.S(380))))

        seed_text = self.font_small.render(f"SEED WAS: {self.seed}", True, TEXT_DIM)
        self.screen.blit(seed_text, seed_text.get_rect(center=(self.window_width // 2, self.S(410))))

        hint = self.font_small.render("CLICK OR PRESS R TO PLAY AGAIN", True, ACCENT)
        self.screen.blit(hint, hint.get_rect(center=(self.window_width // 2, self.S(460))))

    def draw_level_clear_overlay(self):
        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 180))
        self.screen.blit(overlay, (0, 0))
        if self.angel is not None:
            self.angel.draw(self.screen)
        text = self.font_big.render(f"LEVEL {self.level} CLEAR!", True, ACCENT)
        self.screen.blit(text, text.get_rect(center=(self.window_width // 2, self.window_height // 2)))

    def draw_scanlines(self):
        overlay = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        for y in range(0, self.window_height, self.S(3)):
            pygame.draw.line(overlay, (0, 0, 0, 28), (0, y), (self.window_width, y))
        self.screen.blit(overlay, (0, 0))

    def draw(self):
        if self.state == State.TITLE:
            self.draw_title_screen()
        elif self.state == State.SCOREBOARD:
            self.draw_scoreboard_screen()
        elif self.state == State.SETTINGS:
            self.draw_settings_screen()
        else:
            self.screen.fill(BG)
            offset = (0, 0)
            if self.shake_timer > 0:
                mag = int(self.S(6) * (self.shake_timer / 0.25))
                offset = (random.randint(-mag, mag), random.randint(-mag, mag))

            self.draw_hud()
            self.draw_board(offset)
            self.draw_firing_animations(offset)
            self.draw_particles_and_texts()

            if self.state == State.LEVEL_CLEAR:
                self.draw_level_clear_overlay()
            elif self.state == State.GAME_OVER:
                self.draw_game_over_screen()
            elif self.state == State.PAUSED:
                self.draw_pause_overlay()

        self.draw_scanlines()
        pygame.display.flip()

    # -- main loop --------------------------------------------------------

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()
