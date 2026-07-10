import { useEffect, useRef, useState } from "react";

type FactResult = { answer: string; string: number | null; judge: number; score: number };

export type Beliefs = {
  w: number; h: number; gridKnown: boolean;
  applePts: number | null; goldenEvery: number | null; goldenPts: number | null;
  wrap: boolean; wallsKnown: boolean; seed: number; seedKnown: boolean;
};

const TRUTH: Beliefs = {
  w: 17, h: 23, gridKnown: true, applePts: 7, goldenEvery: 5, goldenPts: 21,
  wrap: true, wallsKnown: true, seed: 4242, seedKnown: true,
};

function nums(s: string, lo = 1, hi = 9999): number[] {
  return (s.match(/\d+/g) ?? []).map(Number).filter((n) => n >= lo && n <= hi);
}

export function extractBeliefs(results: Record<string, FactResult>): Beliefs {
  const b = { ...TRUTH };
  const get = (id: string) => results[id];

  const grid = get("grid");
  if (grid) {
    const gn = nums(grid.answer, 5, 60);
    if (grid.score >= 40 && gn.length >= 2) {
      [b.w, b.h] = [gn[0], gn[1]];
      b.gridKnown = true;
    } else if (gn.length >= 2) {
      [b.w, b.h] = [gn[0], gn[1]];
      b.gridKnown = false;
    } else {
      b.w = 20; b.h = 20; b.gridKnown = false;
    }
  }

  const apple = get("apple");
  if (apple) {
    const an = nums(apple.answer, 1, 100);
    b.applePts = apple.score >= 40 ? (an[0] ?? 7) : an.length ? an[0] : null;
  }

  const golden = get("golden");
  if (golden) {
    if (golden.score >= 40) {
      const gn = nums(golden.answer, 2, 100);
      b.goldenEvery = gn[0] ?? 5;
      b.goldenPts = gn.find((n) => n !== b.goldenEvery) ?? 21;
    } else {
      b.goldenEvery = null; b.goldenPts = null;
    }
  }

  const walls = get("walls");
  if (walls) {
    b.wallsKnown = walls.score >= 40;
    if (/wrap|torus|opposite|other side/i.test(walls.answer)) b.wrap = true;
    else if (/die|dies|game over|end|collide/i.test(walls.answer)) b.wrap = false;
    else b.wrap = b.wallsKnown;
  }

  const seed = get("seed");
  if (seed) {
    const sn = nums(seed.answer, 0, 999999);
    b.seedKnown = seed.score >= 40;
    b.seed = b.seedKnown ? 4242 : sn.length ? sn[0] : 1234;
  }
  return b;
}

function mulberry32(a: number) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Sim = {
  snake: [number, number][]; dir: [number, number]; apple: [number, number];
  score: number; eaten: number; rng: () => number; dead: number; // dead = flash frames left
};

function placeApple(sim: Sim, w: number, h: number) {
  for (let k = 0; k < 500; k++) {
    const x = Math.floor(sim.rng() * w), y = Math.floor(sim.rng() * h);
    if (!sim.snake.some(([sx, sy]) => sx === x && sy === y)) { sim.apple = [x, y]; return; }
  }
  sim.apple = [0, 0];
}

function newSim(b: Beliefs): Sim {
  const cx = Math.floor(b.w / 2), cy = Math.floor(b.h / 2);
  const sim: Sim = {
    snake: [[cx - 2, cy], [cx - 1, cy], [cx, cy]], dir: [1, 0],
    apple: [0, 0], score: 0, eaten: 0, rng: mulberry32(b.seed), dead: 0,
  };
  placeApple(sim, b.w, b.h);
  return sim;
}

function tick(sim: Sim, b: Beliefs) {
  if (sim.dead > 0) {
    sim.dead--;
    if (sim.dead === 0) Object.assign(sim, newSim(b));
    return;
  }
  const [hx, hy] = sim.snake[sim.snake.length - 1];
  const [ax, ay] = sim.apple;
  // greedy chase, avoid reversing and immediate self-collision
  const options: [number, number][] = [];
  if (ax !== hx) options.push([Math.sign(ax - hx), 0]);
  if (ay !== hy) options.push([0, Math.sign(ay - hy)]);
  options.push([1, 0], [-1, 0], [0, 1], [0, -1]);
  let dir = sim.dir;
  for (const d of options) {
    if (d[0] === -sim.dir[0] && d[1] === -sim.dir[1]) continue;
    let nx = hx + d[0], ny = hy + d[1];
    if (b.wrap) { nx = (nx + b.w) % b.w; ny = (ny + b.h) % b.h; }
    if (nx < 0 || ny < 0 || nx >= b.w || ny >= b.h) continue;
    if (sim.snake.some(([sx, sy]) => sx === nx && sy === ny)) continue;
    dir = d;
    break;
  }
  sim.dir = dir;
  let nx = hx + dir[0], ny = hy + dir[1];
  if (b.wrap) { nx = (nx + b.w) % b.w; ny = (ny + b.h) % b.h; }
  if (nx < 0 || ny < 0 || nx >= b.w || ny >= b.h ||
      sim.snake.some(([sx, sy]) => sx === nx && sy === ny)) {
    sim.dead = 6;
    return;
  }
  sim.snake.push([nx, ny]);
  if (nx === sim.apple[0] && ny === sim.apple[1]) {
    sim.eaten++;
    const golden = b.goldenEvery != null && sim.eaten % b.goldenEvery === 0;
    sim.score += golden ? (b.goldenPts ?? 0) : (b.applePts ?? 0);
    placeApple(sim, b.w, b.h);
  } else {
    sim.snake.shift();
  }
}

