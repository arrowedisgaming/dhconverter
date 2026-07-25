"""Tests for the Obsidian properties (YAML frontmatter) formatter.

Stdlib-only, like test_adversary_bank_writer: every string scalar is
JSON-encoded, so json.loads validates individual values without PyYAML.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.adversary import Adversary, Attack, Feature
from models.environment import Environment, EnvironmentFeature
from writers.adversary_bank_writer import AdversaryBankWriter
from writers.frontmatter import adversary_frontmatter, environment_frontmatter
from writers.markdown_writer import MarkdownWriter


def base_adversary(**overrides) -> Adversary:
    adv = Adversary(
        name="Test Goblin",
        tier=1,
        adversary_type="Skulk",
        description="A small green menace.",
        difficulty=10,
        threshold_minor=5,
        threshold_major=10,
        hp=3,
        stress=2,
        attack=Attack(modifier="+2", weapon_name="Dagger", range="Melee", damage="1d6+2 phy"),
        experience="Stealth +2",
        motives_tactics="Ambush, retreat",
        source_name="Daggerheart SRD",
        source_page=42,
        features=[
            Feature(name="Sneak", feature_type="Passive", description="Hard to spot."),
        ],
    )
    for key, value in overrides.items():
        setattr(adv, key, value)
    return adv


def base_environment(**overrides) -> Environment:
    env = Environment(
        name="Test Mine",
        tier=1,
        environment_type="Traversal",
        description="A dark tunnel.",
        impulses="Collapse, confuse",
        difficulty=11,
        potential_adversaries="Spiders",
        features=[
            EnvironmentFeature(
                name="Dark", feature_type="Passive", description="No light.",
            ),
        ],
        source_name="Hope and Fear",
        source_page=39,
    )
    for key, value in overrides.items():
        setattr(env, key, value)
    return env


def keys_in_order(block: str) -> list[str]:
    """Top-level YAML keys between the --- fences, in file order."""
    lines = block.split("\n")
    assert lines[0] == "---" and lines[-2] == "---", block
    return [line.split(":", 1)[0] for line in lines[1:-2]]


def scalar_for(block: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}: (.+)$", block, re.MULTILINE)
    if not match:
        raise AssertionError(f"key '{key}' not found in:\n{block}")
    return match.group(1)


class AdversaryFrontmatterTests(unittest.TestCase):
    def test_block_is_fenced_and_ends_with_newline(self):
        block = adversary_frontmatter(base_adversary())
        self.assertTrue(block.startswith("---\n"))
        self.assertTrue(block.endswith("\n---\n"))

    def test_field_order_matches_spec(self):
        block = adversary_frontmatter(base_adversary())
        self.assertEqual(keys_in_order(block), [
            "name", "tier", "type", "difficulty", "hp", "stress",
            "attack", "weapon", "range", "damage",
            "motives", "desc", "source", "feature_count",
        ])

    def test_excludes_thresholds_xp_and_features(self):
        block = adversary_frontmatter(base_adversary())
        self.assertNotIn("thresholds", block)
        self.assertNotIn("xp", block)
        self.assertNotIn("Sneak", block)

    def test_source_omits_page_number(self):
        block = adversary_frontmatter(base_adversary())
        self.assertEqual(json.loads(scalar_for(block, "source")), "Daggerheart SRD")
        self.assertNotIn("p. 42", block)

    def test_name_is_title_cased_like_the_code_block(self):
        block = adversary_frontmatter(base_adversary(name="ACCURSED SOUL"))
        self.assertEqual(json.loads(scalar_for(block, "name")), "Accursed Soul")

    def test_missing_fields_are_omitted(self):
        adv = base_adversary(
            description=None, attack=None, motives_tactics=None,
            source_name=None, source_page=None, features=[],
        )
        block = adversary_frontmatter(adv)
        self.assertEqual(
            keys_in_order(block),
            ["name", "tier", "type", "difficulty", "hp", "stress", "feature_count"],
        )

    def test_feature_count_zero_still_present(self):
        block = adversary_frontmatter(base_adversary(features=[]))
        self.assertEqual(scalar_for(block, "feature_count"), "0")

    def test_attack_modifier_coerced_to_int(self):
        block = adversary_frontmatter(base_adversary())
        self.assertEqual(scalar_for(block, "attack"), "2")

    def test_special_characters_stay_json_quoted(self):
        adv = base_adversary(
            name="WILL-O'-THE-WISP",
            description='Says "boo" — colon: included.',
        )
        block = adversary_frontmatter(adv)
        self.assertEqual(json.loads(scalar_for(block, "name")), "Will-O'-The-Wisp")
        self.assertEqual(
            json.loads(scalar_for(block, "desc")),
            'Says "boo" — colon: included.',
        )


class EnvironmentFrontmatterTests(unittest.TestCase):
    def test_field_order_matches_spec(self):
        block = environment_frontmatter(base_environment())
        self.assertEqual(keys_in_order(block), [
            "name", "tier", "type", "difficulty",
            "impulses", "potential_adversaries",
            "desc", "source", "feature_count",
        ])

    def test_type_is_environment_type(self):
        block = environment_frontmatter(base_environment())
        self.assertEqual(json.loads(scalar_for(block, "type")), "Traversal")

    def test_string_difficulty_is_quoted(self):
        env = base_environment(difficulty='Special (see "Relative Strength")')
        block = environment_frontmatter(env)
        self.assertEqual(
            json.loads(scalar_for(block, "difficulty")),
            'Special (see "Relative Strength")',
        )

    def test_source_omits_page_number(self):
        block = environment_frontmatter(base_environment())
        self.assertEqual(json.loads(scalar_for(block, "source")), "Hope and Fear")
        self.assertNotIn("p. 39", block)


class WriterFlagTests(unittest.TestCase):
    def test_bank_writer_flag_off_output_unchanged(self):
        adv = base_adversary()
        self.assertEqual(
            AdversaryBankWriter.format_adversary(adv),
            AdversaryBankWriter.format_adversary(adv, frontmatter=False),
        )
        self.assertTrue(
            AdversaryBankWriter.format_adversary(adv).startswith("# Test Goblin")
        )

    def test_bank_writer_flag_on_prepends_block(self):
        adv = base_adversary()
        output = AdversaryBankWriter.format_adversary(adv, frontmatter=True)
        self.assertEqual(
            output,
            adversary_frontmatter(adv) + AdversaryBankWriter.format_adversary(adv),
        )
        self.assertTrue(output.startswith("---\n"))
        self.assertIn("\n---\n# Test Goblin", output)
        self.assertIn("```daggerheart", output)

    def test_bank_writer_environment_flag_on(self):
        env = base_environment()
        output = AdversaryBankWriter.format_environment(env, frontmatter=True)
        self.assertEqual(
            output,
            environment_frontmatter(env) + AdversaryBankWriter.format_environment(env),
        )

    def test_markdown_writer_flag_on_prepends_block(self):
        adv = base_adversary()
        output = MarkdownWriter.format_adversary(adv, frontmatter=True)
        self.assertEqual(
            output,
            adversary_frontmatter(adv) + MarkdownWriter.format_adversary(adv),
        )
        self.assertIn("\n---\n# TEST GOBLIN", output)

    def test_markdown_writer_environment_flag_on(self):
        env = base_environment()
        output = MarkdownWriter.format_environment(env, frontmatter=True)
        self.assertEqual(
            output,
            environment_frontmatter(env) + MarkdownWriter.format_environment(env),
        )

    def test_write_multiple_threads_flag(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            AdversaryBankWriter.write_multiple(
                [base_adversary()], Path(tmp),
                overwrite=True,
                environments=[base_environment()],
                frontmatter=True,
            )
            adv_text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            env_text = (
                Path(tmp) / "environments" / "Test_Mine.md"
            ).read_text(encoding="utf-8")
            self.assertTrue(adv_text.startswith("---\n"))
            self.assertTrue(env_text.startswith("---\n"))


class ConvertToFilesTests(unittest.TestCase):
    def _result(self):
        from models.parse_result import ParseResult
        return ParseResult(
            adversaries=[base_adversary()],
            environments=[base_environment()],
        )

    def test_flag_off_writes_no_frontmatter(self):
        import tempfile
        from convert import convert_to_files
        with tempfile.TemporaryDirectory() as tmp:
            convert_to_files(self._result(), Path(tmp), overwrite=True, verbose=False)
            text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Test Goblin"))

    def test_flag_on_writes_frontmatter_for_both_kinds(self):
        import tempfile
        from convert import convert_to_files
        with tempfile.TemporaryDirectory() as tmp:
            convert_to_files(
                self._result(), Path(tmp),
                overwrite=True, verbose=False, frontmatter=True,
            )
            adv_text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            env_text = (
                Path(tmp) / "environments" / "Test_Mine.md"
            ).read_text(encoding="utf-8")
            self.assertTrue(adv_text.startswith("---\n"))
            self.assertTrue(env_text.startswith("---\n"))

    def test_flag_on_with_readable_markdown(self):
        import tempfile
        from convert import convert_to_files
        with tempfile.TemporaryDirectory() as tmp:
            convert_to_files(
                self._result(), Path(tmp),
                overwrite=True, verbose=False,
                readable_markdown=True, frontmatter=True,
            )
            text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            self.assertIn("\n---\n# TEST GOBLIN", text)

    def test_cli_flag_reaches_convert_to_files(self):
        import tempfile
        from unittest.mock import patch
        import convert
        from models.parse_result import ParseResult

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.md"
            src.write_text("stub", encoding="utf-8")
            argv = ["convert.py", str(src), "-o", str(Path(tmp) / "out"),
                    "--frontmatter", "--quiet"]
            with patch.object(convert, "parse_source",
                              return_value=ParseResult(adversaries=[base_adversary()])), \
                 patch.object(convert, "convert_to_files",
                              return_value={}) as mock_convert, \
                 patch.object(sys, "argv", argv):
                convert.main()
            self.assertTrue(mock_convert.call_args.kwargs["frontmatter"])


class WebOptionTests(unittest.TestCase):
    def test_frontmatter_field_default_is_false(self):
        from app import _is_truthy
        fields = {}
        self.assertFalse(_is_truthy(fields.get("frontmatter", "false")))

    def test_frontmatter_field_true(self):
        from app import _is_truthy
        self.assertTrue(_is_truthy("true"))


if __name__ == "__main__":
    unittest.main()
