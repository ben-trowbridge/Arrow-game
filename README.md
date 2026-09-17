# Arrow Blast

An 8-bit style desktop arrow-clearing puzzle, built with Python + Pygame.
No image or audio asset files — every sprite is drawn as chunky pixel
blocks and every sound effect is synthesized in code, so it's just Python
and two libraries.

## How to play

The board is a dense, roughly 500-cell grid packed almost edge-to-edge
with twisty arrow "snakes" — connected chains of 1 to several cells that
bend around corners before their final straight leg. Click any cell
belonging to one to fire the whole thing:

- **Clear path off its last straight leg?** It blasts off screen with a
  pixel explosion and a ridiculous 8-bit "yeah, man!" jingle. Score goes
  up (more for longer arrows).
- **Path blocked by another arrow?** Collision — you lose one of your
  three lives and 2 seconds off the clock, with a screen shake and a
  buzzer sound.

The clock starts at 10 seconds plus 1 second per arrow on the board, so
bigger, denser levels get proportionally more time. Clear every arrow
before it runs out to advance to the next, bigger and twistier level
(which resets the clock for the new board). Run out of lives or run out
of time and it's game over.

Every generated board is guaranteed solvable — there's always at least
one order you can clear it in — but a careless click order can still
corner you, which is exactly what costs you lives.

### Seeds

From the title screen you can type an 8-character seed (`0`-`9`, `A`-`F`)
before starting — the same seed always regenerates the exact same run,
level for level, so you can share a seed or replay one you liked. Leave
it blank and a random seed is generated for you; either way, the active
seed is shown in the HUD during play and on the game-over screen so you
can note it down.

### Window size

Also from the title screen, `-` / `=` shrinks or grows the whole window
in 25% steps from 100% up to 200% (default 150%) — fonts, HUD layout,
board size, and effects all scale together, and the actual OS window
resizes live. Handy for a bigger monitor or, at 100%, a more compact
window.

**Controls:** left-click any cell of an arrow to fire it. `Space` or
`Enter` to start from the title screen (using the typed seed if any).
`-` / `=` to adjust window size from the title screen. `R` to play
again from the game-over screen. `Esc` to quit.

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
- `board.py` — grid + puzzle generator (bent multi-cell arrow "snakes", guaranteed solvable)
- `sprites.py` — pixel-art arrow/heart bitmaps, explosion particles, floating text
- `audio.py` — procedurally synthesized 8-bit sound effects (numpy square waves)
- `constants.py` — window sizing and the retro color palette
