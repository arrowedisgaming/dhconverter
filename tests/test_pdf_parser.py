"""Regression tests for PDF adversary block filtering."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.adversary import Adversary
from models.environment import Environment
from parsers.pdf_parser import PDFParser
from parsers.pdf_text import PageText


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

        result = parser._parse_adversaries_from_pages([(2, text)], "Test Source")

        self.assertEqual(result.adversaries, [])
        self.assertEqual(result.environments, [])

    def test_parse_file_uses_source_name_override(self):
        parser = parser_without_pdfplumber()
        parser._extract_pages = lambda _path: [
            PageText.from_text(16, self.valid_stat_block())
        ]

        result = parser.parse_file(
            Path("/tmp/tmpr7azyncd.pdf"),
            source_name="Underwood - Menagerie of Mayhem #1",
        )

        self.assertEqual(result.adversaries[0].source_name, "Underwood - Menagerie of Mayhem #1")
        self.assertEqual(result.adversaries[0].source_page, 16)

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

        result = parser._parse_adversaries_from_pages([(5, text)], "Test Source")

        self.assertEqual(
            [adv.name for adv in result.adversaries], ["GOBLIN CUTTER", "BONE GUARD"]
        )
        self.assertTrue(all(adv.source_page == 5 for adv in result.adversaries))
        self.assertTrue(all(adv.features for adv in result.adversaries))

    def test_environment_block_without_hp_or_stress_is_kept(self):
        parser = parser_without_pdfplumber()
        text = (
            "RAGING RIVER\n"
            "Tier 2 Traversal\n"
            "A swift waterway that threatens to sweep travelers downstream.\n"
            "Impulses: Pull under, carry away, batter against rocks\n"
            "Difficulty: 14\n"
            "Potential Adversaries: River Serpent, Drowned Dead\n"
            "FEATURES\n"
            "Undertow - Passive: Crossing the river requires an Agility roll.\n"
        )

        result = parser._parse_adversaries_from_pages([(12, text)], "Adversaries: Environments v1.5")

        self.assertEqual(result.adversaries, [])
        self.assertEqual(len(result.environments), 1)
        env = result.environments[0]
        self.assertIsInstance(env, Environment)
        self.assertEqual(env.name, "RAGING RIVER")
        self.assertEqual(env.environment_type, "Traversal")
        self.assertEqual(env.tier, 2)
        self.assertEqual(env.difficulty, 14)
        self.assertEqual(env.impulses, "Pull under, carry away, batter against rocks")
        self.assertEqual(env.potential_adversaries, "River Serpent, Drowned Dead")
        self.assertTrue(env.features)

    def test_event_environment_block_is_kept(self):
        parser = parser_without_pdfplumber()
        text = (
            "AVALANCHE\n"
            "Tier 3 Event\n"
            "A wall of snow and ice crashes down the mountainside.\n"
            "Impulses: Bury, deafen, isolate\n"
            "Difficulty: 16\n"
            "FEATURES\n"
            "Buried Alive - Action: A character caught in the slide is restrained.\n"
        )

        result = parser._parse_adversaries_from_pages([(3, text)], "Test Source")

        self.assertEqual(len(result.environments), 1)
        self.assertEqual(result.environments[0].environment_type, "Event")

    def test_environment_block_without_features_is_still_dropped(self):
        parser = parser_without_pdfplumber()
        text = (
            "EMPTY EXPLORATION\n"
            "Tier 1 Exploration\n"
            "Heading-like text with no features section.\n"
            "Difficulty: 10\n"
        )

        result = parser._parse_adversaries_from_pages([(4, text)], "Test Source")

        self.assertEqual(result.adversaries, [])
        self.assertEqual(result.environments, [])

    def test_combat_adversary_without_hp_is_still_dropped(self):
        parser = parser_without_pdfplumber()
        text = (
            "HOLLOW KNIGHT\n"
            "Tier 2 Bruiser\n"
            "Motives & Tactics: Advance, smash\n"
            "Difficulty: 13\n"
            "FEATURES\n"
            "Relentless - Passive: Acts twice per round.\n"
        )

        result = parser._parse_adversaries_from_pages([(8, text)], "Test Source")

        self.assertEqual(result.adversaries, [])
        self.assertEqual(result.environments, [])

    def test_incomplete_tier_block_is_dropped(self):
        parser = parser_without_pdfplumber()
        text = (
            "BROKEN ENTRY\n"
            "Tier 1 Skulk\n"
            "This looks like a heading but has no stats or features.\n"
        )

        result = parser._parse_adversaries_from_pages([(6, text)], "Test Source")

        self.assertEqual(result.adversaries, [])
        self.assertEqual(result.environments, [])

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

        result = parser._parse_adversaries_from_pages([(7, text)], "Age of Umbra Adversaries")

        self.assertEqual(len(result.adversaries), 1)
        self.assertEqual(result.adversaries[0].hp, 6)
        self.assertEqual(result.adversaries[0].stress, 3)

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

        result = parser._parse_adversaries_from_pages([(9, text)], "Age of Umbra Adversaries")
        adv = result.adversaries[0]

        self.assertEqual(adv.description, "A hardened cutthroat and thief who hunts for the Queens.")
        self.assertEqual(adv.motives_tactics, "Evade, hide, ambush, pilfer")
        self.assertEqual(adv.attack.modifier, "+2")
        self.assertEqual(adv.attack.weapon_name, "Long Knife")
        self.assertEqual(adv.attack.range, "Melee")
        self.assertEqual(adv.attack.damage, "2d6+6 phy")
        self.assertEqual(adv.hp, 5)
        self.assertEqual(adv.stress, 4)


class ThresholdParsingTests(unittest.TestCase):
    """Books print "None" for tracks an adversary can never have."""

    def block(self, thresholds: str, stress: str = "3") -> str:
        return (
            "TEST BEAST\n"
            "Tier 1 Standard\n"
            "A test subject.\n"
            "Motives & Tactics: Exist\n"
            f"Difficulty: 11 | Thresholds: {thresholds} | HP: 4 | Stress: {stress}\n"
            "ATK: +1 | Bite: Melee | 1d6 phy\n"
            "FEATURES\n"
            "Notable - Passive: It is notable.\n"
        )

    def parse(self, text: str):
        result = parser_without_pdfplumber()._parse_adversaries_from_pages(
            [(1, text)], "Test Source"
        )
        self.assertEqual(len(result.adversaries), 1)
        return result.adversaries[0]

    def test_numeric_thresholds_still_parse(self):
        adv = self.parse(self.block("8/15"))

        self.assertEqual((adv.threshold_minor, adv.threshold_major), (8, 15))
        self.assertEqual(adv.thresholds_str, "8/15")

    def test_minion_thresholds_of_none_are_kept_as_a_value(self):
        adv = self.parse(self.block("None"))

        self.assertIsNone(adv.threshold_minor)
        self.assertIsNone(adv.threshold_major)
        self.assertEqual(adv.thresholds_str, "None")
        self.assertNotIn("Missing Thresholds", adv.validate())

    def test_half_pair_keeps_the_number_that_is_present(self):
        # The Phantom prints "Thresholds: 5/None".
        adv = self.parse(self.block("5/None"))

        self.assertEqual(adv.threshold_minor, 5)
        self.assertIsNone(adv.threshold_major)
        self.assertEqual(adv.thresholds_str, "5/None")
        self.assertNotIn("Missing Thresholds", adv.validate())

    def test_absent_thresholds_are_still_reported(self):
        text = (
            "TEST BEAST\n"
            "Tier 1 Standard\n"
            "A test subject.\n"
            "Difficulty: 11 | HP: 4 | Stress: 3\n"
            "FEATURES\n"
            "Notable - Passive: It is notable.\n"
        )

        self.assertIn("Missing Thresholds", self.parse(text).validate())

    def test_stress_of_none_counts_as_zero_rather_than_missing(self):
        # Spellbound Armor can never mark Stress; the block must survive.
        adv = self.parse(self.block("9/17", stress="None"))

        self.assertEqual(adv.stress, 0)


class AttackLineParsingTests(unittest.TestCase):
    """The ATK line must be found by its label, not by prose containing "attack"."""

    def block(self, description: str, atk_line: str = "ATK: -1 | Neuro Spore: Very Close | 4 mag") -> str:
        return (
            "TEST BEAST\n"
            "Tier 2 Minion\n"
            f"{description}\n"
            "Motives & Tactics: Avoid violence, spray attackers\n"
            "Difficulty: 13 | Thresholds: None | HP: 1 | Stress: 1\n"
            f"{atk_line}\n"
            "Experience: Darkness +3\n"
            "FEATURES\n"
            "Notable - Passive: It is notable.\n"
        )

    def parse(self, text: str):
        result = parser_without_pdfplumber()._parse_adversaries_from_pages(
            [(1, text)], "Test Source"
        )
        self.assertEqual(len(result.adversaries), 1)
        return result.adversaries[0]

    def test_prose_containing_the_word_attack_does_not_shadow_the_atk_line(self):
        # The Fungispunj Sporeling's description ends "...defends itself from
        # attackers...", which a case-insensitive search for "Attack" matched
        # before the real ATK line, losing the whole attack.
        adv = self.parse(self.block(
            "A mushroom creature that defends itself from\n"
            "attackers with tiny puffs of neurotoxic spores."
        ))

        self.assertEqual(adv.attack.modifier, "-1")
        self.assertEqual(adv.attack.weapon_name, "Neuro Spore")
        self.assertEqual(adv.attack.range, "Very Close")
        self.assertEqual(adv.attack.damage, "4 mag")

    def test_flat_damage_without_dice_is_kept(self):
        adv = self.parse(self.block("A plain beast."))

        self.assertEqual(adv.attack.damage, "4 mag")

    def test_unicode_minus_modifier_is_normalised(self):
        # Books typeset the sign as U+2212, not a hyphen.
        adv = self.parse(self.block("A plain beast.", "ATK: −2 | Bite: Melee | 1d6 phy"))

        self.assertEqual(adv.attack.modifier, "-2")
        self.assertEqual(adv.attack.weapon_name, "Bite")

    def test_a_prose_line_opening_with_the_label_does_not_win(self):
        # Pins the rule that decides between candidates: this line starts with
        # the label, so only the absence of pipe separators rejects it.
        adv = self.parse(self.block("Attack when cornered. A plain beast."))

        self.assertEqual(adv.attack.weapon_name, "Neuro Spore")
        self.assertEqual(adv.attack.damage, "4 mag")

    def test_prose_sharing_a_line_with_the_label_does_not_swallow_it(self):
        # Each candidate consumes the rest of its line, so prose ahead of the
        # real label on the same line took the pipes with it and lost the
        # modifier. The spelled-out "Attack" must carry a colon to qualify.
        adv = self.parse(self.block(
            "A plain beast.",
            "Attack when cornered. ATK: +2 | Bite: Melee | 1d6 phy",
        ))

        self.assertEqual(adv.attack.modifier, "+2")
        self.assertEqual(adv.attack.weapon_name, "Bite")
        self.assertEqual(adv.attack.damage, "1d6 phy")

    def test_label_run_inline_after_the_other_stats_still_parses(self):
        # Not every book gives the attack its own line.
        text = (
            "TEST BEAST\n"
            "Tier 1 Standard\n"
            "A test subject.\n"
            "Motives & Tactics: Exist\n"
            "Difficulty: 11 | Thresholds: 4/8 | HP: 4 | Stress: 3 | "
            "ATK: +2 | Bite: Melee | 1d6 phy\n"
            "FEATURES\n"
            "Notable - Passive: It is notable.\n"
        )

        adv = self.parse(text)

        self.assertEqual(adv.attack.modifier, "+2")
        self.assertEqual(adv.attack.weapon_name, "Bite")
        self.assertEqual(adv.attack.range, "Melee")
        self.assertEqual(adv.attack.damage, "1d6 phy")


class AgeStyleAttackTests(unittest.TestCase):
    """Age of Umbra prints the weapon on its own line and ATK among the stats."""

    def parse_stats(self, text: str) -> Adversary:
        adv = Adversary(name="TEST BEAST")
        parser_without_pdfplumber()._parse_pdf_stats(adv, text)
        return adv

    def test_modifier_is_read_when_the_label_runs_inline(self):
        adv = self.parse_stats(
            "Difficulty: 11 Thresholds: 4/8 HP: O O O ATK: +2\n"
            "Long Knife: Melee - 2d6+6 phy\n"
        )

        self.assertEqual(adv.attack.modifier, "+2")
        self.assertEqual(adv.attack.weapon_name, "Long Knife")
        self.assertEqual(adv.attack.range, "Melee")
        self.assertEqual(adv.attack.damage, "2d6+6 phy")

    def test_unicode_minus_modifier_is_normalised(self):
        adv = self.parse_stats(
            "Difficulty: 11 HP: O O O ATK: −2\n"
            "Long Knife: Melee - 2d6+6 phy\n"
        )

        self.assertEqual(adv.attack.modifier, "-2")

    def test_a_value_quoted_in_prose_does_not_outrank_the_stat_line(self):
        adv = self.parse_stats(
            "Description: Its printed ATK: -9 is only an example.\n"
            "Difficulty: 11 HP: O O O ATK: +2\n"
            "Long Knife: Melee - 2d6+6 phy\n"
        )

        self.assertEqual(adv.attack.modifier, "+2")

    def test_the_label_is_not_matched_inside_a_longer_word(self):
        adv = self.parse_stats(
            "SPLATK: -9 somewhere\n"
            "Difficulty: 11 HP: O O O ATK: +2\n"
            "Long Knife: Melee - 2d6+6 phy\n"
        )

        self.assertEqual(adv.attack.modifier, "+2")

    def test_a_lone_label_still_parses_without_a_neighbouring_stat(self):
        # The stat-line preference is only a tiebreak, not a requirement.
        adv = self.parse_stats("ATK: +2\nLong Knife: Melee - 2d6+6 phy\n")

        self.assertEqual(adv.attack.modifier, "+2")


class SafeFilenameTests(unittest.TestCase):
    def test_long_adversary_name_is_capped(self):
        adversary = Adversary(name="A" * 300)

        filename = adversary.safe_filename()

        self.assertTrue(filename)
        self.assertLessEqual(len(filename), 120)


if __name__ == "__main__":
    unittest.main()
