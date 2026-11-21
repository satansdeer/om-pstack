# om-pstack

[Poteto's pstack](https://github.com/cursor/plugins/tree/main/pstack), adapted for [OMP](https://omp.sh). This is a fork of `cursor/plugins`, not an upstream Cursor release.

## Install

```sh
omp plugin marketplace add satansdeer/om-pstack
omp plugin install om-pstack@om-pstack
```

Restart OMP or run `/reload-plugins`, then use `/poteto-mode`, `/setup-pstack`, or `/poteto-help`. Skill names are unchanged. If the original `pstack@cursor-plugins` is installed, disable it before loading this fork to avoid duplicate skill and agent names:

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

Every generated skill and delegate agent loads the [OMP adapter](adapters/omp.md). It translates tools, task fields, agent lifecycle, installation paths, model selection, history access, and real-surface verification. Concrete skill/plugin/model-config paths are rewritten in generated Markdown. Upstream instructions remain available beneath the adapter; they are not executable Cursor tool calls in OMP.

`/setup-pstack` writes `~/.omp/agent/pstack-models.md`. Skills explicitly read it. Models come from OMP's inventory, not hard-coded Cursor slugs. Missing role settings inherit the parent model. OMP's current task schema has no independent per-task reasoning setting; requested budgets are not claimed as enforced.

Cursor Automations, cloud VMs, custom modes, external Cursor plugins, and future chat wakes are not emulated. The adapter uses real available equivalents or reports a required capability as blocked. GitHub review comments remain accessible through an authenticated forge CLI. No invented tool calls, fake URLs, or silent weakening of verification gates.

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

Verified with OMP 18.18.6: local and GitHub marketplace installation, adapter-only version upgrades, and installed `setup-pstack` skill resolution. These checks do not certify the semantics of every skill or future upstream change.

## Develop and verify

Requires Git and Python 3.11+. OMP is needed for runtime inspection, not generation.

```sh
git clone --branch omp https://github.com/satansdeer/om-pstack.git
cd om-pstack
python3 scripts/adapt.py
python3 -m unittest discover -s tests
omp --plugin-dir ./omp
```

To import upstream manually:

```sh
git fetch https://github.com/cursor/plugins.git main:refs/remotes/upstream/main
git restore --source upstream/main --staged --worktree -- pstack
python3 scripts/adapt.py --upstream-ref upstream/main
python3 -m unittest discover -s tests
```

Edit `adapters/omp.md` or the generator, not `omp/`. Generation rejects malformed skill/agent frontmatter before replacing the prior distribution. The regression check covers deterministic generation, adapter-only updates, removal of retired skills, preservation of upstream source, and rejection of malformed updates.

Upstream skill author: Lauren Tan. Upstream source and bundled license remain in [`pstack/`](pstack/). Fork adaptation and automation are MIT licensed; see [LICENSE](LICENSE).
