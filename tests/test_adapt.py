import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("adapt", Path(__file__).resolve().parents[1] / "scripts/adapt.py")
adapt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapt)


class AdaptTest(unittest.TestCase):
    def test_metadata_preserves_manual_invocation_and_rejects_unmapped_semantics(self):
        text = (
            "---\nname: example\ndescription: >-\n  First line\n  second line.\n"
            'paths: ["**/*.ts", "**/*.tsx"]\ndisable-model-invocation: true\n'
            "icon: crown\ncolor: yellow\n---\n\nRead references/patterns.md.\n"
        )
        converted, paths = adapt.convert_metadata(text)
        self.assertEqual(paths, ["**/*.ts", "**/*.tsx"])
        self.assertEqual(converted, text.replace('paths: ["**/*.ts", "**/*.tsx"]\n', ""))
        automatic, _ = adapt.convert_metadata(text.replace("invocation: true", "invocation: false"))
        self.assertIn("disable-model-invocation: false", automatic)
        for bad, message in (
            ("unknown: true", "Unsupported frontmatter fields"),
            ("disable-model-invocation: yes", "must be true or false"),
            ("paths: []", "nonempty"),
            ("paths: [1]", "glob strings"),
            ("paths: '**/*.ts'", "JSON array"),
            ("name: first\nname: second", "Duplicate"),
        ):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, message):
                adapt.convert_metadata(f"---\n{bad}\n---\nbody\n")
        agent, paths = adapt.convert_metadata(
            "---\nname: worker\nmodel:\n  - upstream-model\nis_background: true\n---\nbody\n",
            agent=True,
        )
        self.assertEqual(agent, "---\nname: worker\n---\nbody\n")
        self.assertIsNone(paths)

    def test_references_resolve_principles_without_touching_code_or_urls(self):
        relative = Path("skills/example/SKILL.md")
        skills = {
            name: Path("skills") / name / "SKILL.md"
            for name in ("why", "principle-type-system-discipline", "principle-sequence-verifiable-units")
        }
        text = (
            "---\nname: example\ndescription: Use /why.\n---\n"
            "Apply **type-system-discipline** principle skill, then **why** or `why` skill.\n"
            "[**why**](/existing) [/why](../why/SKILL.md)\n"
            "Try `/why`, not https://example/why or /tmp/why or ./why or /why-extra or /skill:why.\n"
            "```ts\nconst path = '/why'; // **why** skill\nreadonly value: string;\n```\n"
            "Keep `cat /why` and `path = '/why'` unchanged.\n"
            "```text\n/why explain\n```\n"
            "Use **create-skill** skill and **principle-<title>** skill.\n"
        )
        converted = adapt.convert_references(text, relative, skills)
        self.assertIn("description: Use /skill:why.", converted)
        self.assertIn("[**type-system-discipline**](../principle-type-system-discipline/SKILL.md)", converted)
        self.assertIn("[`why`](../why/SKILL.md) skill", converted)
        self.assertIn("[**why**](/existing) [/skill:why](../why/SKILL.md)", converted)
        self.assertIn("https://example/why or /tmp/why or ./why or /why-extra or /skill:why", converted)
        self.assertIn("```ts\nconst path = '/why'; // **why** skill\nreadonly value: string;\n```", converted)
        self.assertIn("```text\n/skill:why explain\n```", converted)
        self.assertIn("**create-skill** skill and **principle-<title>** skill", converted)
        self.assertIn("Keep `cat /why` and `path = '/why'` unchanged.", converted)
        self.assertEqual(converted, adapt.convert_references(converted, relative, skills))
        for text, message in (
            ("**missing** skill", "Unknown skill"),
            ("[why](../retired/SKILL.md)", "Missing bundled"),
        ):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, message):
                adapt.convert_references(text, relative, skills)
        skills["type-system-discipline"] = Path("skills/type-system-discipline/SKILL.md")
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            adapt.convert_references("**type-system-discipline** skill", relative, skills)
        self.assertIn("principle-type-system-discipline/SKILL.md", adapt.convert_references(
            "**type-system-discipline** principle skill", relative, skills))
        index = "## Principles\n- **Sequence Work into Verifiable Units** (**principle-sequence-verifiable-units**).\n"
        self.assertIn("(../principle-sequence-verifiable-units/SKILL.md)", adapt.convert_references(
            index, Path("skills/poteto-mode/SKILL.md"), skills))
        with self.assertRaisesRegex(ValueError, "Unknown skill"):
            adapt.convert_references("## Principles\n- **New Missing Principle.** Apply it.\n",
                                     Path("skills/poteto-mode/SKILL.md"), skills)

    def test_tool_migrations_preserve_decisions_and_require_review_on_drift(self):
        source = adapt.ROOT / "pstack"
        for relative in adapt.TOOL_REWRITES:
            text = (source / relative).read_text()
            converted = adapt.convert_tools(text, Path(relative))
            self.assertNotEqual(text, converted)
            with self.assertRaisesRegex(ValueError, "Tool instruction changed"):
                adapt.convert_tools(text.replace(adapt.TOOL_REWRITES[relative][0][0], "changed"),
                                    Path(relative))
        how = adapt.convert_tools((source / "skills/how/SKILL.md").read_text(), Path("skills/how/SKILL.md"))
        self.assertIn('agent: "scout"', how)
        self.assertIn("read-only", how)
        self.assertIn("`solutionSpace`", how)
        comments = adapt.convert_tools((source / "skills/no-comments/SKILL.md").read_text(),
                                       Path("skills/no-comments/SKILL.md"))
        self.assertIn('agent: "comment-sicko"', comments)
        automate = adapt.convert_tools((source / "skills/automate-me/SKILL.md").read_text(),
                                       Path("skills/automate-me/SKILL.md"))
        self.assertNotIn("AskQuestion", automate)
        self.assertIn("otherwise ask in chat with the same options", automate)
        self.assertIn("never infer approval in unattended sessions", automate)
        self.assertIn("allow multiple answers", automate)
        autonomous = adapt.convert_tools((source / "skills/poteto-mode/playbooks/autonomous-run.md").read_text(),
                                         Path("skills/poteto-mode/playbooks/autonomous-run.md"))
        self.assertIn("or ask unnecessary questions", autonomous)


    def test_swarm_workflow_drift_rejects_generation_without_replacing_install(self):
        relative = Path("skills/swarm/SKILL.md")
        upstream = (adapt.ROOT / "pstack" / relative).read_text()
        # These four upstream decisions need explicit OMP migrations: model,
        # dispatch/placement, branch selection, and the full aggregation paragraph.
        # Missing/duplicate/changed anchors must preserve the installed distribution.
        decisions = [
            line for line in upstream.splitlines()
            if line.startswith(("3. Pick the worker model", "Spawn all N workers",
                                "When a worker must start", "Read the terminal results."))
        ]
        self.assertEqual(len(decisions), 4)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "pstack", root / "omp"
            shutil.copytree(adapt.ROOT / "pstack", source)
            adapt.generate(source, adapt.ROOT / "adapters/omp.md", output)
            installed = {p.relative_to(output): p.read_bytes()
                         for p in output.rglob("*") if p.is_file()}
            for decision in decisions:
                replacements = ["", decision + "\n" + decision,
                                decision.replace("worker", "executor")]
                if decision.startswith("Read the terminal results."):
                    replacements.append(decision.replace(
                        "For coverage, every required slice needs a result. ", ""))
                for replacement in replacements:
                    with self.subTest(decision=decision, replacement=replacement):
                        (source / relative).write_text(upstream.replace(decision, replacement))
                        with self.assertRaisesRegex(ValueError, "skills/swarm/SKILL.md"):
                            adapt.generate(source, adapt.ROOT / "adapters/omp.md", output)
                        self.assertEqual(installed, {
                            p.relative_to(output): p.read_bytes()
                            for p in output.rglob("*") if p.is_file()
                        })

    def test_help_swarm_migration_rejects_drift_without_replacing_install(self):
        relative = Path("skills/poteto-help/SKILL.md")
        upstream = (adapt.ROOT / "pstack" / relative).read_text()
        anchor = "Run parallel checks over slices, or race workers, as cloud agents"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "pstack", root / "omp"
            shutil.copytree(adapt.ROOT / "pstack", source)
            adapt.generate(source, adapt.ROOT / "adapters/omp.md", output)
            help_text = (output / relative).read_text()
            self.assertIn(
                "| Run parallel checks over slices or race workers with native OMP tasks; "
                "explicit Fabric LOCAL is optional | [`/skill:swarm`](../swarm/SKILL.md) |",
                help_text,
            )
            self.assertNotIn(anchor, help_text)
            installed = {p.relative_to(output): p.read_bytes()
                         for p in output.rglob("*") if p.is_file()}
            for drift, replacement in (
                ("missing", ""),
                ("duplicate", anchor + "\n" + anchor),
                ("changed cloud wording", anchor.replace("cloud agents", "remote agents")),
            ):
                with self.subTest(drift=drift):
                    (source / relative).write_text(upstream.replace(anchor, replacement))
                    with self.assertRaisesRegex(
                        ValueError, "skills/poteto-help/SKILL.md: Tool instruction changed"
                    ):
                        adapt.generate(source, adapt.ROOT / "adapters/omp.md", output)
                    self.assertEqual(installed, {
                        p.relative_to(output): p.read_bytes()
                        for p in output.rglob("*") if p.is_file()
                    })

    def test_updates_remove_retired_skills_and_publish_adapter_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            for name in ("skills/poteto-mode/SKILL.md", "skills/retired/SKILL.md", "agents/poteto-agent.md"):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                skill_name = path.parent.name if path.name == "SKILL.md" else path.stem
                path.write_text(f"---\nname: {skill_name}\n---\n\n# Example\n")
            manifest = {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "pstack", "version": "1.0.0",
            }
            (source / "plugin.json").write_text(json.dumps(manifest))
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
            (source / "skills/poteto-mode/SKILL.md").write_text(
                "---\nname: poteto-mode\n---\n**retired** skill\n")
            with self.assertRaisesRegex(ValueError, "Unknown skill"):
                adapt.generate(source, adapter, output)
            self.assertEqual(before, (output / "plugin.json").read_bytes())
            (source / "skills/poteto-mode/SKILL.md").write_text("---\nunterminated\n")
            with self.assertRaisesRegex(ValueError, "Unterminated"):
                adapt.generate(source, adapter, output)
            self.assertEqual(before, (output / "plugin.json").read_bytes(), "Rejected updates must preserve the prior distribution")
            self.assertEqual(json.loads(before)["name"], "om-pstack")
            manifest["$schema"] = "https://example.com/unknown-plugin-schema"
            (source / "plugin.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Unsupported upstream plugin schema"):
                adapt.generate(source, adapter, output)
            self.assertEqual(before, (output / "plugin.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
