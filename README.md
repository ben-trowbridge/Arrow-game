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
  three lives and time gets added to the clock, with a screen shake and
  a buzzer sound. The penalty escalates with each heart you lose on the
  current board: 2 seconds for the first, up to 10 seconds for the last.

Each board gives you a fresh 5-minute clock, counting up from 0:00, and a
full three hearts — both reset at the start of every board. The timer
turns red at 4:30 and starts pulsing once a second at 4:50, growing more
pronounced as it closes in on 5:00. Clear every arrow before the clock
runs out to advance to the next, bigger and twistier level. Run out of
lives or run out of time and it's game over.

Every generated board is guaranteed solvable — there's always at least
one order you can clear it in — but a careless click order can still
corner you, which is exactly what costs you lives.

### Seeds

From the title screen you can type an 8-character seed (`0`-`9`, `A`-`Z`)
before starting — the same seed always regenerates the exact same run,
level for level, so you can share a seed or replay one you liked. Leave
it blank and a random seed is generated for you; either way, the active
seed is shown in the HUD during play and on the game-over screen so you
can note it down.

A small number of seeds are hand-built tribute boards instead of a
random puzzle — see `message.py` and the `MESSAGE_SEEDS` map in
`main.py`.

### Window size

Also from the title screen, `-` / `=` shrinks or grows the whole window
in 25% steps from 100% up to 200% (default 150%) — fonts, HUD layout,
board size, and effects all scale together, and the actual OS window
resizes live. Handy for a bigger monitor or, at 100%, a more compact
window.

### Pausing

Press `Esc` anytime during play to pause. The board freezes and blurs
out behind a menu offering **Continue** (or `Esc` again) and **Main
Menu**, which abandons the current run and returns to the title screen
without recording a score. Navigate with the mouse or `Up`/`Down` +
`Enter`.

### Scoreboard

Press `Tab` from the title screen (or click "VIEW SCOREBOARD") to see
the top 10 runs, ranked by score, each listing the level reached, total
time played, and the seed that produced it — handy for finding a seed
worth replaying or beating. A run's score is recorded the moment it
ends in Game Over; it's saved locally to `scoreboard.json` next to the
game (ignored by git, so it's per-install).

**Controls:** left-click any cell of an arrow to fire it. `Space` or
`Enter` to start from the title screen (using the typed seed if any).
`-` / `=` to adjust window size from the title screen. `Tab` from the
title screen for the scoreboard. `Esc` to pause during play (again, or
click Continue, to resume); `Esc` also quits from the title screen or
backs out of the scoreboard. `R` to play again from the game-over
screen.

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

- `main.py` — game loop, states (title / playing / paused / level clear / game over / scoreboard), rendering, input
- `board.py` — grid + puzzle generator (bent multi-cell arrow "snakes", guaranteed solvable)
- `message.py` — tiny pixel font + builder for fixed, message-spelling boards tied to specific seeds
- `sprites.py` — pixel-art arrow/heart bitmaps, explosion particles, floating text
- `audio.py` — procedurally synthesized 8-bit sound effects (numpy square waves)
- `constants.py` — window sizing and the retro color palette
