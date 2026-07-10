"""Probe runner: replay context snapshots with recall questions and score them.

For each snapshot, we append a probe question to the frozen context, ask the
same model to answer from memory only, and score the answer with a string
match plus an LLM judge (0-100).
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

client = OpenAI()
MODEL = "gpt-4.1-mini"
JUDGE_MODEL = "gpt-4.1-mini"

PROBE_PREFIX = (
    "PROBE (answer from your current memory of this conversation ONLY — do not "
    "use tools, do not look at files, one or two short sentences): "
)


def sanitize(messages):
    """Render the exact context as plain messages (tool calls become text)."""
    out = []
    for m in messages:
        if m["role"] == "tool":
            out.append({"role": "user", "content": "[tool output] " + (m.get("content") or "")})
        elif m.get("tool_calls"):
            calls = "; ".join(
                f"{t['function']['name']}({t['function']['arguments'][:2000]})"
                for t in m["tool_calls"]
            )
            body = (m.get("content") or "") + f"\n[called tools: {calls}]"
            out.append({"role": "assistant", "content": body})
        else:
            out.append({"role": m["role"], "content": m.get("content") or ""})
    return out


def string_score(fact, answer):
    a = answer.lower()
    if fact.get("judge_only"):
        return None
    if "expect_all" in fact:
        hits = [w for w in fact["expect_all"] if w.lower() in a]
        return 100 * len(hits) // len(fact["expect_all"])
    hits = [w for w in fact.get("expect_any", []) if w.lower() in a]
    return 100 if hits else 0


def judge_score(fact, answer):
    r = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{
            "role": "user",
            "content": (
                "Ground truth: " + fact["truth"] + "\nQuestion: " + fact["question"] +
                "\nAgent's answer: " + answer +
                "\n\nScore 0-100 how correctly and completely the answer recalls the "
                "ground truth. Vague, hedging or wrong = low. Reply with ONLY the integer."
            ),
        }],
    )
    m = re.search(r"\d+", r.choices[0].message.content)
    return int(m.group()) if m else 0


def probe_snapshot(snap, facts):
    ctx = sanitize(snap["messages"])
    results = {}

    def one(fact):
        r = client.chat.completions.create(
            model=MODEL,
            messages=ctx + [{"role": "user", "content": PROBE_PREFIX + fact["question"]}],
        )
        ans = r.choices[0].message.content or ""
        s = string_score(fact, ans)
        j = judge_score(fact, ans)
        score = j if s is None else round(0.5 * s + 0.5 * j)
        return fact["id"], {"answer": ans.strip(), "string": s, "judge": j, "score": score}

    with ThreadPoolExecutor(8) as ex:
        for fid, res in ex.map(one, facts):
            results[fid] = res
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapdir", required=True)
    ap.add_argument("--facts", default=str(Path(__file__).parent / "facts.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=int, default=3, help="probe every Nth turn snapshot")
    a = ap.parse_args()

    facts = json.loads(Path(a.facts).read_text())
    snaps = sorted(Path(a.snapdir).glob("snap_*.json"))
    out = []
    for i, p in enumerate(snaps):
        snap = json.loads(p.read_text())
        keep = (
            snap["event"] in ("pre_compaction", "post_compaction", "end")
            or snap["i"] % a.every == 0
        )
        if not keep:
            continue
        print(f"probing {p.name} ({snap['event']}, {snap['tokens']} tok)")
        res = probe_snapshot(snap, facts)
        out.append({
            "i": snap["i"], "event": snap["event"], "t": snap["t"],
            "tokens": snap["tokens"], "compactions": snap["compactions"],
            "results": res,
            "mean": round(sum(r["score"] for r in res.values()) / len(res)),
        })
        Path(a.out).write_text(json.dumps(out, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
