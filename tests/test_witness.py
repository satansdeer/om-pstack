import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/witness.py"


class WitnessTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve() / "consumer"
        self.root.mkdir()
        self.source = self.root / "consumer.py"
        self.original = b"print('committed consumer')\n"
        self.source.write_bytes(self.original)
        self.git("init", "-q")
        self.git("add", "consumer.py")
        tree = self.git("write-tree").strip()
        self.head = self.git("commit-tree", tree, "-m", "isolated test fixture").strip()
        self.git("update-ref", "HEAD", self.head)
        self.witness = self.root.parent / "evidence.jsonl"
        self.effect = self.root / "predicate-ran"
        self.method = "one sample; run consumer predicate once, in declared argv order"
        self.command = [sys.executable, "-c",
                        "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('ran')",
                        str(self.effect)]

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgSign=false", *args],
            cwd=self.root, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout

    def run_witness(self, *, head=None, command=None, extra=(), cwd=None, separator=True):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--expected-head", head or self.head,
             "--source", "consumer.py", "--method", self.method,
             "--witness", str(self.witness), *extra,
             *(["--"] if separator else []), *(self.command if command is None else command)],
            cwd=cwd or self.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def records(self):
        return [json.loads(line) for line in self.witness.read_text().splitlines()]

    def assert_rejected(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.effect.exists(), "rejected admission ran the predicate")
        self.assertEqual([row["event"] for row in self.records()], ["rejected"])

    def test_command_observes_bound_pre_test_witness_before_running(self):
        nested = self.root / "nested"
        nested.mkdir()
        alias = self.root.parent / "cwd-alias"
        alias.symlink_to(nested, target_is_directory=True)
        literal = "; echo not-a-shell-command"
        command = [sys.executable, "-c", (
            "import json, sys; from pathlib import Path; "
            "rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]; "
            "assert len(rows) == 1 and rows[0]['event'] == 'pre_test'; "
            "Path(sys.argv[2]).write_text(json.dumps({'witness': rows[0], "
            "'cwd': str(Path.cwd()), 'literal': sys.argv[3]})); "
            "print('predicate observed pre-test witness')"
        ), str(self.witness), str(self.effect), literal]
        result = self.run_witness(command=command, cwd=alias)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "predicate observed pre-test witness\n")
        observed = json.loads(self.effect.read_text())
        before, after = self.records()
        self.assertEqual(observed, {"witness": before, "cwd": str(nested), "literal": literal})
        self.assertEqual(before["cwd"], str(nested))
        self.assertEqual(before["repository"], str(self.root))
        self.assertEqual(before["expected_head"], self.head)
        self.assertEqual(before["observed_head"], self.head)
        self.assertEqual(before["method"], self.method)
        self.assertEqual(before["argv"], command)
        self.assertEqual(before["requested_sources"], ["consumer.py"])
        self.assertEqual(before["sources"], [{
            "path": "consumer.py", "git_blob": self.git("rev-parse", "HEAD:consumer.py").strip(),
            "committed_sha256": hashlib.sha256(self.original).hexdigest(),
            "observed_sha256": hashlib.sha256(self.original).hexdigest(),
        }])
        self.assertEqual(after["event"], "result")
        self.assertEqual(after["returncode"], 0)
        self.assertLessEqual(before["time_ns"], after["time_ns"])

    def test_wrong_full_sha_rejects_before_predicate_side_effect(self):
        wrong = "1" * len(self.head) if self.head != "1" * len(self.head) else "2" * len(self.head)
        self.assert_rejected(self.run_witness(head=wrong))
        self.assertEqual(self.records()[0]["observed_head"], self.head)
        self.assertEqual(self.records()[0]["expected_head"], wrong)

    def test_worktree_byte_changes_reject_even_when_git_index_hides_them(self):
        for flag in (None, "--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", "--no-assume-unchanged", "--no-skip-worktree", "consumer.py")
                self.source.write_bytes(self.original)
                if flag:
                    self.git("update-index", flag, "consumer.py")
                self.source.write_bytes(b"print('changed bytes, unchanged HEAD')\n")
                self.assert_rejected(self.run_witness())
                evidence = self.records()[0]
                self.assertEqual(evidence["observed_head"], self.head)
                self.assertNotEqual(evidence["sources"][0]["observed_sha256"],
                                    evidence["sources"][0]["committed_sha256"])
                self.witness.unlink()

    def test_staged_change_rejects_even_if_worktree_is_restored_to_head_bytes(self):
        self.source.write_bytes(b"staged source change\n")
        self.git("add", "consumer.py")
        self.source.write_bytes(self.original)
        self.assert_rejected(self.run_witness())

    def test_nonzero_predicate_status_is_preserved(self):
        command = self.command.copy()
        command[2] += "; sys.exit(23)"
        result = self.run_witness(command=command)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.effect.read_text(), "ran")
        self.assertEqual([row["event"] for row in self.records()], ["pre_test", "result"])
        self.assertEqual(self.records()[-1]["returncode"], 23)

    @unittest.skipUnless(os.name == "posix", "POSIX signal status")
    def test_signal_status_is_recorded_and_returned_as_shell_status(self):
        result = self.run_witness(command=[sys.executable, "-c",
                                          "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"])
        self.assertEqual(result.returncode, 128 + signal.SIGTERM, result.stderr)
        self.assertEqual(self.records()[-1]["returncode"], -signal.SIGTERM)

    def test_invalid_invocation_rejects_before_predicate_side_effect(self):
        cases = [
            {"head": self.head[:12]},
            {"extra": ("--method", " ")},
            {"command": []},
            {"command": [], "separator": False},
            {"extra": ("--source", "../outside.py")},
            {"extra": ("--source", "untracked.py")},
        ]
        (self.root / "untracked.py").write_bytes(self.original)
        for case in cases:
            with self.subTest(case=case):
                self.assert_rejected(self.run_witness(**case))
                self.witness.unlink()

    def test_symlink_source_rejects_even_with_identical_target_bytes(self):
        target = self.root.parent / "same-bytes.py"
        target.write_bytes(self.original)
        self.source.unlink()
        self.source.symlink_to(target)
        self.assert_rejected(self.run_witness())

    def test_existing_witness_is_not_reused_and_does_not_run_predicate(self):
        self.witness.write_text("previous evidence\n")
        result = self.run_witness()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.witness.read_text(), "previous evidence\n")
        self.assertFalse(self.effect.exists())

    def test_launch_failure_is_not_a_successful_result(self):
        result = self.run_witness(command=[str(self.root / "missing-executable")])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual([row["event"] for row in self.records()], ["pre_test", "launch_error"])
        self.assertFalse(self.effect.exists())


if __name__ == "__main__":
    unittest.main()
