# om-pstack

[Poteto's pstack](https://github.com/cursor/plugins/tree/main/pstack), adapted for [OMP](https://omp.sh). This is a fork of `cursor/plugins`, not an upstream Cursor release.

## Install

```sh
omp plugin marketplace add satansdeer/om-pstack
omp plugin install om-pstack@om-pstack
```

Restart OMP or run `/reload-plugins`, then use `/skill:poteto-mode`, `/skill:setup-pstack`, or `/skill:poteto-help`. Skill names are unchanged. If the original `pstack@cursor-plugins` is installed, disable it before loading this fork to avoid duplicate skill and agent names:

```sh
omp plugin disable pstack@cursor-plugins
```

The fork does not change your existing installations or model configuration itself.

Update an installed copy with:

```sh
omp plugin marketplace update om-pstack
omp plugin upgrade om-pstack@om-pstack
```

## What is adapted

Every generated skill and delegate agent loads the [OMP adapter](adapters/omp.md). Deterministic converters handle metadata, file scope, concrete installation paths, bundled skill references, native command spelling, and the simple tool instructions listed below. The adapter governs remaining Cursor-specific prose; those workflows are not yet fully converted.

The metadata converter preserves `disable-model-invocation`: manual-only skills remain explicitly invocable without appearing in OMP's model-visible skill list. It removes the recognized Agent Plugins `$schema` declaration so OMP uses its native loader, which supports this field. Names, descriptions, icons, and colors are preserved; icon/color rendering is not promised. Unknown metadata and unsupported path syntax fail generation rather than silently losing semantics.

Cursor skill `paths` become native OMP time-traveling stream rules (TTSR), gated to matching `read`, `edit`, and `write` tool paths. Ordinary OMP rule `globs` alone do not attach instructions. The generated rule interrupts a matching tool call and asks the model to read the bundled skill through `skill://`, preserving its relative resource links. This requires enabled OMP rules/TTSR; shell commands and other file-access tools are not covered. It is a native prompt-injection mapping, not a security boundary or a claim of identical Cursor context behavior.

Bundled bold/backtick skill references, including shorthand such as `type-system-discipline`, become relative links to the exact bundled `SKILL.md`. Principle-index entries are validated, existing bundled skill links are checked, and ambiguous or unknown explicit skill references reject the update before replacing the installed tree. Known slash commands become `/skill:<name>` in descriptions, prose, and text/Markdown prompt examples. Executable code fences, inline code expressions, URLs, and link targets are preserved. External dependencies and template skill names are not supplied or guessed. The inherited Claude Code harness is retained as provenance, not converted into OMP instructions.

Explicit tool migrations cover `how`'s read-only scout, `no-comments`' Comment Sicko selector, and questions in `automate-me`, `setup-pstack`, and the autonomous-run playbook. Questions preserve options, multiple-answer intent, and approval requirements; when `ask` is unavailable they require a chat answer, never fabricated unattended approval. These instruction-level rules fail if their expected upstream wording changes, requiring semantic review rather than a blind rename. Delegate execution and interactive `ask` UI behavior are not covered by the runtime smoke check.

The adapter requires `/skill:setup-pstack` to write `~/.omp/agent/pstack-models.md` and discover real OMP models rather than use Cursor slugs. The setup/model workflow itself still needs deterministic conversion. The inspected OMP 19.1.0 task schema exposes neither per-task model selection nor `sourceSession`; required model overrides, multi-model panels, and historical-session delegation cannot be claimed supported through that schema. Other host versions must be checked against their live schemas. Requested reasoning budgets are not claimed as enforced.

Cursor Automations, cloud VMs, custom modes, external Cursor plugins, and future chat wakes are not emulated. The adapter uses real available equivalents or reports a required capability as blocked. GitHub review comments remain accessible through an authenticated forge CLI. No invented tool calls, fake URLs, or silent weakening of verification gates.

Next conversion work: role/model setup, complex delegate lifecycle and panel orchestration, scoped history access, and skill-authoring workflows. Cloud agents and scheduled conversation wakes remain last. These still rely on the adapter's capability gates, not completed reproducible translations.

## Upstream tracking

The default `omp` branch contains:

- `pstack/`: unchanged upstream source.
- `adapters/omp.md`: human-maintained OMP runtime contract.
- `scripts/adapt.py`: Python-standard-library generator.
- `omp/`: generated, installable OMP plugin, including the upstream MIT license.
- `.omp-plugin/marketplace.json`: OMP-only catalog. The inherited Cursor catalogs are not used by OMP.
- `upstream.lock.json`: exact upstream commit and pstack tree used.

The **Sync OMP from upstream** Action runs daily at 06:23 UTC, on manual dispatch, and when its workflow definition changes. It imports only `pstack/` from `cursor/plugins:main`, regenerates the plugin/catalog, runs the regression check, and pushes changes to `omp`. Deleted upstream skills disappear from the generated plugin. Unrelated upstream commits produce no lock or distribution churn. Local adapter changes are never merged into the upstream tree.

A content-addressed, non-semver install version changes for source, adapter, or generator updates, including upstream changes that do not bump pstack's version. OMP detects these versions by inequality. Refreshing the catalog alone does not upgrade an installed plugin.

Checks on adapter changes and PRs require generated output to be current. The inherited Cursor harness validation is replaced by OMP checks. Sync failures are visible as failed GitHub Actions runs; upstream prompt/tool changes may require an adapter update. This is deterministic adaptation, not a claim that every future Cursor-only workflow becomes runnable automatically. GitHub can disable scheduled workflows after 60 days of repository inactivity; re-enable the workflow if that happens.

Verified with OMP 18.18.6: local and GitHub marketplace installation, adapter-only version upgrades, all 58 skills registered, 57 manual-only skills absent from automatic discovery, explicit `/skill:poteto-help` expansion, both delegate agents available, and TS/TSX rule injection before successful reads while Python reads do not trigger it. These checks do not certify the semantics of every skill or future upstream change.

Verified with OMP 19.1.0: all 58 skills registered, manual-only visibility and explicit invocation preserved, native command spelling present in expanded prompts, both agents registered, and TS/TSX reads successfully loading the exact linked principle file without tool errors. Python scope remains excluded. This verifies reference resolution and native loading, not every skill's execution.

## Develop and verify

Requires Git and Python 3.11+. OMP is needed for runtime inspection, not generation.

```sh
git clone --branch omp https://github.com/satansdeer/om-pstack.git
cd om-pstack
python3 scripts/adapt.py
python3 -m unittest discover -s tests
omp --plugin-dir ./omp
```

To reproduce native loading, invocation, and scope checks against an authenticated OMP model:

```sh
python3 scripts/check_omp.py
# Or select an existing authenticated profile:
python3 scripts/check_omp.py --profile YOUR_PROFILE
```

This check makes model requests in temporary directories without saving sessions. It asserts actual runtime events, including successful file reads after skill injection, not the assistant's final prose. It does not exercise edit/write scope or delegate execution. Keep the upstream plugin disabled to avoid name collisions.

To import upstream manually:

```sh
git fetch https://github.com/cursor/plugins.git main:refs/remotes/upstream/main
git restore --source upstream/main --staged --worktree -- pstack
python3 scripts/adapt.py --upstream-ref upstream/main
python3 -m unittest discover -s tests
```

Edit `adapters/omp.md` or the generator, not `omp/`. Generation rejects unsupported frontmatter, unknown/ambiguous explicit references, broken bundled skill links, and drift in migrated tool instructions before replacing the prior distribution. The regression checks cover deterministic generation, adapter-only updates, removal of retired skills, unchanged upstream source, metadata/path semantics, reference resolution and preservation of code/URLs, and decision-preserving tool migrations.

Upstream skill author: Lauren Tan. Upstream source and bundled license remain in [`pstack/`](pstack/). Fork adaptation and automation are MIT licensed; see [LICENSE](LICENSE).
