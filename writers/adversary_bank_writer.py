"""Arrow's Adversary Bank Markdown writer.

Writes one Markdown file per adversary. Each file contains a daggerheart YAML
code block that Arrow's Adversary Bank can scan from an Obsidian library folder.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from ..models.adversary import Adversary, Feature
    from ..models.environment import Environment, EnvironmentFeature
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature
    from models.environment import Environment, EnvironmentFeature


# Environments are written to their own subfolder so an Obsidian library can
# point at adversaries, environments, or both.
ENVIRONMENT_SUBFOLDER = "environments"


class AdversaryBankWriter:
    """Writer for Arrow's Adversary Bank-readable Markdown files."""

    @classmethod
    def write_adversary(cls, adversary: Adversary, output_path: Path) -> None:
        content = cls.format_adversary(adversary)
        output_path.write_text(content, encoding="utf-8")

    @classmethod
    def write_environment(cls, environment: Environment, output_path: Path) -> None:
        content = cls.format_environment(environment)
        output_path.write_text(content, encoding="utf-8")

    @classmethod
    def write_multiple(
        cls,
        adversaries: list[Adversary],
        output_dir: Path,
        overwrite: bool = False,
        environments: list[Environment] | None = None,
    ) -> dict[str, Path]:
        """Write adversaries to ``output_dir`` and environments beneath it."""
        written = cls._write_records(
            adversaries, output_dir, overwrite, cls.write_adversary
        )

        if environments:
            written.update(cls._write_records(
                environments,
                output_dir / ENVIRONMENT_SUBFOLDER,
                overwrite,
                cls.write_environment,
            ))

        return written

    @classmethod
    def write_environments(
        cls,
        environments: list[Environment],
        output_dir: Path,
        overwrite: bool = False,
    ) -> dict[str, Path]:
        """Write environments into ``output_dir`` itself."""
        return cls._write_records(
            environments, output_dir, overwrite, cls.write_environment
        )

    @classmethod
    def _write_records(cls, records, output_dir: Path, overwrite: bool, write) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        used_filenames: set[str] = set()

        for record in records:
            base_name = record.safe_filename()
            output_path = output_dir / f"{base_name}.md"

            i = 1
            while output_path.name in used_filenames or (output_path.exists() and not overwrite):
                output_path = output_dir / f"{base_name} ({i}).md"
                i += 1

            used_filenames.add(output_path.name)

            key = record.name
            if key in written:
                i = 1
                while f"{record.name} ({i})" in written:
                    i += 1
                key = f"{record.name} ({i})"

            write(record, output_path)
            written[key] = output_path

        return written

    @classmethod
    def format_adversary(cls, adv: Adversary) -> str:
        display_name = cls._display_name(adv.name)
        lines = [
            f"# {display_name}",
            "",
            "```daggerheart",
        ]
        lines.extend(cls._yaml_lines(cls._to_data(adv)))
        lines.extend(["```", ""])
        return "\n".join(lines)

    @classmethod
    def format_environment(cls, env: Environment) -> str:
        display_name = cls._display_name(env.name)
        lines = [
            f"# {display_name}",
            "",
            "```daggerheart",
        ]
        lines.extend(cls._yaml_lines(cls._environment_to_data(env)))
        lines.extend(["```", ""])
        return "\n".join(lines)

    @classmethod
    def _environment_to_data(cls, env: Environment) -> dict[str, Any]:
        data: dict[str, Any] = {}

        cls._set(data, "name", cls._display_name(env.name) if env.name else None)
        cls._set(data, "tier", env.tier)
        cls._set(data, "type", env.environment_type)
        cls._set(data, "desc", env.description)
        cls._set(data, "difficulty", env.difficulty)
        cls._set(data, "impulses", env.impulses)
        cls._set(data, "potential_adversaries", env.potential_adversaries)

        if env.source_name:
            cls._set(data, "source", cls._source_value(env))

        if env.features:
            data["features"] = [
                cls._environment_feature_data(feature) for feature in env.features
            ]

        return data

    @classmethod
    def _environment_feature_data(cls, feature: EnvironmentFeature) -> dict[str, Any]:
        data: dict[str, Any] = {}
        cls._set(data, "name", feature.name)
        cls._set(data, "type", feature.feature_type)
        cls._set(data, "desc", feature.description)
        if feature.questions:
            data["questions"] = list(feature.questions)
        return data

    @classmethod
    def _to_data(cls, adv: Adversary) -> dict[str, Any]:
        data: dict[str, Any] = {}

        cls._set(data, "name", cls._display_name(adv.name) if adv.name else None)
        cls._set(data, "tier", adv.tier)
        cls._set(data, "type", adv.adversary_type)
        cls._set(data, "desc", adv.description)
        cls._set(data, "difficulty", adv.difficulty)

        if adv.attack and not adv.attack.is_empty():
            cls._set(data, "attack", cls._format_attack(adv.attack.modifier))
            cls._set(data, "weapon", adv.attack.weapon_name)
            cls._set(data, "range", adv.attack.range)
            cls._set(data, "damage", adv.attack.damage)

        cls._set(data, "thresholds", adv.thresholds_str)
        cls._set(data, "hp", adv.hp)
        cls._set(data, "stress", adv.stress)
        cls._set(data, "xp", adv.experience)
        cls._set(data, "motives", adv.motives_tactics)

        if adv.source_name:
            cls._set(data, "source", cls._source_value(adv))

        if adv.features:
            data["features"] = [cls._feature_data(feature) for feature in adv.features]

        return data

    @staticmethod
    def _set(data: dict[str, Any], key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str) and value == "":
            return
        data[key] = value

    @staticmethod
    def _format_attack(modifier: str | None) -> int | str | None:
        if modifier is None or modifier == "":
            return None
        try:
            return int(modifier)
        except ValueError:
            return modifier

    @staticmethod
    def _source_value(adv: Adversary) -> str:
        # Markdown blocks carry the human-readable source name + page so it
        # renders directly when the file is opened in Obsidian. The JSON
        # writer (BeastvaultWriter._resolve_source_tag) emits a slug instead,
        # for compatibility with the older BeastVault library format. If you
        # change one, consider whether the other should match.
        if adv.source_page is not None:
            return f"{adv.source_name}, p. {adv.source_page}"
        return adv.source_name or ""

    @classmethod
    def _feature_data(cls, feature: Feature) -> dict[str, Any]:
        data: dict[str, Any] = {}
        cls._set(data, "name", feature.name)
        cls._set(data, "type", feature.feature_type)
        cls._set(data, "desc", feature.description)
        return data

    @classmethod
    def _yaml_lines(cls, data: dict[str, Any], indent: int = 0) -> list[str]:
        lines: list[str] = []
        pad = " " * indent

        for key, value in data.items():
            if isinstance(value, list):
                lines.append(f"{pad}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.extend(cls._yaml_dict_list_item(item, indent + 2))
                    else:
                        lines.append(f"{pad}  - {cls._yaml_scalar(item)}")
            elif isinstance(value, dict):
                lines.append(f"{pad}{key}:")
                lines.extend(cls._yaml_lines(value, indent + 2))
            else:
                lines.append(f"{pad}{key}: {cls._yaml_scalar(value)}")

        return lines

    @classmethod
    def _yaml_dict_list_item(cls, data: dict[str, Any], indent: int) -> list[str]:
        pad = " " * indent
        lines: list[str] = []
        first = True

        for key, value in data.items():
            prefix = "- " if first else "  "
            first = False
            if isinstance(value, list):
                lines.append(f"{pad}{prefix}{key}:")
                for item in value:
                    lines.append(f"{pad}    - {cls._yaml_scalar(item)}")
            else:
                lines.append(f"{pad}{prefix}{key}: {cls._yaml_scalar(value)}")

        if first:
            lines.append(f"{pad}- {{}}")

        return lines

    @staticmethod
    def _yaml_scalar(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value), ensure_ascii=False)

    @classmethod
    def _display_name(cls, name: str | None) -> str:
        if not name:
            return "Unknown"
        return re.sub(
            r"[A-Za-z]+(?:'[A-Za-z]+)?",
            lambda match: cls._title_word(match.group(0)),
            name,
        )

    @staticmethod
    def _title_word(word: str) -> str:
        return word[:1].upper() + word[1:].lower()
