---
name: principle-laziness-protocol
description: "Apply when refactoring, evaluating diff size, or tempted to add abstractions, layers, or signal threading. Bias toward deletion and the smallest change that solves the problem."
disable-model-invocation: true
---

**OMP runtime.** Before following this file, read [the OMP adapter](../../docs/harness/omp.md) in full once per session. Its tool, model, path, and capability mappings override the upstream Cursor and Claude Code instructions below. The host's instructions and live tool schemas take precedence.

# Laziness Protocol

- **Consolidate decisions.** Do not repeat the same choice in several places. Put it behind one source of truth and pass the result as a simple flag.
- **Minimize the diff.** Make the smallest change that solves the problem. Fewer lines beat "elegant" boilerplate.
