"""Markdown parser for Daggerheart adversary files.

Handles two formats:
1. Single-adversary format (standardized _SAMPLE.md style)
2. Multi-adversary format (Menagerie style with ## headers)
"""
import re
import sys
from pathlib import Path
from typing import Optional

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary, Attack, Feature
    from .text_cleaner import TextCleaner
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Attack, Feature
    from parsers.text_cleaner import TextCleaner


class MDParser:
    """Parser for Daggerheart adversary markdown files."""

    @classmethod
    def parse_file(cls, file_path: Path) -> list[Adversary]:
        """Parse a markdown file and return list of adversaries."""
        text = file_path.read_text(encoding='utf-8')
        text = TextCleaner.clean_text(text)

        # Detect format
        if cls._is_multi_adversary_format(text):
            adversaries = cls._parse_multi_adversary(text)
        else:
            adv = cls._parse_single_adversary(text)
            adversaries = [adv] if adv else []

        # Set source file for all
        for adv in adversaries:
            adv.source_file = str(file_path)

        return adversaries

    @classmethod
    def _is_multi_adversary_format(cls, text: str) -> bool:
        """Detect if text contains multiple adversaries (Menagerie format)."""
        # Count ## headers that look like adversary names
        header_matches = re.findall(r'^##\s+[A-Z][A-Z\s:\-\']+$', text, re.MULTILINE)
        return len(header_matches) > 1

    @classmethod
    def _parse_single_adversary(cls, text: str) -> Optional[Adversary]:
        """Parse single-adversary markdown format."""
        adv = Adversary()

        # Name from # header
        name_match = re.search(r'^#\s+(.+?)$', text, re.MULTILINE)
        if name_match:
            adv.name = name_match.group(1).strip()

        # Tier line: ***Tier X Type*** or variations
        tier_patterns = [
            r'\*{3}(Tier\s+\d+\s+\w+)\*{3}',  # ***Tier 2 Ranged***
            r'\*{2}(Tier\s+\d+\s+\w+)\*{2}',  # **Tier 2 Ranged**
            r'\*(Tier\s+\d+\s+\w+)\*',         # *Tier 2 Ranged*
        ]
        for pattern in tier_patterns:
            match = re.search(pattern, text)
            if match:
                cls._parse_tier_line(adv, match.group(1))
                break

        # Description: *italic text* after tier line but before Motives
        desc_match = re.search(
            r'\*{3}Tier[^*]+\*{3}\s*\n\*([^*]+)\*\s*\n',
            text
        )
        if not desc_match:
            desc_match = re.search(
                r'\*(Tier[^*]+)\*\s*\n\*([^*]+)\*\s*\n',
                text
            )
            if desc_match:
                adv.description = desc_match.group(2).strip()
        elif desc_match:
            adv.description = desc_match.group(1).strip()

        # Motives & Tactics
        motives_match = re.search(
            r'\*{2}Motives\s*(?:&|and)\s*Tactics:\*{2}\s*(.+?)(?:\n\n|\n>|\n##)',
            text, re.DOTALL
        )
        if motives_match:
            adv.motives_tactics = motives_match.group(1).strip()

        # Stats from blockquote format: > **Difficulty:** X | **Thresholds:** Y/Z ...
        cls._parse_blockquote_stats(adv, text)

        # Features
        adv.features = cls._parse_features(text)

        # Source attribution
        cls._parse_source_line(adv, text)

        return adv

    @classmethod
    def _parse_multi_adversary(cls, text: str) -> list[Adversary]:
        """Parse multi-adversary markdown (Menagerie format)."""
        adversaries = []

        # Split on ## headers
        sections = re.split(r'^##\s+', text, flags=re.MULTILINE)

        for section in sections[1:]:  # Skip text before first ##
            if not section.strip():
                continue

            adv = cls._parse_menagerie_section(section)
            if adv and adv.name:
                adversaries.append(adv)

        return adversaries

    @classmethod
    def _parse_menagerie_section(cls, section: str) -> Optional[Adversary]:
        """Parse a single adversary section from Menagerie format."""
        adv = Adversary()
        lines = section.split('\n')

        if not lines:
            return None

        # First line is the name
        adv.name = lines[0].strip()

        # Tier line: *Tier X Type*
        tier_match = re.search(r'^\*([^*]+)\*\s*$', section, re.MULTILINE)
        if tier_match:
            cls._parse_tier_line(adv, tier_match.group(1))

        # Description: paragraph after tier line, before stats
        # In Menagerie format, it's plain text after *Tier* line
        desc_match = re.search(
            r'^\*Tier[^*]+\*\s*\n\n(.+?)\n\n\*\*Motives',
            section, re.MULTILINE | re.DOTALL
        )
        if desc_match:
            adv.description = desc_match.group(1).strip()

        # Motives & Tactics
        motives_match = re.search(
            r'\*\*Motives\s*(?:&|and)\s*Tactics:\*\*\s*(.+?)(?:\n\n|\n\*\*Difficulty)',
            section, re.DOTALL
        )
        if motives_match:
            adv.motives_tactics = motives_match.group(1).strip()

        # Stats: **Difficulty: X | Thresholds: Y/Z | HP: A | Stress: B**
        cls._parse_menagerie_stats(adv, section)

        # Features
        adv.features = cls._parse_menagerie_features(section)

        return adv

    @classmethod
    def _parse_tier_line(cls, adv: Adversary, tier_text: str) -> None:
        """Parse tier and type from 'Tier 2 Ranged' format."""
        tier_match = re.search(r'Tier\s+(\d+)', tier_text, re.IGNORECASE)
        if tier_match:
            adv.tier = int(tier_match.group(1))

        # Type is everything after 'Tier N '
        type_match = re.search(r'Tier\s+\d+\s+(.+)', tier_text, re.IGNORECASE)
        if type_match:
            adv.adversary_type = type_match.group(1).strip()

    @classmethod
    def _parse_blockquote_stats(cls, adv: Adversary, text: str) -> None:
        """Parse stats from blockquote format."""
        # Find blockquote lines starting with >
        blockquote_lines = re.findall(r'^>\s*(.+)$', text, re.MULTILINE)
        if not blockquote_lines:
            return

        # Process each blockquote line separately to avoid cross-contamination
        for line in blockquote_lines:
            line = line.strip()

            # Check for stats line (has Difficulty, Thresholds, HP, Stress)
            if '**Difficulty:**' in line or '**HP:**' in line:
                # Difficulty
                diff_match = re.search(r'\*{2}Difficulty:\*{2}\s*(\d+)?', line)
                if diff_match and diff_match.group(1):
                    adv.difficulty = int(diff_match.group(1))

                # Thresholds
                thresh_match = re.search(r'\*{2}Thresholds:\*{2}\s*(\d+/\d+)?', line)
                if thresh_match and thresh_match.group(1):
                    adv.threshold_minor, adv.threshold_major = TextCleaner.extract_thresholds(
                        thresh_match.group(1)
                    )

                # HP
                hp_match = re.search(r'\*{2}HP:\*{2}\s*(\d+)?', line)
                if hp_match and hp_match.group(1):
                    adv.hp = int(hp_match.group(1))

                # Stress
                stress_match = re.search(r'\*{2}Stress:\*{2}\s*(\d+)?', line)
                if stress_match and stress_match.group(1):
                    adv.stress = int(stress_match.group(1))

            # Check for ATK line
            elif '**ATK:**' in line:
                # Extract everything after **ATK:**
                atk_match = re.search(r'\*{2}ATK:\*{2}\s*(.+)', line)
                if atk_match:
                    adv.attack = Attack.from_string(atk_match.group(1).strip())

            # Check for Experience line
            elif '**Experience:**' in line:
                exp_match = re.search(r'\*{2}Experience:\*{2}\s*(.+)', line)
                if exp_match:
                    adv.experience = exp_match.group(1).strip()

    @classmethod
    def _parse_menagerie_stats(cls, adv: Adversary, text: str) -> None:
        """Parse stats from Menagerie format: **Stat: Value | Stat: Value**"""
        # Stats line format: **Difficulty: X | Thresholds: Y/Z | HP: A | Stress: B**
        stats_match = re.search(
            r'\*\*Difficulty:\s*(\d+)\s*\|\s*Thresholds:\s*(\d+/\d+)\s*\|\s*HP:\s*(\d+)\s*\|\s*Stress:\s*(\d+)\*\*',
            text
        )
        if stats_match:
            adv.difficulty = int(stats_match.group(1))
            adv.threshold_minor, adv.threshold_major = TextCleaner.extract_thresholds(
                stats_match.group(2)
            )
            adv.hp = int(stats_match.group(3))
            adv.stress = int(stats_match.group(4))

        # ATK line: **ATK: +X | Weapon: Range | Damage**
        atk_match = re.search(
            r'\*\*ATK:\s*([^*]+)\*\*',
            text
        )
        if atk_match:
            adv.attack = Attack.from_string(atk_match.group(1))

        # Experience: **Experience:** Value
        exp_match = re.search(
            r'\*\*Experience:\*\*\s*(.+?)(?:\n|$)',
            text
        )
        if exp_match:
            adv.experience = exp_match.group(1).strip()

    @classmethod
    def _parse_features(cls, text: str) -> list[Feature]:
        """Parse features from standardized format."""
        features = []

        # Find FEATURES section
        features_match = re.search(r'##\s*FEATURES\s*\n(.+)', text, re.DOTALL | re.IGNORECASE)
        if not features_match:
            return features

        features_text = features_match.group(1)

        # Split on ***Name - Type:*** pattern
        feature_blocks = re.split(r'(?=\*{3}[^*]+\s*-\s*[^*:]+:\*{3})', features_text)

        for block in feature_blocks:
            block = block.strip()
            if not block:
                continue

            feature = Feature.from_string(block)
            if feature:
                features.append(feature)

        return features

    @classmethod
    def _parse_menagerie_features(cls, text: str) -> list[Feature]:
        """Parse features from Menagerie format."""
        features = []

        # Find FEATURES section (***FEATURES*** in Menagerie)
        features_match = re.search(
            r'\*{3}FEATURES\*{3}\s*\n(.+?)(?=\n---|\Z)',
            text, re.DOTALL | re.IGNORECASE
        )
        if not features_match:
            return features

        features_text = features_match.group(1)

        # Menagerie uses *Name - Type*: Description format
        feature_pattern = r'\*([^*]+?)\s*-\s*([^*]+?)\*:\s*(.+?)(?=\n\*[^*]|\Z)'
        matches = re.findall(feature_pattern, features_text, re.DOTALL)

        for name, ftype, desc in matches:
            features.append(Feature(
                name=name.strip(),
                feature_type=ftype.strip(),
                description=desc.strip()
            ))

        return features

    @classmethod
    def _parse_source_line(cls, adv: Adversary, text: str) -> None:
        """Parse source attribution from text.

        Expected format: *Source: Name, p. X* or *Source: Name*
        """
        # Pattern matches: *Source: Name* or *Source: Name, p. 12*
        source_match = re.search(
            r'\*Source:\s*([^,*]+?)(?:,\s*p\.\s*(\d+))?\*',
            text
        )
        if source_match:
            adv.source_name = source_match.group(1).strip()
            if source_match.group(2):
                adv.source_page = int(source_match.group(2))
