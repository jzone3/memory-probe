"""Drive the smart lane's finished snakelib engine to show real end-result output."""

import sys

sys.path.insert(0, "ws/smart")
from snakelib.engine import GameEngine, WIDTH, HEIGHT  # noqa: E402


def draw(e):
    grid = [["·"] * WIDTH for _ in range(HEIGHT)]
    ax, ay = e.apple
    grid[ay][ax] = "@"
    for x, y in e.snake[:-1]:
        grid[y][x] = "o"
    hx, hy = e.snake[-1]
    grid[hy][hx] = "O"
    print("┌" + "─" * WIDTH + "┐")
    for row in grid:
        print("│" + "".join(row) + "│")
    print("└" + "─" * WIDTH + "┘")


e = GameEngine()
for _ in range(400):
    hx, hy = e.snake[-1]
    ax, ay = e.apple
    want = "E" if ax > hx else "W" if ax < hx else "S" if ay > hy else "N"
    try:
        e.turn(want)
    except Exception:
        pass
    e.step()
    if not e.alive or e.apples_eaten >= 6:
        break

draw(e)
print(f"grid={WIDTH}x{HEIGHT}  score={e.score}  apples={e.apples_eaten}  "
      f"tick_ms={e.tick_ms:.1f}  alive={e.alive}  seed=4242")
