"""End-to-end check against the real Daggerheart SRD PDF.

Skipped unless the source PDF is present. ``docs/`` is git-ignored, so this
never runs in a clean checkout — it exists to catch regressions locally.

The SRD is the only book in the line that ships as landscape two-page spreads,
so it is the only cover for the four-column extraction path.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PDF_PATH = Path(__file__).parent.parent / "docs" / "Daggerheart-SRD-9-09-25.pdf"

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


@unittest.skipUnless(PDF_PATH.exists(), f"{PDF_PATH.name} not present")
@unittest.skipUnless(pdfplumber is not None, "pdfplumber not installed")
class SRDIntegrationTests(unittest.TestCase):
    """Counts below were verified against the PDF after the spread fix."""

    EXPECTED_ADVERSARIES = 129
    EXPECTED_ENVIRONMENTS = 19

    @classmethod
    def setUpClass(cls):
        from parsers.pdf_parser import PDFParser

        cls.result = PDFParser().parse_file(PDF_PATH)

    def test_every_stat_block_is_extracted(self):
        self.assertEqual(len(self.result.adversaries), self.EXPECTED_ADVERSARIES)
        self.assertEqual(len(self.result.environments), self.EXPECTED_ENVIRONMENTS)

    def test_no_stat_block_fails_to_parse(self):
        self.assertEqual(self.result.rejected, [])

    def test_no_record_has_validation_issues(self):
        offenders = {
            record.name: record.validate()
            for record in (*self.result.adversaries, *self.result.environments)
            if record.validate()
        }

        self.assertEqual(offenders, {})

    def test_no_name_carries_text_from_the_neighbouring_column(self):
        """Merged columns produced names like "DEEPROOT DEFENDER GIANT RAT"."""
        leaked = re.compile(
            r'Motives|Difficulty|Thresholds|ATK:|FEATURES|Experience:|^\(Levels',
            re.IGNORECASE,
        )
        offenders = [
            record.name
            for record in self.result.adversaries + self.result.environments
            if leaked.search(record.name)
        ]

        self.assertEqual(offenders, [])

    def test_the_narrow_gutter_page_keeps_all_three_environments(self):
        """Page 52's gutter is too narrow to measure, so its half is split
        geometrically. Without that these three merge and vanish, and nothing
        is reported as rejected — the loss is silent."""
        names = {environment.name.upper() for environment in self.result.environments}

        self.assertLessEqual(
            {"ABANDONED GROVE", "AMBUSHED", "AMBUSHERS"}, names
        )

    def test_a_name_ending_in_tier_keeps_its_own_type(self):
        """"COURTIER" ends in "TIER" and used to read as type "Tier"."""
        courtier = next(
            a for a in self.result.adversaries if a.name.upper() == "COURTIER"
        )

        self.assertEqual(courtier.tier, 1)
        self.assertEqual(courtier.adversary_type, "Social")
