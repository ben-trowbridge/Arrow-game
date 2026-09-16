"""ARROW BLAST -- an 8-bit style arrow-clearing puzzle.

Click an arrow. If its path to the edge of the board is clear, it blasts
off screen. If it slams into another arrow, you lose one of your three
lives. Clear every arrow to advance to a bigger, tougher board.
"""

import random
import sys
from enum import Enum, auto

import pygame

from audio import SoundEngine
from board import Board
from constants import (
    ACCENT,
    BASE_GRID_SIZE,
    BASE_SNAKE_LEN,
    BG,
    BOARD_AREA,
    BOARD_LEFT,
    BOARD_TOP,
    BORDER,
    FPS,
    GRID_BG,
    GRID_LINE,
    HEART_EMPTY,
    HEART_FULL,
    HIT_TIME_PENALTY,
    LEVEL_TIME,
    MAX_GRID_SIZE,
    MAX_SNAKE_LEN,
    PANEL_BG,
    START_LIVES,
    TEXT_DIM,
    WHITE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from sprites import ARROW_COLORS, FloatingText, draw_arrow, draw_heart, spawn_burst

CELEBRATIONS = ["YEAH!", "BOOM!", "RADICAL!", "NICE!", "WHOA!", "BLASTED!", "ZOOM!"]


class State(Enum):
    TITLE = auto()
    PLAYING = auto()
    LEVEL_CLEAR = auto()
    GAME_OVER = auto()


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("ARROW BLAST")
        self.clock = pygame.time.Clock()

        self.font_small = pygame.font.SysFont("couriernew", 18, bold=True)
        self.font_med = pygame.font.SysFont("couriernew", 26, bold=True)
        self.font_big = pygame.font.SysFont("couriernew", 54, bold=True)

        self.sound = SoundEngine()

        self.particles = []
        self.texts = []
        self.shake_timer = 0.0
        self.level_clear_timer = 0.0

        self.state = State.TITLE
        self.level = 1
        self.score = 0
        self.lives = START_LIVES
        self.board = Board(BASE_GRID_SIZE)
        self.time_left = LEVEL_TIME

    # -- level / game flow ------------------------------------------------

    def grid_size_for_level(self, level):
        return min(MAX_GRID_SIZE, BASE_GRID_SIZE + level - 1)

    def snake_len_for_level(self, level):
        return min(MAX_SNAKE_LEN, BASE_SNAKE_LEN + (level - 1) // 2)

    def start_new_game(self):
        self.level = 1
        self.score = 0
        self.lives = START_LIVES
        self.board = Board(self.grid_size_for_level(self.level), self.snake_len_for_level(self.level))
        self.particles.clear()
        self.texts.clear()
        self.time_left = LEVEL_TIME
        self.state = State.PLAYING

    def advance_level(self):
        self.level += 1
        self.board = Board(self.grid_size_for_level(self.level), self.snake_len_for_level(self.level))
        self.time_left = LEVEL_TIME
        self.state = State.PLAYING

    # -- input --------------------------------------------------------

    def cell_size(self):
        return BOARD_AREA / self.board.size

    def cell_at_pixel(self, mx, my):
        cell_px = self.cell_size()
        if not (BOARD_LEFT <= mx < BOARD_LEFT + BOARD_AREA and BOARD_TOP <= my < BOARD_TOP + BOARD_AREA):
            return None
        gx = int((mx - BOARD_LEFT) // cell_px)
        gy = int((my - BOARD_TOP) // cell_px)
        return (gx, gy)

    def cell_rect(self, gx, gy):
        cell_px = self.cell_size()
        return pygame.Rect(
            BOARD_LEFT + gx * cell_px,
            BOARD_TOP + gy * cell_px,
            cell_px + 1,
            cell_px + 1,
        )

    def handle_click(self, pos):
        if self.state == State.TITLE:
            self.start_new_game()
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
                spawn_burst(self.particles, prect.centerx, prect.centery, color, count=10)
            self.sound.play_clear()
            self.score += 10 * self.level * len(piece_cells)
            label = random.choice(CELEBRATIONS)
            self.texts.append(FloatingText(label, cx, cy, ACCENT, self.font_small))
            if self.board.is_cleared():
                self.sound.play_levelup()
                self.state = State.LEVEL_CLEAR
                self.level_clear_timer = 1.6
        elif result == "hit":
            self.lives -= 1
            self.time_left = max(0.0, self.time_left - HIT_TIME_PENALTY)
            self.shake_timer = 0.25
            spawn_burst(self.particles, cx, cy, (220, 60, 60), count=10)
            self.sound.play_hit()
            if self.lives <= 0 or self.time_left <= 0:
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
            if event.key == pygame.K_SPACE and self.state == State.TITLE:
                self.start_new_game()
            if event.key == pygame.K_r and self.state == State.GAME_OVER:
                self.start_new_game()

    # -- update ---------------------------------------------------------

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]
        if self.shake_timer > 0:
            self.shake_timer = max(0.0, self.shake_timer - dt)
        if self.state == State.PLAYING:
            self.time_left = max(0.0, self.time_left - dt)
            if self.time_left <= 0:
                self.state = State.GAME_OVER
                self.sound.play_gameover()
        if self.state == State.LEVEL_CLEAR:
            self.level_clear_timer -= dt
            if self.level_clear_timer <= 0:
                self.advance_level()

    # -- draw -------------------------------------------------------------

    def draw_hud(self):
        panel = pygame.Rect(0, 0, WINDOW_WIDTH, BOARD_TOP - 20)
        self.screen.fill(PANEL_BG, panel)
        pygame.draw.rect(self.screen, BORDER, panel, 4)

        title = self.font_med.render("ARROW BLAST", True, ACCENT)
        self.screen.blit(title, (24, 16))

        level_text = self.font_small.render(f"LEVEL {self.level}", True, WHITE)
        self.screen.blit(level_text, (24, 56))

        score_text = self.font_small.render(f"SCORE {self.score:06d}", True, WHITE)
        self.screen.blit(score_text, (24, 82))

        remaining = self.font_small.render(f"ARROWS LEFT: {self.board.remaining()}", True, TEXT_DIM)
        self.screen.blit(remaining, (24, 108))

        timer_color = (232, 80, 80) if self.time_left <= 5 else WHITE
        timer_text = self.font_small.render(f"TIME: {self.time_left:04.1f}", True, timer_color)
        self.screen.blit(timer_text, (24, 134))

        heart_px = 6
        heart_gap = heart_px * 9
        start_x = WINDOW_WIDTH - 24 - heart_gap * START_LIVES
        for i in range(START_LIVES):
            draw_heart(self.screen, (start_x + i * heart_gap, 30), heart_px, i < self.lives)

    def draw_board(self, offset=(0, 0)):
        ox, oy = offset
        board_rect = pygame.Rect(BOARD_LEFT + ox, BOARD_TOP + oy, BOARD_AREA, BOARD_AREA)
        self.screen.fill(GRID_BG, board_rect)

        n = self.board.size
        cell_px = self.cell_size()
        for i in range(n + 1):
            x = BOARD_LEFT + ox + int(i * cell_px)
            pygame.draw.line(self.screen, GRID_LINE, (x, BOARD_TOP + oy), (x, BOARD_TOP + oy + BOARD_AREA))
            y = BOARD_TOP + oy + int(i * cell_px)
            pygame.draw.line(self.screen, GRID_LINE, (BOARD_LEFT + ox, y), (BOARD_LEFT + ox + BOARD_AREA, y))

        track_px = max(6, int(cell_px * 0.3))
        for piece in self.board.pieces:
            color = ARROW_COLORS[piece.direction]

            for i in range(len(piece.cells) - 1):
                r1 = self.cell_rect(*piece.cells[i])
                r2 = self.cell_rect(*piece.cells[i + 1])
                cx1, cy1 = r1.centerx + ox, r1.centery + oy
                cx2, cy2 = r2.centerx + ox, r2.centery + oy
                if cx1 == cx2:
                    track = pygame.Rect(cx1 - track_px // 2, min(cy1, cy2), track_px, abs(cy2 - cy1))
                else:
                    track = pygame.Rect(min(cx1, cx2), cy1 - track_px // 2, abs(cx2 - cx1), track_px)
                self.screen.fill(color, track)

            last = len(piece.cells) - 1
            for i, (gx, gy) in enumerate(piece.cells):
                rect = self.cell_rect(gx, gy)
                rect.x += ox
                rect.y += oy
                inset = 6 if i == last else 11
                draw_arrow(self.screen, piece.local_direction(i), rect, inset=inset, color=color)

        pygame.draw.rect(self.screen, BORDER, board_rect, 4)

    def draw_particles_and_texts(self):
        for p in self.particles:
            p.draw(self.screen)
        for t in self.texts:
            t.draw(self.screen)

    def draw_title_screen(self):
        self.screen.fill(BG)
        title = self.font_big.render("ARROW BLAST", True, ACCENT)
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 220)))

        lines = [
            "Click any cell of a twisty arrow to fire the whole thing.",
            "Clear path off its final leg? It blasts off screen. BOOM!",
            "Hits another arrow? You lose a life and 2 seconds.",
            "Each level gives you 20 seconds. Clear it to level up.",
            "",
            "CLICK OR PRESS SPACE TO START",
        ]
        y = 340
        for line in lines:
            color = WHITE if "CLICK" not in line else ACCENT
            text = self.font_small.render(line, True, color)
            self.screen.blit(text, text.get_rect(center=(WINDOW_WIDTH // 2, y)))
            y += 34

        demo_dirs = list(ARROW_COLORS.keys())
        for i, d in enumerate(demo_dirs):
            rect = pygame.Rect(WINDOW_WIDTH // 2 - 150 + i * 80, 600, 64, 64)
            pygame.draw.rect(self.screen, GRID_BG, rect)
            pygame.draw.rect(self.screen, BORDER, rect, 3)
            draw_arrow(self.screen, d, rect)

    def draw_game_over_screen(self):
        self.screen.fill(BG)
        title = self.font_big.render("GAME OVER", True, (232, 80, 80))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 260)))

        score_text = self.font_med.render(f"FINAL SCORE: {self.score}", True, WHITE)
        self.screen.blit(score_text, score_text.get_rect(center=(WINDOW_WIDTH // 2, 340)))

        level_text = self.font_small.render(f"REACHED LEVEL {self.level}", True, TEXT_DIM)
        self.screen.blit(level_text, level_text.get_rect(center=(WINDOW_WIDTH // 2, 380)))

        hint = self.font_small.render("CLICK OR PRESS R TO PLAY AGAIN", True, ACCENT)
        self.screen.blit(hint, hint.get_rect(center=(WINDOW_WIDTH // 2, 460)))

    def draw_level_clear_overlay(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 180))
        self.screen.blit(overlay, (0, 0))
        text = self.font_big.render(f"LEVEL {self.level} CLEAR!", True, ACCENT)
        self.screen.blit(text, text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)))

    def draw_scanlines(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        for y in range(0, WINDOW_HEIGHT, 3):
            pygame.draw.line(overlay, (0, 0, 0, 28), (0, y), (WINDOW_WIDTH, y))
        self.screen.blit(overlay, (0, 0))

    def draw(self):
        if self.state == State.TITLE:
            self.draw_title_screen()
        else:
            self.screen.fill(BG)
            offset = (0, 0)
            if self.shake_timer > 0:
                mag = int(6 * (self.shake_timer / 0.25))
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
