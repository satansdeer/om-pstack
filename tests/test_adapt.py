import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("adapt", Path(__file__).resolve().parents[1] / "scripts/adapt.py")
adapt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapt)


class AdaptTest(unittest.TestCase):
    def test_updates_remove_retired_skills_and_publish_adapter_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            for name in ("skills/poteto-mode/SKILL.md", "skills/retired/SKILL.md", "agents/poteto-agent.md"):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("---\nname: example\n---\n\n# Example\n")
            (source / "plugin.json").write_text('{"name":"pstack","version":"1.0.0"}')
            (source / "LICENSE").write_text("Example license\n")
            adapter = root / "omp.md"
            adapter.write_text("First adapter\n")
            original = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
            first = adapt.generate(source, adapter, output)
            snapshot = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(first, adapt.generate(source, adapter, output))
            self.assertEqual(snapshot, {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()})
            self.assertEqual(original, {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()})
            adapter.write_text("Revised adapter\n")
            second = adapt.generate(source, adapter, output)
            self.assertNotEqual(first, second, "Adapter-only updates must have a distinct install version")
            (source / "skills/retired/SKILL.md").unlink()
            (source / "skills/retired").rmdir()
            adapt.generate(source, adapter, output)
            self.assertFalse((output / "skills/retired").exists(), "Retired upstream skills must not remain installed")
            before = (output / "plugin.json").read_bytes()
            (source / "skills/poteto-mode/SKILL.md").write_text("---\nunterminated\n")
            with self.assertRaisesRegex(ValueError, "Unterminated"):
                adapt.generate(source, adapter, output)
            self.assertEqual(before, (output / "plugin.json").read_bytes(), "Rejected updates must preserve the prior distribution")
            self.assertEqual(json.loads(before)["name"], "om-pstack")


if __name__ == "__main__":
    unittest.main()
