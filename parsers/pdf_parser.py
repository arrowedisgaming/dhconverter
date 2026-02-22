"""PDF parser for Daggerheart adversary extraction.

Uses pdfplumber for text extraction with smart column detection.
"""
import re
import sys
from pathlib import Path
from typing import Optional
from collections import defaultdict

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary, Attack, Feature
    from .text_cleaner import TextCleaner
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Attack, Feature
    from parsers.text_cleaner import TextCleaner


class PDFParser:
    """Parser for extracting adversaries from PDF files."""

    # Patterns for identifying adversary boundaries
    ADVERSARY_START_PATTERNS = [
        r'^[A-Z][A-Z\s]+$',  # ALL CAPS NAME
        r'^TIER\s+\d+',      # Tier indicator
    ]

    # Known adversary type keywords
    ADVERSARY_TYPES = [
        'Bruiser', 'Leader', 'Skulk', 'Support', 'Solo', 'Standard',
        'Ranged', 'Horde', 'Social', 'Minion',
        'Traversal', 'Event', 'Exploration',
    ]

    def __init__(self):
        if pdfplumber is None:
            raise ImportError(
                "pdfplumber is required for PDF parsing. "
                "Install with: pip install pdfplumber"
            )

    def parse_file(self, file_path: Path) -> list[Adversary]:
        """Parse a PDF file and extract all adversaries."""
        # Extract text with page information
        page_texts = self._extract_text_with_pages(file_path)

        # Derive source name from filename
        source_name = self._filename_to_source_name(file_path.name)

        return self._parse_adversaries_from_pages(page_texts, source_name)

    def _extract_text_with_pages(self, file_path: Path) -> list[tuple[int, str]]:
        """Extract text from PDF with page numbers.

        Returns list of (page_number, text) tuples.
        Page numbers are 1-indexed for human readability.
        """
        page_texts = []

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = self._extract_page_with_columns(page)
                page_text = TextCleaner.clean_text(page_text)
                page_texts.append((page_num, page_text))

        return page_texts

    def _extract_text(self, file_path: Path) -> str:
        """Extract text from PDF with column-aware layout (legacy method)."""
        page_texts = self._extract_text_with_pages(file_path)
        return '\n\n'.join(text for _, text in page_texts)

    def _filename_to_source_name(self, filename: str) -> str:
        """Convert PDF filename to human-readable source name.

        Examples:
            'Age-of-Umbra-Adversaries.pdf' -> 'Age of Umbra Adversaries'
            'Adversaries-Environments-v1.5-.pdf' -> 'Adversaries: Environments v1.5'
        """
        # Remove extension
        name = filename.rsplit('.', 1)[0]

        # Replace dashes/underscores with spaces
        name = name.replace('-', ' ').replace('_', ' ')

        # Clean up multiple spaces
        name = ' '.join(name.split())

        # Handle special cases
        if 'Adversaries Environments' in name:
            name = name.replace('Adversaries Environments', 'Adversaries: Environments')

        # Compressed PDF filenames don't produce readable names
        lower_nospace = name.lower().replace(' ', '')
        if 'martialadversaries' in lower_nospace:
            name = 'Martial Adversaries'
        elif 'undeadadversaries' in lower_nospace:
            name = 'Undead Adversaries'

        return name

    def _extract_page_with_columns(self, page) -> str:
        """Extract text from a page, handling multi-column layouts."""
        words = page.extract_words()

        if not words:
            return page.extract_text() or ""

        # Detect columns by analyzing x-coordinates
        columns = self._detect_columns(words, page.width)

        if len(columns) <= 1:
            # Single column - use standard extraction
            return page.extract_text() or ""

        # Multi-column: extract each column separately
        column_texts = []
        for col_words in columns:
            # Sort by y (top to bottom), then x (left to right)
            col_words.sort(key=lambda w: (w['top'], w['x0']))

            # Group words into lines by y-position
            lines = self._group_words_into_lines(col_words)
            col_text = '\n'.join(lines)
            column_texts.append(col_text)

        return '\n\n'.join(column_texts)

    def _detect_columns(self, words: list[dict], page_width: float) -> list[list[dict]]:
        """Detect column layout and group words by column."""
        if not words:
            return []

        # Find the largest gap in x-positions near the center of the page
        # to detect column boundaries more accurately
        x_positions = sorted(set(round(w['x0']) for w in words))

        # Look for the widest gap in the middle 60% of the page
        center_zone_start = page_width * 0.2
        center_zone_end = page_width * 0.8
        best_gap = 0
        best_split = page_width / 2  # fallback to midpoint

        for i in range(len(x_positions) - 1):
            gap_start = x_positions[i]
            gap_end = x_positions[i + 1]
            gap = gap_end - gap_start

            # Only consider gaps in the center zone
            gap_center = (gap_start + gap_end) / 2
            if center_zone_start < gap_center < center_zone_end and gap > best_gap:
                best_gap = gap
                best_split = (gap_start + gap_end) / 2

        # Need a minimum gap to consider it a column split (at least 3% of page width)
        min_gap = page_width * 0.03
        if best_gap < min_gap:
            return [words]

        left_col = []
        right_col = []

        for word in words:
            if word['x0'] < best_split:
                left_col.append(word)
            else:
                right_col.append(word)

        columns = []
        if left_col:
            columns.append(left_col)
        if right_col:
            columns.append(right_col)

        return columns if len(columns) > 1 else [words]

    def _group_words_into_lines(self, words: list[dict], tolerance: float = 5) -> list[str]:
        """Group words into lines based on y-position."""
        if not words:
            return []

        # Group words by approximate y-position
        lines_dict = defaultdict(list)
        for word in words:
            # Round y to nearest tolerance
            y_key = round(word['top'] / tolerance) * tolerance
            lines_dict[y_key].append(word)

        # Sort lines by y-position and words within each line by x
        lines = []
        for y_key in sorted(lines_dict.keys()):
            line_words = sorted(lines_dict[y_key], key=lambda w: w['x0'])
            line_text = ' '.join(w['text'] for w in line_words)
            lines.append(line_text)

        return lines

    def _parse_adversaries_from_pages(
        self,
        page_texts: list[tuple[int, str]],
        source_name: str
    ) -> list[Adversary]:
        """Parse adversaries from page-tagged text blocks."""
        adversaries = []

        for page_num, page_text in page_texts:
            page_text = TextCleaner.deduplicate_text(page_text)
            blocks = self._split_into_adversary_blocks(page_text)

            for block in blocks:
                adv = self._parse_adversary_block(block)
                if adv and adv.name:
                    adv.source_name = source_name
                    adv.source_page = page_num
                    adversaries.append(adv)

        return adversaries

    def _parse_adversaries_from_text(self, text: str) -> list[Adversary]:
        """Parse adversaries from extracted text (legacy method)."""
        adversaries = []

        # Split text into potential adversary blocks
        blocks = self._split_into_adversary_blocks(text)

        for block in blocks:
            adv = self._parse_adversary_block(block)
            if adv and adv.name:
                adversaries.append(adv)

        return adversaries

    def _split_into_adversary_blocks(self, text: str) -> list[str]:
        """Split text into individual adversary blocks.

        Uses a two-pass strategy:
        1. Primary: Find Tier lines, then look backward 1-2 lines for the name
        2. Fallback: ALL-CAPS name detection (for backward compat with older PDFs)
        """
        lines = text.split('\n')

        # Build a regex matching any known adversary type keyword
        type_keywords = '|'.join(re.escape(t) for t in self.ADVERSARY_TYPES)
        tier_pattern = re.compile(
            rf'^Tier\s+\d+\s+(?:{type_keywords})',
            re.IGNORECASE
        )

        # Collect start-line indices where adversary blocks begin
        start_indices = set()

        # Pass 1: Tier-line backward lookup
        for i, line in enumerate(lines):
            if tier_pattern.match(line.strip()):
                # Look backward for the name line
                name_idx = None
                if i >= 2:
                    two_back = lines[i - 2].strip()
                    # Two-line name: first part ends with colon (e.g., "Dragon Lich:")
                    if two_back and two_back.endswith(':') and lines[i - 1].strip():
                        name_idx = i - 2
                if name_idx is None and i >= 1 and lines[i - 1].strip():
                    name_idx = i - 1

                if name_idx is not None:
                    start_indices.add(name_idx)

        # Pass 2: ALL-CAPS fallback for any blocks not caught by Tier lookup
        for i, line in enumerate(lines):
            if i not in start_indices and self._is_adversary_start(line, []):
                # Only add if there isn't already a nearby start index
                # (within 2 lines) to avoid duplicates
                if any(abs(i - s) <= 2 for s in start_indices):
                    continue
                # Verify a Tier line follows within the next 5 lines
                # This prevents motives/tactics text in ALL-CAPS from
                # being misidentified as adversary names
                has_tier_nearby = any(
                    re.match(r'^\s*Tier\s+\d+', lines[j], re.IGNORECASE)
                    for j in range(i + 1, min(i + 6, len(lines)))
                )
                if has_tier_nearby:
                    start_indices.add(i)

        if not start_indices:
            return [text] if text.strip() else []

        # Sort and split
        sorted_starts = sorted(start_indices)
        blocks = []
        for j, start in enumerate(sorted_starts):
            end = sorted_starts[j + 1] if j + 1 < len(sorted_starts) else len(lines)
            block = '\n'.join(lines[start:end])
            if block.strip():
                blocks.append(block)

        return blocks

    def _is_adversary_start(self, line: str, current_block: list) -> bool:
        """Determine if a line starts a new adversary block."""
        stripped = line.strip()

        if not stripped:
            return False

        # ALL CAPS line that's not a section header (allow commas/colons for names like "XERO, CASTLE KILLER")
        if (re.match(r'^[A-Z][A-Z\s,:]+$', stripped) and
            len(stripped) > 3 and
            stripped not in ('FEATURES', 'ACTIONS', 'REACTIONS', 'PASSIVE')):

            # Check if next lines look like adversary content
            return True

        return False

    def _parse_adversary_block(self, block: str) -> Optional[Adversary]:
        """Parse a single adversary block into an Adversary object."""
        if not block.strip():
            return None

        adv = Adversary()
        lines = block.split('\n')

        # First non-empty line is usually the name
        for i, line in enumerate(lines):
            if line.strip():
                adv.name = line.strip()
                # Multi-line names: "Dragon Lich:" on one line, "Decay-Bringer" on the next
                if adv.name.endswith(':') and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.match(r'^Tier\s+\d+', next_line, re.IGNORECASE):
                        adv.name = adv.name + ' ' + next_line
                break

        # Look for Tier line (captures "Horde (8/HP)" style parentheticals)
        tier_match = re.search(
            r'Tier\s+(\d+)\s+(\w+(?:\s*\([^)]+\))?)',
            block, re.IGNORECASE
        )
        if tier_match:
            adv.tier = int(tier_match.group(1))
            adv.adversary_type = tier_match.group(2)

        # Parse stats: Difficulty, Thresholds, HP, Stress
        self._parse_pdf_stats(adv, block)

        # Parse description (italic-like text or flavor text)
        self._parse_pdf_description(adv, block)

        # Parse Motives & Tactics
        motives_match = re.search(
            r'Motives\s*(?:&|and)\s*Tactics[:\s]+(.+?)(?:Difficulty|$)',
            block, re.IGNORECASE | re.DOTALL
        )
        if motives_match:
            adv.motives_tactics = motives_match.group(1).strip()

        # Parse features
        adv.features = self._parse_pdf_features(block)

        return adv

    def _parse_pdf_stats(self, adv: Adversary, text: str) -> None:
        """Parse stat values from PDF text."""
        # Difficulty
        diff_match = re.search(r'Difficulty[:\s]+(\d+)', text, re.IGNORECASE)
        if diff_match:
            adv.difficulty = int(diff_match.group(1))

        # Thresholds (various formats)
        thresh_patterns = [
            r'Thresholds?[:\s]+(\d+)\s*/\s*(\d+)',
            r'Minor[:\s]+(\d+).*Major[:\s]+(\d+)',
        ]
        for pattern in thresh_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                adv.threshold_minor = int(match.group(1))
                adv.threshold_major = int(match.group(2))
                break

        # HP
        hp_match = re.search(r'HP[:\s]+(\d+)', text, re.IGNORECASE)
        if hp_match:
            adv.hp = int(hp_match.group(1))

        # Stress
        stress_match = re.search(r'Stress[:\s]+(\d+)', text, re.IGNORECASE)
        if stress_match:
            adv.stress = int(stress_match.group(1))

        # Attack info
        atk_match = re.search(
            r'(?:ATK|Attack)[:\s]+([+-]?\d+)[^|]*\|([^|]+)\|([^|\n]+)',
            text, re.IGNORECASE
        )
        if atk_match:
            adv.attack = Attack(
                modifier=atk_match.group(1).strip(),
                weapon_name=atk_match.group(2).strip().split(':')[0].strip(),
                range=atk_match.group(2).strip().split(':')[-1].strip() if ':' in atk_match.group(2) else None,
                damage=TextCleaner.normalize_damage_type(atk_match.group(3).strip())
            )

        # Experience
        exp_match = re.search(
            r'Experience[:\s]+(.+?)(?:FEATURES|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        if exp_match:
            adv.experience = exp_match.group(1).strip()

    def _parse_pdf_description(self, adv: Adversary, text: str) -> None:
        """Extract description/flavor text from PDF block."""
        # Look for text between name/tier and Motives
        # This is typically italic in the PDF
        lines = text.split('\n')
        in_description = False
        desc_lines = []

        # Build a set of name-line strings to skip (handles multi-line names)
        name_parts = set()
        if adv.name:
            name_parts.add(adv.name)
            # For multi-line names like "Dragon Lich: Decay-Bringer",
            # also skip each individual line
            for part in adv.name.split(': ', 1):
                name_parts.add(part)
                name_parts.add(part + ':')  # "Dragon Lich:"

        for line in lines:
            stripped = line.strip()

            # Skip name lines (ALL-CAPS or matching the parsed name)
            if re.match(r'^[A-Z][A-Z\s,:]+$', stripped):
                continue
            if stripped in name_parts:
                continue
            if re.match(r'^Tier\s+\d+', stripped, re.IGNORECASE):
                in_description = True
                continue

            # Stop at Motives or stats
            if 'Motives' in stripped or 'Difficulty' in stripped:
                break

            if in_description and stripped:
                desc_lines.append(stripped)

        if desc_lines:
            adv.description = ' '.join(desc_lines)

    def _parse_pdf_features(self, text: str) -> list[Feature]:
        """Parse features from PDF text."""
        features = []

        # Find FEATURES section
        features_start = text.upper().find('FEATURES')
        if features_start == -1:
            return features

        features_text = text[features_start:]

        # Skip the "FEATURES" header line itself
        features_text = re.sub(r'^FEATURES\s*', '', features_text, flags=re.IGNORECASE)

        # Collapse newlines to spaces so multi-line PDF text is treated as continuous
        features_text = re.sub(r'\n', ' ', features_text)

        # Pattern for feature entries: Name - Type: Description
        # Feature names contain letters, digits, spaces, parens, quotes
        # The colon after the type is required to anchor the match precisely
        feature_pattern = r'([\w][\w\s()\"\']+?)\s*-\s*(Passive|Action|Reaction|Evolution):\s*(.+?)(?=[\w][\w\s()\"\']+?\s*-\s*(?:Passive|Action|Reaction|Evolution):|$)'

        matches = re.findall(feature_pattern, features_text, re.IGNORECASE)

        for name, ftype, desc in matches:
            # Clean up the name and description
            name = re.sub(r'\s+', ' ', name).strip()
            desc = re.sub(r'\s+', ' ', desc).strip()

            # Clean up name if it starts with non-alpha chars (artifacts from inline stat text)
            name = re.sub(r'^[^A-Za-z]+', '', name).strip()

            if name:
                features.append(Feature(
                    name=name,
                    feature_type=ftype.strip().capitalize(),
                    description=desc
                ))

        return features
