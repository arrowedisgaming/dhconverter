"""PDF parser for Daggerheart adversary and environment extraction.

Text extraction (columns, line grouping, glyph decoding) lives in
:mod:`parsers.pdf_text`; this module turns the resulting lines into stat-block
records.
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary, Attack, Feature
    from ..models.environment import (
        Environment,
        EnvironmentFeature,
        base_type,
        is_ambiguous_type,
        is_environment_only_type,
    )
    from ..models.parse_result import ParseResult
    from .text_cleaner import TextCleaner
    from .pdf_text import LineStyle, PageLine, PageText, PDFTextExtractor
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Attack, Feature
    from models.environment import (
        Environment,
        EnvironmentFeature,
        base_type,
        is_ambiguous_type,
        is_environment_only_type,
    )
    from models.parse_result import ParseResult
    from parsers.text_cleaner import TextCleaner
    from parsers.pdf_text import LineStyle, PageLine, PageText, PDFTextExtractor


# A page supplied either as styled lines or as plain text with a page number.
PageInput = Union[PageText, tuple[int, str]]


@dataclass
class _Block:
    """One stat block's lines, with the section it was found under."""

    lines: list[PageLine]
    page_number: int
    section: Optional[str] = None  # "ADVERSARIES" | "ENVIRONMENTS" | None
    section_tier: Optional[int] = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


