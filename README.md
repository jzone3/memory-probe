# Memory Probe

**What does an AI coding agent still know?** A demo that visualizes how context-window
compaction quality determines what an agent remembers during long tasks — inspired by
the trained self-compaction in [SWE-1.7](https://cognition.com/blog/swe-1-7).

## How it works

1. **Harness** (`harness/agent.py`) — a tool-using coding agent runs a long, constraint-heavy
   task with a deliberately small context cap. When the cap is hit, the context is compacted
   and the agent resumes from its own summary. Two lanes:
   - `naive`: generic "briefly summarize the conversation" prompt (gpt-4.1-mini harness)
   - `smart`: the **real SWE-1.7** running the same task through the Devin CLI, using its
     trained self-compaction (compactions forced with `/compact` between phases; full
     trajectories exported per turn and merged with `probe/cli_merge.py`)
   Every turn and every compaction, the exact context (full message list + token count)
   is snapshotted to JSON.

2. **Probe** (`probe/probe.py`) — replays each frozen snapshot with ~11 recall questions
   ("what seed must the RNG use?", "what's the golden apple rule?") answered from memory
   only, scored by string match + LLM judge against a ground-truth fact sheet
   (`probe/facts.json`).

3. **App** (`app/`) — visualizes the results: memory-fidelity curves over time with
   compaction markers, knowledge cards that literally blur out as facts are forgotten,
   and a probe panel showing both agents' verbatim answers at any point in time.

## Run it

```bash
export OPENAI_API_KEY=...
pip install openai tiktoken pytest

# 1. run both lanes (identical task, identical cap)
CONTEXT_CAP=4500 python3 harness/agent.py --lane naive --task-file harness/task.md --workspace ws/naive --outdir runs/naive
CONTEXT_CAP=4500 python3 harness/agent.py --lane smart --task-file harness/task.md --workspace ws/smart --outdir runs/smart

# 1b. (smart lane) run the task via Devin CLI with SWE-1.7, /compact between phases,
#     exporting the trajectory after each turn, then merge into snapshots:
python3 probe/cli_merge.py turn1.json turn2.json ... runs/swe

# 2. probe the snapshots
python3 probe/probe.py --snapdir runs/naive --out app/public/data/results_naive.json
python3 probe/probe.py --snapdir runs/smart --out app/public/data/results_smart.json
cp probe/facts.json app/public/data/

# 3. visualize
cd app && npm install && npm run dev
```
