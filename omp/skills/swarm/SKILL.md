---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /skill:swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
disable-model-invocation: true
---

**OMP runtime.** Before following this file, read [the OMP adapter](../../docs/harness/omp.md) in full once per session. Its tool, model, path, and capability mappings override the upstream Cursor and Claude Code instructions below. The host's instructions and live tool schemas take precedence.

# Swarm

## Start

Open a todolist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Read the OMP adapter's swarm routing section before selecting workers. Ordinary `/skill:swarm` uses native OMP `task`; only explicit `--fabric-local` selects Fabric. Read `~/.omp/agent/pstack-models.md` if present. Native tasks inherit the parent unless their live schema supports an explicitly validated model choice; Fabric workers inherit their requested harness's native default when `model` is omitted. Never guess model identifiers or claim unsupported model/effort controls. For a model race, establish supported exact choices before launching; otherwise report that gate BLOCKED.
4. Give each worker its own writable output when it writes. When workers verify or measure commits, each brief names the exact SHAs. A measurement brief also names the method (sample count, what one sample is, order). The worker records both in its result.

## Phase B: Fan out

For ordinary swarm, spawn all N workers with native OMP `task`: shared `context` and one self-contained `tasks` entry per worker with `task` and `solutionSpace`; omit `agent` for the default worker. Native completion auto-delivers; use `wait` only when blocked. For explicit `/skill:swarm --fabric-local --fabric-project NAME --fabric-harness ID`, follow the OMP adapter's typed Fabric route instead. Do not invoke both routes. Required remote/cloud execution or security isolation is unsupported: report BLOCKED before spawning, never substitute local workers.

For Fabric, resolve any requested branch to its exact commit SHA and require a matching READY source through `source_ref`; never prepare implicitly or use an older base. Ordinary native tasks needing an independent checkout require an explicitly authorized real worktree and exact working directory in their briefs. Record each worker's actual source SHA; neither route provides a cloud branch field.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence. A worker that can prove a defect reports `ISSUES` and lists every issue it can prove, not only the first.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Drop a result that does not record the SHAs and method its brief names, and respawn that worker once. After a second miss, record a gap. A gap does not count as a pass. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

## Phase D: Report

Return one consolidated in-chat report with a result table, issue one-liners, gaps or dropouts, and the race rule when used.