class PDFParser:
    """Parser for extracting adversaries and environments from PDF files."""

    # Known type keywords appearing on a tier line, for both record kinds.
    ADVERSARY_TYPES = [
        'Bruiser', 'Leader', 'Skulk', 'Support', 'Solo', 'Standard',
        'Ranged', 'Horde', 'Social', 'Minion',
        'Traversal', 'Event', 'Exploration',
    ]

    # "TIER 3 ADVERSARIES (LEVELS 5-7)" / "TIER 1 ENVIRONMENTS (LEVEL 1)"
    SECTION_RE = re.compile(
        r'^TIER\s+(\d+)\s+(ADVERSARIES|ENVIRONMENTS)\b',
        re.IGNORECASE,
    )

    def __init__(self):
        if pdfplumber is None:
            raise ImportError(
                "pdfplumber is required for PDF parsing. "
                "Install with: pip install pdfplumber"
            )
        self.extractor = PDFTextExtractor()

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def parse_file(
        self, file_path: Path, source_name: Optional[str] = None
    ) -> ParseResult:
        """Parse a PDF file and extract all adversaries and environments."""
        pages = self._extract_pages(file_path)
        source_name = source_name or self._filename_to_source_name(file_path.name)
        return self._parse_pages(pages, source_name)

    def _extract_pages(self, file_path: Path) -> list[PageText]:
        """Extract every page as styled lines."""
        with pdfplumber.open(file_path) as pdf:
            pages = self.extractor.extract_pages(pdf)

        for page in pages:
            for line in page.lines:
                line.text = TextCleaner.fix_common_ocr_errors(line.text)

        return pages

    def _extract_text_with_pages(self, file_path: Path) -> list[tuple[int, str]]:
        """Extract text from PDF with page numbers (legacy plain-text view)."""
        return [(page.page_number, page.text) for page in self._extract_pages(file_path)]

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
        elif 'hopeandfear' in lower_nospace or lower_nospace.startswith('hf'):
            name = 'Hope and Fear'

        return name

    # ------------------------------------------------------------------
    # Block discovery and routing
    # ------------------------------------------------------------------

    def _parse_pages(self, pages: list[PageInput], source_name: str) -> ParseResult:
        """Parse styled or plain-text pages into records."""
        result = ParseResult()
        section: Optional[str] = None
        section_tier: Optional[int] = None

        for page in pages:
            page = self._coerce_page(page)

            for block in self._split_into_blocks(page, section, section_tier):
                section = block.section
                section_tier = block.section_tier

                record = self._parse_block(block)
                if record is None:
                    continue
                record.source_name = source_name
                record.source_page = page.page_number
                if isinstance(record, Environment):
                    result.environments.append(record)
                else:
                    result.adversaries.append(record)

            section, section_tier = self._trailing_section(page, section, section_tier)

        return result

    def _parse_adversaries_from_pages(
        self, pages: list[PageInput], source_name: str
    ) -> ParseResult:
        """Parse records from page-tagged text blocks."""
        return self._parse_pages(pages, source_name)

    @staticmethod
    def _coerce_page(page: PageInput) -> PageText:
        """Accept either styled pages or (page_number, text) tuples."""
        if isinstance(page, PageText):
            return page.ensure_cleaned()
        page_number, text = page
        cleaned = TextCleaner.clean_text(text)
        return PageText.from_text(page_number, cleaned).ensure_cleaned()

    def _trailing_section(
        self, page: PageText, section: Optional[str], section_tier: Optional[int]
    ) -> tuple[Optional[str], Optional[int]]:
        """Carry the last section header on a page over to the next page."""
        for line in page.lines:
            match = self.SECTION_RE.match(line.text.strip())
            if match:
                section_tier = int(match.group(1))
                section = match.group(2).upper()
        return section, section_tier

    def _tier_line_re(self) -> re.Pattern:
        keywords = '|'.join(re.escape(t) for t in self.ADVERSARY_TYPES)
        return re.compile(
            rf'^Tier\s+(\d+)?\s*({keywords})(\s*\([^)]*\))?\s*$',
            re.IGNORECASE,
        )

    def _split_into_blocks(
        self,
        page: PageText,
        section: Optional[str],
        section_tier: Optional[int],
    ) -> list[_Block]:
        """Split a page into stat blocks, anchored on tier lines.

        Each block starts at its name line — the heading lines immediately
        preceding the tier line — and runs to the next block or the end of the
        page.
        """
        lines = page.lines
        tier_re = self._tier_line_re()

        # Section headers as they appear down the page, so each block inherits
        # the section it sits under.
        sections: dict[int, tuple[str, int]] = {}
        for i, line in enumerate(lines):
            match = self.SECTION_RE.match(line.text.strip())
            if match:
                sections[i] = (match.group(2).upper(), int(match.group(1)))

        starts: list[int] = []
        for i, line in enumerate(lines):
            if tier_re.match(line.text.strip()):
                name_start = self._find_name_start(lines, i)
                if name_start is not None and name_start not in starts:
                    starts.append(name_start)

        blocks = []
        for j, start in enumerate(starts):
            end = starts[j + 1] if j + 1 < len(starts) else len(lines)

            # A section header between two blocks belongs to neither. Without
            # this the header is swept into the preceding block and ends up
            # appended to its last feature's description.
            for index in sections:
                if start < index < end:
                    end = index

            block_section, block_tier = section, section_tier
            for index, (name, tier) in sections.items():
                if index < start:
                    block_section, block_tier = name, tier

            block_lines = lines[start:end]
            if any(line.text.strip() for line in block_lines):
                blocks.append(_Block(
                    lines=block_lines,
                    page_number=page.page_number,
                    section=block_section,
                    section_tier=block_tier,
                ))

        return blocks

    def _find_name_start(self, lines: list[PageLine], tier_index: int) -> Optional[int]:
        """Locate the first line of the name preceding a tier line.

        With font information, the name is the run of heading lines directly
        above the tier line — which handles names wrapping across two lines,
        such as "ALCHEMIST'S ABANDONED / WORKSHOP". Without it, fall back to
        the preceding non-empty line, extended one line up when it ends in a
        colon ("Dragon Lich: / Decay-Bringer").
        """
        styled = any(line.style is not None for line in lines)

        if styled:
            start = None
            i = tier_index - 1
            while i >= 0:
                line = lines[i]
                if line.style is not LineStyle.HEADING:
                    break
                if self.SECTION_RE.match(line.text.strip()):
                    break
                start = i
                i -= 1
            if start is not None:
                return start

        index = tier_index - 1
        while index >= 0 and not lines[index].text.strip():
            index -= 1
        if index < 0:
            return None

        if index >= 1 and lines[index].text.strip().endswith(':'):
            return index
        if index >= 1 and lines[index - 1].text.strip().endswith(':'):
            return index - 1
        return index

    def _parse_block(self, block: _Block) -> Optional[Union[Adversary, Environment]]:
        """Parse a block into whichever record kind it represents."""
        if self._is_environment_block(block):
            environment = self._parse_environment_block(block)
            return environment if self._is_valid_environment(environment) else None

        adversary = self._parse_adversary_block(block)
        return adversary if self._is_valid_pdf_adversary(adversary) else None

    def _is_environment_block(self, block: _Block) -> bool:
        """Decide whether a block is an environment.

        The type keyword decides when it is unambiguous. "Social" is shared by
        both kinds, so it defers to the enclosing section header and, failing
        that, to the block's field shape.
        """
        type_name = self._tier_type(block)

        if is_environment_only_type(type_name):
            return True

        if is_ambiguous_type(type_name):
            # Field shape is decisive when it is unambiguous: Impulses and no
            # HP/Stress is an environment whatever section we think we are in,
            # and HP/Stress is an adversary. Only fall back to the section
            # header when the block itself does not say. A section header
            # carried over from an earlier page is easily stale, and letting
            # it win here silently discarded whole records.
            shape = self._environment_by_shape(block.text)
            if shape is not None:
                return shape
            if block.section == "ENVIRONMENTS":
                return True
            if block.section == "ADVERSARIES":
                return False
            return self._looks_like_environment(block.text)

        if type_name:
            return False

        return self._looks_like_environment(block.text)

    @classmethod
    def _environment_by_shape(cls, text: str) -> Optional[bool]:
        """Classify by field shape, or None when the block is not decisive.

        Impulses with no combat track is unambiguously an environment; a
        combat track is unambiguously an adversary. Anything else abstains.
        """
        has_impulses = bool(re.search(r'\bImpulses\s*:', text, re.IGNORECASE))
        has_combat = bool(re.search(r'\b(?:HP|Stress)\s*:', text, re.IGNORECASE))

        if has_impulses and not has_combat:
            return True
        if has_combat and not has_impulses:
            return False
        return None

    @classmethod
    def _looks_like_environment(cls, text: str) -> bool:
        """Fall back to field shape: environments have Impulses and no HP."""
        shape = cls._environment_by_shape(text)
        if shape is not None:
            return shape
        return not re.search(r'\b(?:HP|Stress)\s*:', text, re.IGNORECASE)

    def _tier_type(self, block: _Block) -> Optional[str]:
        """Read the type keyword off the block's tier line."""
        tier_re = self._tier_line_re()
        for line in block.lines:
            match = tier_re.match(line.text.strip())
            if match:
                return match.group(2)
        return None

    # ------------------------------------------------------------------
    # Shared block helpers
    # ------------------------------------------------------------------

    def _parse_name(self, lines: list[PageLine]) -> str:
        """Read the name from the leading lines of a block.

        Names wrap across lines ("ALCHEMIST'S ABANDONED / WORKSHOP"). With font
        information the name is the leading run of heading lines; otherwise a
        trailing colon marks a continuation ("Dragon Lich: / Decay-Bringer").
        """
        collected: list[str] = []

        for line in lines:
            stripped = line.text.strip()
            if not stripped:
                if collected:
                    break
                continue
            if re.match(r'^Tier\b', stripped, re.IGNORECASE):
                break

            collected.append(stripped)

            if line.style is LineStyle.HEADING:
                continue
            if line.style is None and stripped.endswith(':'):
                continue
            break

        return ' '.join(collected)

    @staticmethod
    def _parse_tier_line(text: str) -> tuple[Optional[int], Optional[str]]:
        """Read tier number and type keyword from a block's tier line."""
        match = re.search(
            r'Tier\s+(\d+)?\s*(\w+(?:\s*\([^)]+\))?)',
            text, re.IGNORECASE
        )
        if not match:
            return None, None
        tier = int(match.group(1)) if match.group(1) else None
        return tier, match.group(2)

    # ------------------------------------------------------------------
    # Adversary parsing
    # ------------------------------------------------------------------

    def _parse_adversary_block(self, block: _Block) -> Optional[Adversary]:
        """Parse a single adversary block into an Adversary object."""
        text = block.text
        if not text.strip():
            return None

        adv = Adversary()
        adv.name = self._parse_name(block.lines)
        adv.tier, adv.adversary_type = self._parse_tier_line(text)
        if adv.tier is None:
            adv.tier = block.section_tier

        self._parse_pdf_stats(adv, text)
        self._parse_pdf_description(adv, text)
        self._parse_pdf_motives(adv, text)
        adv.features = self._parse_pdf_features(text)

        return adv

    def _is_valid_pdf_adversary(self, adv: Optional[Adversary]) -> bool:
        """Return True when a parsed block has the minimum stat-block shape."""
        if adv is None:
            return False
        if not adv.name or len(adv.name) > 120:
            return False
        return all([
            adv.tier is not None,
            adv.adversary_type,
            adv.difficulty is not None,
            bool(adv.features),
            adv.hp is not None,
            adv.stress is not None,
        ])

    def _parse_pdf_stats(self, adv: Adversary, text: str) -> None:
        """Parse stat values from PDF text."""
        # Difficulty
        diff_match = re.search(r'Difficulty[:\s]+(\d+)', text, re.IGNORECASE)
        if diff_match:
            adv.difficulty = int(diff_match.group(1))

        self._parse_thresholds(adv, text)

        adv.hp = self._parse_stat_value(text, "HP")
        adv.stress = self._parse_stat_value(text, "Stress")

        # Attack info. The pipe-separated form is handed to Attack.from_string
        # so both paths share one modifier grammar — parsing the modifier here
        # with a plain `\d+` truncated variable modifiers, turning "+2d4" into
        # "+2" with nothing to indicate the loss.
        atk_match = re.search(
            r'(?:ATK|Attack)\s*:?\s*([^\n]+)', text, re.IGNORECASE
        )
        if atk_match and '|' in atk_match.group(1):
            payload = atk_match.group(1).strip()
            attack = Attack.from_string(payload)
            # Attack.from_string requires a sign on the modifier. Some books
            # print it unsigned ("ATK: 2 | Bite: Melee | 1d6 phy"), which the
            # previous regex accepted, so recover that case here rather than
            # loosening the shared grammar and changing Markdown parsing too.
            if attack.modifier is None:
                leading = payload.split('|', 1)[0].strip()
                if re.fullmatch(r'\d+', leading):
                    attack.modifier = leading
                    if attack.weapon_name == leading:
                        attack.weapon_name = None
            if attack.damage:
                attack.damage = TextCleaner.normalize_damage_type(attack.damage)
            adv.attack = attack
        else:
            self._parse_age_style_attack(adv, text)

        # Experience
        exp_match = re.search(
            r'Experience[:\s]+(.+?)(?:FEATURES|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        if exp_match:
            adv.experience = exp_match.group(1).strip()

    @staticmethod
    def _parse_thresholds(adv: Adversary, text: str) -> None:
        """Parse thresholds, keeping the printed form when a side reads "None".

        Minions print "Thresholds: None"; adversaries destroyed outright at
        Major print a half pair such as "5/None". Both are real values, so the
        printed text is retained alongside whichever number is present.
        """
        value = r'\d+|None'
        match = re.search(
            rf'Thresholds?[:\s]+({value})\s*/\s*({value})', text, re.IGNORECASE
        )
        if match:
            minor, major = match.group(1), match.group(2)
            adv.threshold_minor = int(minor) if minor.isdigit() else None
            adv.threshold_major = int(major) if major.isdigit() else None
            if not (minor.isdigit() and major.isdigit()):
                adv.thresholds_raw = f"{minor}/{major}"
            return

        if re.search(r'Thresholds?[:\s]+None\b', text, re.IGNORECASE):
            adv.thresholds_raw = "None"
            return

        legacy = re.search(r'Minor[:\s]+(\d+).*Major[:\s]+(\d+)', text, re.IGNORECASE)
        if legacy:
            adv.threshold_minor = int(legacy.group(1))
            adv.threshold_major = int(legacy.group(2))

    def _parse_age_style_attack(self, adv: Adversary, text: str) -> None:
        """Parse lines like `Long Knife: Melee - 2d6+6 phy` plus a separate ATK line."""
        range_pattern = r'(?:Melee|Very Close|Close|Far|Very Far)'
        weapon_match = re.search(
            rf'^([^:\n]+):\s*({range_pattern})\s*-\s*(.+?)(?:\s+Thresholds?:|\n|$)',
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if not weapon_match:
            return

        modifier = None
        modifier_match = re.search(r'ATK:\s*([+-]?\d+(?:d\d+(?:[+-]\d+)?)?)', text, re.IGNORECASE)
        if modifier_match:
            modifier = modifier_match.group(1).strip()

        damage = weapon_match.group(3).strip()
        if damage.lower().startswith("threshold"):
            damage = ""

        adv.attack = Attack(
            modifier=modifier,
            weapon_name=weapon_match.group(1).strip(),
            range=weapon_match.group(2).strip(),
            damage=TextCleaner.normalize_damage_type(damage) if damage else None,
        )

    def _parse_pdf_motives(self, adv: Adversary, text: str) -> None:
        """Parse motives without swallowing following stat or attack lines."""
        range_pattern = r'(?:Melee|Very Close|Close|Far|Very Far)'
        motives_match = re.search(
            rf'Motives\s*(?:&|and)\s*Tactics[:\s]+(.+?)(?=\n(?:'
            rf'Thresholds?:|[^\n:]+:\s*{range_pattern}\s*-|ATK:|Difficulty:|Experience:|FEATURES'
            rf')|$)',
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if motives_match:
            adv.motives_tactics = re.sub(r'\s*\n\s*', ' ', motives_match.group(1)).strip()

    def _parse_stat_value(self, text: str, label: str) -> Optional[int]:
        """Parse numeric stats or count circle pips like `HP: O O O`."""
        numeric_match = re.search(rf'{label}[:\s]+(\d+)', text, re.IGNORECASE)
        if numeric_match:
            return int(numeric_match.group(1))

        # Some adversaries print "None" for a track they can never mark, e.g.
        # Spellbound Armor's "Stress: None". That is a value of zero, not a
        # missing field, so the block must not be discarded as incomplete.
        if re.search(rf'{label}\s*:\s*None\b', text, re.IGNORECASE):
            return 0

        if label.lower() == "stress":
            after_label_match = re.search(
                r'Stress:\s*((?:[O0]\s*)+)',
                text,
                re.IGNORECASE,
            )
            if after_label_match:
                return self._count_stat_pips(after_label_match.group(1))

            before_label_match = re.search(
                r'Difficulty:\s*\d+\s+((?:[O0](?:\s+|$))+)\s*\nStress:',
                text,
                re.IGNORECASE | re.MULTILINE,
            )
            if before_label_match:
                return self._count_stat_pips(before_label_match.group(1))
        else:
            pip_match = re.search(
                rf'{label}:\s*((?:[O0]\s*)+)',
                text,
                re.IGNORECASE,
            )
            if pip_match:
                return self._count_stat_pips(pip_match.group(1))

        return None

    @staticmethod
    def _count_stat_pips(text: str) -> int:
        """Count HP/Stress circles extracted from PDFs as O or 0 glyphs."""
        return len(re.findall(r'[O0]', text, re.IGNORECASE))

    def _parse_pdf_description(self, adv: Adversary, text: str) -> None:
        """Extract description/flavor text from PDF block."""
        adv.description = self._parse_description(text, adv.name, stop_labels=(
            'Motives', 'Impulses', 'Difficulty', 'Thresholds?', 'ATK', 'FEATURES',
        ))

    def _parse_description(
        self, text: str, name: Optional[str], stop_labels: tuple[str, ...]
    ) -> Optional[str]:
        """Collect the flavor text between the tier line and the first label."""
        lines = text.split('\n')
        in_description = False
        desc_lines = []

        name_parts = set()
        if name:
            name_parts.add(name)
            for part in name.split(': ', 1):
                name_parts.add(part)
                name_parts.add(part + ':')

        stop_re = re.compile(rf'^({"|".join(stop_labels)})\b', re.IGNORECASE)

        for line in lines:
            stripped = line.strip()

            if re.match(r'^[A-Z][A-Z\s,:\'’]+$', stripped):
                continue
            if stripped in name_parts:
                continue
            if re.match(r'^Tier\b', stripped, re.IGNORECASE):
                in_description = True
                continue

            if stop_re.match(stripped):
                break
            if re.match(r'^[^:\n]+:\s*(?:Melee|Very Close|Close|Far|Very Far)\s*-', stripped, re.IGNORECASE):
                break

            if re.match(r'^Description:', stripped, re.IGNORECASE):
                desc_lines.append(re.sub(r'^Description:\s*', '', stripped, flags=re.IGNORECASE))
                in_description = True
                continue

            if in_description and stripped:
                desc_lines.append(stripped)

        return ' '.join(desc_lines) if desc_lines else None

    def _parse_pdf_features(self, text: str) -> list[Feature]:
        """Parse features from PDF text."""
        return [
            Feature(name=name, feature_type=ftype, description=desc)
            for name, ftype, desc, _ in self._iter_features(text)
        ]

    # ------------------------------------------------------------------
    # Environment parsing
    # ------------------------------------------------------------------

    def _parse_environment_block(self, block: _Block) -> Optional[Environment]:
        """Parse a single block into an Environment object."""
        text = block.text
        if not text.strip():
            return None

        env = Environment()
        env.name = self._parse_name(block.lines)
        tier, type_name = self._parse_tier_line(text)
        env.tier = tier if tier is not None else block.section_tier
        env.environment_type = base_type(type_name) or None

        env.description = self._parse_description(text, env.name, stop_labels=(
            'Impulses', 'Motives', 'Difficulty', 'Potential', 'FEATURES',
        ))

        env.impulses = self._parse_labelled_field(text, 'Impulses')
        env.potential_adversaries = self._parse_labelled_field(
            text, 'Potential Adversaries'
        )

        env.difficulty = self._parse_environment_difficulty(text)

        env.features = self._parse_environment_features(block)

        return env

    # Labels that end the preceding field's value. Column extraction does not
    # guarantee one label per line — "Difficulty: 11 Potential Adversaries: ..."
    # can arrive as a single line — so a value must stop at the next label
    # wherever it appears, not merely at a line break.
    _FIELD_LABELS = (
        r'Impulses', r'Motives\s*(?:&|and)\s*Tactics', r'Motives',
        r'Difficulty', r'Thresholds?', r'Potential\s+Adversaries',
        r'ATK', r'Attack', r'Experience',
    )

    @classmethod
    def _field_value(cls, text: str, label: str) -> Optional[str]:
        """Return a `Label: value` field, unwrapped onto one line.

        The value runs until the next known label or the FEATURES section,
        whichever comes first, on the same line or a later one.
        """
        next_label = '|'.join(cls._FIELD_LABELS)
        pattern = re.compile(
            rf'\b{label}\s*:\s*(.+?)'
            rf'(?=\s*(?:{next_label})\s*:|\s*\bFEATURES\b|\Z)',
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            return None
        value = re.sub(r'\s*\n\s*', ' ', match.group(1)).strip()
        return value or None

    @classmethod
    def _parse_environment_difficulty(cls, text: str) -> Optional[Union[int, str]]:
        """Read an environment's Difficulty, which is not always a number.

        The Duel event prints `Difficulty: Special (see "Relative Strength")`,
        so the printed text is preserved when no number is given.
        """
        value = cls._field_value(text, 'Difficulty')
        if value is None:
            return None

        numeric = re.match(r'(\d+)\s*$', value)
        return int(numeric.group(1)) if numeric else value

    @classmethod
    def _parse_labelled_field(cls, text: str, label: str) -> Optional[str]:
        """Read a wrapped `Label: value` field up to the next label or section."""
        return cls._field_value(text, label)

    def _parse_environment_features(self, block: _Block) -> list[EnvironmentFeature]:
        """Parse features, attaching the GM prompts that follow each one.

        Prompts are identified by their italic style where font information is
        available. Otherwise every line is treated as description text.
        """
        body, questions_by_offset = self._split_feature_questions(block)

        features = []
        for name, ftype, desc, offset in self._iter_features(body):
            features.append(EnvironmentFeature(
                name=name,
                feature_type=ftype,
                description=desc,
                questions=questions_by_offset.get(offset, []),
            ))
        return features

    def _split_feature_questions(
        self, block: _Block
    ) -> tuple[str, dict[int, list[str]]]:
        """Separate question lines from feature body text.

        Returns the body text with prompts removed, plus the prompts keyed by
        the index of the feature they followed.
        """
        body_lines: list[str] = []
        questions: dict[int, list[str]] = {}
        pending: list[str] = []
        feature_index = -1
        feature_re = self._feature_heading_re()

        for line in block.lines:
            stripped = line.text.strip()
            if line.style is LineStyle.QUESTION:
                pending.append(stripped)
                continue

            if pending and stripped:
                questions.setdefault(max(feature_index, 0), []).extend(
                    self._join_questions(pending)
                )
                pending = []

            if feature_re.match(stripped):
                feature_index += 1

            body_lines.append(line.text)

        if pending:
            questions.setdefault(max(feature_index, 0), []).extend(
                self._join_questions(pending)
            )

        return '\n'.join(body_lines), questions

    @staticmethod
    def _join_questions(lines: list[str]) -> list[str]:
        """Rejoin wrapped prompt lines and split them into questions."""
        joined = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
        parts = re.findall(r'[^?]+\?', joined)
        if not parts:
            return [joined] if joined else []
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _feature_heading_re() -> re.Pattern:
        """Match a line that opens a feature: `Name - Type: description`.

        Anchored to the start of a line because feature headings always begin
        a paragraph. Matching against the whole block instead lets a name start
        mid-sentence and absorb trailing damage text, turning
        `...1d8+1 phy` + `Double Swipe - Action:` into a feature named
        "phy Double Swipe". The permissive name class accepts the typographic
        apostrophes and hyphens real names use ("Into the Spider's Web").
        """
        # The name is anchored by the " - <Type>:" separator rather than by
        # banning colons, so names that legitimately contain one ("Phase 1:
        # The Trap") still match. Excluding colons dropped such features
        # entirely, and with them any block whose only features were named
        # that way.
        return re.compile(
            r'^(?P<name>.{1,70}?)\s+[-–—]\s+'
            r'(?P<type>Passive|Action|Reaction|Evolution)\s*:\s*'
            r'(?P<rest>.*)$',
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    # Feature parsing shared by both record kinds
    # ------------------------------------------------------------------

    def _iter_features(self, text: str):
        """Yield (name, type, description, index) for each feature in a block.

        Walks lines from the FEATURES header, opening a new feature on each
        heading line and folding every following line into its description.
        """
        lines = text.split('\n')

        start = next(
            (i for i, line in enumerate(lines) if line.strip().upper().startswith('FEATURES')),
            None,
        )
        if start is None:
            return

        heading_re = self._feature_heading_re()
        current: Optional[list] = None
        index = 0

        for line in lines[start:]:
            stripped = re.sub(r'^FEATURES\s*', '', line.strip(), flags=re.IGNORECASE)

            match = heading_re.match(stripped)
            if match:
                if current:
                    yield self._finish_feature(current, index)
                    index += 1
                current = [
                    match.group('name').strip(),
                    match.group('type').strip().capitalize(),
                    [match.group('rest').strip()],
                ]
            elif current is not None and stripped:
                current[2].append(stripped)

        if current:
            yield self._finish_feature(current, index)

    @staticmethod
    def _finish_feature(current: list, index: int) -> tuple[str, str, str, int]:
        name, ftype, desc_parts = current
        description = re.sub(r'\s+', ' ', ' '.join(desc_parts)).strip()
        return name, ftype, description, index

    def _is_valid_environment(self, env: Optional[Environment]) -> bool:
        """Return True when a parsed block has the minimum environment shape."""
        if env is None:
            return False
        if not env.name or len(env.name) > 120:
            return False
        return all([
            env.tier is not None,
            env.environment_type,
            env.difficulty is not None,
            bool(env.features),
        ])
