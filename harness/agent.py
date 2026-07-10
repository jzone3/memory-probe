"""Agent harness with a hard context cap and pluggable compaction strategies.

Runs a tool-using coding agent on a long task, snapshotting the exact
context (message list + token counts) every turn and around every
compaction event.
"""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import tiktoken
from openai import OpenAI

client = OpenAI()
ENC = tiktoken.get_encoding("o200k_base")

MODEL = os.environ.get("HARNESS_MODEL", "gpt-4.1-mini")
CONTEXT_CAP = int(os.environ.get("CONTEXT_CAP", "9000"))  # tokens, deliberately small
MAX_TURNS = int(os.environ.get("MAX_TURNS", "60"))

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a file (overwrites). Path is relative to workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file. Path is relative to workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_cmd",
            "description": "Run a shell command inside the workspace (e.g. python -m pytest).",
            "parameters": {
                "type": "object",
                "properties": {"cmd": {"type": "string"}},
                "required": ["cmd"],
            },
        },
    },
]

REQUIRED_FILES = [
    "snakelib/engine.py", "snakelib/rng.py", "snakelib/render.py",
    "snakelib/obstacles.py", "snakelib/replay.py", "snakelib/powerups.py",
    "tests/test_engine.py", "tests/test_render.py", "tests/test_obstacles.py",
    "tests/test_replay.py", "tests/test_powerups.py", "cli.py", "README.md",
]

NAIVE_COMPACTION_PROMPT = (
    "The conversation is too long. Briefly summarize what has happened so far "
    "in a short paragraph."
)

SMART_COMPACTION_PROMPT = (
    "You are about to lose your context window. Write a complete working-state "
    "summary you will resume from. It is the ONLY thing you will remember. "
    "Use exactly this structure, be precise, keep every number, name, path and "
    "constraint verbatim:\n"
    "## Goal\n## Hard constraints (verbatim)\n## Decisions made\n"
    "## Work completed (files + what's in them)\n## Test status\n## Next step\n"
    "## Open problems / gotchas"
)


def ntokens(messages):
    return sum(len(ENC.encode(json.dumps(m, default=str))) for m in messages)


def msg_to_dict(m):
    d = {"role": m.role, "content": m.content or ""}
    if m.tool_calls:
        d["tool_calls"] = [
            {
                "id": t.id,
                "type": "function",
                "function": {"name": t.function.name, "arguments": t.function.arguments},
            }
            for t in m.tool_calls
        ]
    return d


class Harness:
    def __init__(self, lane, task, workspace, outdir):
        self.lane = lane  # "naive" or "smart"
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.snap_i = 0
        self.compactions = 0
        self.t0 = time.time()
        self.system = {
            "role": "system",
            "content": (
                "You are an expert software engineer agent working autonomously in a "
                "workspace. Use the tools to build and test. Work step by step. "
                "Never ask the user questions. Keep going until the task is fully done, "
                "then reply with exactly DONE."
            ),
        }
        self.messages = [self.system, {"role": "user", "content": task}]

    def snapshot(self, event, extra=None):
        snap = {
            "i": self.snap_i,
            "lane": self.lane,
            "event": event,
            "t": round(time.time() - self.t0, 1),
            "tokens": ntokens(self.messages),
            "compactions": self.compactions,
            "messages": self.messages,
        }
        if extra:
            snap.update(extra)
        path = self.outdir / f"snap_{self.snap_i:04d}.json"
        path.write_text(json.dumps(snap))
        self.snap_i += 1

    def exec_tool(self, name, args):
        try:
            if name == "write_file":
                p = self.workspace / args["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args["content"])
                return f"wrote {args['path']} ({len(args['content'])} chars)"
            if name == "read_file":
                return (self.workspace / args["path"]).read_text()[:6000]
            if name == "run_cmd":
                r = subprocess.run(
                    args["cmd"], shell=True, cwd=self.workspace,
                    capture_output=True, text=True, timeout=120,
                )
                return (r.stdout + r.stderr)[-4000:] or "(no output)"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"
        return "unknown tool"

    def compact(self):
        self.snapshot("pre_compaction")
        prompt = NAIVE_COMPACTION_PROMPT if self.lane == "naive" else SMART_COMPACTION_PROMPT
        r = client.chat.completions.create(
            model=MODEL,
            messages=self.messages + [{"role": "user", "content": prompt}],
        )
        summary = r.choices[0].message.content
        self.compactions += 1
        self.messages = [
            self.system,
            {
                "role": "user",
                "content": (
                    "You are resuming a task after a context compaction. "
                    "Your summary of prior work:\n\n" + summary +
                    "\n\nContinue the task from here."
                ),
            },
        ]
        self.snapshot("post_compaction", {"summary": summary})

    def run(self):
        for turn in range(MAX_TURNS):
            if ntokens(self.messages) > CONTEXT_CAP:
                self.compact()
            r = client.chat.completions.create(
                model=MODEL, messages=self.messages, tools=TOOLS,
            )
            m = r.choices[0].message
            self.messages.append(msg_to_dict(m))
            if m.tool_calls:
                for t in m.tool_calls:
                    out = self.exec_tool(t.function.name, json.loads(t.function.arguments))
                    self.messages.append(
                        {"role": "tool", "tool_call_id": t.id, "content": out}
                    )
            self.snapshot("turn")
            if not m.tool_calls and m.content and "DONE" in m.content:
                missing = [f for f in REQUIRED_FILES if not (self.workspace / f).exists()]
                if not missing:
                    break
                self.messages.append({
                    "role": "user",
                    "content": (
                        "NOT done. These required deliverables are still missing: "
                        + ", ".join(missing)
                        + ". Re-read the task requirements in your memory and continue."
                    ),
                })
            if not m.tool_calls:
                self.messages.append(
                    {"role": "user", "content": "Continue. Use tools. Reply DONE only when fully finished."}
                )
        self.snapshot("end")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=["naive", "smart"], required=True)
    ap.add_argument("--task-file", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    task = Path(a.task_file).read_text()
    Harness(a.lane, task, a.workspace, a.outdir).run()


if __name__ == "__main__":
    main()
