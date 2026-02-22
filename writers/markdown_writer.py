"""Markdown writer for standardized adversary output format.

Produces output matching _SAMPLE.md format exactly:
- Title: # NAME (uppercase)
- Tier line: ***Tier X Type*** with trailing spaces
- Description: *italic* with trailing spaces (optional)
- Motives: **Motives & Tactics:** value
- Stats: Blockquote with pipe separators and trailing spaces
- ATK line: Only if attack data exists
- Experience line: Only if experience exists
- Features: ***Name - Type:*** Description
"""
import sys
from pathlib import Path
from typing import Optional

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary, Feature
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature


class MarkdownWriter:
    """Writer for standardized Daggerheart adversary markdown format."""

    # Two trailing spaces for markdown line break
    LINE_BREAK = "  \n"
    NEWLINE = "\n"

    @classmethod
    def write_adversary(cls, adversary: Adversary, output_path: Path) -> None:
        """Write adversary to markdown file."""
        content = cls.format_adversary(adversary)
        output_path.write_text(content, encoding='utf-8')

    @classmethod
    def format_adversary(cls, adv: Adversary) -> str:
        """Format adversary as standardized markdown string."""
        lines = []

        # Title (uppercase)
        name = adv.name.upper() if adv.name else "UNKNOWN"
        lines.append(f"# {name}")
        lines.append("")

        # Tier line with trailing spaces for line break
        tier_line = cls._format_tier_line(adv)
        if tier_line:
            lines.append(f"***{tier_line}***  ")  # Two trailing spaces

        # Description (italic) with trailing spaces - only if present
        if adv.description:
            # Handle multi-line descriptions
            desc = adv.description.strip()
            lines.append(f"*{desc}*  ")  # Two trailing spaces

        # Motives & Tactics
        if adv.motives_tactics:
            lines.append(f"**Motives & Tactics:** {adv.motives_tactics}")

        lines.append("")

        # Stats block (blockquote)
        stats_line = cls._format_stats_line(adv)
        lines.append(f"> {stats_line}  ")  # Two trailing spaces

        # ATK line - only if attack data exists
        if adv.attack and not adv.attack.is_empty():
            atk_str = adv.attack.to_string()
            lines.append(f"> **ATK:** {atk_str}  ")  # Two trailing spaces

        # Experience line - only if present
        if adv.experience:
            lines.append(f"> **Experience:** {adv.experience}")

        lines.append("")

        # Features section
        if adv.features:
            lines.append("## FEATURES")
            lines.append("")

            for feature in adv.features:
                lines.append(feature.to_markdown())
                lines.append("")

        # Source attribution (if available)
        source_line = cls._format_source_line(adv)
        if source_line:
            lines.append("---")
            lines.append("")
            lines.append(source_line)
            lines.append("")

        # Ensure file ends with newline
        return "\n".join(lines)

    @classmethod
    def _format_tier_line(cls, adv: Adversary) -> str:
        """Format tier/type line like 'Tier 2 Ranged'."""
        parts = []
        if adv.tier is not None:
            parts.append(f"Tier {adv.tier}")
        if adv.adversary_type:
            parts.append(adv.adversary_type)
        return " ".join(parts)

    @classmethod
    def _format_stats_line(cls, adv: Adversary) -> str:
        """Format stats line with pipe separators.

        Format: **Difficulty:** X | **Thresholds:** Y/Z | **HP:** A | **Stress:** B
        """
        parts = []

        # Difficulty - show empty if missing
        diff_val = str(adv.difficulty) if adv.difficulty is not None else ""
        parts.append(f"**Difficulty:** {diff_val}")

        # Thresholds
        thresh_val = adv.thresholds_str if adv.thresholds_str else ""
        parts.append(f"**Thresholds:** {thresh_val}")

        # HP
        hp_val = str(adv.hp) if adv.hp is not None else ""
        parts.append(f"**HP:** {hp_val}")

        # Stress
        stress_val = str(adv.stress) if adv.stress is not None else ""
        parts.append(f"**Stress:** {stress_val}")

        return " | ".join(parts)

    @classmethod
    def _format_source_line(cls, adv: Adversary) -> str:
        """Format source attribution line.

        Format: *Source: Name, p. X* or *Source: Name* (without page)
        """
        if not adv.source_name:
            return ""

        if adv.source_page is not None:
            return f"*Source: {adv.source_name}, p. {adv.source_page}*"
        else:
            return f"*Source: {adv.source_name}*"

    @classmethod
    def write_multiple(
        cls,
        adversaries: list[Adversary],
        output_dir: Path,
        overwrite: bool = False
    ) -> dict[str, Path]:
        """Write multiple adversaries to individual files.

        Returns dict mapping adversary name to output path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        written = {}

        for adv in adversaries:
            filename = f"{adv.safe_filename()}.md"
            output_path = output_dir / filename

            if output_path.exists() and not overwrite:
                # Add suffix to avoid overwriting
                i = 1
                while output_path.exists():
                    output_path = output_dir / f"{adv.safe_filename()} ({i}).md"
                    i += 1

            cls.write_adversary(adv, output_path)
            written[adv.name] = output_path

        return written

    @classmethod
    def format_validation_report(cls, adversaries: list[Adversary]) -> str:
        """Generate a validation report for a list of adversaries."""
        lines = ["# Adversary Validation Report", ""]

        issues_count = 0
        complete_count = 0

        for adv in adversaries:
            issues = adv.validate()
            if issues:
                issues_count += 1
                lines.append(f"## {adv.name or 'UNNAMED'}")
                for issue in issues:
                    lines.append(f"- {issue}")
                lines.append("")
            else:
                complete_count += 1

        # Summary at top
        summary = [
            f"**Total adversaries:** {len(adversaries)}",
            f"**Complete:** {complete_count}",
            f"**With issues:** {issues_count}",
            ""
        ]

        return "\n".join(summary + lines)
