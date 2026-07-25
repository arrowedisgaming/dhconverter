"""Obsidian properties (YAML frontmatter) blocks for exported records.

Obsidian Bases filters on note properties, not code blocks, so each exported
file can optionally start with a frontmatter block of the record's filterable
stats. The source field deliberately omits the page number: with pages
included, one book shows up in a Base as dozens of distinct sources.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from ..models.adversary import Adversary
    from ..models.environment import Environment
    from .yaml_format import display_name, format_attack, set_field, yaml_lines
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary
    from models.environment import Environment
    from writers.yaml_format import display_name, format_attack, set_field, yaml_lines


def adversary_frontmatter(adv: Adversary) -> str:
    data: dict[str, Any] = {}
    set_field(data, "name", display_name(adv.name) if adv.name else None)
    set_field(data, "tier", adv.tier)
    set_field(data, "type", adv.adversary_type)
    set_field(data, "difficulty", adv.difficulty)
    set_field(data, "hp", adv.hp)
    set_field(data, "stress", adv.stress)

    if adv.attack and not adv.attack.is_empty():
        set_field(data, "attack", format_attack(adv.attack.modifier))
        set_field(data, "weapon", adv.attack.weapon_name)
        set_field(data, "range", adv.attack.range)
        set_field(data, "damage", adv.attack.damage)

    set_field(data, "motives", adv.motives_tactics)
    set_field(data, "desc", adv.description)
    set_field(data, "source", adv.source_name)
    data["feature_count"] = len(adv.features)
    return _fenced(data)


def environment_frontmatter(env: Environment) -> str:
    data: dict[str, Any] = {}
    set_field(data, "name", display_name(env.name) if env.name else None)
    set_field(data, "tier", env.tier)
    set_field(data, "type", env.environment_type)
    set_field(data, "difficulty", env.difficulty)
    set_field(data, "impulses", env.impulses)
    set_field(data, "potential_adversaries", env.potential_adversaries)
    set_field(data, "desc", env.description)
    set_field(data, "source", env.source_name)
    data["feature_count"] = len(env.features)
    return _fenced(data)


def _fenced(data: dict[str, Any]) -> str:
    return "\n".join(["---", *yaml_lines(data), "---", ""])
