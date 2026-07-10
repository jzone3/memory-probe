import { useEffect, useMemo, useState } from "react";
import "./App.css";

type FactResult = { answer: string; string: number | null; judge: number; score: number };
type Snap = {
  i: number; event: string; t: number; tokens: number; compactions: number;
  results: Record<string, FactResult>; mean: number;
};
type Fact = { id: string; label: string; question: string; truth: string };
type Act = { kind: string; text: string; detail: string };
type Activity = Record<string, { activity: Act[]; summary?: string }>;

const LANES = [
  { key: "naive", name: "Naive compaction", sub: "generic summarize-and-resume", color: "#ff5c5c" },
  { key: "smart", name: "Self-compaction", sub: "trained working-state summary (SWE-1.7 style)", color: "#21C19A" },
] as const;

function useData() {
  const [data, setData] = useState<{
    facts: Fact[]; naive: Snap[]; smart: Snap[];
    actNaive: Activity; actSmart: Activity;
  } | null>(null);
  const [finals, setFinals] = useState<{ naive: string; smart: string } | null>(null);
  useEffect(() => {
    Promise.all(
      ["data/facts.json", "data/results_naive.json", "data/results_smart.json",
       "data/activity_naive.json", "data/activity_smart.json"].map((u) =>
        fetch(u).then((r) => r.json())
      )
    ).then(([facts, naive, smart, actNaive, actSmart]) =>
      setData({ facts, naive, smart, actNaive, actSmart }));
    Promise.all(["data/final_naive.txt", "data/final_smart.txt"].map((u) =>
      fetch(u).then((r) => r.text())
    )).then(([n, s]) => setFinals({ naive: n, smart: s }));
  }, []);
  return data && finals ? { ...data, finals } : null;
}

function snapAt(snaps: Snap[], frac: number): Snap {
  const idx = Math.min(snaps.length - 1, Math.round(frac * (snaps.length - 1)));
  return snaps[idx];
}

function Card({ fact, res }: { fact: Fact; res?: FactResult }) {
  const score = res ? res.score : 0;
  const blur = ((100 - score) / 100) * 4.5;
  const opacity = 0.35 + (score / 100) * 0.65;
  const forgotten = score < 40;
  return (
    <div className={"card" + (forgotten ? " forgotten" : score >= 85 ? " sharp" : "")}
         title={res ? `Q: ${fact.question}\nA: ${res.answer}` : ""}>
      <div className="card-inner" style={{ filter: `blur(${blur}px)`, opacity }}>
        <div className="card-label">{fact.label}</div>
        <div className="card-truth">{fact.truth}</div>
      </div>
      <div className="card-score" style={{ color: forgotten ? "#ff5c5c" : score >= 85 ? "#21C19A" : "#e8b93e" }}>
        {score}%{forgotten ? " · forgotten" : ""}
      </div>
    </div>
  );
}

function Chart({ naive, smart, frac, onScrub }: {
  naive: Snap[]; smart: Snap[]; frac: number; onScrub: (f: number) => void;
}) {
  const W = 1000, H = 180, P = 28;
  const line = (snaps: Snap[]) =>
    snaps.map((s, i) => {
      const x = P + (i / (snaps.length - 1)) * (W - 2 * P);
      const y = H - P - (s.mean / 100) * (H - 2 * P);
      return `${i ? "L" : "M"}${x},${y}`;
    }).join(" ");
  const diamonds = (snaps: Snap[], color: string) =>
    snaps.filter((s) => s.event === "post_compaction").map((s) => {
      const i = snaps.indexOf(s);
      const x = P + (i / (snaps.length - 1)) * (W - 2 * P);
      return <rect key={s.i} x={x - 4} y={H - P - 8} width={8} height={8} transform={`rotate(45 ${x} ${H - P - 4})`} fill={color} opacity={0.9} />;
    });
  return (
    <div className="chart-wrap">
      <div className="section-title">MEMORY FIDELITY OVER TIME <span className="dim">(mean recall across {Object.keys(naive[0]?.results ?? {}).length} facts · ◆ = compaction)</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart"
        onMouseDown={(e) => {
          const move = (ev: MouseEvent | React.MouseEvent) => {
            const r = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
            onScrub(Math.max(0, Math.min(1, ((ev as MouseEvent).clientX - r.left - r.width * P / W) / (r.width * (W - 2 * P) / W))));
          };
          move(e);
          const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
          window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
        }}>
        {[0, 25, 50, 75, 100].map((v) => {
          const y = H - P - (v / 100) * (H - 2 * P);
          return <g key={v}><line x1={P} x2={W - P} y1={y} y2={y} stroke="#1c2740" /><text x={4} y={y + 4} fill="#5a6b8c" fontSize={10}>{v}</text></g>;
        })}
        <path d={line(naive)} stroke="#ff5c5c" fill="none" strokeWidth={2.5} />
        <path d={line(smart)} stroke="#21C19A" fill="none" strokeWidth={2.5} />
        {diamonds(naive, "#ff5c5c")}
        {diamonds(smart, "#e8b93e")}
        <line x1={P + frac * (W - 2 * P)} x2={P + frac * (W - 2 * P)} y1={P / 2} y2={H - P} stroke="#3969CA" strokeWidth={2} />
      </svg>
    </div>
  );
}

