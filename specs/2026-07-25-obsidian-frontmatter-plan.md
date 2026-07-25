# Obsidian Properties Frontmatter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in flag that prepends an Obsidian properties (YAML frontmatter) block to every exported per-record Markdown file, with a page-free `source` value so Obsidian Bases can filter by book.

**Architecture:** A new `writers/frontmatter.py` module builds the fenced block from a record; the YAML emission and display-name helpers move out of `AdversaryBankWriter` into a shared `writers/yaml_format.py` (the bank writer keeps thin delegating attributes so nothing else changes). Both writers accept `frontmatter: bool = False` and prepend the block; `convert.py` adds `--frontmatter`; `app.py`/`index.html` add a `frontmatter` form field and checkbox.

**Tech Stack:** Python 3 stdlib only (dataclasses, argparse, unittest, http.server). No new dependencies. Tests run with `python3 -m unittest`.

**Spec:** `specs/2026-07-25-obsidian-frontmatter-design.md`

## Global Constraints

- Flag default is **off** everywhere (CLI, `convert_to_files`, writers, web form). Output with the flag off must be byte-identical to today.
- Frontmatter `source` is `source_name` only — never the page number. The ```` ```daggerheart ```` code block keeps `"name, p. N"` unchanged.
- Adversary frontmatter field order: `name, tier, type, difficulty, hp, stress, attack, weapon, range, damage, motives, desc, source, feature_count`.
- Environment frontmatter field order: `name, tier, type, difficulty, impulses, potential_adversaries, desc, source, feature_count`.
- Missing/empty fields are omitted; `feature_count` is always present (0 allowed).
- String scalars are JSON-quoted (existing `_yaml_scalar` behavior). Frontmatter must be the first bytes of the file, before the `# Title` heading.
- `IndexGenerator`, `BeastvaultWriter`, and the JSON export are untouched.
- Writers use the project's try/except relative-import pattern (see any existing writer module head).
- Run tests from the project root with `.venv/bin/python -m unittest <module>` (plain `python3` lacks pdfplumber; unit tests are stdlib-only but use the venv for consistency).

---

### Task 1: Extract shared formatting helpers to `writers/yaml_format.py`

Pure refactor — no behavior change. Existing tests are the safety net; two of them (`tests/test_release_review_fixes.py:299-303`) call `AdversaryBankWriter._yaml_lines` / `._yaml_dict_list_item` directly, so the class keeps delegating attributes.

**Files:**
- Create: `writers/yaml_format.py`
- Modify: `writers/adversary_bank_writer.py` (delete moved bodies, delegate)

**Interfaces:**
- Produces (used by Tasks 2–3): module `writers.yaml_format` with functions
  `set_field(data: dict, key: str, value) -> None`,
  `format_attack(modifier: str | None) -> int | str | None`,
  `yaml_scalar(value) -> str`,
  `yaml_lines(data: dict, indent: int = 0) -> list[str]`,
  `yaml_dict_list_item(data: dict, indent: int) -> list[str]`,
  `display_name(name: str | None) -> str`.

- [ ] **Step 1: Baseline — run the full suite, all green**

Run: `.venv/bin/python -m unittest discover tests -v 2>&1 | tail -5`
Expected: OK (note the test count for comparison after the move).

- [ ] **Step 2: Create `writers/yaml_format.py`**

Move the bodies of `_set`, `_format_attack`, `_yaml_scalar`, `_yaml_lines`, `_yaml_dict_list_item`, `_display_name`, `_title_word`, and the `_YAML_FORBIDDEN_RE` constant from `writers/adversary_bank_writer.py` into module-level functions. The logic is copied verbatim; only `cls.`/`@classmethod` scaffolding changes:

