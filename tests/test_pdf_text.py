"""Tests for font-aware PDF text extraction."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.pdf_text import (
    LineStyle,
    PageLine,
    PageText,
    PDFTextExtractor,
    classify_font,
    decode_pua_digits,
)


def word(text, x0, x1, top, size=8.0, fontname="ABCDEF+QuestaSans-Light"):
    """Build a pdfplumber-shaped word dict."""
    return {
        "text": text,
        "x0": x0,
        "x1": x1,
        "top": top,
        "bottom": top + size,
        "size": size,
        "fontname": fontname,
    }


class PUADigitTests(unittest.TestCase):
    """Display fonts map digits into the Private Use Area with no ToUnicode."""

    def test_tier_digit_is_decoded(self):
        self.assertEqual(decode_pua_digits("Tier  Skulk"), "Tier 1 Skulk")

    def test_zero_is_decoded_from_its_own_codepoint(self):
        # "Horde (10/HP)" — 0 sits at U+E53F, apart from the 1-9 run.
        self.assertEqual(decode_pua_digits("(/HP)"), "(10/HP)")

    def test_observed_digits_decode(self):
        """Digits confirmed by rendering the glyphs or by tier cross-check.

        7 and 9 do not appear anywhere in the source book, so they are
        extrapolated from the contiguous run and deliberately excluded here —
        asserting them would only restate the extrapolation.
        """
        observed = {0: "0", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 8: "8"}

        for digit, expected in observed.items():
            codepoint = 0xE53F if digit == 0 else 0xE541 + digit - 1
            self.assertEqual(decode_pua_digits(chr(codepoint)), expected)

    def test_unmapped_pua_characters_pass_through_untouched(self):
        # Only the known digit codepoints are translated, so a different
        # subset encoding degrades to visible junk rather than silently
        # becoming a plausible wrong number.
        self.assertEqual(decode_pua_digits(""), "")

    def test_text_without_pua_is_unchanged(self):
        self.assertEqual(decode_pua_digits("Difficulty: 12"), "Difficulty: 12")


class FontClassificationTests(unittest.TestCase):
    def test_name_art_is_marked_for_dropping(self):
        self.assertIs(classify_font("ABCDEF+EllisHandRegular", 7.0), LineStyle.ART)

    def test_block_name_and_folio_share_a_font_but_differ_by_size(self):
        self.assertIs(
            classify_font("ABCDEF+EvelethCleanRegular", 12.0), LineStyle.HEADING
        )
        self.assertIs(
            classify_font("ABCDEF+EvelethCleanRegular", 7.5), LineStyle.PAGE_NUMBER
        )

    def test_tier_and_question_fonts_are_distinguished(self):
        self.assertIs(
            classify_font("ABCDEF+QuestaSlab-BoldItalic", 9.0), LineStyle.TIER
        )
        self.assertIs(
            classify_font("ABCDEF+QuestaSlab-Italic", 7.5), LineStyle.QUESTION
        )

    def test_unknown_font_falls_back_to_body(self):
        self.assertIs(classify_font("ABCDEF+SomeOtherFont", 8.0), LineStyle.BODY)


class LineRenderingTests(unittest.TestCase):
    def setUp(self):
        self.extractor = PDFTextExtractor.__new__(PDFTextExtractor)

    def test_ligature_split_words_rejoin_without_a_space(self):
        # pdfplumber emits "Ruffi" and "ans" as separate words with a zero gap.
        row = [word("Ruffi", 357.8, 373.5, 100), word("ans", 373.5, 385.2, 100)]

        line = self.extractor._render_line(row)

        self.assertEqual(line.text, "Ruffians")

    def test_real_word_gaps_still_produce_spaces(self):
        row = [word("Tier", 63.0, 80.0, 100), word("Skulk", 82.0, 105.0, 100)]

        self.assertEqual(self.extractor._render_line(row).text, "Tier Skulk")

    def test_bold_label_and_light_value_stay_on_one_line(self):
        # The two runs differ slightly in `top`; fixed-bucket rounding split
        # them and sorted the value above its label.
        rows = self.extractor._group_words_into_lines([
            word("Motives", 63.0, 95.0, 131.0, fontname="ABCDEF+QuestaSans-Bold"),
            word("&", 97.0, 103.0, 131.0, fontname="ABCDEF+QuestaSans-Bold"),
            word("Tactics:", 105.0, 140.0, 131.0, fontname="ABCDEF+QuestaSans-Bold"),
            word("Avoid,", 142.0, 170.0, 132.4),
            word("escape", 172.0, 200.0, 132.4),
        ])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].text, "Motives & Tactics: Avoid, escape")

    def test_separate_lines_stay_separate(self):
        rows = self.extractor._group_words_into_lines([
            word("first", 63.0, 90.0, 100.0),
            word("second", 63.0, 95.0, 120.0),
        ])

        self.assertEqual([r.text for r in rows], ["first", "second"])

    def test_line_style_follows_the_dominant_font(self):
        row = [
            word("What", 63.0, 85.0, 100, 7.5, "ABCDEF+QuestaSlab-Italic"),
            word("now?", 87.0, 110.0, 100, 7.5, "ABCDEF+QuestaSlab-Italic"),
        ]

        self.assertIs(self.extractor._render_line(row).style, LineStyle.QUESTION)


class PageTextTests(unittest.TestCase):
    def test_plain_text_pages_have_unknown_styles(self):
        page = PageText.from_text(3, "GOBLIN\nTier 1 Skulk")

        self.assertEqual(page.page_number, 3)
        self.assertEqual([line.text for line in page.lines], ["GOBLIN", "Tier 1 Skulk"])
        self.assertTrue(all(line.style is None for line in page.lines))

    def test_text_property_rejoins_lines(self):
        page = PageText(1, [PageLine("a"), PageLine("b")])

        self.assertEqual(page.text, "a\nb")

    def test_page_furniture_is_flagged_for_dropping(self):
        self.assertTrue(PageLine("ROC", LineStyle.ART).is_dropped())
        self.assertTrue(PageLine("86", LineStyle.PAGE_NUMBER).is_dropped())
        self.assertFalse(PageLine("Tier 1 Skulk", LineStyle.TIER).is_dropped())


class VisibleWordTests(unittest.TestCase):
    """Some pages park duplicate stat blocks outside the page box."""

    class FakePage:
        width = 612.0
        height = 792.0

        def __init__(self, words):
            self._words = words

        def extract_words(self, **_kwargs):
            return self._words

    def test_words_outside_the_page_box_are_dropped(self):
        page = self.FakePage([
            word("ROC", -301.0, -271.0, 100.0),
            word("SANDWYRM", 63.0, 130.0, 100.0),
        ])

        visible = PDFTextExtractor._extract_words(page)

        self.assertEqual([w["text"] for w in visible], ["SANDWYRM"])

    def test_visible_words_are_pua_decoded(self):
        page = self.FakePage([word("Tier ", 63.0, 90.0, 100.0)])

        self.assertEqual(PDFTextExtractor._extract_words(page)[0]["text"], "Tier 3")


if __name__ == "__main__":
    unittest.main()
