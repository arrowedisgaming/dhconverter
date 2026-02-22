"""Adversary dataclass for Daggerheart adversary data."""
from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class Attack:
    """Represents an adversary's attack information."""
    modifier: Optional[str] = None  # e.g., "+4"
    weapon_name: Optional[str] = None  # e.g., "Staff"
    range: Optional[str] = None  # e.g., "Far"
    damage: Optional[str] = None  # e.g., "2d10+4 mag"

    @classmethod
    def from_string(cls, text: str) -> "Attack":
        """Parse attack string like '+4 | Staff: Far | 2d10+4 mag'."""
        if not text or not text.strip():
            return cls()

        # Strip markdown bold markers from the entire text first
        text = re.sub(r'\*{2}', '', text)

        parts = [p.strip() for p in text.split("|")]
        attack = cls()

        for part in parts:
            # Check for modifier (starts with + or -)
            if re.match(r'^[+-]\d+$', part):
                attack.modifier = part
            # Check for weapon: range pattern (colon separator)
            elif ":" in part:
                weapon_range = part.split(":", 1)
                attack.weapon_name = weapon_range[0].strip()
                attack.range = weapon_range[1].strip() if len(weapon_range) > 1 else None
            # Check for weapon - range pattern (hyphen separator, e.g. "Staff - Far")
            elif " - " in part and not re.search(r'\d+d\d+', part) and not re.match(r'^[+-]\d+$', part):
                weapon_range = part.split(" - ", 1)
                attack.weapon_name = weapon_range[0].strip()
                attack.range = weapon_range[1].strip() if len(weapon_range) > 1 else None
            # Check for damage dice pattern
            elif re.search(r'\d+d\d+', part):
                attack.damage = part
            # If it's just a word and we don't have weapon yet, treat as weapon
            elif not attack.weapon_name and part:
                attack.weapon_name = part
            # Fallback: capture remaining unclassified parts as damage (e.g. "1 Stress")
            elif not attack.damage:
                attack.damage = part

        return attack

    def to_string(self) -> str:
        """Convert back to formatted string.

        Format: +4 | **Staff:** Far | 2d10+4 mag
        """
        parts = []
        if self.modifier:
            parts.append(self.modifier)
        if self.weapon_name:
            if self.range:
                parts.append(f"**{self.weapon_name}:** {self.range}")
            else:
                parts.append(f"**{self.weapon_name}**")
        if self.damage:
            parts.append(self.damage)
        return " | ".join(parts) if parts else ""

    def is_empty(self) -> bool:
        """Check if attack has no meaningful data."""
        return not any([self.modifier, self.weapon_name, self.range, self.damage])


@dataclass
class Feature:
    """Represents an adversary feature/ability."""
    name: str
    feature_type: str  # e.g., "Passive", "Action", "Reaction"
    description: str

    @classmethod
    def from_string(cls, text: str) -> Optional["Feature"]:
        """Parse feature from markdown text.

        Expected formats:
        - ***Name - Type:*** Description
        - *Name - Type*: Description
        - **Name - Type:** Description
        """
        if not text or not text.strip():
            return None

        # Pattern for ***Name - Type:*** or variations
        patterns = [
            r'\*{3}([^*]+?)\s*[-–—]\s*([^*:]+?):\*{3}\s*(.*)',  # ***Name - Type:*** Desc
            r'\*{2}([^*]+?)\s*[-–—]\s*([^*:]+?):\*{2}\s*(.*)',  # **Name - Type:** Desc
            r'\*([^*]+?)\s*[-–—]\s*([^*:]+?)\*:\s*(.*)',        # *Name - Type*: Desc
        ]

        for pattern in patterns:
            match = re.match(pattern, text.strip(), re.DOTALL)
            if match:
                return cls(
                    name=match.group(1).strip(),
                    feature_type=match.group(2).strip(),
                    description=match.group(3).strip()
                )

        return None

    def to_markdown(self) -> str:
        """Convert to standardized markdown format."""
        return f"***{self.name} - {self.feature_type}:*** {self.description}"


@dataclass
class Adversary:
    """Represents a Daggerheart adversary with all stat block information."""

    # Required fields
    name: str = ""

    # Tier/Type info
    tier: Optional[int] = None
    adversary_type: Optional[str] = None  # e.g., "Ranged", "Bruiser", "Solo"

    # Flavor text
    description: Optional[str] = None
    motives_tactics: Optional[str] = None

    # Core stats
    difficulty: Optional[int] = None
    threshold_minor: Optional[int] = None
    threshold_major: Optional[int] = None
    hp: Optional[int] = None
    stress: Optional[int] = None

    # Combat info
    attack: Optional[Attack] = None
    experience: Optional[str] = None

    # Features
    features: list[Feature] = field(default_factory=list)

    # Metadata for tracking issues
    source_file: Optional[str] = None
    parse_warnings: list[str] = field(default_factory=list)

    # Source attribution
    source_name: Optional[str] = None  # e.g., "Age of Umbra Adversaries"
    source_page: Optional[int] = None  # e.g., 12

    @property
    def thresholds_str(self) -> str:
        """Return thresholds as 'minor/major' string."""
        if self.threshold_minor is not None and self.threshold_major is not None:
            return f"{self.threshold_minor}/{self.threshold_major}"
        elif self.threshold_minor is not None:
            return f"{self.threshold_minor}/"
        elif self.threshold_major is not None:
            return f"/{self.threshold_major}"
        return ""

    @property
    def tier_line(self) -> str:
        """Return tier/type line like 'Tier 2 Ranged'."""
        parts = []
        if self.tier is not None:
            parts.append(f"Tier {self.tier}")
        if self.adversary_type:
            parts.append(self.adversary_type)
        return " ".join(parts)

    def validate(self) -> list[str]:
        """Return list of validation issues/warnings."""
        issues = []

        if not self.name:
            issues.append("Missing name")
        if self.tier is None:
            issues.append("Missing tier")
        if not self.adversary_type:
            issues.append("Missing adversary type")
        if self.difficulty is None:
            issues.append("Missing Difficulty")
        if self.threshold_minor is None and self.threshold_major is None:
            issues.append("Missing Thresholds")
        if self.hp is None:
            issues.append("Missing HP")
        if self.stress is None:
            issues.append("Missing Stress")
        if not self.features:
            issues.append("No features found")

        return issues

    def has_complete_stats(self) -> bool:
        """Check if all core stats are present."""
        return all([
            self.name,
            self.tier is not None,
            self.adversary_type,
            self.difficulty is not None,
            self.threshold_minor is not None,
            self.threshold_major is not None,
            self.hp is not None,
            self.stress is not None
        ])

    def safe_filename(self) -> str:
        """Generate a safe filename from the adversary name."""
        if not self.name:
            return "unknown"
        # Remove special characters, keep spaces (will become spaces in filename)
        safe = re.sub(r'[^\w\s-]', '', self.name)
        # Collapse multiple spaces
        safe = re.sub(r'\s+', ' ', safe).strip()
        return safe
