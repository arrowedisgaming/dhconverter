"""End-to-end check against the real Hope & Fear PDF.

Skipped unless the source PDF is present. ``docs/`` is git-ignored, so this
never runs in a clean checkout — it exists to catch regressions locally,
against the book the parser was built for.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PDF_PATH = Path(__file__).parent.parent / "docs" / "HF-adversariesonly.pdf"

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


@unittest.skipUnless(PDF_PATH.exists(), f"{PDF_PATH.name} not present")
@unittest.skipUnless(pdfplumber is not None, "pdfplumber not installed")
class HopeAndFearIntegrationTests(unittest.TestCase):
    """Counts below were verified against the printed book."""

    EXPECTED_ADVERSARIES = 135
    EXPECTED_ENVIRONMENTS = 28

    @classmethod
    def setUpClass(cls):
        from parsers.pdf_parser import PDFParser

        cls.result = PDFParser().parse_file(PDF_PATH)

    def test_every_stat_block_is_extracted(self):
        self.assertEqual(len(self.result.adversaries), self.EXPECTED_ADVERSARIES)
        self.assertEqual(len(self.result.environments), self.EXPECTED_ENVIRONMENTS)

    def test_no_record_has_validation_issues(self):
        offenders = {
            record.name: record.validate()
            for record in (*self.result.adversaries, *self.result.environments)
            if record.validate()
        }

        self.assertEqual(offenders, {})

    def test_tier_numbers_are_decoded_for_every_record(self):
        # Tier digits are Private Use Area glyphs; a decode failure leaves
        # every tier None and silently drops the whole book.
        tiers = {
            record.tier
            for record in (*self.result.adversaries, *self.result.environments)
        }

        self.assertEqual(tiers, {1, 2, 3, 4})

    def test_ligatures_are_rejoined(self):
        blob = " ".join(
            f"{a.description} {a.motives_tactics}" for a in self.result.adversaries
        )

        for broken in ("fi ", "fl ", "Diffi", "Ruffi"):
            self.assertNotIn(f" {broken}", blob)

    def test_social_blocks_route_by_section(self):
        social_envs = [
            e for e in self.result.environments if e.environment_type == "Social"
        ]
        social_advs = [
            a for a in self.result.adversaries if a.adversary_type == "Social"
        ]

        self.assertEqual(len(social_envs), 6)
        self.assertEqual(len(social_advs), 5)
        # Social adversaries are told apart from Social environments only by
        # their section header, so confirm they really carry combat stats.
        self.assertTrue(all(a.hp is not None and a.attack for a in social_advs))

    def test_no_duplicate_records(self):
        names = [
            r.name for r in (*self.result.adversaries, *self.result.environments)
        ]

        self.assertEqual(len(names), len(set(names)))

    def test_every_environment_feature_has_gm_prompts(self):
        without = [
            f"{env.name}: {feature.name}"
            for env in self.result.environments
            for feature in env.features
            if not feature.questions
        ]

        self.assertEqual(without, [])

    def test_a_known_environment_parses_completely(self):
        mine = next(
            e for e in self.result.environments if e.name == "ABANDONED MINE"
        )

        self.assertEqual(mine.tier, 1)
        self.assertEqual(mine.environment_type, "Traversal")
        self.assertEqual(mine.difficulty, 11)
        self.assertEqual(mine.source_page, 39)
        self.assertEqual([f.name for f in mine.features], [
            "Pitch Black",
            "Labyrinth",
            "Into the Spider’s Web",
            "Impending Collapse",
        ])
        self.assertEqual(mine.features[0].questions, [
            "What fuel does the party’s light source use, and how long will it last?",
            "What unwanted attention does the light attract?",
        ])

    def test_a_known_adversary_parses_completely(self):
        ahuizotl = next(
            a for a in self.result.adversaries if a.name == "AHUIZOTL"
        )

        self.assertEqual(ahuizotl.tier, 1)
        self.assertEqual(ahuizotl.adversary_type, "Skulk")
        self.assertEqual(ahuizotl.difficulty, 12)
        self.assertEqual(ahuizotl.thresholds_str, "5/9")
        self.assertEqual((ahuizotl.hp, ahuizotl.stress), (4, 3))
        self.assertEqual(ahuizotl.attack.modifier, "+2")
        self.assertEqual(ahuizotl.attack.weapon_name, "Bite")
        self.assertEqual(ahuizotl.attack.range, "Melee")
        self.assertEqual(ahuizotl.attack.damage, "1d6+2 phy")
        self.assertEqual(len(ahuizotl.features), 3)

    def test_off_page_duplicate_text_does_not_corrupt_neighbours(self):
        # Page 27 parks a hidden copy of the Roc outside the page box.
        sandwyrm = next(
            a for a in self.result.adversaries if a.name == "SANDWYRM"
        )

        self.assertEqual([f.name for f in sandwyrm.features], [
            "Venomous Tail Stinger",
            "Devour",
            "Hungry, Not Stupid",
        ])


if __name__ == "__main__":
    unittest.main()
