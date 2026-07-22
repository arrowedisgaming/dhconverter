"""Environment dataclass for Daggerheart environment stat blocks.

Environments share a stat-block silhouette with adversaries but carry a
different field set: they have Impulses rather than Motives & Tactics, a
Potential Adversaries roster, no HP/Stress/attack, and their features end in
italic GM question prompts.
"""
from dataclasses import dataclass, field
from typing import Optional, Union
import re
import sys
from pathlib import Path

try:
    from .naming import safe_filename
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.naming import safe_filename


# Type keywords that only ever appear on an environment's tier line.
ENVIRONMENT_ONLY_TYPES = ("Traversal", "Event", "Exploration")

# "Social" is printed on both adversary and environment tier lines — Hope &
# Fear alone has 4 Social adversaries and 6 Social environments — so the
# keyword cannot route a block on its own. Callers must disambiguate using the
# enclosing "TIER n ADVERSARIES" / "TIER n ENVIRONMENTS" section header, or
# failing that the block's field shape.
AMBIGUOUS_TYPES = ("Social",)

ENVIRONMENT_TYPES = ENVIRONMENT_ONLY_TYPES + AMBIGUOUS_TYPES


def base_type(type_name: Optional[str]) -> str:
    """Strip parentheticals such as 'Horde (10/HP)' from a type keyword."""
    if not type_name:
        return ""
    return type_name.split("(")[0].strip()


def is_environment_only_type(type_name: Optional[str]) -> bool:
    """True when the keyword can only belong to an environment."""
    return base_type(type_name).lower() in {t.lower() for t in ENVIRONMENT_ONLY_TYPES}


def is_ambiguous_type(type_name: Optional[str]) -> bool:
    """True when the keyword is shared by adversaries and environments."""
    return base_type(type_name).lower() in {t.lower() for t in AMBIGUOUS_TYPES}


@dataclass
class EnvironmentFeature:
    """An environment feature, with the GM prompts that follow it."""

    name: str
    feature_type: str  # "Passive", "Action", "Reaction"
    description: str
    questions: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert to standardized markdown format."""
        lines = [f"***{self.name} - {self.feature_type}:*** {self.description}"]
        lines.extend(f"*{question}*" for question in self.questions)
        return "\n".join(lines)


@dataclass
class Environment:
    """Represents a Daggerheart environment stat block."""

    name: str = ""

    tier: Optional[int] = None
    environment_type: Optional[str] = None  # e.g., "Traversal", "Event"

    description: Optional[str] = None
    impulses: Optional[str] = None
    difficulty: Optional[Union[int, str]] = None
    potential_adversaries: Optional[str] = None

    features: list[EnvironmentFeature] = field(default_factory=list)

    # Metadata for tracking issues
    source_file: Optional[str] = None
    parse_warnings: list[str] = field(default_factory=list)

    # Source attribution
    source_name: Optional[str] = None
    source_page: Optional[int] = None

    @property
    def tier_line(self) -> str:
        """Return tier/type line like 'Tier 2 Traversal'."""
        parts = []
        if self.tier is not None:
            parts.append(f"Tier {self.tier}")
        if self.environment_type:
            parts.append(self.environment_type)
        return " ".join(parts)

    def validate(self) -> list[str]:
        """Return list of validation issues/warnings."""
        issues = []

        if not self.name:
            issues.append("Missing name")
        if self.tier is None:
            issues.append("Missing tier")
        if not self.environment_type:
            issues.append("Missing environment type")
        if self.difficulty is None:
            issues.append("Missing Difficulty")
        if not self.impulses:
            issues.append("Missing Impulses")
        if not self.features:
            issues.append("No features found")

        return issues

    def has_complete_stats(self) -> bool:
        """Check if all core fields are present."""
        return all([
            self.name,
            self.tier is not None,
            self.environment_type,
            self.difficulty is not None,
            bool(self.impulses),
        ])

    def safe_filename(self) -> str:
        """Generate a safe filename stem from the environment name."""
        return safe_filename(self.name)
