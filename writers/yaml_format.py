"""Formatting helpers shared by the Markdown writers.

String scalars are JSON-encoded, which is a strict subset of YAML 1.2, so the
emitted YAML stays valid without a PyYAML dependency.
"""
from __future__ import annotations

import json
import re
from typing import Any

# DEL, the C1 control block, and the two noncharacters YAML excludes from its
# printable set. json.dumps leaves all of these literal when ensure_ascii is
# off, and a single stray one makes the whole block unparseable.
_YAML_FORBIDDEN_RE = re.compile(r"[\x7f-\x9f￾￿]")


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


# Apostrophe variants that sit inside a word. Books typeset the possessive as
# U+2019 rather than the ASCII quote; matching only the latter split
# "Archmage’s" into two words and capitalised the tail as "Archmage’S". This
# affects display text only; filenames are built separately by
# ``models/naming.py``, which drops apostrophes altogether.
_APOSTROPHES = "'‘’ʼ`´"

_APOSTROPHE_CLASS = f"[{re.escape(_APOSTROPHES)}]"

# A word may carry more than one apostrophe — "O'Connor's" is both a name
# element and a possessive — so the segment repeats.
_WORD_RE = re.compile(rf"[A-Za-z]+(?:{_APOSTROPHE_CLASS}[A-Za-z]+)*")

_APOSTROPHE_SPLIT_RE = re.compile(f"({_APOSTROPHE_CLASS})")

# Endings that stay lowercase after an apostrophe. Anything longer is a name
# element rather than a contraction — "O'Connor", "D'Artagnan" — and keeps its
# capital, so the rule cannot be "lowercase whatever follows an apostrophe".
_CONTRACTION_ENDINGS = frozenset({"s", "t", "d", "m", "ll", "re", "ve"})


def display_name(name: str | None) -> str:
    if not name:
        return "Unknown"
    return _WORD_RE.sub(lambda match: _title_word(match.group(0)), name)


def _title_word(word: str) -> str:
    # Alternates segment, apostrophe, segment, ... so the separators are the
    # odd indices and the segments after the first are the even ones.
    parts = _APOSTROPHE_SPLIT_RE.split(word)

    cased = [_capitalize(parts[0])]
    for apostrophe, segment in zip(parts[1::2], parts[2::2]):
        if segment.lower() in _CONTRACTION_ENDINGS:
            cased.append(f"{apostrophe}{segment.lower()}")
        else:
            cased.append(f"{apostrophe}{_capitalize(segment)}")

    return "".join(cased)


def _capitalize(word: str) -> str:
    return word[:1].upper() + word[1:].lower()
