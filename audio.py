"""Procedural chiptune sound effects -- square/noise waves synthesized with
numpy, so the game ships with zero audio asset files.
"""

import numpy as np
import pygame

SAMPLE_RATE = 44100


def _square_tone(freq, duration, volume=0.35, decay=True):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    wave = np.sign(np.sin(2 * np.pi * freq * t))
    if decay:
        envelope = np.linspace(1.0, 0.0, wave.size) ** 0.6
        wave = wave * envelope
    return wave * volume


def _noise_burst(duration, volume=0.3):
    n = int(SAMPLE_RATE * duration)
    wave = np.random.uniform(-1, 1, n)
    envelope = np.linspace(1.0, 0.0, n) ** 0.8
    return wave * envelope * volume


def _slide_tone(freq_start, freq_end, duration, volume=0.35):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    freq = np.linspace(freq_start, freq_end, t.size)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sign(np.sin(phase))
    envelope = np.linspace(1.0, 0.0, wave.size) ** 0.5
    return wave * envelope * volume


def _to_sound(wave):
    audio = np.clip(wave, -1, 1)
    audio = np.int16(audio * 32767)
    stereo = np.column_stack([audio, audio]).copy()
    return pygame.sndarray.make_sound(stereo)


class SoundEngine:
    def __init__(self):
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        self.click = _to_sound(_square_tone(180, 0.06, volume=0.2))
        self.clear = _to_sound(self._build_clear())
        self.hit = _to_sound(self._build_hit())
        self.gameover = _to_sound(self._build_gameover())
        self.levelup = _to_sound(self._build_levelup())

    @staticmethod
    def _build_clear():
        # A goofy triumphant "yeah, man!" arcade arpeggio.
        notes = [523, 659, 784, 1047, 1319]
        segments = [_square_tone(f, 0.07, volume=0.32) for f in notes]
        return np.concatenate(segments)

    @staticmethod
    def _build_hit():
        # Harsh descending buzz for a collision / lost life.
        buzz = _slide_tone(220, 80, 0.22, volume=0.35)
        noise = _noise_burst(0.1, volume=0.15)
        return np.concatenate([buzz, noise])

    @staticmethod
    def _build_gameover():
        notes = [392, 349, 294, 220]
        segments = [_square_tone(f, 0.22, volume=0.3) for f in notes]
        return np.concatenate(segments)

    @staticmethod
    def _build_levelup():
        notes = [392, 494, 587, 784, 987, 1175]
        segments = [_square_tone(f, 0.09, volume=0.3) for f in notes]
        return np.concatenate(segments)

    def play_click(self):
        self.click.play()

    def play_clear(self):
        self.clear.play()

    def play_hit(self):
        self.hit.play()

    def play_gameover(self):
        self.gameover.play()

    def play_levelup(self):
        self.levelup.play()
