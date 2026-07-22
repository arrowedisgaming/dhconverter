"""Tests for environment stat-block parsing and output."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.environment import Environment, EnvironmentFeature
from parsers.pdf_parser import PDFParser
from parsers.pdf_text import LineStyle, PageLine, PageText
from writers.adversary_bank_writer import AdversaryBankWriter
from writers.beastvault_writer import BeastvaultWriter


def parser() -> PDFParser:
    return PDFParser.__new__(PDFParser)


def styled_page(page_number: int, rows: list[tuple[str, LineStyle]]) -> PageText:
    return PageText(page_number, [PageLine(text, style) for text, style in rows])


ABANDONED_MINE = [
    ("TIER 1 ENVIRONMENTS (LEVEL 1)", LineStyle.HEADING),
    ("ABANDONED MINE", LineStyle.HEADING),
    ("Tier 1 Traversal", LineStyle.TIER),
    ("A twisting warren of disused tunnels.", LineStyle.BODY),
    ("Impulses: Poison the party with deadly gasses, rumble and", LineStyle.BODY),
    ("collapse, split the party", LineStyle.BODY),
    ("Difficulty: 11", LineStyle.BODY),
    ("Potential Adversaries: Darkweave Spiders (Darkweave", LineStyle.BODY),
    ("Crawler, Darkweave Spinner)", LineStyle.BODY),
    ("FEATURES", LineStyle.BODY),
    ("Pitch Black - Passive: There is no light in these tunnels.", LineStyle.BODY),
    ("What fuel does the light source use?", LineStyle.QUESTION),
    ("What unwanted attention does the light attract?", LineStyle.QUESTION),
    ("Labyrinth - Passive: The party must complete a Countdown (4).", LineStyle.BODY),
    ("What did miners extract here?", LineStyle.QUESTION),
]


class EnvironmentParsingTests(unittest.TestCase):
    def parse_mine(self) -> Environment:
        result = parser()._parse_pages(
            [styled_page(39, ABANDONED_MINE)], "Hope and Fear"
        )
        self.assertEqual(result.adversaries, [])
        self.assertEqual(len(result.environments), 1)
        return result.environments[0]

    def test_core_fields_are_parsed(self):
        env = self.parse_mine()

        self.assertEqual(env.name, "ABANDONED MINE")
        self.assertEqual(env.tier, 1)
        self.assertEqual(env.environment_type, "Traversal")
        self.assertEqual(env.difficulty, 11)
        self.assertEqual(env.description, "A twisting warren of disused tunnels.")
        self.assertEqual(env.source_name, "Hope and Fear")
        self.assertEqual(env.source_page, 39)

    def test_wrapped_labelled_fields_are_rejoined(self):
        env = self.parse_mine()

        self.assertEqual(
            env.impulses,
            "Poison the party with deadly gasses, rumble and collapse, split the party",
        )
        self.assertEqual(
            env.potential_adversaries,
            "Darkweave Spiders (Darkweave Crawler, Darkweave Spinner)",
        )

    def test_questions_attach_to_the_feature_they_follow(self):
        env = self.parse_mine()

        self.assertEqual([f.name for f in env.features], ["Pitch Black", "Labyrinth"])
        self.assertEqual(env.features[0].questions, [
            "What fuel does the light source use?",
            "What unwanted attention does the light attract?",
        ])
        self.assertEqual(env.features[1].questions, ["What did miners extract here?"])

    def test_questions_are_excluded_from_the_description(self):
        env = self.parse_mine()

        self.assertEqual(
            env.features[0].description, "There is no light in these tunnels."
        )

    def test_wrapped_question_lines_are_rejoined_then_split(self):
        page = styled_page(1, [
            ("CAVERN", LineStyle.HEADING),
            ("Tier 1 Traversal", LineStyle.TIER),
            ("A cave.", LineStyle.BODY),
            ("Impulses: Echo", LineStyle.BODY),
            ("Difficulty: 10", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Dark - Passive: It is dark.", LineStyle.BODY),
            ("What did miners previously extract here? Who in the", LineStyle.QUESTION),
            ("party knows how to navigate below ground?", LineStyle.QUESTION),
        ])

        env = parser()._parse_pages([page], "Test").environments[0]

        self.assertEqual(env.features[0].questions, [
            "What did miners previously extract here?",
            "Who in the party knows how to navigate below ground?",
        ])

    def test_non_numeric_difficulty_is_preserved(self):
        # The Duel event prints Difficulty: Special (see "Relative Strength").
        page = styled_page(44, [
            ("DUEL", LineStyle.HEADING),
            ("Tier 2 Event", LineStyle.TIER),
            ("A challenge to single combat.", LineStyle.BODY),
            ("Impulses: Focus on one PC", LineStyle.BODY),
            ('Difficulty: Special (see "Relative Strength")', LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Satisfaction - Passive: The PC chooses whether to accept.", LineStyle.BODY),
        ])

        env = parser()._parse_pages([page], "Test").environments[0]

        self.assertEqual(env.difficulty, 'Special (see "Relative Strength")')

    def test_name_wrapping_across_heading_lines_is_rejoined(self):
        page = styled_page(39, [
            ("ALCHEMIST'S ABANDONED", LineStyle.HEADING),
            ("WORKSHOP", LineStyle.HEADING),
            ("Tier 1 Exploration", LineStyle.TIER),
            ("A laboratory.", LineStyle.BODY),
            ("Impulses: Overclock the machinery", LineStyle.BODY),
            ("Difficulty: 11", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Curiosities - Passive: The shelves are cluttered.", LineStyle.BODY),
        ])

        env = parser()._parse_pages([page], "Test").environments[0]

        self.assertEqual(env.name, "ALCHEMIST'S ABANDONED WORKSHOP")


class SocialRoutingTests(unittest.TestCase):
    """"Social" labels both adversaries and environments."""

    def social_block(self, kind: str) -> PageText:
        return styled_page(1, [
            (f"TIER 1 {kind} (LEVEL 1)", LineStyle.HEADING),
            ("GRAND FEAST", LineStyle.HEADING),
            ("Tier 1 Social", LineStyle.TIER),
            ("A celebration.", LineStyle.BODY),
            ("Impulses: Bring everyone together", LineStyle.BODY),
            ("Difficulty: 11", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Toast - Action: Someone makes a speech.", LineStyle.BODY),
        ])

    def test_social_under_environments_header_is_an_environment(self):
        result = parser()._parse_pages([self.social_block("ENVIRONMENTS")], "Test")

        self.assertEqual(len(result.environments), 1)
        self.assertEqual(result.environments[0].environment_type, "Social")

    def test_social_adversary_is_not_routed_to_environments(self):
        page = styled_page(1, [
            ("TIER 3 ADVERSARIES (LEVELS 5-7)", LineStyle.HEADING),
            ("PAIN PRIEST", LineStyle.HEADING),
            ("Tier 3 Social", LineStyle.TIER),
            ("A member of a religious order.", LineStyle.BODY),
            ("Motives & Tactics: Feed on emotions", LineStyle.BODY),
            ("Difficulty: 16 | Thresholds: 16/32 | HP: 6 | Stress: 5", LineStyle.BODY),
            ("ATK: +0 | Torture Implements: Melee | 3d6+4 phy", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Walk Between Worlds - Action: Mark a Stress.", LineStyle.BODY),
        ])

        result = parser()._parse_pages([page], "Test")

        self.assertEqual(result.environments, [])
        self.assertEqual(len(result.adversaries), 1)
        self.assertEqual(result.adversaries[0].adversary_type, "Social")

    def test_section_header_carries_across_pages(self):
        header_page = styled_page(1, [
            ("TIER 1 ENVIRONMENTS (LEVEL 1)", LineStyle.HEADING),
        ])
        result = parser()._parse_pages(
            [header_page, self.social_block("ENVIRONMENTS")], "Test"
        )

        self.assertEqual(len(result.environments), 1)

    def test_social_without_a_section_falls_back_to_field_shape(self):
        page = styled_page(1, [
            ("GRAND FEAST", LineStyle.HEADING),
            ("Tier 1 Social", LineStyle.TIER),
            ("A celebration.", LineStyle.BODY),
            ("Impulses: Bring everyone together", LineStyle.BODY),
            ("Difficulty: 11", LineStyle.BODY),
            ("FEATURES", LineStyle.BODY),
            ("Toast - Action: Someone makes a speech.", LineStyle.BODY),
        ])

        result = parser()._parse_pages([page], "Test")

        self.assertEqual(len(result.environments), 1)


class FeatureHeadingTests(unittest.TestCase):
    def test_name_cannot_start_mid_sentence(self):
        # Matching the whole block let a name absorb trailing damage text,
        # producing "phy Double Swipe".
        text = (
            "FEATURES\n"
            "Flail Swipe - Action: Make an attack dealing 1d8+1 phy\n"
            "Double Swipe - Action: Mark a Stress to attack twice.\n"
        )

        features = parser()._parse_pdf_features(text)

        self.assertEqual(
            [f.name for f in features], ["Flail Swipe", "Double Swipe"]
        )

    def test_typographic_apostrophes_survive_in_names(self):
        text = (
            "FEATURES\n"
            "Into the Spider’s Web - Action: Summon a Darkweave Queen.\n"
        )

        features = parser()._parse_pdf_features(text)

        self.assertEqual(features[0].name, "Into the Spider’s Web")

    def test_description_lines_are_folded_into_the_feature(self):
        text = (
            "FEATURES\n"
            "Pitch Black - Passive: There is no light,\n"
            "natural or otherwise, in these tunnels.\n"
        )

        features = parser()._parse_pdf_features(text)

        self.assertEqual(len(features), 1)
        self.assertEqual(
            features[0].description,
            "There is no light, natural or otherwise, in these tunnels.",
        )


class EnvironmentWriterTests(unittest.TestCase):
    def environment(self) -> Environment:
        return Environment(
            name="ABANDONED MINE",
            tier=1,
            environment_type="Traversal",
            description="A twisting warren of disused tunnels.",
            impulses="Poison the party, split the party",
            difficulty=11,
            potential_adversaries="Darkweave Crawler, Poltergeist",
            features=[EnvironmentFeature(
                name="Pitch Black",
                feature_type="Passive",
                description="There is no light in these tunnels.",
                questions=["What fuel does the light source use?"],
            )],
            source_name="Hope and Fear",
            source_page=39,
        )

    def test_markdown_block_carries_environment_fields(self):
        content = AdversaryBankWriter.format_environment(self.environment())

        self.assertIn("# Abandoned Mine", content)
        self.assertIn('type: "Traversal"', content)
        self.assertIn('impulses: "Poison the party, split the party"', content)
        self.assertIn(
            'potential_adversaries: "Darkweave Crawler, Poltergeist"', content
        )
        self.assertIn('source: "Hope and Fear, p. 39"', content)
        self.assertIn("    questions:", content)
        self.assertIn('      - "What fuel does the light source use?"', content)

    def test_markdown_block_omits_combat_fields(self):
        content = AdversaryBankWriter.format_environment(self.environment())

        for absent in ("hp:", "stress:", "thresholds:", "attack:", "motives:"):
            self.assertNotIn(absent, content)

    def test_non_numeric_difficulty_is_quoted(self):
        env = self.environment()
        env.difficulty = 'Special (see "Relative Strength")'

        content = AdversaryBankWriter.format_environment(env)

        self.assertIn(
            'difficulty: "Special (see \\"Relative Strength\\")"', content
        )

    def test_json_entry_carries_environment_fields(self):
        entry = BeastvaultWriter.format_environment(self.environment())

        self.assertEqual(entry["name"], "ABANDONED MINE")
        self.assertEqual(entry["type"], "Traversal")
        self.assertEqual(entry["impulses"], "Poison the party, split the party")
        self.assertEqual(entry["source"], "hope-and-fear")
        self.assertEqual(
            entry["features"][0]["questions"],
            ["What fuel does the light source use?"],
        )
        for absent in ("hp", "stress", "thresholds", "attack", "xp", "motives"):
            self.assertNotIn(absent, entry)

    def test_environments_are_appended_to_the_json_array(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adversaries.json"
            count = BeastvaultWriter.write_adversaries(
                [], path, environments=[self.environment()]
            )
            entries = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertEqual(entries[0]["name"], "ABANDONED MINE")

    def test_environments_are_written_to_their_own_subfolder(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            written = AdversaryBankWriter.write_multiple(
                [], output_dir, environments=[self.environment()]
            )

            self.assertEqual(len(written), 1)
            path = written["ABANDONED MINE"]
            self.assertEqual(path.parent.name, "environments")
            self.assertTrue(path.exists())


class EnvironmentModelTests(unittest.TestCase):
    def test_validate_reports_missing_fields(self):
        issues = Environment(name="X").validate()

        self.assertIn("Missing tier", issues)
        self.assertIn("Missing environment type", issues)
        self.assertIn("Missing Difficulty", issues)
        self.assertIn("Missing Impulses", issues)
        self.assertIn("No features found", issues)

    def test_safe_filename_is_capped_and_sanitized(self):
        self.assertEqual(
            Environment(name="ALCHEMIST'S ABANDONED WORKSHOP").safe_filename(),
            "Alchemists Abandoned Workshop",
        )
        self.assertLessEqual(len(Environment(name="A" * 300).safe_filename()), 120)

    def test_feature_markdown_includes_questions(self):
        markdown = EnvironmentFeature(
            name="Pitch Black",
            feature_type="Passive",
            description="There is no light.",
            questions=["What now?"],
        ).to_markdown()

        self.assertEqual(
            markdown, "***Pitch Black - Passive:*** There is no light.\n*What now?*"
        )


if __name__ == "__main__":
    unittest.main()
