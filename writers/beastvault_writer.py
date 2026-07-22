"""Arrow's Adversary Bank JSON writer for Daggerheart adversary data.

Produces a JSON array compatible with Arrow's Adversary Bank and the older
BeastVault Obsidian plugin library format. Each adversary becomes a dict with
fields matching the plugin conventions:
- Adversaries: name, tier, type, desc, difficulty, motives, hp, stress,
  attack, weapon, range, damage, thresholds, xp, source, features
- Environments: name, tier, type, desc, difficulty, impulses, source, features
  (combat fields omitted)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary, Feature
    from ..models.environment import Environment, EnvironmentFeature
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature
    from models.environment import Environment, EnvironmentFeature


# Maps source display names to Arrow's Adversary Bank source tags
SOURCE_TAG_MAP = {
    'Age of Umbra Adversaries': 'age-of-umbra',
    'Martial Adversaries': 'martial',
    'Undead Adversaries': 'undead',
    'Adversaries: Environments v1.5': 'environments',
    'Menagerie of Mayhem': 'menagerie',
    'Daggerheart System Reference Document': 'corebook',
    'Hope and Fear': 'hope-and-fear',
}


class BeastvaultWriter:
    """Writer for Arrow's Adversary Bank-compatible JSON adversary format."""

    @classmethod
    def write_adversaries(
        cls,
        adversaries: list[Adversary],
        output_path: Path,
        source_tag: Optional[str] = None,
        environments: Optional[list[Environment]] = None,
    ) -> int:
        """Write adversaries as an Arrow's Adversary Bank JSON array file.

        Environments, when given, are appended to the same array.

        Returns the number of entries written.
        """
        entries = [cls.format_adversary(adv, source_tag) for adv in adversaries]
        entries.extend(
            cls.format_environment(env, source_tag) for env in (environments or [])
        )
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
        """Format a single adversary as an Arrow's Adversary Bank-compatible dict.

        Only emits fields that have values (sparse format), except xp which
        is emitted as "" for adversaries without experience data.
        """
        entry: dict = {}

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

        if adv.motives_tactics:
            entry["motives"] = adv.motives_tactics

        if adv.hp is not None:
            entry["hp"] = adv.hp
        if adv.stress is not None:
            entry["stress"] = adv.stress

        if adv.attack and not adv.attack.is_empty():
            modifier = cls._format_attack_modifier(adv.attack.modifier)
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

        # xp: emit "" for adversaries without experience, matching the
        # existing built-in library data shape.
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
    def format_environment(
        cls, env: Environment, source_tag: Optional[str] = None
    ) -> dict:
        """Format an environment as an Arrow's Adversary Bank-compatible dict.

        Combat fields are absent by construction rather than by inference.
        """
        entry: dict = {}

        if env.name:
            entry["name"] = env.name.upper()
        if env.tier is not None:
            entry["tier"] = env.tier
        if env.environment_type:
            entry["type"] = env.environment_type
        if env.description:
            entry["desc"] = env.description
        if env.difficulty is not None:
            entry["difficulty"] = env.difficulty
        if env.impulses:
            entry["impulses"] = env.impulses
        if env.potential_adversaries:
            entry["potential_adversaries"] = env.potential_adversaries

        tag = source_tag or cls._resolve_source_tag(env)
        if tag:
            entry["source"] = tag

        if env.features:
            entry["features"] = [
                cls._format_environment_feature(f) for f in env.features
            ]

        return entry

    @classmethod
    def _format_environment_feature(cls, feature: EnvironmentFeature) -> dict:
        """Format an environment feature, including its GM prompts."""
        entry: dict = {}
        if feature.name:
            entry["name"] = feature.name
        if feature.feature_type:
            entry["type"] = feature.feature_type
        if feature.description:
            entry["desc"] = feature.description
        if feature.questions:
            entry["questions"] = list(feature.questions)
        return entry

    @classmethod
    def _format_attack_modifier(cls, modifier: Optional[str]) -> Optional[int | str]:
        """Convert plain numeric modifiers to int; preserve variable modifiers."""
        if modifier is None:
            return None
        try:
            return int(modifier)
        except (ValueError, TypeError):
            return modifier

    @classmethod
    def _format_thresholds(cls, adv: Adversary) -> str:
        """Format thresholds as 'minor/major' string."""
        return adv.thresholds_str

    @classmethod
    def _format_feature(cls, feature: Feature) -> dict:
        """Format a single feature as an Arrow's Adversary Bank dict."""
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
        """Resolve source display name to an Arrow's Adversary Bank source tag."""
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
