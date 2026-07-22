"""Generate master index files for adversary collections."""
import sys
from pathlib import Path
from typing import Optional

# Handle imports for both module and direct execution
try:
    from ..models.adversary import Adversary
    from ..models.environment import Environment
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary
    from models.environment import Environment


class IndexGenerator:
    """Generator for adversary index/reference files."""

    @classmethod
    def generate_master_index(
        cls,
        adversaries: list[Adversary],
        title: str = "Adversaries Master Index",
        environments: Optional[list[Environment]] = None,
    ) -> str:
        """Generate a master index markdown file.

        Groups adversaries by tier and includes quick reference stats.
        Environments, when given, follow in their own section.
        """
        lines = [f"# {title}", ""]

        # With environments present the two record kinds each get a section,
        # so tier headings drop a level to sit beneath them.
        sectioned = bool(environments)
        tier_heading = "###" if sectioned else "##"

        if sectioned:
            lines.extend(["## Adversaries", ""])

        by_tier = cls._group_by_tier(adversaries)
        for tier in sorted(by_tier):
            lines.append(f"{tier_heading} {cls._tier_name(tier)}")
            lines.append("")
            lines.append("| Name | Type | Difficulty | Thresholds | HP | Stress |")
            lines.append("|------|------|------------|------------|----|----|")

            for adv in sorted(by_tier[tier], key=lambda a: a.name or ""):
                lines.append(
                    f"| {adv.name or 'Unknown'} | {adv.adversary_type or '-'} "
                    f"| {cls._or_dash(adv.difficulty)} | {adv.thresholds_str or '-'} "
                    f"| {cls._or_dash(adv.hp)} | {cls._or_dash(adv.stress)} |"
                )

            lines.append("")

        env_by_tier: dict[int, list[Environment]] = {}
        if environments:
            lines.extend(["## Environments", ""])
            env_by_tier = cls._group_by_tier(environments)

            for tier in sorted(env_by_tier):
                lines.append(f"{tier_heading} {cls._tier_name(tier)}")
                lines.append("")
                lines.append("| Name | Type | Difficulty | Impulses |")
                lines.append("|------|------|------------|----------|")

                for env in sorted(env_by_tier[tier], key=lambda e: e.name or ""):
                    lines.append(
                        f"| {env.name or 'Unknown'} | {env.environment_type or '-'} "
                        f"| {cls._or_dash(env.difficulty)} | {env.impulses or '-'} |"
                    )

                lines.append("")

        # Summary statistics
        lines.append("## Summary")
        lines.append("")
        lines.append(f"**Total adversaries:** {len(adversaries)}")

        for tier in sorted(by_tier):
            lines.append(f"- {cls._tier_name(tier)}: {len(by_tier[tier])}")

        if environments:
            lines.append("")
            lines.append(f"**Total environments:** {len(environments)}")
            for tier in sorted(env_by_tier):
                lines.append(f"- {cls._tier_name(tier)}: {len(env_by_tier[tier])}")

        return "\n".join(lines)

    @staticmethod
    def _group_by_tier(records: list) -> dict[int, list]:
        """Group records by tier, filing missing tiers under 0."""
        grouped: dict[int, list] = {}
        for record in records:
            grouped.setdefault(record.tier if record.tier is not None else 0, []).append(record)
        return grouped

    @staticmethod
    def _tier_name(tier: int) -> str:
        return f"Tier {tier}" if tier > 0 else "Unknown Tier"

    @staticmethod
    def _or_dash(value) -> str:
        return str(value) if value is not None else "-"

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
        index_type: str = "master",
        environments: Optional[list[Environment]] = None,
    ) -> None:
        """Write an index file."""
        if index_type == "master":
            content = cls.generate_master_index(adversaries, environments=environments)
        elif index_type == "type":
            content = cls.generate_type_index(adversaries)
        else:
            raise ValueError(f"Unknown index type: {index_type}")

        output_path.write_text(content, encoding='utf-8')
