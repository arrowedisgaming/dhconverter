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
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

try:
    from .text_cleaner import TextCleaner
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from parsers.text_cleaner import TextCleaner


# Digits rendered in display fonts are mapped into the Private Use Area by the
# subset encoding, with no ToUnicode entry for pdfplumber to fall back on.
# 0 sits at U+E53F; 1-9 run contiguously from U+E541. Verified by rendering
# the affected glyphs and by cross-checking 113 tier lines against their
# "TIER n ADVERSARIES" / "TIER n ENVIRONMENTS" section headers.
PUA_DIGITS: dict[int, str] = {0xE53F: "0"}
PUA_DIGITS.update({0xE541 + n - 1: str(n) for n in range(1, 10)})

_PUA_TABLE = str.maketrans(PUA_DIGITS)

# Below this fraction of the font size, a gap between two extracted words is a
# ligature or punctuation artifact rather than a real space.
#
# Measured across every word pair in the Hope & Fear chapter: ligature and
# punctuation artifacts top out at 0.078, and real prose spaces start at 0.152.
# (Gaps between are table-of-contents dot leaders, on pages that hold no stat
# blocks.) 0.11 sits near the geometric mean of those two bands.
_SPACE_GAP_RATIO = 0.11

# Vertical tolerance for treating two words as part of the same visual line, as
# a fraction of the font size.
#
# Must exceed the baseline jitter between a bold label and its light-weight
# value on one visual line (up to ~1.4pt at 8pt, i.e. 0.18) while staying under
# the leading between distinct lines (>= 4.9pt, i.e. 0.61 at 8pt). 0.30 sits
# between the two; the previous 0.5 left only 0.17pt of headroom at 12pt.
_LINE_TOLERANCE_RATIO = 0.30


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
    # Whether page furniture and hyphen breaks have already been resolved.
    # Cleaning must happen per column, before columns are concatenated, or a
    # hyphen at the foot of one column joins to the head of the next — so it
    # cannot simply be redone later. Pages built by hand start out uncleaned.
    cleaned: bool = False

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    def ensure_cleaned(self) -> "PageText":
        """Return this page with cleanup applied if it has not been already."""
        if self.cleaned:
            return self
        return PageText(
            page_number=self.page_number,
            lines=clean_page_lines(self.lines),
            cleaned=True,
        )

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

    @classmethod
    def from_cleaned_lines(cls, page_number: int, lines: list[PageLine]) -> "PageText":
        """Build a page whose lines have already been cleaned per column."""
        return cls(page_number=page_number, lines=lines, cleaned=True)


def decode_pua_digits(text: str) -> str:
    """Replace Private Use Area digit glyphs with their ASCII digits."""
    return text.translate(_PUA_TABLE)


def is_page_artifact(text: str) -> bool:
    """True when a line is page furniture rather than stat-block content.

    Style classification catches this for books whose fonts we recognise, but
    the text-pattern check has to stay for every other book: dropping bare
    folios and repeated running heads is behaviour the plain-text path has
    always had, and losing it lets a stray page number attach itself to the
    preceding feature's description.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if _FOOTER_RE.match(stripped):
        return True
    patterns = TextCleaner.PAGE_NUMBER_PATTERNS + TextCleaner.HEADER_PATTERNS
    return any(re.match(pattern, stripped, re.IGNORECASE) for pattern in patterns)


def clean_page_lines(lines: list["PageLine"]) -> list["PageLine"]:
    """Drop page furniture and rejoin words hyphenated across a line break.

    The styled extraction path replaces ``TextCleaner.clean_text``, which used
    to do both of these on the joined page text. Doing it here keeps each
    line's style intact.
    """
    kept: list[PageLine] = []

    for line in lines:
        if line.is_dropped() or is_page_artifact(line.text):
            continue

        # "under-" + "ground" is one word split across lines; "- " with a
        # space before it is a dash and must not swallow the next line.
        if kept and re.search(r'\w-$', kept[-1].text) and re.match(r'\w', line.text):
            kept[-1].text = kept[-1].text[:-1] + line.text
            continue

        kept.append(line)

    return kept


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
            return PageText.from_text(page_number, raw).ensure_cleaned()

        lines: list[PageLine] = []
        for column in self._detect_columns(words, page.width):
            # Cleanup runs per column: a hyphen-broken word must never be
            # joined across the gutter to the top of the next column.
            lines.extend(clean_page_lines(self._group_words_into_lines(column)))

        return PageText.from_cleaned_lines(page_number, lines)

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
