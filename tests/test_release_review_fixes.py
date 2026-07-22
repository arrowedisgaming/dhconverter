"""Regression tests for defects found by the pre-release adversarial review."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import normalize
from models.adversary import Adversary
from parsers.pdf_parser import PDFParser
from parsers.pdf_text import LineStyle, PageLine, PageText
from writers.adversary_bank_writer import AdversaryBankWriter


def parser() -> PDFParser:
    return PDFParser.__new__(PDFParser)


class NormalizeDoesNotDestroyBankFilesTests(unittest.TestCase):
    """normalize.py rewrote the converter's own default output into an empty
    stat block, because MDParser reads only the heading from a daggerheart
    block."""

    def bank_file(self, directory: Path) -> Path:
        adversary = Adversary(
            name="JAGGED KNIFE LACKEY",
            tier=1,
            adversary_type="Minion",
            difficulty=9,
            hp=1,
            stress=1,
        )
        path = directory / "Jagged_Knife_Lackey.md"
        AdversaryBankWriter.write_adversary(adversary, path)
        return path

    def test_bank_format_file_is_skipped_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.bank_file(Path(tmp))
            before = path.read_text(encoding="utf-8")

            result = normalize.normalize_file(path)

            self.assertTrue(result["skipped"])
            self.assertTrue(result["success"])
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_directory_run_leaves_bank_files_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.bank_file(Path(tmp))
            before = path.read_text(encoding="utf-8")

            summary = normalize.normalize_directory(Path(tmp), verbose=False)

            self.assertEqual(summary["skipped"], 1)
            self.assertEqual(summary["changed"], 0)
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_a_plain_stat_block_is_still_normalized(self):
        # The skip must not disable normalize.py for its actual input format.
        content = (
            "# TEST GOBLIN\n\n"
            "***Tier 1 Skulk***  \n"
            "*A goblin.*  \n"
            "**Motives & Tactics:** Stab\n\n"
            "> **Difficulty:** 10 | **Thresholds:** 4/8 | **HP:** 3 | **Stress:** 2\n\n"
            "## FEATURES\n\n"
            "***Slip Away - Passive:*** It moves.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Test_Goblin.md"
            path.write_text(content, encoding="utf-8")

            result = normalize.normalize_file(path)

            self.assertFalse(result["skipped"])
            self.assertTrue(result["success"])
            self.assertIn("Difficulty:** 10", path.read_text(encoding="utf-8"))


class NormalizeDoesNotDestroyNonStatBlockFilesTests(unittest.TestCase):
    """The generated index was rewritten into an empty stat block: SKIP_FILES
    named Adversaries_Master_Index.md while the generator writes
    Adversaries_Index.md."""

    INDEX = (
        "# Adversaries Master Index\n\n"
        "## Adversaries\n\n"
        "### Tier 1\n\n"
        "| Name | Type |\n|------|------|\n| AHUIZOTL | Skulk |\n"
    )

    def test_generated_index_filename_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Adversaries_Index.md"
            path.write_text(self.INDEX, encoding="utf-8")

            normalize.normalize_directory(Path(tmp), verbose=False)

            self.assertEqual(path.read_text(encoding="utf-8"), self.INDEX)

    def test_a_file_with_no_stat_block_is_never_rewritten(self):
        # The general safety net, independent of filename.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Some_Notes.md"
            path.write_text(self.INDEX, encoding="utf-8")

            result = normalize.normalize_file(path)

            self.assertTrue(result["skipped"])
            self.assertFalse(result["changed"])
            self.assertEqual(path.read_text(encoding="utf-8"), self.INDEX)

    def test_notes_with_a_features_heading_are_not_rewritten(self):
        # A FEATURES section alone is not a stat block; campaign notes have
        # one, and normalizing wiped the surrounding prose.
        notes = (
            "# House Notes\n\n"
            "Campaign notes about our table rules.\n\n"
            "## FEATURES\n\n"
            "***Camp Alarm - Passive:*** Someone always keeps watch.\n\n"
            "More prose that matters.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "House_Notes.md"
            path.write_text(notes, encoding="utf-8")

            result = normalize.normalize_file(path)

            self.assertTrue(result["skipped"])
            self.assertEqual(path.read_text(encoding="utf-8"), notes)

    def test_a_lone_tier_line_is_not_a_stat_block(self):
        content = "# Something\n\n***Tier 1 Skulk***\n\nJust a note.\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Note.md"
            path.write_text(content, encoding="utf-8")

            result = normalize.normalize_file(path)

            self.assertTrue(result["skipped"])
            self.assertEqual(path.read_text(encoding="utf-8"), content)


class VariableAttackModifierTests(unittest.TestCase):
    """The PDF path parsed the modifier with a plain \\d+, truncating "+2d4"."""

    def block(self, atk: str) -> str:
        return (
            "CHAOS MAGE\n"
            "Tier 2 Ranged\n"
            "A mage.\n"
            "Motives & Tactics: Blast\n"
            "Difficulty: 14 | Thresholds: 8/16 | HP: 5 | Stress: 4\n"
            f"{atk}\n"
            "FEATURES\n"
            "Zap - Action: Blast them.\n"
        )

    def parse(self, atk: str):
        result = parser()._parse_adversaries_from_pages([(1, self.block(atk))], "Test")
        self.assertEqual(len(result.adversaries), 1)
        return result.adversaries[0].attack

    def test_dice_modifier_survives(self):
        attack = self.parse("ATK: +2d4 | Chaos Orb: Far | 2d6+3 mag")

        self.assertEqual(attack.modifier, "+2d4")
        self.assertEqual(attack.weapon_name, "Chaos Orb")
        self.assertEqual(attack.range, "Far")
        self.assertEqual(attack.damage, "2d6+3 mag")

    def test_dice_modifier_with_trailing_bonus_survives(self):
        self.assertEqual(self.parse("ATK: +2d4+1 | Orb: Far | 1d6 mag").modifier, "+2d4+1")

    def test_plain_integer_modifier_still_parses(self):
        attack = self.parse("ATK: +2 | Bite: Melee | 1d6+2 phy")

        self.assertEqual(attack.modifier, "+2")
        self.assertEqual(attack.weapon_name, "Bite")
        self.assertEqual(attack.range, "Melee")
        self.assertEqual(attack.damage, "1d6+2 phy")

    def test_negative_modifier_still_parses(self):
        self.assertEqual(self.parse("ATK: -1 | Claw: Melee | 1d4 phy").modifier, "-1")

    def test_unsigned_modifier_still_parses(self):
        # The regex this replaced accepted an unsigned modifier; delegating to
        # Attack.from_string, which requires a sign, silently lost it.
        attack = self.parse("ATK: 2 | Bite: Melee | 1d6 phy")

        self.assertEqual(attack.modifier, "2")
        self.assertEqual(attack.weapon_name, "Bite")
        self.assertEqual(attack.range, "Melee")
        self.assertEqual(attack.damage, "1d6 phy")

    def test_dice_modifier_is_not_coerced_to_int_in_yaml(self):
        adversary = Adversary(name="X")
        adversary.attack = self.parse("ATK: +2d4 | Chaos Orb: Far | 2d6+3 mag")

        content = AdversaryBankWriter.format_adversary(adversary)

        self.assertIn('attack: "+2d4"', content)


class SectionHeaderLeakTests(unittest.TestCase):
    """A header between two blocks was swept into the preceding one."""

    def test_header_does_not_join_the_previous_feature(self):
        rows = [
            ("GOBLIN", LineStyle.HEADING),
            ("Tier 1 Skulk", LineStyle.TIER),
            ("A goblin.", LineStyle.BODY),
            ("Motives & Tactics: Stab", LineStyle.BODY),
            ("Difficulty: 10 | Thresholds: 4/8 | HP: 3 | Stress: 2", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Burrow - Passive: It moves.", LineStyle.BODY),
            ("TIER 1 ENVIRONMENTS (LEVEL 1)", LineStyle.HEADING),
            ("ABANDONED MINE", LineStyle.HEADING),
            ("Tier 1 Traversal", LineStyle.TIER),
            ("A mine.", LineStyle.BODY),
            ("Impulses: Collapse", LineStyle.BODY),
            ("Difficulty: 11", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Dark - Passive: No light.", LineStyle.BODY),
        ]
        page = PageText(1, [PageLine(t, s) for t, s in rows])

        result = parser()._parse_pages([page], "Test")

        self.assertEqual(len(result.adversaries), 1)
        self.assertEqual(len(result.environments), 1)
        self.assertEqual(result.adversaries[0].features[-1].description, "It moves.")
        self.assertEqual(result.environments[0].name, "ABANDONED MINE")


class MultipartBoundaryTests(unittest.TestCase):
    """RFC 2045 allows a quoted boundary; leaving the quotes corrupted uploads."""

    BODY = (
        b'--abc\r\n'
        b'Content-Disposition: form-data; name="f"\r\n\r\n'
        b'value\r\n'
        b'--abc--\r\n'
    )

    def test_unquoted_boundary(self):
        from app import parse_multipart

        self.assertEqual(
            parse_multipart(self.BODY, "multipart/form-data; boundary=abc"),
            {"f": "value"},
        )

    def test_quoted_boundary_parses_identically(self):
        from app import parse_multipart

        self.assertEqual(
            parse_multipart(self.BODY, 'multipart/form-data; boundary="abc"'),
            {"f": "value"},
        )

    def test_missing_delimiter_is_rejected_rather_than_silently_wrong(self):
        from app import parse_multipart

        with self.assertRaises(ValueError):
            parse_multipart(self.BODY, "multipart/form-data; boundary=different")


class YamlScalarSafetyTests(unittest.TestCase):
    def block(self, content: str) -> str:
        return re.search(r"```daggerheart\n(.*?)```", content, re.S).group(1)

    def test_c1_control_characters_do_not_break_the_block(self):
        content = AdversaryBankWriter.format_adversary(
            Adversary(name="X", description="danger \x80 here")
        )

        self.assertNotIn("\x80", content)
        self.assertIn("\\u0080", content)

    def test_readable_unicode_is_not_escaped(self):
        content = AdversaryBankWriter.format_adversary(
            Adversary(name="X", description="the Spider’s Web — a café")
        )

        self.assertIn("Spider’s", content)
        self.assertIn("café", content)

    def test_empty_containers_round_trip_as_containers(self):
        self.assertEqual(AdversaryBankWriter._yaml_lines({"x": []}), ["x: []"])
        self.assertEqual(AdversaryBankWriter._yaml_lines({"x": {}}), ["x: {}"])

    def test_empty_list_inside_a_dict_list_item(self):
        lines = AdversaryBankWriter._yaml_dict_list_item({"name": "a", "q": []}, 2)

        self.assertIn("    q: []", lines)


class CrossTypeCollisionTests(unittest.TestCase):
    """An adversary and an environment may share a name."""

    def test_both_paths_are_reported_when_names_collide(self):
        from models.environment import Environment, EnvironmentFeature

        adversary = Adversary(name="GRAND FEAST", tier=1, adversary_type="Social")
        environment = Environment(
            name="GRAND FEAST",
            tier=1,
            environment_type="Social",
            difficulty=11,
            features=[EnvironmentFeature("Toast", "Action", "A speech.")],
        )

        with tempfile.TemporaryDirectory() as tmp:
            written = AdversaryBankWriter.write_multiple(
                [adversary], Path(tmp), environments=[environment]
            )

            self.assertEqual(len(written), 2)
            paths = sorted(str(p.relative_to(Path(tmp))) for p in written.values())

        self.assertEqual(paths, ["Grand_Feast.md", "environments/Grand_Feast.md"])


if __name__ == "__main__":
    unittest.main()