```python
"""Formatting helpers shared by the Markdown writers.

String scalars are JSON-encoded, which is a strict subset of YAML 1.2, so the
emitted YAML stays valid without a PyYAML dependency.
"""
from __future__ import annotations

import json
import re
from typing import Any

# DEL and the C1 control block. YAML rejects these outright, and json.dumps
# leaves them literal when ensure_ascii is off.
_YAML_FORBIDDEN_RE = re.compile(r"[\x7f-\x9f]")


def set_field(data: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str) and value == "":
        return
    data[key] = value


def format_attack(modifier: str | None) -> int | str | None:
    if modifier is None or modifier == "":
        return None
    try:
        return int(modifier)
    except ValueError:
        return modifier


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    encoded = json.dumps(str(value), ensure_ascii=False)
    # json.dumps escapes C0 controls but passes DEL and the C1 block
    # through literally. YAML forbids those, so a stray one makes the
    # whole block unparseable. \u escapes are valid in a YAML
    # double-quoted scalar, and non-ASCII text stays readable.
    return _YAML_FORBIDDEN_RE.sub(
        lambda match: "\\u%04x" % ord(match.group(0)), encoded
    )


def yaml_lines(data: dict[str, Any], indent: int = 0) -> list[str]:
    lines: list[str] = []
    pad = " " * indent

    for key, value in data.items():
        if isinstance(value, list):
            # A bare "key:" parses back as null, not as an empty list.
            if not value:
                lines.append(f"{pad}{key}: []")
                continue
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.extend(yaml_dict_list_item(item, indent + 2))
                else:
                    lines.append(f"{pad}  - {yaml_scalar(item)}")
        elif isinstance(value, dict):
            if not value:
                lines.append(f"{pad}{key}: {{}}")
                continue
            lines.append(f"{pad}{key}:")
            lines.extend(yaml_lines(value, indent + 2))
        else:
            lines.append(f"{pad}{key}: {yaml_scalar(value)}")

    return lines


def yaml_dict_list_item(data: dict[str, Any], indent: int) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    first = True

    for key, value in data.items():
        prefix = "- " if first else "  "
        first = False
        if isinstance(value, list):
            if not value:
                lines.append(f"{pad}{prefix}{key}: []")
                continue
            lines.append(f"{pad}{prefix}{key}:")
            for item in value:
                lines.append(f"{pad}    - {yaml_scalar(item)}")
        else:
            lines.append(f"{pad}{prefix}{key}: {yaml_scalar(value)}")

    if first:
        lines.append(f"{pad}- {{}}")

    return lines


def display_name(name: str | None) -> str:
    if not name:
        return "Unknown"
    return re.sub(
        r"[A-Za-z]+(?:'[A-Za-z]+)?",
        lambda match: _title_word(match.group(0)),
        name,
    )


def _title_word(word: str) -> str:
    return word[:1].upper() + word[1:].lower()
```

- [ ] **Step 3: Delegate from `AdversaryBankWriter`**

