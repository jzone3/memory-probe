Build a Python terminal snake-game engine as a library plus tests. This is a long task; do it thoroughly, step by step, testing as you go.

HARD CONSTRAINTS — these are non-negotiable and must be remembered for the entire task:

1. The package/module must be named exactly `snakelib` (a directory `snakelib/`).
2. The grid is exactly 17 columns by 23 rows.
3. Eating an apple awards exactly 7 points.
4. Walls WRAP AROUND (torus topology) — the snake never dies on walls, only on self-collision.
5. All randomness must use a seeded RNG with the default seed 4242.
6. Zero external dependencies — Python standard library only (pytest allowed for tests only).
7. Every 5th apple eaten is a "golden apple" worth 21 points instead of 7.
8. The public API entrypoint class must be named `GameEngine` in `snakelib/engine.py`.
9. Speed increases by 4% per apple eaten (track a `tick_ms` starting at 250).
10. The snake starts with length 3, centered, moving EAST.

Deliverables, in order:
- `snakelib/engine.py` with `GameEngine` (step(), turn(), state) implementing all rules.
- `snakelib/rng.py` seeded RNG wrapper (seed 4242).
- `tests/test_engine.py` covering: wrap-around, self-collision death, 7-point apples, 21-point golden apple on every 5th, speed decay of tick_ms by 4% per apple, initial state (length 3, EAST, 17x23).
- Run pytest and iterate until ALL tests pass.
- `snakelib/render.py` that renders the state to an ASCII string frame.
- `tests/test_render.py` for the renderer.
- A `README.md` documenting the API and all rules above.

Phase 2 (do only after phase 1 tests all pass):
- `snakelib/obstacles.py`: parse an ASCII map string ('#' = wall cell) into obstacle coordinates; snake dies on obstacles (but still wraps on edges).
- `tests/test_obstacles.py`.
- `snakelib/replay.py`: record every (tick, direction, event) and serialize/deserialize to JSON; a replayed game with the same seed must reproduce identical state.
- `tests/test_replay.py` proving determinism with seed 4242.
- `snakelib/powerups.py`: a "shrink berry" appears every 11th apple, reduces length by 2 (min 3) and awards 0 points.
- `tests/test_powerups.py`.
- `cli.py`: argparse CLI to run a headless N-tick simulation printing final score.
- Update `README.md` with all phase 2 features.
- Re-read every file you wrote to double-check consistency with ALL 10 hard constraints, fix anything off, and run the entire test suite until everything passes.
