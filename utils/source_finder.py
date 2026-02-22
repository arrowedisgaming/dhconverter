"""Source finder utility for tracing adversaries back to their original sources.

Searches through source PDFs and MDs to find which source contains each adversary.
"""
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# Handle imports for both module and direct execution
try:
    from ..parsers.text_cleaner import TextCleaner
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from parsers.text_cleaner import TextCleaner


@dataclass
class SourceMatch:
    """Represents a source match for an adversary."""
    source_name: str
    source_page: Optional[int] = None
    confidence: float = 1.0  # 0.0-1.0 match confidence


# Source file configurations
SOURCE_CONFIGS = {
    'Age-of-Umbra-Adversaries.pdf': {
        'display_name': 'Age of Umbra Adversaries',
        'type': 'pdf',
    },
    'Adversaries-Environments-v1.5-.pdf': {
        'display_name': 'Adversaries: Environments v1.5',
        'type': 'pdf',
    },
    'Menagerie_of_Mayhem-MUnderwood.md': {
        'display_name': 'Menagerie of Mayhem',
        'type': 'md',
    },
    'martialadversaries-compressed.pdf': {
        'display_name': 'Martial Adversaries',
        'type': 'pdf',
    },
    'undeadadversaries-compressed.pdf': {
        'display_name': 'Undead Adversaries',
        'type': 'pdf',
    },
}


class SourceFinder:
    """Finds source attribution for adversaries by searching source files."""

    def __init__(self, sources_dir: Path):
        """Initialize with path to sources directory."""
        self.sources_dir = sources_dir
        self._pdf_cache: dict[str, list[tuple[int, str]]] = {}
        self._md_cache: dict[str, str] = {}

    def find_source(self, adversary_name: str) -> Optional[SourceMatch]:
        """Find the source for an adversary by name.

        Searches through all source files to find where the adversary appears.
        Returns SourceMatch with source name and page number if found.
        """
        if not adversary_name:
            return None

        # Normalize name for searching (remove special chars, case-insensitive)
        search_name = self._normalize_name(adversary_name)

        # Search each source file
        for filename, config in SOURCE_CONFIGS.items():
            source_path = self.sources_dir / filename

            if not source_path.exists():
                continue

            if config['type'] == 'pdf':
                match = self._search_pdf(source_path, search_name, config['display_name'])
            else:
                match = self._search_md(source_path, search_name, config['display_name'])

            if match:
                return match

        return None

    def _normalize_name(self, name: str) -> str:
        """Normalize adversary name for fuzzy searching."""
        # Convert to uppercase and remove non-alphanumeric chars
        normalized = re.sub(r'[^A-Z0-9\s]', '', name.upper())
        # Collapse multiple spaces
        normalized = ' '.join(normalized.split())
        return normalized

    def _search_pdf(
        self,
        pdf_path: Path,
        search_name: str,
        display_name: str
    ) -> Optional[SourceMatch]:
        """Search a PDF file for an adversary name."""
        if pdfplumber is None:
            return None

        # Use cached pages if available
        cache_key = str(pdf_path)
        if cache_key not in self._pdf_cache:
            self._pdf_cache[cache_key] = self._extract_pdf_pages(pdf_path)

        pages = self._pdf_cache[cache_key]

        for page_num, page_text in pages:
            # Normalize page text for comparison
            normalized_text = self._normalize_name(page_text)

            # Look for the adversary name as a standalone line or header
            # This helps avoid false positives from partial matches
            if self._is_adversary_on_page(search_name, normalized_text):
                return SourceMatch(
                    source_name=display_name,
                    source_page=page_num
                )

        return None

    def _extract_pdf_pages(self, pdf_path: Path) -> list[tuple[int, str]]:
        """Extract text from each page of a PDF."""
        pages = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    text = TextCleaner.clean_text(text)
                    pages.append((page_num, text))
        except Exception:
            pass

        return pages

    def _search_md(
        self,
        md_path: Path,
        search_name: str,
        display_name: str
    ) -> Optional[SourceMatch]:
        """Search a Markdown file for an adversary name."""
        cache_key = str(md_path)
        if cache_key not in self._md_cache:
            try:
                self._md_cache[cache_key] = md_path.read_text(encoding='utf-8')
            except Exception:
                return None

        text = self._md_cache[cache_key]
        normalized_text = self._normalize_name(text)

        # Check if adversary appears as a header (## NAME) in the MD file
        if self._is_adversary_in_md(search_name, normalized_text):
            return SourceMatch(
                source_name=display_name,
                source_page=None  # MD files don't have page numbers
            )

        return None

    def _is_adversary_on_page(self, search_name: str, normalized_text: str) -> bool:
        """Check if an adversary name appears on a page.

        Uses word-boundary matching to find the name without false positives
        from partial matches (e.g., "TROLL" shouldn't match "CONTROLLER").
        """
        # Use word boundaries to find the exact name
        # \b ensures we match whole words, not substrings
        pattern = r'\b' + re.escape(search_name) + r'\b'
        return bool(re.search(pattern, normalized_text))

    def _is_adversary_in_md(self, search_name: str, normalized_text: str) -> bool:
        """Check if adversary name appears as a header in MD file."""
        # In Menagerie format, adversaries appear as ## HEADER NAME
        # After normalization, look for the name
        return self._is_adversary_on_page(search_name, normalized_text)

    def clear_cache(self):
        """Clear cached file contents."""
        self._pdf_cache.clear()
        self._md_cache.clear()


def find_sources_for_adversaries(
    adversary_names: list[str],
    sources_dir: Path
) -> dict[str, Optional[SourceMatch]]:
    """Find sources for a list of adversary names.

    Returns dict mapping adversary name to SourceMatch (or None if not found).
    """
    finder = SourceFinder(sources_dir)
    results = {}

    for name in adversary_names:
        results[name] = finder.find_source(name)

    return results
