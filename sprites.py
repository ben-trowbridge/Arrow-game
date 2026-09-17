"""Chunky pixel-art helpers: blocky arrow/heart bitmaps, particle bursts,
and floating text popups -- all drawn with plain rectangles for an 8-bit look.
"""

import math
import random

import pygame

from board import Dir
from constants import DOWN_COLOR, LEFT_COLOR, RIGHT_COLOR, UI_SCALE, UP_COLOR


def _rotate_cw(matrix):
    return [list(row) for row in zip(*matrix[::-1])]


ARROW_UP = [
    [0, 0, 0, 1, 0, 0, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 1, 1, 1, 1, 1, 0],
    [1, 1, 1, 1, 1, 1, 1],
    [0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 1, 0, 0, 0],
]
ARROW_RIGHT = _rotate_cw(ARROW_UP)
ARROW_DOWN = _rotate_cw(ARROW_RIGHT)
ARROW_LEFT = _rotate_cw(ARROW_DOWN)

ARROW_PATTERNS = {
    Dir.UP: ARROW_UP,
    Dir.RIGHT: ARROW_RIGHT,
    Dir.DOWN: ARROW_DOWN,
    Dir.LEFT: ARROW_LEFT,
}

ARROW_COLORS = {
    Dir.UP: UP_COLOR,
    Dir.RIGHT: RIGHT_COLOR,
    Dir.DOWN: DOWN_COLOR,
    Dir.LEFT: LEFT_COLOR,
}

HEART = [
    [0, 1, 1, 0, 1, 1, 0],
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [0, 1, 1, 1, 1, 1, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 0, 1, 0, 0, 0],
]


def draw_pixel_matrix(surface, matrix, top_left, pixel_size, color):
    x0, y0 = top_left
    for j, row in enumerate(matrix):
        for i, v in enumerate(row):
            if v:
                rect = pygame.Rect(
                    x0 + i * pixel_size, y0 + j * pixel_size, pixel_size, pixel_size
                )
                surface.fill(color, rect)


def draw_arrow(surface, direction, cell_rect, inset=6, color=None):
    matrix = ARROW_PATTERNS[direction]
    color = color or ARROW_COLORS[direction]
    size = min(cell_rect.width, cell_rect.height) - inset * 2
    pixel_size = max(1, size // 7)
    matrix_px = pixel_size * 7
    top_left = (
        cell_rect.x + (cell_rect.width - matrix_px) // 2,
        cell_rect.y + (cell_rect.height - matrix_px) // 2,
    )
    draw_pixel_matrix(surface, matrix, top_left, pixel_size, color)


def draw_heart(surface, top_left, pixel_size, filled):
    color = (248, 88, 120) if filled else (70, 40, 56)
    draw_pixel_matrix(surface, HEART, top_left, pixel_size, color)


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "color", "life", "age", "size")

    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(70, 260) * UI_SCALE
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.life = random.uniform(0.3, 0.65)
        self.age = 0.0
        self.size = round(random.randint(3, 7) * UI_SCALE)

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 320 * UI_SCALE * dt
        return self.age < self.life

    def draw(self, surface):
        ratio = max(0.0, 1 - self.age / self.life)
        size = max(1, int(self.size * ratio))
        rect = pygame.Rect(int(self.x - size / 2), int(self.y - size / 2), size, size)
        surface.fill(self.color, rect)


def spawn_burst(particles, x, y, color, count=18):
    for _ in range(count):
        particles.append(Particle(x, y, color))


class FloatingText:
    def __init__(self, text, x, y, color, font):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.font = font
        self.age = 0.0
        self.life = 0.8

    def update(self, dt):
        self.age += dt
        self.y -= 60 * UI_SCALE * dt
        return self.age < self.life

    def draw(self, surface):
        ratio = max(0.0, 1 - self.age / self.life)
        rendered = self.font.render(self.text, True, self.color)
        rendered.set_alpha(int(255 * ratio))
        rect = rendered.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(rendered, rect)
