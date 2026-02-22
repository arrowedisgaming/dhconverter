"""Text cleaning utilities for PDF and markdown processing."""
import re
from typing import Optional


class TextCleaner:
    """Utility class for cleaning extracted text."""

    # Common PDF artifacts to remove
    PAGE_NUMBER_PATTERNS = [
        r'^\d+\s*$',  # Standalone page numbers
        r'^Page\s+\d+',  # "Page N" format
        r'^\d+\s+of\s+\d+',  # "N of M" format
    ]

    # Headers that often repeat in PDFs
    HEADER_PATTERNS = [
        r'^ADVERSARIES?\s*$',
        r'^DAGGERHEART\s*$',
        r'^SRD\s*$',
    ]

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Apply all cleaning operations to text."""
        if not text:
            return ""

        # Remove BOM (byte order mark) if present
        text = text.lstrip('\ufeff')

        text = cls.remove_page_artifacts(text)
        text = cls.fix_common_ocr_errors(text)
        text = cls.normalize_whitespace(text)
        text = cls.fix_broken_words(text)

        return text

    @classmethod
    def remove_page_artifacts(cls, text: str) -> str:
        """Remove page numbers and repeated headers."""
        lines = text.split('\n')
        cleaned = []

        for line in lines:
            stripped = line.strip()

            # Skip page numbers
            is_page_num = any(
                re.match(p, stripped, re.IGNORECASE)
                for p in cls.PAGE_NUMBER_PATTERNS
            )
            if is_page_num:
                continue

            # Skip repeated headers
            is_header = any(
                re.match(p, stripped, re.IGNORECASE)
                for p in cls.HEADER_PATTERNS
            )
            if is_header:
                continue

            cleaned.append(line)

        return '\n'.join(cleaned)

    @classmethod
    def fix_common_ocr_errors(cls, text: str) -> str:
        """Fix common OCR/extraction errors."""
        # Regex-based replacements
        regex_replacements = [
            (r'Diffi\s*culty', 'Difficulty'),  # Split word
            (r'fl\s*ail', 'flail'),  # Split word
            (r'\bphy\s+damage\b', 'phy'),  # Normalize damage type
            (r'\bmag\s+damage\b', 'mag'),
        ]

        for pattern, replacement in regex_replacements:
            text = re.sub(pattern, replacement, text)

        # Simple character replacements (no regex needed)
        char_replacements = [
            ('–', '-'),  # En-dash to hyphen
            ('—', '-'),  # Em-dash to hyphen
            ('−', '-'),  # Unicode minus (U+2212) to hyphen
            ('"', '"'),  # Smart quotes
            ('"', '"'),
            (''', "'"),
            (''', "'"),
        ]

        for old, new in char_replacements:
            text = text.replace(old, new)

        return text

    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """Normalize whitespace while preserving structure."""
        # Replace multiple spaces with single space (but not newlines)
        text = re.sub(r'[^\S\n]+', ' ', text)
        # Remove trailing whitespace from lines
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        # Collapse more than 2 consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

    @classmethod
    def fix_broken_words(cls, text: str) -> str:
        """Fix words broken across lines by hyphenation."""
        # Pattern: word- at end of line followed by continuation
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        return text

    @classmethod
    def deduplicate_text(cls, text: str, window_size: int = 100) -> str:
        """Remove duplicated text segments common in PDF column extraction.

        PDF tools sometimes read multi-column layouts incorrectly, resulting
        in the same content appearing twice.
        """
        if len(text) < window_size * 2:
            return text

        # Check if the text appears to be duplicated
        # by comparing first and second halves
        mid = len(text) // 2
        first_half = text[:mid]
        second_half = text[mid:]

        # Use a sliding window to find repeated content
        for i in range(0, len(first_half) - window_size, window_size // 2):
            segment = first_half[i:i + window_size]
            if segment in second_half:
                # Found duplication - return just the first occurrence
                # Find where the duplication starts
                dup_start = second_half.find(segment)
                if dup_start != -1:
                    return text[:mid + dup_start].strip()

        return text

    @classmethod
    def extract_number(cls, text: str) -> Optional[int]:
        """Extract first number from text."""
        if not text:
            return None
        match = re.search(r'\d+', str(text))
        return int(match.group()) if match else None

    @classmethod
    def extract_thresholds(cls, text: str) -> tuple[Optional[int], Optional[int]]:
        """Extract threshold values from 'minor/major' format."""
        if not text:
            return None, None

        match = re.search(r'(\d+)\s*/\s*(\d+)', str(text))
        if match:
            return int(match.group(1)), int(match.group(2))

        return None, None

    @classmethod
    def normalize_damage_type(cls, text: str) -> str:
        """Normalize damage type abbreviations."""
        if not text:
            return text

        # Ensure consistent spacing
        text = re.sub(r'\s+', ' ', text.strip())

        # Normalize common damage type variations
        replacements = {
            'physical': 'phy',
            'magic': 'mag',
            'magical': 'mag',
        }

        for old, new in replacements.items():
            text = re.sub(rf'\b{old}\b', new, text, flags=re.IGNORECASE)

        return text
