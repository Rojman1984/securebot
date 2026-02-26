---
name: report-costs
description: Summarize Anthropic API spending from cost logs
triggers:
  - show me my api costs
  - cost report
  - how much have i spent
  - api spending
  - show costs
  - spending report
execution_mode: python
timeout: 10
---

# Report Costs

## Purpose
Reads `/memory/cost_logs.json`, aggregates Anthropic API costs by day and session,
and prints a clean plaintext summary to stdout for the Gateway synthesizer to read.

## Script
```python
#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict

COST_LOG_PATH = Path("/memory/cost_logs.json")

if not COST_LOG_PATH.exists():
    print("No cost logs found. No Anthropic API calls have been made yet.")
    sys.exit(0)

try:
    logs = json.loads(COST_LOG_PATH.read_text())
except Exception as e:
    print(f"Error reading cost logs: {e}")
    sys.exit(1)

if not isinstance(logs, list) or len(logs) == 0:
    print("Cost log is empty. No Anthropic API calls recorded.")
    sys.exit(0)

# Aggregate by day
by_day = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_cost": 0.0})
# Aggregate by session
by_session = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_cost": 0.0})

grand_calls = 0
grand_input = 0
grand_output = 0
grand_cost = 0.0

for entry in logs:
    day = entry.get("timestamp", "unknown")[:10]
    session = entry.get("session_id", "unknown")
    input_t = entry.get("input_tokens", 0)
    output_t = entry.get("output_tokens", 0)
    cost = entry.get("total_cost", 0.0)

    by_day[day]["calls"] += 1
    by_day[day]["input_tokens"] += input_t
    by_day[day]["output_tokens"] += output_t
    by_day[day]["total_cost"] += cost

    by_session[session]["calls"] += 1
    by_session[session]["input_tokens"] += input_t
    by_session[session]["output_tokens"] += output_t
    by_session[session]["total_cost"] += cost

    grand_calls += 1
    grand_input += input_t
    grand_output += output_t
    grand_cost += cost

lines = []
lines.append("=== SecureBot API Cost Report ===\n")
lines.append(f"Total API Calls : {grand_calls}")
lines.append(f"Total Input     : {grand_input:,} tokens")
lines.append(f"Total Output    : {grand_output:,} tokens")
lines.append(f"Grand Total Cost: ${grand_cost:.4f}\n")

lines.append("--- By Day ---")
for day in sorted(by_day.keys()):
    d = by_day[day]
    lines.append(
        f"  {day}: {d['calls']} calls | "
        f"{d['input_tokens']:,} in / {d['output_tokens']:,} out | "
        f"${d['total_cost']:.4f}"
    )

lines.append("\n--- By Session ---")
for session in sorted(by_session.keys()):
    s = by_session[session]
    lines.append(
        f"  {session}: {s['calls']} calls | "
        f"{s['input_tokens']:,} in / {s['output_tokens']:,} out | "
        f"${s['total_cost']:.4f}"
    )

print("\n".join(lines))
```

## Output Format
Plaintext report with grand totals, per-day breakdown, and per-session breakdown.

## Examples
User: "show me my api costs"
Output:
  === SecureBot API Cost Report ===
  Total API Calls : 3
  Total Input     : 4,512 tokens
  Total Output    : 892 tokens
  Grand Total Cost: $0.0090
  --- By Day ---
    2026-02-26: 3 calls | 4,512 in / 892 out | $0.0090
  --- By Session ---
    haiku_fallback: 3 calls | 4,512 in / 892 out | $0.0090
