"""Generate master index files for adversary collections."""
import sys
from pathlib import Path
from typing import Optional

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary


class IndexGenerator:
    """Generator for adversary index/reference files."""

    @classmethod
    def generate_master_index(
        cls,
        adversaries: list[Adversary],
        title: str = "Adversaries Master Index"
    ) -> str:
        """Generate a master index markdown file.

        Groups adversaries by tier and includes quick reference stats.
        """
        lines = [f"# {title}", ""]

        # Group by tier
        by_tier: dict[int, list[Adversary]] = {}
        for adv in adversaries:
            tier = adv.tier if adv.tier is not None else 0
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(adv)

        # Sort tiers and adversaries within tiers
        for tier in sorted(by_tier.keys()):
            tier_advs = sorted(by_tier[tier], key=lambda a: a.name or "")

            tier_name = f"Tier {tier}" if tier > 0 else "Unknown Tier"
            lines.append(f"## {tier_name}")
            lines.append("")

            # Table header
            lines.append("| Name | Type | Difficulty | Thresholds | HP | Stress |")
            lines.append("|------|------|------------|------------|----|----|")

            for adv in tier_advs:
                name = adv.name or "Unknown"
                adv_type = adv.adversary_type or "-"
                diff = str(adv.difficulty) if adv.difficulty is not None else "-"
                thresh = adv.thresholds_str or "-"
                hp = str(adv.hp) if adv.hp is not None else "-"
                stress = str(adv.stress) if adv.stress is not None else "-"

                lines.append(f"| {name} | {adv_type} | {diff} | {thresh} | {hp} | {stress} |")

            lines.append("")

        # Summary statistics
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Total adversaries:** {len(adversaries)}")

        for tier in sorted(by_tier.keys()):
            tier_name = f"Tier {tier}" if tier > 0 else "Unknown Tier"
            lines.append(f"- {tier_name}: {len(by_tier[tier])}")

        return "\n".join(lines)

    @classmethod
    def generate_type_index(
        cls,
        adversaries: list[Adversary],
        title: str = "Adversaries by Type"
    ) -> str:
        """Generate index grouped by adversary type (Bruiser, Leader, etc.)."""
        lines = [f"# {title}", ""]

        # Group by type
        by_type: dict[str, list[Adversary]] = {}
        for adv in adversaries:
            adv_type = adv.adversary_type or "Unknown"
            if adv_type not in by_type:
                by_type[adv_type] = []
            by_type[adv_type].append(adv)

        for adv_type in sorted(by_type.keys()):
            type_advs = sorted(by_type[adv_type], key=lambda a: (a.tier or 0, a.name or ""))

            lines.append(f"## {adv_type}")
            lines.append("")

            for adv in type_advs:
                tier_str = f"Tier {adv.tier}" if adv.tier else "?"
                lines.append(f"- **{adv.name}** ({tier_str})")

            lines.append("")

        return "\n".join(lines)

    @classmethod
    def write_index(
        cls,
        adversaries: list[Adversary],
        output_path: Path,
        index_type: str = "master"
    ) -> None:
        """Write an index file."""
        if index_type == "master":
            content = cls.generate_master_index(adversaries)
        elif index_type == "type":
            content = cls.generate_type_index(adversaries)
        else:
            raise ValueError(f"Unknown index type: {index_type}")

        output_path.write_text(content, encoding='utf-8')
