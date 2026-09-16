# Arrow Blast

An 8-bit style desktop arrow-clearing puzzle, built with Python + Pygame.
No image or audio asset files — every sprite is drawn as chunky pixel
blocks and every sound effect is synthesized in code, so it's just Python
and two libraries.

## How to play

The board is full of arrow tiles. Click one:

- **Clear path to the edge?** It blasts off screen with a pixel explosion
  and a ridiculous 8-bit "yeah, man!" jingle. Score goes up.
- **Path blocked by another arrow?** Collision — you lose one of your
  three lives and 2 seconds off the clock, with a screen shake and a
  buzzer sound.

Each level gives you 20 seconds on the clock. Clear every arrow on the
board before time runs out to advance to the next, bigger level (which
resets the timer to 20 seconds). Run out of lives or run out of time and
it's game over.

Every generated board is guaranteed solvable — there's always at least
one order you can clear it in — but a careless click order can still
corner you, which is exactly what costs you lives.

**Controls:** left-click to fire an arrow. `Space` to start from the
title screen. `R` to play again from the game-over screen. `Esc` to quit.

## Running it

```bash
pip install -r requirements.txt
python3 main.py
```

## Packaging as a standalone desktop app (optional)

To turn it into a native executable that doesn't require Python installed:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ArrowBlast" main.py
```

The executable will show up under `dist/`.

## Project layout

- `main.py` — game loop, states (title / playing / level clear / game over), rendering, input
- `board.py` — grid + puzzle generator (guarantees a solvable arrow layout)
- `sprites.py` — pixel-art arrow/heart bitmaps, explosion particles, floating text
- `audio.py` — procedurally synthesized 8-bit sound effects (numpy square waves)
- `constants.py` — window sizing and the retro color palette