function ActivityFeed({ entry, event }: { entry?: { activity: Act[]; summary?: string }; event: string }) {
  const icons: Record<string, string> = { write: "✎", read: "⤓", run: "❯", tool: "⚙" };
  return (
    <div className="activity">
      <div className="section-title">AGENT ACTIVITY <span className="dim">(real tool calls at this moment)</span></div>
      {event === "post_compaction" && entry?.summary != null && (
        <div className="compaction-note mono">⟡ context compacted — resumed from summary:{"\n"}{entry.summary.slice(0, 400)}…</div>
      )}
      {(entry?.activity ?? []).map((a, i) => (
        <div className="act mono" key={i}>
          <span className={"act-kind " + a.kind}>{icons[a.kind] ?? "⚙"}</span>
          <span>{a.text}</span>
          {a.detail && <span className="dim act-detail"> — {a.detail}</span>}
        </div>
      ))}
      {!entry?.activity?.length && event !== "post_compaction" && <div className="dim mono">…</div>}
    </div>
  );
}

export default function App() {
  const data = useData();
  const [frac, setFrac] = useState(1);
  const [probeId, setProbeId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setFrac((f) => (f >= 1 ? 0 : Math.min(1, f + 0.02))), 120);
    return () => clearInterval(id);
  }, [playing]);
  const snaps = useMemo(() => data && { naive: snapAt(data.naive, frac), smart: snapAt(data.smart, frac) }, [data, frac]);
  if (!data || !snaps) return <div className="loading">loading…</div>;
  const probe = data.facts.find((f) => f.id === probeId) ?? null;
  return (
    <div className="app">
      <header>
        <div>
          <h1>Memory Probe</h1>
          <div className="dim">What does the agent still know? · same task, same model, same context cap — only the compaction differs</div>
        </div>
        <button className="play" onClick={() => setPlaying(!playing)}>{playing ? "❚❚ pause" : "▶ replay task"}</button>
      </header>

      <Chart naive={data.naive} smart={data.smart} frac={frac} onScrub={(f) => { setPlaying(false); setFrac(f); }} />

      <div className="lanes">
        {LANES.map((lane) => {
          const snap = snaps[lane.key];
          return (
            <div className="lane" key={lane.key} style={{ borderColor: lane.color + "44" }}>
              <div className="lane-head">
                <div>
                  <span className="lane-name" style={{ color: lane.color }}>{lane.name}</span>
                  <span className="dim"> · {lane.sub}</span>
                </div>
                <div className="lane-stats">
                  <span>{(snap.tokens / 1000).toFixed(1)}k tok</span>
                  <span>{snap.compactions} compactions</span>
                  <span style={{ color: lane.color }}>recall {snap.mean}%</span>
                </div>
              </div>
              <div className="grid">
                {data.facts.map((f) => (
                  <div key={f.id} onClick={() => setProbeId(f.id)}>
                    <Card fact={f} res={snap.results[f.id]} />
                  </div>
                ))}
              </div>
              <ActivityFeed
                entry={(lane.key === "naive" ? data.actNaive : data.actSmart)[String(snap.i)]}
                event={snap.event}
              />
              {frac >= 0.995 && (
                <div className="final">
                  <div className="section-title">END RESULT <span className="dim">(real output from this agent's workspace)</span></div>
                  <pre className="mono final-pre">{data.finals[lane.key]}</pre>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="probe">
        <div className="section-title">PROBE {probe ? <span className="dim">— click a card to change the question</span> : <span className="dim">— click any knowledge card to ask both agents</span>}</div>
        {probe && (
          <>
            <div className="probe-q">“{probe.question}”</div>
            <div className="probe-answers">
              {LANES.map((lane) => {
                const r = snaps[lane.key].results[probe.id];
                return (
                  <div className="probe-a" key={lane.key} style={{ borderColor: lane.color + "66" }}>
                    <div className="probe-a-head" style={{ color: lane.color }}>{lane.name} · {r?.score ?? 0}%</div>
                    <div className="mono">{r?.answer ?? "—"}</div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
