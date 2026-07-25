"""Arrow's Adversary Bank Markdown writer.

Writes one Markdown file per adversary. Each file contains a daggerheart YAML
code block that Arrow's Adversary Bank can scan from an Obsidian library folder.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from ..models.adversary import Adversary, Feature
    from ..models.environment import Environment, EnvironmentFeature
    from . import yaml_format
    from .frontmatter import adversary_frontmatter, environment_frontmatter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature
    from models.environment import Environment, EnvironmentFeature
    from writers import yaml_format
    from writers.frontmatter import adversary_frontmatter, environment_frontmatter


# Environments are written to their own subfolder so an Obsidian library can
# point at adversaries, environments, or both.
ENVIRONMENT_SUBFOLDER = "environments"


class AdversaryBankWriter:
    """Writer for Arrow's Adversary Bank-readable Markdown files."""

    # Formatting helpers live in writers.yaml_format so the frontmatter
    # module can share them; these aliases keep the old class-level API.
    _set = staticmethod(yaml_format.set_field)
    _format_attack = staticmethod(yaml_format.format_attack)
    _yaml_scalar = staticmethod(yaml_format.yaml_scalar)
    _yaml_lines = staticmethod(yaml_format.yaml_lines)
    _yaml_dict_list_item = staticmethod(yaml_format.yaml_dict_list_item)
    _display_name = staticmethod(yaml_format.display_name)

    @classmethod
    def write_adversary(cls, adversary: Adversary, output_path: Path,
                        frontmatter: bool = False) -> None:
        content = cls.format_adversary(adversary, frontmatter=frontmatter)
        output_path.write_text(content, encoding="utf-8")

    @classmethod
    def write_environment(cls, environment: Environment, output_path: Path,
                          frontmatter: bool = False) -> None:
        content = cls.format_environment(environment, frontmatter=frontmatter)
        output_path.write_text(content, encoding="utf-8")

    @classmethod
    def write_multiple(
        cls,
        adversaries: list[Adversary],
        output_dir: Path,
        overwrite: bool = False,
        environments: list[Environment] | None = None,
        frontmatter: bool = False,
    ) -> dict[str, Path]:
        """Write adversaries to ``output_dir`` and environments beneath it."""
        write_adv = lambda record, path: cls.write_adversary(
            record, path, frontmatter=frontmatter
        )
        write_env = lambda record, path: cls.write_environment(
            record, path, frontmatter=frontmatter
        )
        written = cls._write_records(adversaries, output_dir, overwrite, write_adv)

        if environments:
            # Merged rather than updated: an adversary and an environment can
            # share a name, and a plain update would drop one of the two paths
            # even though both files were written.
            cls._merge_written(written, cls._write_records(
                environments,
                output_dir / ENVIRONMENT_SUBFOLDER,
                overwrite,
                write_env,
            ))

        return written

    @staticmethod
    def _merge_written(target: dict[str, Path], extra: dict[str, Path]) -> None:
        """Merge write results, renaming keys that collide across record kinds."""
        for key, path in extra.items():
            unique = key
            i = 1
            while unique in target:
                unique = f"{key} ({i})"
                i += 1
            target[unique] = path

    @classmethod
    def write_environments(
        cls,
        environments: list[Environment],
        output_dir: Path,
        overwrite: bool = False,
        frontmatter: bool = False,
    ) -> dict[str, Path]:
        """Write environments into ``output_dir`` itself."""
        write_env = lambda record, path: cls.write_environment(
            record, path, frontmatter=frontmatter
        )
        return cls._write_records(environments, output_dir, overwrite, write_env)

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
                output_path = output_dir / f"{base_name}_{i}.md"
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
    def format_adversary(cls, adv: Adversary, frontmatter: bool = False) -> str:
        display_name = cls._display_name(adv.name)
        lines = [
            f"# {display_name}",
            "",
            "```daggerheart",
        ]
        lines.extend(cls._yaml_lines(cls._to_data(adv)))
        lines.extend(["```", ""])
        body = "\n".join(lines)
        if frontmatter:
            return adversary_frontmatter(adv) + body
        return body

    @classmethod
    def format_environment(cls, env: Environment, frontmatter: bool = False) -> str:
        display_name = cls._display_name(env.name)
        lines = [
            f"# {display_name}",
            "",
            "```daggerheart",
        ]
        lines.extend(cls._yaml_lines(cls._environment_to_data(env)))
        lines.extend(["```", ""])
        body = "\n".join(lines)
        if frontmatter:
            return environment_frontmatter(env) + body
        return body

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

