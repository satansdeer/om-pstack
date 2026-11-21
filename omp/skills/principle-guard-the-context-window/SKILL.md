---
name: principle-guard-the-context-window
description: "Apply when context is filling up: large outputs, long files, repeated reads, fan-out planning. Route bulk to subagents; keep summaries in the main thread, not raw payloads."
disable-model-invocation: true
---

**OMP runtime.** Before following this file, read [the OMP adapter](../../docs/harness/omp.md) in full once per session. Its tool, model, path, and capability mappings override the upstream Cursor and Claude Code instructions below. The host's instructions and live tool schemas take precedence.

# Guard the Context Window

[**Why:**](../why/SKILL.md) Context overflow degrades reasoning quality, creates compression artifacts, and halts progress.

**Pattern:**
- **Size phases and cap scope.** Limit files per phase, set turn budgets, account for mechanism costs.
