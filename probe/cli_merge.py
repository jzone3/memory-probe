"""Merge multiple per-turn Devin CLI exports (with compactions between turns)
into a single chronological snapshot sequence for probing."""

import json
import sys
from pathlib import Path


def messages_from_steps(steps, upto_idx):
    msgs = []
    for st in steps[: upto_idx + 1]:
        src = st["source"]
        m = st.get("message") or ""
        if src == "system":
            msgs.append({"role": "system", "content": m})
        elif src == "user":
            msgs.append({"role": "user", "content": m})
        elif src == "agent":
            tcs = st.get("tool_calls") or []
            am = {"role": "assistant", "content": m}
            if st.get("reasoning_content"):
                am["content"] = (m + "\n\n[reasoning] " + st["reasoning_content"]).strip()
            if tcs:
                am["tool_calls"] = [
                    {
                        "id": tc["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": tc["function_name"],
                            "arguments": json.dumps(tc.get("arguments") or {}),
                        },
                    }
                    for tc in tcs
                ]
            msgs.append(am)
            for res in (st.get("observation") or {}).get("results", []):
                msgs.append({
                    "role": "tool",
                    "tool_call_id": res.get("source_call_id", ""),
                    "content": (res.get("content") or "")[:4000],
                })
    return msgs


def merge(files, outdir, lane="swe"):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    snap_i = 0
    compactions = 0
    last_ts = ""
    for fi, f in enumerate(files):
        d = json.loads(Path(f).read_text())
        steps = d["steps"]
        first_new = True
        for idx, st in enumerate(steps):
            if st["source"] != "agent" or st["timestamp"] <= last_ts:
                continue
            event = "turn"
            if fi > 0 and first_new:
                compactions += 1
                event = "post_compaction"
            first_new = False
            snap = {
                "i": snap_i,
                "lane": lane,
                "event": event,
                "t": 0,
                "tokens": (st.get("metrics") or {}).get("prompt_tokens", 0),
                "compactions": compactions,
                "messages": messages_from_steps(steps, idx),
            }
            if event == "post_compaction":
                for s2 in steps:
                    m2 = s2.get("message") or ""
                    if s2["source"] == "system" and "summary of the previous conversation" in m2[:200]:
                        start = m2.find("<summary>")
                        snap["summary"] = m2[start:start + 1500] if start >= 0 else m2[:1500]
            (out / f"snap_{snap_i:04d}.json").write_text(json.dumps(snap))
            snap_i += 1
        last_ts = max(last_ts, steps[-1]["timestamp"])
    print(f"wrote {snap_i} snapshots, {compactions} compactions, to {outdir}")


if __name__ == "__main__":
    merge(sys.argv[1:-1], sys.argv[-1])
