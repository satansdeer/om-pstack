#!/usr/bin/env python3
"""Admit committed source bytes, write a JSONL witness, then run an argv without a shell."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def git(cwd, *args):
    return subprocess.run(
        ["git", "--no-replace-objects", "--literal-pathspecs", *args], cwd=cwd,
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def record(output, evidence):
    output.write(json.dumps(evidence, sort_keys=True) + "\n")
    output.flush()
    os.fsync(output.fileno())


def admit(options, command, evidence):
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", options.expected_head):
        raise ValueError("--expected-head must be a full lowercase Git SHA")
    if not options.method.strip() or not command or not command[0]:
        raise ValueError("a nonempty --method and -- command argv are required")
    if any("\0" in arg for arg in command):
        raise ValueError("command argv cannot contain NUL")
    cwd = evidence["cwd"]
    root = Path(os.fsdecode(git(cwd, "rev-parse", "--show-toplevel")).rstrip("\n")).resolve()
    evidence["repository"] = str(root)
    head = git(cwd, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    evidence["observed_head"] = head
    if head != options.expected_head:
        raise ValueError("observed HEAD does not match --expected-head")
    for name in options.source:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name:
            raise ValueError(f"source must be a canonical repository-relative file: {name}")
        path = root / relative
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError(f"source must be a regular file without symlinks: {name}")
        entry = git(root, "ls-tree", "-z", head, "--", name).rstrip(b"\0")
        metadata, separator, tracked_name = entry.partition(b"\t")
        fields = metadata.split()
        if (not separator or tracked_name != os.fsencode(name) or len(fields) != 3
                or fields[0] not in (b"100644", b"100755") or fields[1] != b"blob"):
            raise ValueError(f"source is not a committed regular file: {name}")
        committed = git(root, "cat-file", "blob", fields[2].decode())
        actual = path.read_bytes()
        evidence["sources"].append({
            "path": name, "git_blob": fields[2].decode(),
            "committed_sha256": hashlib.sha256(committed).hexdigest(),
            "observed_sha256": hashlib.sha256(actual).hexdigest(),
        })
        if actual != committed:
            raise ValueError(f"working-tree bytes differ from committed source: {name}")
    # Compare the index separately: staged edits must not be blessed by clean worktree bytes.
    git(root, "diff", "--cached", "--quiet", head, "--", *options.source)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--source", action="append", required=True,
                        help="relevant committed file, relative to repository root; repeat as needed")
    parser.add_argument("--method", required=True, help="exact requested verification/measurement method")
    parser.add_argument("--witness", required=True, type=Path, help="new JSONL output file")
    args = sys.argv[1:]
    split = args.index("--") if "--" in args else len(args)
    options = parser.parse_args(args[:split])
    command = args[split + 1:]
    evidence = {
        "event": "pre_test", "cwd": str(Path.cwd().resolve()),
        "expected_head": options.expected_head, "method": options.method,
        "argv": command, "requested_sources": options.source, "sources": [],
    }
    try:
        # Exclusive creation prevents stale evidence reuse or source-file clobbering.
        with options.witness.open("x", encoding="utf-8") as output:
            try:
                admit(options, command, evidence)
            except (ValueError, OSError, subprocess.CalledProcessError) as error:
                evidence.update(event="rejected", error=str(error), time_ns=time.time_ns())
                record(output, evidence)
                print(f"source admission rejected: {error}", file=sys.stderr)
                return 2
            evidence["time_ns"] = time.time_ns()
            record(output, evidence)
            try:
                result = subprocess.run(command, cwd=evidence["cwd"], shell=False)
            except (OSError, ValueError) as error:
                record(output, {"event": "launch_error", "error": str(error), "time_ns": time.time_ns()})
                print(f"predicate launch failed: {error}", file=sys.stderr)
                return 2
            record(output, {"event": "result", "returncode": result.returncode, "time_ns": time.time_ns()})
            return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except OSError as error:
        print(f"witness I/O failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
