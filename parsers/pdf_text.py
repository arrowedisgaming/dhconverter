"""Font-aware page text extraction for Daggerheart source PDFs.

Separated from ``pdf_parser`` so that layout concerns (columns, line grouping,
glyph decoding) stay independent of stat-block field parsing.

Three extraction problems are handled here, all of which affect every book in
the Daggerheart line rather than any single release:

1. **Private Use Area digits.** The Questa subset fonts map digits in display
   text to PUA codepoints, so ``Tier 1 Skulk`` extracts as ``Tier  Skulk``.
   See :data:`PUA_DIGITS`.
2. **Split ligatures.** pdfplumber emits ``fi``/``fl`` ligatures as separate
   words with a zero x-gap, producing ``Ruffi ans`` and ``fi nd``. Words are
   joined by measured gap rather than unconditionally spaced.
3. **Split visual lines.** Bold labels and their light-weight values sit a
   fraction of a point apart vertically, so fixed-bucket rounding splits one
   visual line in two and sorts the value above its label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


# Digits rendered in display fonts are mapped into the Private Use Area by the
# subset encoding, with no ToUnicode entry for pdfplumber to fall back on.
# 0 sits at U+E53F; 1-9 run contiguously from U+E541. Verified by rendering
# the affected glyphs and by cross-checking 113 tier lines against their
# "TIER n ADVERSARIES" / "TIER n ENVIRONMENTS" section headers.
PUA_DIGITS: dict[int, str] = {0xE53F: "0"}
PUA_DIGITS.update({0xE541 + n - 1: str(n) for n in range(1, 10)})

_PUA_TABLE = str.maketrans(PUA_DIGITS)

# Below this fraction of the font size, a gap between two extracted words is a
# ligature or punctuation artifact rather than a real space. Measured gaps in
# 8pt body text: real spaces >= 1.3pt, artifacts <= 0.4pt.
_SPACE_GAP_RATIO = 0.12

# Vertical tolerance for treating two words as part of the same visual line,
# as a fraction of the font size.
_LINE_TOLERANCE_RATIO = 0.5


class LineStyle(Enum):
    """Role of a line, inferred from its dominant font.

    Only roles that the parsers actually act on are modelled. Anything else is
    :attr:`BODY`, and text supplied without font information is ``None``.
    """

    HEADING = "heading"        # Block name, or a "TIER n ADVERSARIES" header
    TIER = "tier"              # "Tier 2 Skulk" / "Tier 4 Horde (10/HP)"
    QUESTION = "question"      # Italic GM prompt trailing an environment feature
    ART = "art"                # Decorative name art; duplicates the block name
    PAGE_NUMBER = "page_number"
    BODY = "body"


# Font suffix -> role. Sizes disambiguate the two EvelethClean uses: block
# names and section headers are set at 12pt, folios at 7.5pt.
_ART_FONTS = ("EllisHandRegular",)
_HEADING_FONTS = ("EvelethCleanRegular",)
_TIER_FONTS = ("QuestaSlab-BoldItalic",)
_QUESTION_FONTS = ("QuestaSlab-Italic",)
_HEADING_MIN_SIZE = 10.0

# Running feet carry no stat-block content. The folio sits on the same visual
# line on verso pages, so allow a leading page number: "86 Chapter 3: Tier 3
# Adversaries" as well as "Chapter 3: Adversaries & Environments 61".
_FOOTER_RE = re.compile(r"^\d*\s*Chapter\s+\d+:", re.IGNORECASE)


@dataclass
class PageLine:
    """One visual line of a page, with the role implied by its typography."""

    text: str
    style: Optional[LineStyle] = None

    def is_dropped(self) -> bool:
        """True when the line is page furniture rather than stat-block content."""
        return self.style in (LineStyle.ART, LineStyle.PAGE_NUMBER)


@dataclass
class PageText:
    """All content lines of a single page, in reading order."""

    page_number: int
    lines: list[PageLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @classmethod
    def from_text(cls, page_number: int, text: str) -> "PageText":
        """Build a page from plain text, leaving every line's style unknown.

        Lets callers that already hold extracted text (tests, the Markdown
        parser) share the block-parsing code path. Parsers fall back to regex
        heuristics wherever a style would otherwise have informed them.
        """
        return cls(
            page_number=page_number,
            lines=[PageLine(text=line) for line in text.split("\n")],
        )


def decode_pua_digits(text: str) -> str:
    """Replace Private Use Area digit glyphs with their ASCII digits."""
    return text.translate(_PUA_TABLE)


def classify_font(fontname: str, size: float) -> LineStyle:
    """Map a font name and size to the role it plays in a stat block."""
    suffix = fontname.split("+")[-1]

    if suffix in _ART_FONTS:
        return LineStyle.ART
    if suffix in _HEADING_FONTS:
        return LineStyle.HEADING if size >= _HEADING_MIN_SIZE else LineStyle.PAGE_NUMBER
    if suffix in _TIER_FONTS:
        return LineStyle.TIER
    if suffix in _QUESTION_FONTS:
        return LineStyle.QUESTION
    return LineStyle.BODY


class PDFTextExtractor:
    """Extracts column-aware, style-tagged lines from a PDF page."""

    def extract_pages(self, pdf) -> list[PageText]:
        """Extract every page of an open pdfplumber document."""
        return [
            self.extract_page(page, page_number)
            for page_number, page in enumerate(pdf.pages, start=1)
        ]

    def extract_page(self, page, page_number: int) -> PageText:
        """Extract a single page into styled lines, dropping page furniture."""
        words = self._extract_words(page)

        if not words:
            raw = page.extract_text() or ""
            return PageText.from_text(page_number, raw)

        lines: list[PageLine] = []
        for column in self._detect_columns(words, page.width):
            lines.extend(self._group_words_into_lines(column))

        kept = [
            line
            for line in lines
            if not line.is_dropped() and not _FOOTER_RE.match(line.text.strip())
        ]
        return PageText(page_number=page_number, lines=kept)

    @staticmethod
    def _extract_words(page) -> list[dict]:
        """Pull visible words with font metadata, PUA-decoded.

        Some pages carry stat-block text parked entirely outside the page box —
        Hope & Fear page 27 holds a hidden duplicate of the Roc at negative x.
        It never renders, but left in place it interleaves with the real
        columns and corrupts both. Words are kept only when their midpoint
        falls inside the page, which tolerates small overhangs.
        """
        words = page.extract_words(extra_attrs=["fontname", "size"])

        visible = []
        for word in words:
            x_mid = (word["x0"] + word["x1"]) / 2
            y_mid = (word["top"] + word["bottom"]) / 2
            if not (0 <= x_mid <= page.width and 0 <= y_mid <= page.height):
                continue
            word["text"] = decode_pua_digits(word["text"])
            visible.append(word)

        return visible

    def _detect_columns(self, words: list[dict], page_width: float) -> list[list[dict]]:
        """Split words into columns at the widest gap near the page centre."""
        if not words:
            return []

        x_positions = sorted({round(w["x0"]) for w in words})

        center_zone_start = page_width * 0.2
        center_zone_end = page_width * 0.8
        best_gap = 0.0
        best_split = page_width / 2

        for left, right in zip(x_positions, x_positions[1:]):
            gap = right - left
            gap_center = (left + right) / 2
            if center_zone_start < gap_center < center_zone_end and gap > best_gap:
                best_gap = gap
                best_split = gap_center

        if best_gap < page_width * 0.03:
            return [words]

        left_col = [w for w in words if w["x0"] < best_split]
        right_col = [w for w in words if w["x0"] >= best_split]

        columns = [col for col in (left_col, right_col) if col]
        return columns if len(columns) > 1 else [words]

    def _group_words_into_lines(self, words: list[dict]) -> list[PageLine]:
        """Cluster words into visual lines and render each with its style.

        Clusters greedily on ``top`` with a tolerance proportional to the font
        size, so a bold label and its light-weight value stay on one line even
        when their baselines differ slightly.
        """
        if not words:
            return []

        ordered = sorted(words, key=lambda w: (w["top"], w["x0"]))

        rows: list[list[dict]] = [[ordered[0]]]
        for word in ordered[1:]:
            current = rows[-1]
            tolerance = max(w.get("size", 8.0) for w in current) * _LINE_TOLERANCE_RATIO
            if abs(word["top"] - current[0]["top"]) <= tolerance:
                current.append(word)
            else:
                rows.append([word])

        return [self._render_line(row) for row in rows]

    def _render_line(self, row: list[dict]) -> PageLine:
        """Join one row's words, spacing them by measured gap, and style it."""
        row = sorted(row, key=lambda w: w["x0"])

        parts = [row[0]["text"]]
        for previous, word in zip(row, row[1:]):
            gap = word["x0"] - previous["x1"]
            threshold = previous.get("size", 8.0) * _SPACE_GAP_RATIO
            parts.append(" " if gap > threshold else "")
            parts.append(word["text"])

        return PageLine(text="".join(parts), style=self._dominant_style(row))

    @staticmethod
    def _dominant_style(row: Iterable[dict]) -> LineStyle:
        """Style a line by the font covering the most characters in it."""
        weights: dict[LineStyle, int] = {}
        for word in row:
            style = classify_font(word.get("fontname", ""), word.get("size", 8.0))
            weights[style] = weights.get(style, 0) + len(word["text"])

        if not weights:
            return LineStyle.BODY
        return max(weights.items(), key=lambda item: item[1])[0]