In `writers/adversary_bank_writer.py`: delete the moved method bodies, the `_YAML_FORBIDDEN_RE` constant, and the now-unused `import json` / `import re` if nothing else uses them (`re` is still used by `_YAML_FORBIDDEN_RE` only — check; `_display_name`'s `re.sub` also moves). Add to the import block (both branches of the try/except):

```python
try:
    from ..models.adversary import Adversary, Feature
    from ..models.environment import Environment, EnvironmentFeature
    from . import yaml_format
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature
    from models.environment import Environment, EnvironmentFeature
    from writers import yaml_format
```

Inside the class, replace the removed methods with delegating attributes (keeps `cls._yaml_lines(...)` call sites and the two direct test references working):

```python
    # Formatting helpers live in writers.yaml_format so the frontmatter
    # module can share them; these aliases keep the old class-level API.
    _set = staticmethod(yaml_format.set_field)
    _format_attack = staticmethod(yaml_format.format_attack)
    _yaml_scalar = staticmethod(yaml_format.yaml_scalar)
    _yaml_lines = staticmethod(yaml_format.yaml_lines)
    _yaml_dict_list_item = staticmethod(yaml_format.yaml_dict_list_item)
    _display_name = staticmethod(yaml_format.display_name)
```

`_source_value` stays in the class unchanged (it is bank-block-specific: it keeps the page number).

- [ ] **Step 4: Run the full suite — same count, all green**

Run: `.venv/bin/python -m unittest discover tests -v 2>&1 | tail -5`
Expected: OK, same test count as Step 1.

- [ ] **Step 5: Commit**

```bash
git add writers/yaml_format.py writers/adversary_bank_writer.py
git commit -m "Extract shared YAML/name formatting helpers to writers.yaml_format"
```

---

### Task 2: Frontmatter module

**Files:**
- Create: `writers/frontmatter.py`
- Test: `tests/test_frontmatter.py`

**Interfaces:**
- Consumes: `writers.yaml_format` functions from Task 1.
- Produces (used by Task 3): `adversary_frontmatter(adv: Adversary) -> str` and `environment_frontmatter(env: Environment) -> str`, each returning the full block — opening `---` line through closing `---` line — ending with a trailing newline, so `block + existing_output` puts the `# Title` heading immediately after.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_frontmatter.py`:

```python
"""Tests for the Obsidian properties (YAML frontmatter) formatter.

Stdlib-only, like test_adversary_bank_writer: every string scalar is
JSON-encoded, so json.loads validates individual values without PyYAML.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.adversary import Adversary, Attack, Feature
from models.environment import Environment, EnvironmentFeature
from writers.frontmatter import adversary_frontmatter, environment_frontmatter


def base_adversary(**overrides) -> Adversary:
    adv = Adversary(
        name="Test Goblin",
        tier=1,
        adversary_type="Skulk",
        description="A small green menace.",
        difficulty=10,
        threshold_minor=5,
        threshold_major=10,
        hp=3,
        stress=2,
        attack=Attack(modifier="+2", weapon_name="Dagger", range="Melee", damage="1d6+2 phy"),
        experience="Stealth +2",
        motives_tactics="Ambush, retreat",
        source_name="Daggerheart SRD",
        source_page=42,
        features=[
            Feature(name="Sneak", feature_type="Passive", description="Hard to spot."),
        ],
    )
    for key, value in overrides.items():
        setattr(adv, key, value)
    return adv


def base_environment(**overrides) -> Environment:
    env = Environment(
        name="Test Mine",
        tier=1,
        environment_type="Traversal",
        description="A dark tunnel.",
        impulses="Collapse, confuse",
        difficulty=11,
        potential_adversaries="Spiders",
        features=[
            EnvironmentFeature(
                name="Dark", feature_type="Passive", description="No light.",
            ),
        ],
        source_name="Hope and Fear",
        source_page=39,
    )
    for key, value in overrides.items():
        setattr(env, key, value)
    return env


def keys_in_order(block: str) -> list[str]:
    """Top-level YAML keys between the --- fences, in file order."""
    lines = block.split("\n")
    assert lines[0] == "---" and lines[-2] == "---", block
    return [line.split(":", 1)[0] for line in lines[1:-2]]


def scalar_for(block: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}: (.+)$", block, re.MULTILINE)
    if not match:
        raise AssertionError(f"key '{key}' not found in:\n{block}")
    return match.group(1)


class AdversaryFrontmatterTests(unittest.TestCase):
    def test_block_is_fenced_and_ends_with_newline(self):
        block = adversary_frontmatter(base_adversary())
        self.assertTrue(block.startswith("---\n"))
        self.assertTrue(block.endswith("\n---\n"))

    def test_field_order_matches_spec(self):
        block = adversary_frontmatter(base_adversary())
        self.assertEqual(keys_in_order(block), [
            "name", "tier", "type", "difficulty", "hp", "stress",
            "attack", "weapon", "range", "damage",
            "motives", "desc", "source", "feature_count",
        ])

    def test_excludes_thresholds_xp_and_features(self):
        block = adversary_frontmatter(base_adversary())
        self.assertNotIn("thresholds", block)
        self.assertNotIn("xp", block)
        self.assertNotIn("Sneak", block)

    def test_source_omits_page_number(self):
        block = adversary_frontmatter(base_adversary())
        self.assertEqual(json.loads(scalar_for(block, "source")), "Daggerheart SRD")
        self.assertNotIn("p. 42", block)

    def test_name_is_title_cased_like_the_code_block(self):
        block = adversary_frontmatter(base_adversary(name="ACCURSED SOUL"))
        self.assertEqual(json.loads(scalar_for(block, "name")), "Accursed Soul")

    def test_missing_fields_are_omitted(self):
        adv = base_adversary(
            description=None, attack=None, motives_tactics=None,
            source_name=None, source_page=None, features=[],
        )
        block = adversary_frontmatter(adv)
        self.assertEqual(
            keys_in_order(block),
            ["name", "tier", "type", "difficulty", "hp", "stress", "feature_count"],
        )

    def test_feature_count_zero_still_present(self):
        block = adversary_frontmatter(base_adversary(features=[]))
        self.assertEqual(scalar_for(block, "feature_count"), "0")

    def test_attack_modifier_coerced_to_int(self):
        block = adversary_frontmatter(base_adversary())
        self.assertEqual(scalar_for(block, "attack"), "2")

    def test_special_characters_stay_json_quoted(self):
        adv = base_adversary(
            name="WILL-O'-THE-WISP",
            description='Says "boo" — colon: included.',
        )
        block = adversary_frontmatter(adv)
        self.assertEqual(json.loads(scalar_for(block, "name")), "Will-O'-The-Wisp")
        self.assertEqual(
            json.loads(scalar_for(block, "desc")),
            'Says "boo" — colon: included.',
        )


class EnvironmentFrontmatterTests(unittest.TestCase):
    def test_field_order_matches_spec(self):
        block = environment_frontmatter(base_environment())
        self.assertEqual(keys_in_order(block), [
            "name", "tier", "type", "difficulty",
            "impulses", "potential_adversaries",
            "desc", "source", "feature_count",
        ])

    def test_type_is_environment_type(self):
        block = environment_frontmatter(base_environment())
        self.assertEqual(json.loads(scalar_for(block, "type")), "Traversal")

    def test_string_difficulty_is_quoted(self):
        env = base_environment(difficulty='Special (see "Relative Strength")')
        block = environment_frontmatter(env)
        self.assertEqual(
            json.loads(scalar_for(block, "difficulty")),
            'Special (see "Relative Strength")',
        )

    def test_source_omits_page_number(self):
        block = environment_frontmatter(base_environment())
        self.assertEqual(json.loads(scalar_for(block, "source")), "Hope and Fear")
        self.assertNotIn("p. 39", block)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_frontmatter -v 2>&1 | tail -3`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'writers.frontmatter'`

- [ ] **Step 3: Implement `writers/frontmatter.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_frontmatter -v 2>&1 | tail -3`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add writers/frontmatter.py tests/test_frontmatter.py
git commit -m "Add Obsidian frontmatter formatter for adversaries and environments"
```

---

### Task 3: Writers accept a `frontmatter` flag

**Files:**
- Modify: `writers/adversary_bank_writer.py`
- Modify: `writers/markdown_writer.py`
- Test: `tests/test_frontmatter.py` (append a class)

**Interfaces:**
- Consumes: `adversary_frontmatter` / `environment_frontmatter` from Task 2.
- Produces (used by Task 4): every format/write method on both writers gains a trailing keyword `frontmatter: bool = False`:
  `format_adversary(adv, frontmatter=False)`, `format_environment(env, frontmatter=False)`, `write_adversary(adv, path, frontmatter=False)`, `write_environment(env, path, frontmatter=False)`, `AdversaryBankWriter.write_multiple(advs, dir, overwrite=False, environments=None, frontmatter=False)`, `AdversaryBankWriter.write_environments(envs, dir, overwrite=False, frontmatter=False)`, `MarkdownWriter.write_multiple(advs, dir, overwrite=False, frontmatter=False)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_frontmatter.py` (imports at top of file gain `from writers.adversary_bank_writer import AdversaryBankWriter` and `from writers.markdown_writer import MarkdownWriter`):

```python
class WriterFlagTests(unittest.TestCase):
    def test_bank_writer_flag_off_output_unchanged(self):
        adv = base_adversary()
        self.assertEqual(
            AdversaryBankWriter.format_adversary(adv),
            AdversaryBankWriter.format_adversary(adv, frontmatter=False),
        )
        self.assertTrue(
            AdversaryBankWriter.format_adversary(adv).startswith("# Test Goblin")
        )

    def test_bank_writer_flag_on_prepends_block(self):
        adv = base_adversary()
        output = AdversaryBankWriter.format_adversary(adv, frontmatter=True)
        self.assertEqual(
            output,
            adversary_frontmatter(adv) + AdversaryBankWriter.format_adversary(adv),
        )
        self.assertTrue(output.startswith("---\n"))
        self.assertIn("\n---\n# Test Goblin", output)
        self.assertIn("```daggerheart", output)

    def test_bank_writer_environment_flag_on(self):
        env = base_environment()
        output = AdversaryBankWriter.format_environment(env, frontmatter=True)
        self.assertEqual(
            output,
            environment_frontmatter(env) + AdversaryBankWriter.format_environment(env),
        )

    def test_markdown_writer_flag_on_prepends_block(self):
        adv = base_adversary()
        output = MarkdownWriter.format_adversary(adv, frontmatter=True)
        self.assertEqual(
            output,
            adversary_frontmatter(adv) + MarkdownWriter.format_adversary(adv),
        )
        self.assertIn("\n---\n# TEST GOBLIN", output)

    def test_markdown_writer_environment_flag_on(self):
        env = base_environment()
        output = MarkdownWriter.format_environment(env, frontmatter=True)
        self.assertEqual(
            output,
            environment_frontmatter(env) + MarkdownWriter.format_environment(env),
        )

    def test_write_multiple_threads_flag(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            AdversaryBankWriter.write_multiple(
                [base_adversary()], Path(tmp),
                overwrite=True,
                environments=[base_environment()],
                frontmatter=True,
            )
            adv_text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            env_text = (
                Path(tmp) / "environments" / "Test_Mine.md"
            ).read_text(encoding="utf-8")
            self.assertTrue(adv_text.startswith("---\n"))
            self.assertTrue(env_text.startswith("---\n"))
```

- [ ] **Step 2: Run tests to verify the new class fails**

Run: `.venv/bin/python -m unittest tests.test_frontmatter -v 2>&1 | tail -5`
Expected: the `WriterFlagTests` cases FAIL with `TypeError: ... unexpected keyword argument 'frontmatter'`

- [ ] **Step 3: Implement the flag in both writers**

`writers/adversary_bank_writer.py` — import the formatters alongside `yaml_format` (both import branches):

```python
    from .frontmatter import adversary_frontmatter, environment_frontmatter
```
```python
    from writers.frontmatter import adversary_frontmatter, environment_frontmatter
```

Method changes:

```python
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
```

`write_multiple` and `write_environments` gain `frontmatter: bool = False` and bind it into the callback passed to `_write_records` (which calls `write(record, output_path)`):

```python
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
```

`writers/markdown_writer.py` — add the same import (both branches):

```python
try:
    from ..models.adversary import Adversary, Feature
    from ..models.environment import Environment
    from .frontmatter import adversary_frontmatter, environment_frontmatter
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models.adversary import Adversary, Feature
    from models.environment import Environment
    from writers.frontmatter import adversary_frontmatter, environment_frontmatter
```

`format_adversary` / `format_environment` gain the keyword; at the end of each, replace `return "\n".join(lines)` with:

```python
        body = "\n".join(lines)
        if frontmatter:
            return adversary_frontmatter(adv) + body   # environment_frontmatter(env) in format_environment
        return body
```

`write_adversary` / `write_environment` pass it through exactly as in the bank writer. `MarkdownWriter.write_multiple` gains `frontmatter: bool = False` and its body's `cls.write_adversary(adv, output_path)` becomes `cls.write_adversary(adv, output_path, frontmatter=frontmatter)`.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m unittest discover tests -v 2>&1 | tail -5`
Expected: OK — new tests pass, no existing test regresses (flag-off output unchanged).

- [ ] **Step 5: Commit**

```bash
git add writers/adversary_bank_writer.py writers/markdown_writer.py tests/test_frontmatter.py
git commit -m "Add frontmatter flag to both Markdown writers"
```

---

### Task 4: CLI plumbing (`convert.py --frontmatter`)

**Files:**
- Modify: `convert.py` (`convert_to_files` at :93, argparse in `main()` at :166, call site at :286)
- Test: `tests/test_frontmatter.py` (append a class)

**Interfaces:**
- Consumes: writer `frontmatter` keywords from Task 3.
- Produces (used by Task 5): `convert_to_files(result, output_dir, overwrite=False, verbose=True, readable_markdown=False, frontmatter=False)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_frontmatter.py`:

```python
class ConvertToFilesTests(unittest.TestCase):
    def _result(self):
        from models.parse_result import ParseResult
        return ParseResult(
            adversaries=[base_adversary()],
            environments=[base_environment()],
        )

    def test_flag_off_writes_no_frontmatter(self):
        import tempfile
        from convert import convert_to_files
        with tempfile.TemporaryDirectory() as tmp:
            convert_to_files(self._result(), Path(tmp), overwrite=True, verbose=False)
            text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Test Goblin"))

    def test_flag_on_writes_frontmatter_for_both_kinds(self):
        import tempfile
        from convert import convert_to_files
        with tempfile.TemporaryDirectory() as tmp:
            convert_to_files(
                self._result(), Path(tmp),
                overwrite=True, verbose=False, frontmatter=True,
            )
            adv_text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            env_text = (
                Path(tmp) / "environments" / "Test_Mine.md"
            ).read_text(encoding="utf-8")
            self.assertTrue(adv_text.startswith("---\n"))
            self.assertTrue(env_text.startswith("---\n"))

    def test_flag_on_with_readable_markdown(self):
        import tempfile
        from convert import convert_to_files
        with tempfile.TemporaryDirectory() as tmp:
            convert_to_files(
                self._result(), Path(tmp),
                overwrite=True, verbose=False,
                readable_markdown=True, frontmatter=True,
            )
            text = (Path(tmp) / "Test_Goblin.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"))
            self.assertIn("\n---\n# TEST GOBLIN", text)

    def test_cli_flag_reaches_convert_to_files(self):
        import tempfile
        from unittest.mock import patch
        import convert
        from models.parse_result import ParseResult

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.md"
            src.write_text("stub", encoding="utf-8")
            argv = ["convert.py", str(src), "-o", str(Path(tmp) / "out"),
                    "--frontmatter", "--quiet"]
            with patch.object(convert, "parse_source",
                              return_value=ParseResult(adversaries=[base_adversary()])), \
                 patch.object(convert, "convert_to_files",
                              return_value={}) as mock_convert, \
                 patch.object(sys, "argv", argv):
                convert.main()
            self.assertTrue(mock_convert.call_args.kwargs["frontmatter"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_frontmatter.ConvertToFilesTests -v 2>&1 | tail -5`
Expected: FAIL — `convert_to_files` rejects `frontmatter` keyword; the CLI test errors on the unknown `--frontmatter` argument (argparse exits).

- [ ] **Step 3: Implement**

`convert_to_files` signature and callbacks:

```python
def convert_to_files(
    result: ParseResult,
    output_dir: Path,
    overwrite: bool = False,
    verbose: bool = True,
    readable_markdown: bool = False,
    frontmatter: bool = False,
) -> dict[str, Path]:
```

and inside, bind the flag into the write callbacks:

```python
    writer = MarkdownWriter if readable_markdown else AdversaryBankWriter
    write_adv = lambda record, path: writer.write_adversary(
        record, path, frontmatter=frontmatter
    )
    write_env = lambda record, path: writer.write_environment(
        record, path, frontmatter=frontmatter
    )
```

with the two `_write_records(...)` calls taking `write_adv` / `write_env` instead of `writer.write_adversary` / `writer.write_environment`.

Argparse, after the `--readable-markdown` block:

```python
    parser.add_argument(
        '--frontmatter',
        action='store_true',
        help=(
            "Prepend an Obsidian properties block (YAML frontmatter) to each "
            "file, for use with Obsidian Bases"
        ),
    )
```

Call site in `main()`:

```python
        written = convert_to_files(
            result,
            args.output,
            overwrite=args.overwrite,
            verbose=not args.quiet,
            readable_markdown=args.readable_markdown,
            frontmatter=args.frontmatter,
        )
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m unittest discover tests -v 2>&1 | tail -5`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add convert.py tests/test_frontmatter.py
git commit -m "Add --frontmatter CLI flag"
```

---

### Task 5: Web UI plumbing (`app.py` + `index.html`)

**Files:**
- Modify: `app.py` (option parsing ~:280, `convert_to_files` call ~:297)
- Modify: `index.html` (Format fieldset ~:560, form submission paths ~:741 and ~:753)
- Test: `tests/test_frontmatter.py` (append one test)

**Interfaces:**
- Consumes: `convert_to_files(..., frontmatter=...)` from Task 4.
- Produces: `/api/convert` accepts a `frontmatter` field (multipart or JSON), default false.

- [ ] **Step 1: Write the failing test**

The handler needs a live socket, so the unit test covers only the field-parsing contract (matching how the existing suite tests `parse_multipart`); the actual wiring is verified by Step 4's end-to-end check against the running server. Append to `tests/test_frontmatter.py`:

```python
class WebOptionTests(unittest.TestCase):
    def test_frontmatter_field_default_is_false(self):
        from app import _is_truthy
        fields = {}
        self.assertFalse(_is_truthy(fields.get("frontmatter", "false")))

    def test_frontmatter_field_true(self):
        from app import _is_truthy
        self.assertTrue(_is_truthy("true"))
```

and rely on Step 4's end-to-end check for the actual wiring.

- [ ] **Step 2: Implement `app.py`**

In `_handle_convert`, alongside the other options (after the `do_index` line at ~:285):

```python
                do_frontmatter = _is_truthy(fields.get("frontmatter", "false"))
```

and the `convert_to_files` call becomes:

```python
                    written = convert_to_files(
                        result, output_dir,
                        overwrite=overwrite, verbose=False,
                        frontmatter=do_frontmatter,
                    )
```

- [ ] **Step 3: Implement `index.html`**

In the Format fieldset (after the `opt-index` label, index.html:562):

```html
        <label class="check-item"><input type="checkbox" id="opt-frontmatter"> Obsidian properties (YAML frontmatter)</label>
```

Multipart path (after `form.append('overwrite', ...)`, index.html:744):

```javascript
      form.append('frontmatter', $('#opt-frontmatter').checked);
```

JSON path (after `overwrite: $('#opt-overwrite').checked,`, index.html:756):

```javascript
          frontmatter: $('#opt-frontmatter').checked,
```

- [ ] **Step 4: End-to-end check through the web handler**

Start the server, post a convert request with `frontmatter: true` using one of the bundled sources, and confirm the written file starts with `---`:

```bash
.venv/bin/python app.py & SERVER_PID=$!
sleep 2
curl -s -X POST http://localhost:8000/api/convert \
  -H 'Content-Type: application/json' \
  -d '{"source": "<one of the filenames the UI lists from docs/>", "output_dir": "output/web-frontmatter-test", "markdown": "true", "frontmatter": "true", "overwrite": "true"}' | head -c 300
head -5 output/web-frontmatter-test/*.md | head -10
kill $SERVER_PID
rm -rf output/web-frontmatter-test
```

Check `app.py`'s `_resolve_source` / source-listing endpoint first for the exact `source` value format (it lists files from `docs/`; use `HF-adversariesonly.pdf` if listed). If the port differs, read it from `app.py`. Expected: JSON response with `"success": true`, and the head of each written file is `---`.

- [ ] **Step 5: Run the full suite and commit**

Run: `.venv/bin/python -m unittest discover tests -v 2>&1 | tail -5`
Expected: OK

```bash
git add app.py index.html tests/test_frontmatter.py
git commit -m "Add Obsidian frontmatter option to the web UI"
```

---

### Task 6: CHANGELOG, final verification, regenerate Hope & Fear

**Files:**
- Modify: `CHANGELOG.md`
- Regenerate: `output/hope-and-fear/` (user's working data, not a code artifact)

- [ ] **Step 1: Update CHANGELOG**

Add under an `## [Unreleased]` section (create it above the latest release heading if absent), following the file's Keep a Changelog format:

```markdown
### Added

- Optional Obsidian properties block (YAML frontmatter) on every exported
  adversary and environment file, for filtering with Obsidian Bases: new
  `--frontmatter` CLI flag and a matching web UI checkbox. The frontmatter
  `source` omits the page number so each book filters as a single source.
```

- [ ] **Step 2: Full suite, one last time**

Run: `.venv/bin/python -m unittest discover tests -v 2>&1 | tail -5`
Expected: OK

- [ ] **Step 3: Regenerate the Hope & Fear exports with frontmatter**

```bash
.venv/bin/python convert.py docs/HF-adversariesonly.pdf -o output/hope-and-fear --index --overwrite --quiet --frontmatter
head -20 output/hope-and-fear/Ahuizotl.md
head -15 output/hope-and-fear/environments/Abandoned_Mine.md
```

Expected: 163 files; both samples begin with `---`, `source: "Hope and Fear"` with no page number in the frontmatter, and the ```` ```daggerheart ```` block below still shows `source: "Hope and Fear, p. N"`.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "Add frontmatter feature to changelog"
```

(`output/` regeneration is committed only if the repo already tracks those files — check `git status`; if `output/` is untracked or ignored, leave it out.)
