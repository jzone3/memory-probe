"""Extract per-snapshot agent activity (tool calls + outputs) for the app."""

import json
import sys
from pathlib import Path


def label(tc, next_tool_msg):
    fn = tc["function"]["name"]
    try:
        args = json.loads(tc["function"]["arguments"])
    except Exception:  # noqa: BLE001
        args = {}
    out = (next_tool_msg or "")[:160].replace("\n", " ")
    if fn in ("write_file", "write"):
        path = args.get("path") or args.get("file_path")
        return {"kind": "write", "text": f"wrote {path}", "detail": out}
    if fn in ("read_file", "read"):
        path = args.get("path") or args.get("file_path")
        return {"kind": "read", "text": f"read {path}", "detail": ""}
    if fn in ("run_cmd", "exec"):
        cmd = args.get("cmd") or args.get("command") or ""
        return {"kind": "run", "text": f"$ {cmd[:80]}", "detail": out}
    return {"kind": "tool", "text": fn, "detail": out}


def activity_of(snap):
    msgs = snap["messages"]
    acts = []
    for idx, m in enumerate(msgs):
        if m["role"] == "assistant" and m.get("tool_calls"):
            for j, tc in enumerate(m["tool_calls"]):
                nxt = ""
                k = idx + 1 + j
                if k < len(msgs) and msgs[k]["role"] == "tool":
                    nxt = msgs[k].get("content") or ""
                acts.append(label(tc, nxt))
    return acts[-5:]


def main(snapdir, results_file, out):
    results = json.loads(Path(results_file).read_text())
    data = {}
    for r in results:
        p = Path(snapdir) / f"snap_{r['i']:04d}.json"
        snap = json.loads(p.read_text())
        entry = {"activity": activity_of(snap)}
        if snap["event"] == "post_compaction":
            entry["summary"] = snap.get("summary", "")[:1500]
        data[str(r["i"])] = entry
    Path(out).write_text(json.dumps(data))
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
