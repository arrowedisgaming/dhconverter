"""End-to-end check against a third-party book (issue #2).

Skipped unless the source PDF is present. ``docs/`` is git-ignored, so this
never runs in a clean checkout — it exists to catch regressions locally.

*Assortment of Adversaries* is not an official release, and that is the point:
it sets the difficulty on the tier line, lets blocks run across page breaks,
prints Experience before the combat stats, and separates weapon range from
damage with a pipe. Every one of those made the whole book parse to zero
records. It guards the general-case handling that the official books, which
happen to do none of these things, cannot exercise.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PDF_PATH = (
    Path(__file__).parent.parent / "docs" / "Daggerheart_ Assortment of Adversaries.pdf"
)

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


@unittest.skipUnless(PDF_PATH.exists(), f"{PDF_PATH.name} not present")
@unittest.skipUnless(pdfplumber is not None, "pdfplumber not installed")
class AssortmentIntegrationTests(unittest.TestCase):
    # 275 stat blocks are printed; one carries a typo ("Darkness 12" where the
    # difficulty belongs) that leaves it with no difficulty to read.
    EXPECTED_ADVERSARIES = 274
    EXPECTED_BLOCKS = 275

    @classmethod
    def setUpClass(cls):
        from parsers.pdf_parser import PDFParser

        cls.result = PDFParser().parse_file(PDF_PATH)

    def test_every_stat_block_is_extracted(self):
        self.assertEqual(len(self.result.adversaries), self.EXPECTED_ADVERSARIES)
        self.assertEqual(self.result.blocks_detected, self.EXPECTED_BLOCKS)

    def test_the_only_unparsed_block_is_the_one_with_a_typo(self):
        self.assertEqual(len(self.result.rejected), 1)
        self.assertIn("Darkness Elemental", self.result.rejected[0])

    def test_blocks_spanning_a_page_break_keep_their_features(self):
        # Blocks flow continuously here, so roughly a quarter of them have
        # their FEATURES section printed on the page after their name.
        featureless = [a.name for a in self.result.adversaries if not a.features]

        self.assertEqual(featureless, [])

    def test_every_adversary_has_an_attack(self):
        # Weapon lines use "Name: Range | damage"; the official books use a
        # dash, and only the dash was recognised.
        missing = [a.name for a in self.result.adversaries if not a.attack]

        self.assertEqual(missing, [])

    def test_experience_does_not_swallow_the_combat_stats(self):
        # Experience is printed above Thresholds/HP/Stress/ATK in this book.
        offenders = [
            a.name
            for a in self.result.adversaries
            if a.experience and ("\n" in a.experience or "Thresholds" in a.experience)
        ]

        self.assertEqual(offenders, [])

    def test_horde_parenthetical_is_normalised_whichever_side_it_is_printed(self):
        # One block prints "Tier 1 (10/HP) Horde"; the rest print the
        # parenthetical after the keyword. Missing the first form both lost
        # that block and folded its features into the block above it.
        beetle = next(
            a for a in self.result.adversaries if a.name == "Dire Grave Beetle Swarm"
        )
        boar = next(a for a in self.result.adversaries if a.name == "Dire Boar")

        self.assertEqual(beetle.adversary_type, "Horde (10/HP)")
        self.assertNotIn("Bury", [f.name for f in boar.features])
        self.assertIn("Bury", [f.name for f in beetle.features])

    def test_no_feature_absorbed_a_page_of_front_matter(self):
        # A complete block followed by an index or credits page must not read
        # that page into its last feature.
        worst = max(
            (len(f.description or ""), a.name, f.name)
            for a in self.result.adversaries
            for f in a.features
        )

        self.assertLess(worst[0], 1500, f"{worst[1]} :: {worst[2]} looks absorbed")

    def test_tiers_cover_the_whole_book(self):
        self.assertEqual({a.tier for a in self.result.adversaries}, {1, 2, 3, 4})

    def test_records_have_no_validation_issues_beyond_source_typos(self):
        offenders = {
            a.name: a.validate() for a in self.result.adversaries if a.validate()
        }

        # "Thresholds: 10//20" is a typo in the source, not a parse failure.
        self.assertEqual(offenders, {"Crawling Haunter": ["Missing Thresholds"]})


if __name__ == "__main__":
    unittest.main()
