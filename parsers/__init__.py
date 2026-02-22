"""Daggerheart Adversary parsers."""
from .md_parser import MDParser
from .text_cleaner import TextCleaner

# PDFParser requires pdfplumber, so import conditionally
try:
    from .pdf_parser import PDFParser
    __all__ = ["MDParser", "PDFParser", "TextCleaner"]
except ImportError:
    __all__ = ["MDParser", "TextCleaner"]
