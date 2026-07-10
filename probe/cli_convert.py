"""Convert a Devin CLI ATIF trajectory export into harness-style snapshots."""

import json
import sys
from pathlib import Path


def convert(traj_file, outdir, lane="swe"):
    d = json.loads(Path(traj_file).read_text())
    steps = d["steps"]
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    messages = []
    snap_i = 0
    compactions = 0
    t0 = None
    for st in steps:
        ts = st["timestamp"]
        if t0 is None:
            t0 = ts
        src = st["source"]
        msg = st.get("message") or ""
        event = "turn"
        if src == "system":
            if "compact" in msg.lower()[:200] or "summary of the conversation" in msg.lower():
                compactions += 1
                event = "post_compaction"
            messages.append({"role": "system", "content": msg})
            if event != "post_compaction":
                continue
        elif src == "user":
            messages.append({"role": "user", "content": msg})
            continue
        elif src == "agent":
            tcs = st.get("tool_calls") or []
            am = {"role": "assistant", "content": msg}
            if st.get("reasoning_content"):
                am["content"] = (msg + "\n\n[reasoning] " + st["reasoning_content"]).strip()
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
            messages.append(am)
            for res in (st.get("observation") or {}).get("results", []):
                messages.append({
                    "role": "tool",
                    "tool_call_id": res.get("source_call_id", ""),
                    "content": (res.get("content") or "")[:4000],
                })
        tokens = (st.get("metrics") or {}).get("prompt_tokens", 0)
        snap = {
            "i": snap_i,
            "lane": lane,
            "event": event,
            "t": 0,
            "tokens": tokens,
            "compactions": compactions,
            "messages": messages,
        }
        (out / f"snap_{snap_i:04d}.json").write_text(json.dumps(snap))
        snap_i += 1
    print(f"wrote {snap_i} snapshots, {compactions} compactions, to {outdir}")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
