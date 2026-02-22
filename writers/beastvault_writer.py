"""BeastVault JSON writer for Daggerheart adversary data.

Produces a JSON array compatible with the BeastVault Obsidian plugin's
library format. Each adversary becomes a dict with fields matching
BeastVault conventions:
- Adversaries: name, tier, type, desc, difficulty, motives, hp, stress,
  attack, weapon, range, damage, thresholds, xp, source, features
- Environments: name, tier, type, desc, difficulty, impulses, source, features
  (combat fields omitted)
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary, Feature
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature


# Maps source display names to BeastVault slug tags
SOURCE_TAG_MAP = {
    'Age of Umbra Adversaries': 'age-of-umbra',
    'Martial Adversaries': 'martial',
    'Undead Adversaries': 'undead',
    'Adversaries: Environments v1.5': 'environments',
    'Menagerie of Mayhem': 'menagerie',
    'Daggerheart System Reference Document': 'corebook',
}


class BeastvaultWriter:
    """Writer for BeastVault-compatible JSON adversary format."""

    @classmethod
    def write_adversaries(
        cls,
        adversaries: list[Adversary],
        output_path: Path,
        source_tag: Optional[str] = None,
    ) -> int:
        """Write adversaries as a BeastVault JSON array file.

        Returns the number of entries written.
        """
        entries = [cls.format_adversary(adv, source_tag) for adv in adversaries]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return len(entries)

    @classmethod
    def format_adversary(
        cls, adv: Adversary, source_tag: Optional[str] = None
    ) -> dict:
        """Format a single adversary as a BeastVault-compatible dict.

        Only emits fields that have values (sparse format), except xp which
        is emitted as "" for adversaries without experience data.
        """
        entry: dict = {}
        is_env = cls._is_environment(adv)

        # Core identity fields
        if adv.name:
            entry["name"] = adv.name.upper()
        if adv.tier is not None:
            entry["tier"] = adv.tier
        if adv.adversary_type:
            entry["type"] = adv.adversary_type
        if adv.description:
            entry["desc"] = adv.description
        if adv.difficulty is not None:
            entry["difficulty"] = adv.difficulty

        # Motives vs impulses
        if adv.motives_tactics:
            if is_env:
                entry["impulses"] = adv.motives_tactics
            else:
                entry["motives"] = adv.motives_tactics

        # Combat fields — only for non-environments
        if not is_env:
            if adv.hp is not None:
                entry["hp"] = adv.hp
            if adv.stress is not None:
                entry["stress"] = adv.stress

            if adv.attack and not adv.attack.is_empty():
                modifier = cls._parse_attack_modifier(adv.attack.modifier)
                if modifier is not None:
                    entry["attack"] = modifier
                if adv.attack.weapon_name:
                    entry["weapon"] = adv.attack.weapon_name
                if adv.attack.range:
                    entry["range"] = adv.attack.range
                if adv.attack.damage:
                    entry["damage"] = adv.attack.damage

            thresholds = cls._format_thresholds(adv)
            if thresholds:
                entry["thresholds"] = thresholds

            # xp: emit "" for adversaries without experience (BV convention)
            entry["xp"] = adv.experience if adv.experience else ""

        # Source tag
        tag = source_tag or cls._resolve_source_tag(adv)
        if tag:
            entry["source"] = tag

        # Features
        if adv.features:
            entry["features"] = [cls._format_feature(f) for f in adv.features]

        return entry

    @classmethod
    def _is_environment(cls, adv: Adversary) -> bool:
        """Detect environment stat blocks (no HP and no Stress)."""
        return adv.hp is None and adv.stress is None

    @classmethod
    def _parse_attack_modifier(cls, modifier: Optional[str]) -> Optional[int]:
        """Convert modifier string like '+3' or '-1' to int."""
        if modifier is None:
            return None
        try:
            return int(modifier)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _format_thresholds(cls, adv: Adversary) -> str:
        """Format thresholds as 'minor/major' string."""
        return adv.thresholds_str

    @classmethod
    def _format_feature(cls, feature: Feature) -> dict:
        """Format a single feature as a BeastVault dict."""
        entry: dict = {}
        if feature.name:
            entry["name"] = feature.name
        if feature.feature_type:
            entry["type"] = feature.feature_type
        if feature.description:
            entry["desc"] = feature.description
        return entry

    @classmethod
    def _resolve_source_tag(cls, adv: Adversary) -> str:
        """Resolve source display name to a BeastVault slug tag."""
        if not adv.source_name:
            return "homebrew"

        # Direct lookup
        tag = SOURCE_TAG_MAP.get(adv.source_name)
        if tag:
            return tag

        # Fallback: slugify the display name
        slug = adv.source_name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug
