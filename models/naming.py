"""Filename generation shared by adversary and environment records.

Output filenames are restricted to ``A-Z``, ``a-z``, ``0-9`` and ``_`` so they
survive any filesystem, shell, or sync tool without quoting.
"""
import re
import unicodedata
from typing import Optional


# Longest permitted stem, before any collision suffix.
FILENAME_MAX_LENGTH = 120

FALLBACK_FILENAME = "unknown"

# Apostrophes sit inside a word, so they are dropped rather than replaced with
# a separator: "Alchemist's" -> "Alchemists", not "Alchemist_s".
_APOSTROPHES = "'‘’ʼ`´"

_APOSTROPHE_RE = re.compile(f"[{re.escape(_APOSTROPHES)}]")
_SEPARATOR_RE = re.compile(r"[^A-Za-z0-9]+")


def safe_filename(name: Optional[str]) -> str:
    """Return a filename stem containing only ``[A-Za-z0-9_]``.

    Accented letters are decomposed to their base form so they survive as
    ASCII rather than being deleted. Every other run of non-alphanumeric
    characters becomes a single underscore, which keeps word boundaries
    readable: "CONVERGENCE, THE CITY OF PORTALS" becomes
    ``Convergence_The_City_Of_Portals``.
    """
    if not name:
        return FALLBACK_FILENAME

    # Decompose accents, then drop the combining marks: "é" -> "e".
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))

    without_apostrophes = _APOSTROPHE_RE.sub("", stripped)
    underscored = _SEPARATOR_RE.sub("_", without_apostrophes).strip("_")

    if not underscored:
        return FALLBACK_FILENAME

    titled = "_".join(_title_word(word) for word in underscored.split("_"))

    # Trim after casing so the cap applies to the final text, then clear any
    # underscore the cut left dangling.
    capped = titled[:FILENAME_MAX_LENGTH].rstrip("_")
    return capped or FALLBACK_FILENAME


def _title_word(word: str) -> str:
    return word[:1].upper() + word[1:].lower()
