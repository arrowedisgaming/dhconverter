"""Tests for output filename generation.

Filenames are restricted to [A-Za-z0-9_] so they survive any filesystem,
shell, or sync tool without quoting.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.adversary import Adversary
from models.environment import Environment
from models.naming import FILENAME_MAX_LENGTH, safe_filename

ALLOWED = re.compile(r"[A-Za-z0-9_]+")


class CharacterSetTests(unittest.TestCase):
    def assertAllowed(self, value: str) -> None:
        self.assertRegex(value, r"\A[A-Za-z0-9_]+\Z")

    def test_every_hope_and_fear_name_shape_is_allowed(self):
        names = [
            "AHUIZOTL",
            "ALCHEMIST'S ABANDONED WORKSHOP",
            "CONVERGENCE, THE CITY OF PORTALS",
            "JACK-O’-LANTERN",
            "WILL-O’-THE-WISPS",
            "CHICKEN-FOOT HUT",
            "SOUL-SHATTERED MAGE",
            "XERO, CASTLE KILLER",
            "DRAGON LICH: DECAY-BRINGER",
        ]

        for name in names:
            with self.subTest(name=name):
                self.assertAllowed(safe_filename(name))

    def test_spaces_become_single_underscores(self):
        self.assertEqual(safe_filename("GRAND FEAST"), "Grand_Feast")
        self.assertEqual(safe_filename("  spaced   out  "), "Spaced_Out")

    def test_punctuation_becomes_a_separator(self):
        self.assertEqual(
            safe_filename("CONVERGENCE, THE CITY OF PORTALS"),
            "Convergence_The_City_Of_Portals",
        )
        self.assertEqual(safe_filename("CHICKEN-FOOT HUT"), "Chicken_Foot_Hut")

    def test_apostrophes_are_dropped_rather_than_separated(self):
        # "Alchemist's" is one word; splitting it would give "Alchemist_S".
        self.assertEqual(
            safe_filename("ALCHEMIST'S ABANDONED WORKSHOP"),
            "Alchemists_Abandoned_Workshop",
        )
        self.assertEqual(safe_filename("WITCH’S HUT"), "Witchs_Hut")

    def test_accented_letters_degrade_to_ascii_rather_than_vanishing(self):
        self.assertEqual(safe_filename("Café Brûlé"), "Cafe_Brule")

    def test_runs_of_separators_collapse_and_do_not_dangle(self):
        self.assertEqual(safe_filename("--- A -- B ---"), "A_B")

    def test_names_without_usable_characters_fall_back(self):
        for name in ("", "   ", "!!!", "——", None):
            with self.subTest(name=name):
                self.assertEqual(safe_filename(name), "unknown")

    def test_length_is_capped_without_a_trailing_underscore(self):
        name = " ".join(["word"] * 200)

        result = safe_filename(name)

        self.assertLessEqual(len(result), FILENAME_MAX_LENGTH)
        self.assertFalse(result.endswith("_"))
        self.assertAllowed(result)

    def test_path_separators_cannot_survive(self):
        for name in ("../../etc/passwd", "a/b", "a\\b"):
            with self.subTest(name=name):
                result = safe_filename(name)
                self.assertAllowed(result)
                self.assertNotIn("/", result)
                self.assertNotIn("\\", result)
                self.assertNotIn("..", result)


class RecordFilenameTests(unittest.TestCase):
    def test_both_record_types_use_the_same_rule(self):
        name = "ALCHEMIST'S ABANDONED WORKSHOP"

        self.assertEqual(
            Adversary(name=name).safe_filename(),
            Environment(name=name).safe_filename(),
        )


class CollisionSuffixTests(unittest.TestCase):
    """The dedupe suffix must not reintroduce forbidden characters."""

    def test_written_filenames_stay_within_the_character_set(self):
        import tempfile

        from writers.adversary_bank_writer import AdversaryBankWriter

        duplicates = [
            Adversary(name="GRAND FEAST", tier=1, adversary_type="Solo"),
            Adversary(name="GRAND FEAST", tier=2, adversary_type="Solo"),
            Adversary(name="GRAND, FEAST!", tier=3, adversary_type="Solo"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            written = AdversaryBankWriter.write_multiple(duplicates, Path(tmp))

            stems = sorted(path.stem for path in written.values())

        self.assertEqual(stems, ["Grand_Feast", "Grand_Feast_1", "Grand_Feast_2"])
        for stem in stems:
            self.assertRegex(stem, r"\A[A-Za-z0-9_]+\Z")


if __name__ == "__main__":
    unittest.main()
