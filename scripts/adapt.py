#!/usr/bin/env python3
"""Generate the OMP distribution without modifying the upstream pstack tree."""

import argparse
import hashlib
import json
import os
from pathlib import Path
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


def inject_adapter(text, link, *, agent=False):
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
    if agent:
        frontmatter = text[:end].splitlines(keepends=True)
        text = "".join(line for line in frontmatter if not line.startswith(("model:", "is_background:"))) + text[end:]
        end = text.find("\n---\n", 4) + len("\n---\n")
    return text[:end] + "\n" + notice + text[end:].lstrip("\n")


def generate(source, adapter, destination):
    """Replace the generated tree, including removal of deleted upstream skills."""
    manifest = json.loads((source / "plugin.json").read_text())
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
        for path in sorted(stage.rglob("*.md")):
            if path == harness:
                continue
            text = path.read_text()
            for old, new in PATHS.items():
                text = text.replace(old, new)
            relative = path.relative_to(stage)
            if path.name == "SKILL.md" or relative.parts[0] == "agents":
                link = os.path.relpath(harness, path.parent).replace(os.sep, "/")
                text = inject_adapter(text, link, agent=relative.parts[0] == "agents")
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
