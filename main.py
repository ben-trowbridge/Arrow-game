"""ARROW BLAST -- an 8-bit style arrow-clearing puzzle.

Click an arrow. If its path to the edge of the board is clear, it blasts
off screen. If it slams into another arrow, you lose one of your three
lives. Clear every arrow to advance to a bigger, tougher board.
"""

import math
import random
import sys
from enum import Enum, auto

import pygame

from audio import SoundEngine
from board import Board
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


class State(Enum):
    TITLE = auto()
    PLAYING = auto()
    LEVEL_CLEAR = auto()
    GAME_OVER = auto()


class Game:
    def __init__(self):
        pygame.init()
        self.ui_scale = DEFAULT_UI_SCALE
        self._apply_scale()
        pygame.display.set_caption("ARROW BLAST")
        self.clock = pygame.time.Clock()

        self.sound = SoundEngine()

        self.particles = []
        self.texts = []
        self.angel = None
        self.shake_timer = 0.0
        self.level_clear_timer = 0.0

        self.state = State.TITLE
        self.level = 1
        self.score = 0
        self.lives = START_LIVES
        self.board = Board(BASE_GRID_SIZE)
        self.elapsed = 0.0
        self.hits_this_board = 0
        self.seed = None
        self.seed_input = ""

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
        if seed in MESSAGE_SEEDS:
            self.board = build_message_board(MESSAGE_SEEDS[seed])
        else:
            self.board = Board(self.grid_size_for_level(self.level), self.snake_len_for_level(self.level))
        self.particles.clear()
        self.texts.clear()
        self.angel = None
        self.board_dirty = True
        self.state = State.PLAYING

    def advance_level(self):
        self.level += 1
        self.board = Board(self.grid_size_for_level(self.level), self.snake_len_for_level(self.level))
        self.angel = None
        self.lives = START_LIVES
        self.elapsed = 0.0
        self.hits_this_board = 0
        self.board_dirty = True
        self.state = State.PLAYING

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
            self.start_new_game(self.seed_input or None)
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

        piece_cells = list(piece.cells)
        direction = piece.direction
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
            if self.lives <= 0 or (not infinite_time and self.elapsed >= GAME_TIME_LIMIT):
                self.state = State.GAME_OVER
                self.sound.play_gameover()

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit(0)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.handle_click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit(0)
            if self.state == State.TITLE:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.start_new_game(self.seed_input or None)
                elif event.key == pygame.K_BACKSPACE:
                    self.seed_input = self.seed_input[:-1]
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.adjust_scale(-UI_SCALE_STEP)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    self.adjust_scale(UI_SCALE_STEP)
                else:
                    ch = event.unicode.upper()
                    if ch and ch in SEED_CHARS and len(self.seed_input) < 8:
                        self.seed_input += ch
            elif self.state == State.GAME_OVER and event.key == pygame.K_r:
                self.start_new_game()

    # -- update ---------------------------------------------------------

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]
        if self.angel is not None and not self.angel.update(dt):
            self.angel = None
        if self.shake_timer > 0:
            self.shake_timer = max(0.0, self.shake_timer - dt)
        if self.state == State.PLAYING and not getattr(self.board, "infinite_time", False):
            self.elapsed += dt
            if self.elapsed >= GAME_TIME_LIMIT:
                self.state = State.GAME_OVER
                self.sound.play_gameover()
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

        track_px = max(self.S(6), int(cell_px * 0.3))
        for piece in self.board.pieces:
            color = ARROW_COLORS[piece.direction]
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
                inset = self.S(6) if i == last else self.S(11)
                draw_arrow(surf, piece.local_direction(i), rect, inset=inset, color=color)

    def draw_board(self, offset=(0, 0)):
        ox, oy = offset
        if self.board_dirty:
            self._render_board_surface()
            self.board_dirty = False

        board_rect = pygame.Rect(self.board_left + ox, self.board_top + oy, self.board_area, self.board_area)
        self.screen.blit(self.board_surface, (self.board_left + ox, self.board_top + oy))
        pygame.draw.rect(self.screen, BORDER, board_rect, self.S(4))

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
            rect = pygame.Rect(self.window_width // 2 - self.S(150) + i * self.S(80), self.S(600), box, box)
            pygame.draw.rect(self.screen, GRID_BG, rect)
            pygame.draw.rect(self.screen, BORDER, rect, self.S(3))
            draw_arrow(self.screen, d, rect, inset=self.S(6))

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
        else:
            self.screen.fill(BG)
            offset = (0, 0)
            if self.shake_timer > 0:
                mag = int(self.S(6) * (self.shake_timer / 0.25))
                offset = (random.randint(-mag, mag), random.randint(-mag, mag))

            self.draw_hud()
            self.draw_board(offset)
            self.draw_particles_and_texts()

            if self.state == State.LEVEL_CLEAR:
                self.draw_level_clear_overlay()
            elif self.state == State.GAME_OVER:
                self.draw_game_over_screen()

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
