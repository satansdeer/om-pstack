#!/usr/bin/env python3
"""Generate the OMP distribution without modifying the upstream pstack tree."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/satansdeer/om-pstack"
PATHS = {
    "~/.cursor/rules/pstack-models.mdc": "~/.omp/agent/pstack-models.md",
    ".cursor-plugin/plugin.json": "plugin.json",
    "~/.cursor/plugins/": "~/.omp/plugins/",
    "~/.cursor/skills/": "~/.omp/skills/",
    ".cursor/skills/": ".omp/skills/",
}


def json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def convert_metadata(text, *, agent=False):
    """Translate the supported upstream frontmatter; reject new semantics."""
    if not text.startswith("---\n"):
        raise ValueError("Expected YAML frontmatter in skill or agent")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("Unterminated YAML frontmatter in skill or agent")
    fields = {}
    key = None
    for line in text[4:end].splitlines(keepends=True):
        match = re.match(r"^([a-z][a-z_-]*):", line)
        if match:
            key = match[1]
            if key in fields:
                raise ValueError(f"Duplicate frontmatter field: {key}")
            fields[key] = line
        elif key is None or (line.strip() and not line[0].isspace()):
            raise ValueError(f"Unsupported frontmatter syntax: {line.rstrip()}")
        else:
            fields[key] += line
    allowed = {"name", "description", "model", "is_background"} if agent else {
        "name", "description", "disable-model-invocation", "icon", "color", "paths",
    }
    if unknown := fields.keys() - allowed:
        raise ValueError(f"Unsupported frontmatter fields: {', '.join(sorted(unknown))}")
    if "disable-model-invocation" in fields:
        value = fields["disable-model-invocation"].split(":", 1)[1].strip()
        if value not in ("true", "false"):
            raise ValueError("disable-model-invocation must be true or false")
    paths = None
    if "paths" in fields:
        value = fields.pop("paths").split(":", 1)[1].strip()
        try:
            paths = json.loads(value)
        except ValueError as error:
            raise ValueError("paths must be a JSON array of glob strings") from error
        if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p for p in paths):
            raise ValueError("paths must be a nonempty JSON array of glob strings")
    if agent:
        # Model/background execution is governed by the adapter until its own converter lands.
        fields.pop("model", None)
        fields.pop("is_background", None)
    header = "".join(value.rstrip("\n") + "\n" for value in fields.values())
    return "---\n" + header + "---\n" + text[end + len("\n---\n"):], paths


def inject_adapter(text, link):
    notice = (
        f"**OMP runtime.** Before following this file, read [the OMP adapter]({link}) "
        "in full once per session. Its tool, model, path, and capability mappings "
        "override the upstream Cursor and Claude Code instructions below. "
        "The host's instructions and live tool schemas take precedence.\n\n"
    )
    if not text.startswith("---\n"):
        raise ValueError("Expected YAML frontmatter in skill or agent")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("Unterminated YAML frontmatter in skill or agent")
    end += len("\n---\n")
    return text[:end] + "\n" + notice + text[end:].lstrip("\n")


EXTERNAL_SKILLS = {"create-skill", "deslop", "/orchestrate"}
QUESTION = (
    "use OMP's `ask` tool if exposed, otherwise ask in chat with the same options; "
    "wait for the user's answer and never infer approval in unattended sessions"
)
TOOL_REWRITES = {
    "skills/swarm/SKILL.md": [
        (
            "3. Pick the worker model from the `swarm workers` line in `~/.cursor/rules/pstack-models.mdc`. "
            "If the rule or that line is missing, use `claude-opus-5-5-high-fast`. "
            "For `auto` or `inherit-parent`, omit `model` so the workers run on the parent model. "
            "If the Task tool rejects a slug, use the default and say so. "
            "If it rejects the default, use the closest valid slug of the same family from its error message. "
            "For a model race, name each arm's model up front. "
            "Pick each subagent's reasoning level for the job, per the Subagents section of the **poteto-mode** skill.",
            "3. Read the OMP adapter's swarm routing section before selecting workers. Ordinary "
            "`/swarm` uses native OMP `task`; only explicit `--fabric-local` selects Fabric. "
            "Read `~/.omp/agent/pstack-models.md` if present. Native tasks inherit the parent "
            "unless their live schema supports an explicitly validated model choice; Fabric workers "
            "inherit their requested harness's native default when `model` is omitted. Never guess "
            "model identifiers or claim unsupported model/effort controls. For a model race, "
            "establish supported exact choices before launching; otherwise report that gate BLOCKED.",
        ),
        (
            "Spawn all N workers in one message with `subagent_type: generalPurpose`, "
            '`environment: "cloud"`, `run_in_background: true`, and the step 3 model, '
            "left unset for `auto` or `inherit-parent`. "
            'Use `environment: "local"` only when the worker needs access to something on the user\'s computer.',
            "For ordinary swarm, spawn all N workers with native OMP `task`: shared `context` "
            "and one self-contained `tasks` entry per worker with `task` and `solutionSpace`; "
            "omit `agent` for the default worker. Native completion auto-delivers; use `wait` "
            "only when blocked. For explicit `/swarm --fabric-local --fabric-project NAME "
            "--fabric-harness ID`, follow the OMP adapter's typed Fabric route instead. "
            "Do not invoke both routes. Required remote/cloud execution or security isolation "
            "is unsupported: report BLOCKED before spawning, never substitute local workers.",
        ),
        (
            "When a worker must start from a non-default pushed branch, pass `cloud_base_branch`.",
            "For Fabric, resolve any requested branch to its exact commit SHA and require a "
            "matching READY source through `source_ref`; never prepare implicitly or use an older "
            "base. Ordinary native tasks needing an independent checkout require an explicitly "
            "authorized real worktree and exact working directory in their briefs. Record each "
            "worker's actual source SHA; neither route provides a cloud branch field.",
        ),
    ],
    "skills/poteto-help/SKILL.md": [(
        "Run parallel checks over slices, or race workers, as cloud agents",
        "Run parallel checks over slices or race workers with native OMP tasks; explicit Fabric LOCAL is optional",
    )],
    "skills/how/SKILL.md": [(
        "Spawn one Task subagent with `subagent_type: generalPurpose` and `readonly: true` "
        "that explores and explains in one pass.",
        "Use OMP `task` with one `tasks` entry selecting `agent: \"scout\"` to explore and "
        "explain read-only in one pass. Supply the shared `context`, a self-contained "
        "`task`, and its bounded `solutionSpace`; do not pass Cursor's `readonly` field.",
    )],
    "skills/no-comments/SKILL.md": [(
        'Spawn `Task` with `subagent_type: "comment-sicko"`. Pass the scope.',
        'Use OMP `task` with one `tasks` entry selecting `agent: "comment-sicko"`. '
        'Supply shared `context`, the scope in its self-contained `task`, and a bounded `solutionSpace`.',
    )],
    "skills/automate-me/SKILL.md": [
        ("confirm intent with `AskQuestion`", f"confirm intent: {QUESTION}"),
        ("Use the `AskQuestion` tool (structured multi-choice) rather than asking the user to type from scratch.",
         f"For structured choices, {QUESTION}."),
        ("`allow_multiple: true` for category questions",
         "allow multiple answers for category questions (use the live tool schema, not Cursor's `allow_multiple` field)"),
    ],
    "skills/setup-pstack/SKILL.md": [(
        "Prefer AskQuestion over free text.", f"For these choices, {QUESTION}.",
    )],
    "skills/poteto-mode/playbooks/autonomous-run.md": [(
        "or use `AskQuestion`", "or ask unnecessary questions with `ask` or in chat",
    )],
}


def convert_tools(text, relative):
    """Explicit migrations: upstream wording changes require semantic review."""
    for old, new in TOOL_REWRITES.get(relative.as_posix(), []):
        expected = 2 if relative.as_posix() == "skills/setup-pstack/SKILL.md" else 1
        if text.count(old) != expected:
            raise ValueError(f"Tool instruction changed; review conversion of {old!r}")
        text = text.replace(old, new)
    return text


def convert_references(text, relative, skills):
    """Resolve bundled references to same-plugin files, not guessed skill aliases."""
    aliases = {}
    for name in sorted(skills):
        for alias in {name, name.removeprefix("principle-")}:
            aliases.setdefault(alias, set()).add(name)

    def resolve(label, required=False, principle=False):
        slug = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-")
        candidates = aliases.get(slug, set())
        if principle:
            candidates = {name for name in candidates if name.startswith("principle-")}
        if len(candidates) > 1:
            raise ValueError(f"Ambiguous skill reference: {label}")
        if candidates:
            return next(iter(candidates))
        if required and label not in EXTERNAL_SKILLS and not re.search(r"[<>*]|^-mode$", label):
            raise ValueError(f"Unknown skill reference: {label}")
        return None

    def link(label, name):
        target = os.path.relpath(skills[name], relative.parent).replace(os.sep, "/")
        return f"[{label}]({target})"

    commands = re.compile(
        r"(?<![\w/:.~])/(?P<name>" + "|".join(re.escape(n) for n in sorted(skills, key=lambda n: (-len(n), n)))
        + r")(?![\w/-]|\.[\w.-])"
    )

    def prose(part):
        parts = re.split(r"(`[^`\n]+`)", part)
        part = "".join(
            token if index % 2 and not token.startswith("`/") else
            commands.sub(lambda m: "/skill:" + m["name"], token)
            for index, token in enumerate(parts)
        )
        def reference(match):
            label = match[2] or match[3]
            suffix = match[4]
            name = resolve(label, required=bool(suffix), principle=bool(suffix and "principle" in suffix))
            return (link(match[1], name) if name else match[1]) + (suffix or "")
        return re.sub(r"(\*\*([^*\n]+)\*\*|`([^`\n]+)`)( ((?:principle )?skills?)\b)?", reference, part)

    output, fence = [], None
    header_end = text.find("\n---\n", 4) + 5 if text.startswith("---\n") else 0
    if header_end:
        output.append(commands.sub(lambda m: "/skill:" + m["name"], text[:header_end]))
    principle_index = False
    for line in text[header_end:].splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)", line)
        if marker:
            if fence is None:
                fence = (marker[1][0], len(marker[1]), marker[2].strip() in ("", "text", "markdown"))
            elif marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            output.append(line)
            continue
        if fence and not fence[2]:
            output.append(line)
            continue
        if relative.as_posix() == "skills/poteto-mode/SKILL.md" and line.startswith("## "):
            principle_index = line.strip() == "## Principles"
        if principle_index and (entry := re.match(r"- \*\*([^*]+)\*\*(?: \(\*\*([^*]+)\*\*\))?", line)):
            resolve(entry[2] or entry[1], required=True, principle=True)
        # Existing links retain their target and label; only command labels change.
        parts = re.split(r"(\[[^\]\n]*\]\([^)\n]*\))", line)
        for index in range(1, len(parts), 2):
            label, target = parts[index].split("](", 1)
            if target[:-1].endswith("SKILL.md") and not re.match(r"[a-z]+://", target):
                resolved = Path(os.path.normpath(relative.parent / target[:-1]))
                if resolved not in skills.values():
                    raise ValueError(f"Missing bundled skill target: {target[:-1]}")
            parts[index] = commands.sub(lambda m: "/skill:" + m["name"], label) + "](" + target
        output.append("".join(part if index % 2 else prose(part) for index, part in enumerate(parts)))
    return "".join(output)


def generate(source, adapter, destination):
    """Replace the generated tree, including removal of deleted upstream skills."""
    manifest = json.loads((source / "plugin.json").read_text())
    schema = manifest.pop("$schema", None)
    if schema not in (None, "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"):
        raise ValueError(f"Unsupported upstream plugin schema: {schema}")
    # OMP's native loader preserves manual-only skills; its strict schema loader rejects them.
    for required in ("skills/poteto-mode/SKILL.md", "agents/poteto-agent.md", "LICENSE"):
        if not (source / required).is_file():
            raise ValueError(f"Missing upstream entrypoint: {required}")
    with tempfile.TemporaryDirectory(prefix="om-pstack-") as temporary:
        stage = Path(temporary) / "plugin"
        stage.mkdir()
        for name in ("skills", "agents", "docs", "assets", "LICENSE", "README.md"):
            item = source / name
            if item.is_dir():
                shutil.copytree(item, stage / name)
            elif item.is_file():
                shutil.copy2(item, stage / name)
        harness = stage / "docs/harness/omp.md"
        harness.parent.mkdir(parents=True, exist_ok=True)
        harness.write_text(adapter.read_text())
        skills = {p.parent.name: p.relative_to(stage) for p in (stage / "skills").glob("*/SKILL.md")}
        for path in sorted(stage.rglob("*.md")):
            if path == harness:
                continue
            text = path.read_text()
            relative = path.relative_to(stage)
            if not relative.as_posix().startswith("docs/harness/"):
                try:
                    text = convert_tools(text, relative)
                    text = convert_references(text, relative, skills)
                except ValueError as error:
                    raise ValueError(f"{relative}: {error}") from error
            for old, new in PATHS.items():
                text = text.replace(old, new)
            if path.name == "SKILL.md" or relative.parts[0] == "agents":
                try:
                    text, paths = convert_metadata(text, agent=relative.parts[0] == "agents")
                    if path.name == "SKILL.md":
                        name = re.search(r"^name: ([a-z0-9-]+)$", text, re.MULTILINE)
                        if name is None or name[1] != path.parent.name:
                            raise ValueError("Skill name must match its directory")
                except ValueError as error:
                    raise ValueError(f"{relative}: {error}") from error
                link = os.path.relpath(harness, path.parent).replace(os.sep, "/")
                text = inject_adapter(text, link)
                if paths:
                    rules = stage / "rules"
                    rules.mkdir(exist_ok=True)
                    (rules / f"{path.parent.name}.md").write_text(
                        "---\nglobs: " + json.dumps(paths) + "\n"
                        'condition: ".*"\nscope: ["tool:read", "tool:edit", "tool:write"]\n'
                        "interruptMode: always\n---\n\n"
                        f"Before continuing with matching files, read `skill://{path.parent.name}` "
                        "and follow its instructions.\n"
                    )
            path.write_text(text)
        digest = hashlib.sha256()
        digest.update(Path(__file__).read_bytes())
        digest.update((source / "plugin.json").read_bytes())
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(stage).as_posix().encode() + b"\0")
                digest.update(path.read_bytes() + b"\0")
        # Non-semver versions let OMP detect adapter-only updates as changed.
        version = f"omp-{manifest['version']}-{digest.hexdigest()[:12]}"
        manifest.update(
            name="om-pstack",
            version=version,
            description="Poteto's pstack skills adapted for OMP, automatically tracking cursor/plugins.",
            homepage=REPOSITORY,
            repository=REPOSITORY,
        )
        (stage / "plugin.json").write_text(json_text(manifest))
        metadata = stage / ".omp-plugin"
        metadata.mkdir()
        (metadata / "plugin.json").write_text(json_text(manifest))
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(stage, destination)
    return version


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-ref", help="Git ref containing the mirrored upstream pstack tree")
    args = parser.parse_args()
    lock_path = ROOT / "upstream.lock.json"
    previous = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    ref = args.upstream_ref or previous.get("commit", "HEAD")
    commit = git("rev-parse", f"{ref}^{{commit}}")
    tree = git("rev-parse", f"{commit}:pstack")
    if git("diff", commit, "--", "pstack"):
        raise SystemExit("pstack/ differs from the selected upstream ref; import upstream before generating")
    if previous.get("tree") == tree:
        commit = previous["commit"]
    version = generate(ROOT / "pstack", ROOT / "adapters/omp.md", ROOT / "omp")
    lock_path.write_text(json_text({
        "repository": "https://github.com/cursor/plugins",
        "path": "pstack",
        "commit": commit,
        "tree": tree,
    }))
    catalog = ROOT / ".omp-plugin/marketplace.json"
    catalog.parent.mkdir(exist_ok=True)
    catalog.write_text(json_text({
        "name": "om-pstack",
        "owner": {"name": "satansdeer"},
        "plugins": [{
            "name": "om-pstack",
            "source": "./omp",
            "version": version,
            "description": "Poteto's pstack skills adapted for OMP.",
            "homepage": REPOSITORY,
        }],
    }))
    print(f"Generated om-pstack {version} from cursor/plugins@{commit[:12]}")


if __name__ == "__main__":
    main()
