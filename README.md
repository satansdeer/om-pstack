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

Explicit tool migrations cover `how`'s read-only scout, `no-comments`' Comment Sicko selector, questions in `automate-me`, `setup-pstack`, and the autonomous-run playbook, and `poteto-help`'s swarm row: its upstream cloud-agent wording becomes native OMP tasks with explicit Fabric LOCAL optional. Questions preserve options, multiple-answer intent, and approval requirements; when `ask` is unavailable they require a chat answer, never fabricated unattended approval. These instruction-level rules fail if their expected upstream wording changes, requiring semantic review rather than a blind rename. Delegate execution and interactive `ask` UI behavior are not covered by the runtime smoke check.

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

Swarm aggregation now has a full-paragraph, exact-once migration: missing, duplicate, or changed upstream wording (including removal of required coverage) rejects generation without replacing the installed distribution. These regression checks verify fail-closed conversion, not live RT03/RT04/RT09 aggregation or race behavior, which remains NOT_VERIFIED. Source/method admission, coverage, authorized retries, and race selection are controller instructions, not hard runtime or billing enforcement.

## Develop and verify

Requires Git and Python 3.11+. OMP is needed for runtime inspection, not generation.

```sh
git clone --branch omp https://github.com/satansdeer/om-pstack.git
cd om-pstack
python3 scripts/adapt.py
python3 -m unittest discover -s tests
omp --plugin-dir ./omp
```

In a shallow clone or Fabric prepared checkout without the locked upstream Git
object, use `python3 scripts/adapt.py --upstream-ref HEAD`. The generator checks
the committed `pstack/` tree and rejects local source changes; when that tree
matches `upstream.lock.json`, it preserves the existing upstream commit identity.

To reproduce native loading, invocation, and scope checks against an authenticated OMP model:

```sh
python3 scripts/check_omp.py
# Or select an existing authenticated profile:
python3 scripts/check_omp.py --profile YOUR_PROFILE
```

This check makes model requests in temporary directories without saving sessions. It asserts actual runtime events, including successful file reads after skill injection, not the assistant's final prose. It does not exercise edit/write scope or delegate execution. Keep the upstream plugin disabled to avoid name collisions.

### Source witness for a native swarm child

The controller freezes the consumer's full Git SHA, relevant repository-relative
files, exact method (including measurement count/order), and command argv in each
brief. In the child's authorized consumer checkout, run the checkout's standalone
stdlib command, for example:

```sh
python3 /absolute/path/to/om-pstack/scripts/witness.py \
  --expected-head FULL_CONSUMER_SHA \
  --source scripts/adapt.py --source adapters/omp.md --source tests/test_adapt.py \
  --method 'Run the adapter unittest suite once; no measurement sampling' \
  --witness /absolute/path/to/new-child-evidence.jsonl \
  -- python3 -m unittest discover -s tests -p test_adapt.py
```

Replace the example SHA, paths, method, and argv with the frozen brief; list every
relevant committed file, including predicate inputs/tests. Source paths are
relative to the consumer repository root, even when invoked from a subdirectory.
The command independently resolves canonical cwd, repository root, and full HEAD,
then compares actual file bytes directly with committed Git blobs. Wrong HEAD,
edited/missing/untracked source, symlinks, and staged changes to listed files
reject admission before the predicate runs. Raw-byte comparison also catches
edits hidden by `assume-unchanged`/`skip-worktree`; Git filters or line-ending
conversions are not treated as identical bytes. Unlisted changes are out of scope.

The new witness file is exclusively created, never reused or overwritten. Its
first JSONL record is either `rejected` with an error, or a flushed/fsynced
`pre_test` binding the exact argv/method, canonical cwd/root, requested/observed
HEAD, source paths, Git blob IDs, and committed/observed SHA-256 hashes.
Only after that write does the predicate run, without a shell, in the recorded
cwd. Stdout/stderr remain on the child's normal streams; they are not captured
in the witness. A second `result` record contains the subprocess return code;
ordinary exit status is preserved, and signal termination returns `128 + signal`
while retaining Python's negative return code in the artifact. Admission,
launch, and witness I/O errors return 2; launch failure records `launch_error`.
An interrupted or incomplete witness is not success. CLI parse errors or an
unwritable/existing witness can fail before a new artifact exists.

The artifact does not collect environment variables, auth, credentials, provider,
or model identity. Do not put secrets in argv or the method: both are recorded.
This is pre-test source evidence, not a snapshot, filesystem lock, sandbox, or
protection against concurrent edits or a malicious child. The controller must
independently check the frozen source list, method/argv, terminal record, and
predicate evidence; an arbitrary method label or exit 0 alone is not acceptance.
It does not prove model selection, native Fabric execution, swarm coverage,
aggregation, or race selection. Historical v0.1.20 two-adapter-test acceptance
was narrow and append-only, not full swarm parity. Live RT03/RT04/RT09 acceptance
on the accepted Fabric v0.1.21 / OMP 19.1.1 route still needs a concrete scenario,
fresh execution admission, and independent manager review; fixtures and worker
self-reports do not satisfy that gate. No upstream or generated skill changes
are needed to invoke this command from a native `/skill:swarm` brief.

To import upstream manually:

```sh
git fetch https://github.com/cursor/plugins.git main:refs/remotes/upstream/main
git restore --source upstream/main --staged --worktree -- pstack
python3 scripts/adapt.py --upstream-ref upstream/main
python3 -m unittest discover -s tests
```

Edit `adapters/omp.md` or the generator, not `omp/`. Generation rejects unsupported frontmatter, unknown/ambiguous explicit references, broken bundled skill links, and drift in migrated tool instructions before replacing the prior distribution. The regression checks cover deterministic generation, adapter-only updates, removal of retired skills, unchanged upstream source, metadata/path semantics, reference resolution and preservation of code/URLs, and decision-preserving tool migrations.

Upstream skill author: Lauren Tan. Upstream source and bundled license remain in [`pstack/`](pstack/). Fork adaptation and automation are MIT licensed; see [LICENSE](LICENSE).
