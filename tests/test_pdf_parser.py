"""Regression tests for PDF adversary block filtering."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.adversary import Adversary
from parsers.pdf_parser import PDFParser


def parser_without_pdfplumber() -> PDFParser:
    return PDFParser.__new__(PDFParser)


class PDFParserBlockFilteringTests(unittest.TestCase):
    def valid_stat_block(self) -> str:
        return (
            "GOBLIN CUTTER\n"
            "Tier 1 Skulk\n"
            "A quick goblin with a knife.\n"
            "Motives & Tactics: Hide, stab, run\n"
            "Difficulty: 10 | Thresholds: 4/8 | HP: 3 | Stress: 2\n"
            "ATK: +1 | Knife: Melee | 1d6 phy\n"
            "Experience: Sneak +2\n"
            "FEATURES\n"
            "Slip Away - Passive: The cutter can move after attacking.\n"
        )

    def test_page_without_adversary_markers_returns_no_adversaries(self):
        parser = parser_without_pdfplumber()
        text = (
            "Welcome to the Menagerie of Mayhem.\n"
            "These foes are intended for your home game.\n"
            "Credits\n"
            "Design and Writing\n"
            "Monster Mike\n"
        )

        adversaries = parser._parse_adversaries_from_pages([(2, text)], "Test Source")

        self.assertEqual(adversaries, [])

    def test_parse_file_uses_source_name_override(self):
        parser = parser_without_pdfplumber()
        parser._extract_text_with_pages = lambda _path: [(16, self.valid_stat_block())]

        adversaries = parser.parse_file(
            Path("/tmp/tmpr7azyncd.pdf"),
            source_name="Underwood - Menagerie of Mayhem #1",
        )

        self.assertEqual(adversaries[0].source_name, "Underwood - Menagerie of Mayhem #1")
        self.assertEqual(adversaries[0].source_page, 16)

    def test_two_valid_stat_blocks_on_one_page_are_preserved(self):
        parser = parser_without_pdfplumber()
        text = (
            "GOBLIN CUTTER\n"
            "Tier 1 Skulk\n"
            "A quick goblin with a knife.\n"
            "Motives & Tactics: Hide, stab, run\n"
            "Difficulty: 10 | Thresholds: 4/8 | HP: 3 | Stress: 2\n"
            "ATK: +1 | Knife: Melee | 1d6 phy\n"
            "Experience: Sneak +2\n"
            "FEATURES\n"
            "Slip Away - Passive: The cutter can move after attacking.\n"
            "\n"
            "BONE GUARD\n"
            "Tier 2 Bruiser\n"
            "A skeleton with a heavy shield.\n"
            "Motives & Tactics: Block paths, protect allies\n"
            "Difficulty: 13 | Thresholds: 7/14 | HP: 6 | Stress: 3\n"
            "ATK: +2 | Shield: Melee | 1d8+2 phy\n"
            "Experience: Guardian +2\n"
            "FEATURES\n"
            "Shield Wall - Passive: The guard grants cover to nearby allies.\n"
        )

        adversaries = parser._parse_adversaries_from_pages([(5, text)], "Test Source")

        self.assertEqual([adv.name for adv in adversaries], ["GOBLIN CUTTER", "BONE GUARD"])
        self.assertTrue(all(adv.source_page == 5 for adv in adversaries))
        self.assertTrue(all(adv.features for adv in adversaries))

    def test_incomplete_tier_block_is_dropped(self):
        parser = parser_without_pdfplumber()
        text = (
            "BROKEN ENTRY\n"
            "Tier 1 Skulk\n"
            "This looks like a heading but has no stats or features.\n"
        )

        adversaries = parser._parse_adversaries_from_pages([(6, text)], "Test Source")

        self.assertEqual(adversaries, [])

    def test_circle_pips_parse_as_hp_and_stress(self):
        parser = parser_without_pdfplumber()
        text = (
            "Pain Beast\n"
            "Tier 1 Bruiser\n"
            "Description: Mutated, feral predator.\n"
            "Motives & Tactics: Pounce, bite\n"
            "Claws: Very Close - 1d12+3 phy Thresholds: 7/14\n"
            "ATK: +2 HP: O O O O O O\n"
            "Difficulty: 13 Stress: O O O\n"
            "FEATURES\n"
            "Paired Hunters - Passive: The attack has advantage near allies.\n"
        )

        adversaries = parser._parse_adversaries_from_pages([(7, text)], "Age of Umbra Adversaries")

        self.assertEqual(len(adversaries), 1)
        self.assertEqual(adversaries[0].hp, 6)
        self.assertEqual(adversaries[0].stress, 3)

    def test_age_stat_lines_do_not_leak_into_motives(self):
        parser = parser_without_pdfplumber()
        text = (
            "Damask Ambusher\n"
            "Tier 2 Skulk\n"
            "Description: A hardened cutthroat and thief who hunts for the Queens.\n"
            "Motives & Tactics: Evade, hide, ambush, pilfer\n"
            "Thresholds: 8/17\n"
            "Long Knife: Melee - 2d6+6 phy\n"
            "ATK: +2 HP: O O O O O\n"
            "Difficulty: 14 O O O O\n"
            "Stress:\n"
            "FEATURES\n"
            "Backstab - Passive: The ambusher deals extra damage.\n"
        )

        adversaries = parser._parse_adversaries_from_pages([(9, text)], "Age of Umbra Adversaries")
        adv = adversaries[0]

        self.assertEqual(adv.description, "A hardened cutthroat and thief who hunts for the Queens.")
        self.assertEqual(adv.motives_tactics, "Evade, hide, ambush, pilfer")
        self.assertEqual(adv.attack.modifier, "+2")
        self.assertEqual(adv.attack.weapon_name, "Long Knife")
        self.assertEqual(adv.attack.range, "Melee")
        self.assertEqual(adv.attack.damage, "2d6+6 phy")
        self.assertEqual(adv.hp, 5)
        self.assertEqual(adv.stress, 4)


class SafeFilenameTests(unittest.TestCase):
    def test_long_adversary_name_is_capped(self):
        adversary = Adversary(name="A" * 300)

        filename = adversary.safe_filename()

        self.assertTrue(filename)
        self.assertLessEqual(len(filename), 120)


if __name__ == "__main__":
    unittest.main()