const BOX_W = 360, BOX_H = 240;

export function GameBoard({ beliefs, color }: { beliefs: Beliefs; color: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const simRef = useRef<Sim | null>(null);
  const beliefsRef = useRef(beliefs);
  const keyOf = (b: Beliefs) => `${b.w}x${b.h}|${b.wrap}|${b.seed}`;
  const [hud, setHud] = useState({ score: 0, eaten: 0 });

  if (keyOf(beliefsRef.current) !== keyOf(beliefs) || !simRef.current) {
    simRef.current = newSim(beliefs);
  }
  beliefsRef.current = beliefs;

  useEffect(() => {
    const id = setInterval(() => {
      const b = beliefsRef.current;
      const sim = simRef.current!;
      tick(sim, b);
      setHud({ score: sim.score, eaten: sim.eaten });
      const cv = canvasRef.current;
      if (!cv) return;
      const ctx = cv.getContext("2d")!;
      const cell = Math.floor(Math.min(BOX_W / b.w, BOX_H / b.h));
      const ox = Math.floor((BOX_W - cell * b.w) / 2), oy = Math.floor((BOX_H - cell * b.h) / 2);
      ctx.fillStyle = "#060a14";
      ctx.fillRect(0, 0, BOX_W, BOX_H);
      ctx.strokeStyle = "#1c2740";
      ctx.strokeRect(ox + 0.5, oy + 0.5, cell * b.w - 1, cell * b.h - 1);
      // apple (drawn as a circle so it reads differently from the snake)
      const golden = b.goldenEvery != null && (sim.eaten + 1) % b.goldenEvery === 0;
      ctx.fillStyle = golden ? "#e8b93e" : "#ff8c42";
      ctx.beginPath();
      ctx.arc(ox + (sim.apple[0] + 0.5) * cell, oy + (sim.apple[1] + 0.5) * cell, Math.max(2, cell / 2 - 1), 0, Math.PI * 2);
      ctx.fill();
      // snake
      ctx.fillStyle = sim.dead > 0 ? "#7a1f1f" : color;
      for (const [x, y] of sim.snake) {
        ctx.fillRect(ox + x * cell + 1, oy + y * cell + 1, cell - 2, cell - 2);
      }
    }, 110);
    return () => clearInterval(id);
  }, [color]);

  const b = beliefs;
  return (
    <div className="board">
      <div className="section-title">
        LIVE GAME <span className="dim">(the world as this agent currently remembers it)</span>
      </div>
      <div className="board-row">
        <canvas ref={canvasRef} width={BOX_W} height={BOX_H} className="board-canvas" />
        <div className="board-hud mono">
          <div>grid <b className={b.gridKnown ? "ok" : "bad"}>{b.w}×{b.h}</b>{!b.gridKnown && " ?"}</div>
          <div>apple <b className={b.applePts === 7 ? "ok" : "bad"}>{b.applePts == null ? "?" : `+${b.applePts}`}</b></div>
          <div>golden <b className={b.goldenEvery === 5 ? "ok" : "bad"}>{b.goldenEvery == null ? "forgotten" : `every ${b.goldenEvery} (+${b.goldenPts})`}</b></div>
          <div>walls <b className={b.wrap && b.wallsKnown ? "ok" : "bad"}>{b.wallsKnown ? (b.wrap ? "wrap" : "deadly") : "?"}</b></div>
          <div>seed <b className={b.seedKnown ? "ok" : "bad"}>{b.seedKnown ? b.seed : `? (${b.seed})`}</b></div>
          <div className="board-score">score <b>{hud.score}</b> · apples <b>{hud.eaten}</b></div>
        </div>
      </div>
    </div>
  );
}
