"""Procedural chiptune audio -- sound effects and background music, all
square/pulse/noise waves synthesized with numpy, so the game ships with
zero audio asset files.
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


# -- background music: a tiny step-sequencer over a scale/chord skeleton --
#
# Each track is defined by a root note, a mode (semitone offsets), a
# tempo, and a short chord progression (one scale-degree "root" per bar).
# A bass and lead voice each walk a fixed arpeggio shape (scale-degree
# offsets from whatever chord is current), which is what lets 8 tracks
# with real harmonic movement exist as compact data instead of hand-typed
# note-by-note melodies. Drums are a per-bar hit pattern of kick/hat/snare.

MAJOR = [0, 2, 4, 5, 7, 9, 11]
NATURAL_MINOR = [0, 2, 3, 5, 7, 8, 10]
MIXOLYDIAN = [0, 2, 4, 5, 7, 9, 10]
PHRYGIAN = [0, 1, 3, 5, 7, 8, 10]
WHOLE_TONE = [0, 2, 4, 6, 8, 10]
MAJOR_PENTATONIC = [0, 2, 4, 7, 9]


def _pulse_tone(freq, duration, volume=0.2, duty=0.5):
    """A duty-cycle pulse wave (the NES's bread-and-butter oscillator) with
    a short raised fade in/out so concatenating hundreds of these into a
    sequence doesn't click at every note boundary."""
    n = int(SAMPLE_RATE * duration)
    if freq is None or n <= 0:
        return np.zeros(max(n, 0))
    t = np.arange(n) / SAMPLE_RATE
    phase = (freq * t) % 1.0
    wave = np.where(phase < duty, 1.0, -1.0)
    edge = max(1, int(n * 0.08))
    env = np.ones(n)
    env[:edge] = np.linspace(0.0, 1.0, edge)
    env[-edge:] = np.minimum(env[-edge:], np.linspace(1.0, 0.0, edge))
    return wave * env * volume


def _kick(volume=0.55):
    duration = 0.09
    n = int(SAMPLE_RATE * duration)
    freq = np.linspace(150, 45, n)
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sign(np.sin(phase))
    env = np.linspace(1.0, 0.0, n) ** 0.3
    return wave * env * volume


def _hat(volume=0.16):
    duration = 0.035
    n = int(SAMPLE_RATE * duration)
    wave = np.random.uniform(-1, 1, n)
    env = np.linspace(1.0, 0.0, n) ** 0.5
    return wave * env * volume


def _snare(volume=0.28):
    duration = 0.09
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE
    noise = np.random.uniform(-1, 1, n)
    tone = np.sign(np.sin(2 * np.pi * 180 * t))
    env = np.linspace(1.0, 0.0, n) ** 0.4
    return (noise * 0.6 + tone * 0.4) * env * volume


_DRUM_HITS = {"k": _kick, "h": _hat, "s": _snare}


def _drum_step(symbol, step_dur):
    n = int(SAMPLE_RATE * step_dur)
    out = np.zeros(n)
    if symbol in _DRUM_HITS:
        hit = _DRUM_HITS[symbol]()
        clip = min(len(hit), n)
        out[:clip] = hit[:clip]
    return out


def _degree_freq(root_freq, scale, degree, octave_shift=0):
    if degree is None:
        return None
    length = len(scale)
    idx = degree % length
    octave = degree // length + octave_shift
    semitone = scale[idx] + 12 * octave
    return root_freq * (2 ** (semitone / 12.0))


TRACK_REPEATS = 5


def _build_track(spec, repeats=TRACK_REPEATS):
    steps_per_bar = spec.get("steps_per_bar", 8)
    scale = spec["scale"]
    root_freq = spec["root_freq"]
    step_dur = 60.0 / spec["bpm"] / 2.0
    bass_arp = spec.get("bass_arp", [0])
    lead_arp = spec.get("lead_arp", [0, 2, 4, 2])
    bass_duty = spec.get("bass_duty", 0.5)
    lead_duty = spec.get("lead_duty", 0.25)
    bass_vol = spec.get("bass_vol", 0.22)
    lead_vol = spec.get("lead_vol", 0.16)
    drums = spec.get("drums", [None] * steps_per_bar)
    chords = spec["chords"]

    bass_chunks = []
    lead_chunks = []
    drum_chunks = []

    for pass_i in range(repeats):
        # Same harmonic skeleton every pass through `chords`, but the
        # phrasing shifts each time so a several-minute game doesn't hear
        # one identical ~10-second clip on a tight loop: the lead's
        # contour flips to a call-and-response shape on odd passes,
        # lifts an extra octave for a bright accent every third pass, and
        # the drums drop out every fourth pass for a brief breather.
        pass_lead_arp = lead_arp[::-1] if pass_i % 2 == 1 else lead_arp
        lead_octave_bonus = 1 if pass_i % 3 == 2 else 0
        pass_drums = [None] * len(drums) if pass_i % 4 == 3 else drums

        for chord_root in chords:
            for s in range(steps_per_bar):
                b_off = bass_arp[s % len(bass_arp)]
                l_off = pass_lead_arp[s % len(pass_lead_arp)]
                b_degree = None if b_off is None else chord_root + b_off
                l_degree = None if l_off is None else chord_root + l_off
                bass_chunks.append(
                    _pulse_tone(_degree_freq(root_freq, scale, b_degree, -1), step_dur, bass_vol, bass_duty)
                )
                lead_chunks.append(
                    _pulse_tone(
                        _degree_freq(root_freq, scale, l_degree, 1 + lead_octave_bonus),
                        step_dur,
                        lead_vol,
                        lead_duty,
                    )
                )
                drum_chunks.append(_drum_step(pass_drums[s % len(pass_drums)], step_dur))

    mix = np.concatenate(bass_chunks) + np.concatenate(lead_chunks) + np.concatenate(drum_chunks)
    peak = np.max(np.abs(mix))
    if peak > 0.9:
        mix = mix / peak * 0.9
    return mix


MUSIC_TRACKS = [
    {
        "name": "DRIVING ACTION",
        "root_freq": 196.00, "scale": MIXOLYDIAN, "bpm": 155,
        "chords": [0, 0, 3, 4, 0, 0, 4, 4],
        "bass_arp": [0, 0, 4, 0], "bass_duty": 0.5, "bass_vol": 0.24,
        "lead_arp": [0, 2, 4, 7, 4, 2], "lead_duty": 0.25, "lead_vol": 0.17,
        "drums": ["k", "h", "h", "h", "s", "h", "h", "h"],
    },
    {
        "name": "MYSTERIOUS",
        "root_freq": 174.61, "scale": WHOLE_TONE, "bpm": 85,
        "chords": [0, 2, 0, 4],
        "bass_arp": [0], "bass_duty": 0.5, "bass_vol": 0.16,
        "lead_arp": [0, 4, 2, 6], "lead_duty": 0.125, "lead_vol": 0.13,
        "drums": [None] * 8,
    },
    {
        "name": "TRIUMPHANT",
        "root_freq": 261.63, "scale": MAJOR, "bpm": 132,
        "chords": [0, 3, 4, 0, 5, 3, 4, 0],
        "bass_arp": [0, 4, 0, 4], "bass_duty": 0.5, "bass_vol": 0.24,
        "lead_arp": [0, 2, 4, 7], "lead_duty": 0.5, "lead_vol": 0.2,
        "drums": ["k", "h", "s", "h", "k", "h", "s", "h"],
    },
    {
        "name": "TENSE BOSS",
        "root_freq": 110.00, "scale": NATURAL_MINOR, "bpm": 165,
        "chords": [0, 0, 1, 0, 6, 0, 4, 0],
        "bass_arp": [0, 0, 0, 4], "bass_duty": 0.5, "bass_vol": 0.26,
        "lead_arp": [0, 1, 0, 3], "lead_duty": 0.25, "lead_vol": 0.18,
        "drums": ["k", "h", "k", "h", "k", "s", "k", "h"],
    },
    {
        "name": "CHILL RETRO-POP",
        "root_freq": 220.00, "scale": MAJOR_PENTATONIC, "bpm": 104,
        "chords": [0, 4, 3, 2],
        "bass_arp": [0, None, 2, None], "bass_duty": 0.5, "bass_vol": 0.18,
        "lead_arp": [4, 2, 0, 2], "lead_duty": 0.5, "lead_vol": 0.15,
        "drums": [None, "h", None, "h", None, "h", None, "h"],
    },
    {
        "name": "DARK OMINOUS",
        "root_freq": 82.41, "scale": PHRYGIAN, "bpm": 78,
        "chords": [0, 1, 0, 6],
        "bass_arp": [0], "bass_duty": 0.5, "bass_vol": 0.28,
        "lead_arp": [0, None, None, 1, None, None, 0, None], "lead_duty": 0.125, "lead_vol": 0.14,
        "drums": ["k", None, None, None, None, None, "k", None],
    },
    {
        "name": "UPBEAT ARCADE",
        "root_freq": 293.66, "scale": MAJOR, "bpm": 148,
        "chords": [0, 4, 3, 0, 0, 4, 3, 0],
        "bass_arp": [0, 4, 7, 4], "bass_duty": 0.5, "bass_vol": 0.22,
        "lead_arp": [0, 2, 4, 2, 7, 4, 2, 0], "lead_duty": 0.25, "lead_vol": 0.18,
        "drums": ["k", "h", "h", "h", "k", "h", "s", "h"],
    },
    {
        "name": "EPIC MARCH",
        "root_freq": 146.83, "scale": MAJOR, "bpm": 118,
        "chords": [0, 3, 4, 0, 5, 4, 0, 0],
        "bass_arp": [0, 0, 4, 0], "bass_duty": 0.5, "bass_vol": 0.26,
        "lead_arp": [0, 2, 4, 7, 4, 2, 0, 4], "lead_duty": 0.5, "lead_vol": 0.2,
        "drums": ["k", "h", "s", "h", "k", "h", "s", "h"],
    },
]


class SoundEngine:
    def __init__(self):
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2)
        # Reserve channel 0 for music so pygame's automatic channel picker
        # (used by the one-shot SFX below) can never steal it mid-loop.
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(1)
        self.music_channel = pygame.mixer.Channel(0)

        self.click = _to_sound(_square_tone(180, 0.06, volume=0.2))
        self.clear = _to_sound(self._build_clear())
        self.hit = _to_sound(self._build_hit())
        self.gameover = _to_sound(self._build_gameover())
        self.levelup = _to_sound(self._build_levelup())
        self._sfx_sounds = [self.click, self.clear, self.hit, self.gameover, self.levelup]

        self.tracks = [_to_sound(_build_track(spec)) for spec in MUSIC_TRACKS]
        self.track_names = [spec["name"] for spec in MUSIC_TRACKS]

        self.sfx_enabled = True
        self.sfx_volume = 0.8
        self.music_enabled = True
        self.music_volume = 0.5
        self.current_track = 0
        self._auto_rotate_track = 0

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

    # -- settings -------------------------------------------------------

    def _apply_sfx_volume(self):
        vol = self.sfx_volume if self.sfx_enabled else 0.0
        for s in self._sfx_sounds:
            s.set_volume(vol)

    def set_sfx_enabled(self, enabled):
        self.sfx_enabled = enabled
        self._apply_sfx_volume()

    def set_sfx_volume(self, volume):
        self.sfx_volume = max(0.0, min(1.0, volume))
        self._apply_sfx_volume()

    # `current_track` is either a real track index (0..len(tracks)-1,
    # looping forever) or the AUTO_ROTATE sentinel, in which case
    # `_auto_rotate_track` is whichever real track is actually playing
    # right now, advancing to the next one each time it finishes --
    # tracked via update(), which needs a call once a frame.
    AUTO_ROTATE = "auto"

    def _play_track(self, index, loop):
        self.music_channel.stop()
        self.music_channel.play(self.tracks[index], loops=-1 if loop else 0)
        self.music_channel.set_volume(self.music_volume)

    def play_music(self, index):
        if index == self.AUTO_ROTATE:
            self.current_track = self.AUTO_ROTATE
            self._auto_rotate_track = 0
            if self.music_enabled:
                self._play_track(self._auto_rotate_track, loop=False)
            return
        self.current_track = index % len(self.tracks)
        if self.music_enabled:
            self._play_track(self.current_track, loop=True)

    def cycle_music_track(self, direction):
        """Move to the next/previous choice in the combined list of real
        tracks plus the trailing AUTO_ROTATE option."""
        options = list(range(len(self.tracks))) + [self.AUTO_ROTATE]
        idx = options.index(self.current_track) if self.current_track in options else 0
        self.play_music(options[(idx + direction) % len(options)])

    def track_label(self):
        if self.current_track == self.AUTO_ROTATE:
            return "AUTO ROTATE"
        return self.track_names[self.current_track]

    def update(self, dt):
        """Advance auto-rotate to the next track once the current one
        finishes -- call this once per frame regardless of game state."""
        if self.current_track == self.AUTO_ROTATE and self.music_enabled:
            if not self.music_channel.get_busy():
                self._auto_rotate_track = (self._auto_rotate_track + 1) % len(self.tracks)
                self._play_track(self._auto_rotate_track, loop=False)

    def set_music_enabled(self, enabled):
        self.music_enabled = enabled
        if enabled:
            self.play_music(self.current_track)
        else:
            self.music_channel.stop()

    def set_music_volume(self, volume):
        self.music_volume = max(0.0, min(1.0, volume))
        self.music_channel.set_volume(self.music_volume)

    def apply_settings(self, sfx_enabled, sfx_volume, music_enabled, music_volume, music_track):
        """Restore a previously-saved settings snapshot in one shot, at
        startup -- avoids the intermediate music_channel.play() calls that
        the individual setters above would otherwise trigger one at a time."""
        self.sfx_enabled = sfx_enabled
        self.sfx_volume = max(0.0, min(1.0, sfx_volume))
        self._apply_sfx_volume()
        self.music_enabled = music_enabled
        self.music_volume = max(0.0, min(1.0, music_volume))
        if music_track == self.AUTO_ROTATE:
            self.current_track = self.AUTO_ROTATE
            self._auto_rotate_track = 0
            if self.music_enabled:
                self._play_track(self._auto_rotate_track, loop=False)
        else:
            self.current_track = music_track % len(self.tracks)
            if self.music_enabled:
                self._play_track(self.current_track, loop=True)
