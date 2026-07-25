# Obsidian Properties Frontmatter — Design

Date: 2026-07-25

## Problem

Exported per-record Markdown files carry their data only inside a
```` ```daggerheart ```` code block. Obsidian **Bases** reads note *properties*
(YAML frontmatter), not code blocks, so exported files cannot be filtered or
sorted in a Base.

A secondary problem: the code block's `source` value includes the page number
(`"undeadadversaries-compressed, p. 16"`). Used as a Base filter, every page
becomes a distinct source value. The frontmatter needs one source value per
book.

## Requirements

- Opt-in flag, off by default, available in both the CLI and the web UI.
- When on, every per-record file (adversaries and environments, in both the
  default Adversary Bank format and `--readable-markdown` format) starts with
  a YAML frontmatter block.
- Frontmatter `source` is the source name only — no page number.
- The ```` ```daggerheart ```` code block is unchanged, page number included.
- The index file and the combined JSON library get no frontmatter.

## Output format

Frontmatter is the first bytes of the file (an Obsidian requirement), before
the `# Title` heading.

Adversary fields, in order:
`name, tier, type, difficulty, hp, stress, attack, weapon, range, damage,
motives, desc, source, feature_count`

Environment fields, in order:
`name, tier, type, difficulty, impulses, potential_adversaries, desc, source,
feature_count`

````markdown
---
name: "Accursed Soul"
tier: 4
type: "Minion"
difficulty: 16
hp: 1
stress: 1
attack: 3
weapon: "Deathly Grasp"
range: "Melee"
damage: "10 mag"
motives: "Bring pain to the living, rage, gang up"
desc: "A tormented ghost unleashed as punishment or repayment for their actions in life."
source: "undeadadversaries-compressed"
feature_count: 4
---
# Accursed Soul

```daggerheart
...unchanged...
```
````

Rules:

- Strings are double-quoted with the same JSON-based escaping the code block
  already uses (valid YAML; Obsidian renders quoted values without quotes).
  This protects apostrophes, colons, and control characters in names and
  descriptions.
- Missing/empty fields are omitted rather than emitted blank, matching the
  existing `_set` semantics.
- `feature_count` is always present, `0` when the record has no features —
  it is a filtering field.
- `attack` keeps the existing int-when-possible coercion.
- Environment `difficulty` may be a string
  (`Special (see "Relative Strength")`); quoting handles it.

## Design

### New module — `writers/frontmatter.py`

Two functions returning the fenced block text (including both `---` lines and
a trailing newline):

- `adversary_frontmatter(adv: Adversary) -> str`
- `environment_frontmatter(env: Environment) -> str`

Each builds a flat dict in the field order above and emits it with the shared
YAML helpers. Source is `record.source_name` alone; when `source_name` is
missing the field is omitted.

### Shared YAML helpers — `writers/yaml_format.py`

`_yaml_lines`, `_yaml_dict_list_item`, `_yaml_scalar`, `_set`, and the
`_YAML_FORBIDDEN_RE` control-character guard move out of
`AdversaryBankWriter` into module-level functions here. `AdversaryBankWriter`
and `frontmatter.py` both import them; `MarkdownWriter` never has to import
the bank writer. Behavior is unchanged — this is a move, not a rewrite.

### Writers

`AdversaryBankWriter` and `MarkdownWriter`:

- `format_adversary(adv, frontmatter: bool = False)` /
  `format_environment(env, frontmatter: bool = False)` prepend the block when
  the flag is set.
- `write_adversary`, `write_environment`, `write_multiple`, and
  `write_environments` gain the same keyword and thread it through.

### Entry points

- `convert.py`: `convert_to_files(..., frontmatter: bool = False)` passes the
  flag to the writer calls (the `_write_records` callback binds it). New CLI
  flag:

  ```
  --frontmatter    Prepend an Obsidian properties block (YAML frontmatter)
                   to each file, for use with Obsidian Bases
  ```

- `app.py`: reads `frontmatter` from the form (default false, parsed with
  `_is_truthy` like `overwrite`) and passes it to `convert_to_files`.
- `index.html`: an "Obsidian properties (YAML frontmatter)" checkbox, off by
  default, posting the `frontmatter` field.

Untouched: `IndexGenerator`, `BeastvaultWriter`, `--adversary-bank` JSON
export.

## Testing

New `tests/test_frontmatter.py` in the existing synthetic-fixture style (no
PDF binaries):

- Adversary field set and order match the spec; extra fields (thresholds, xp,
  features) stay out.
- `source` has no page number even when `source_page` is set.
- Missing fields are omitted; `feature_count: 0` still appears.
- Environment variant, including string difficulty.
- Special characters (apostrophes, colons, control chars) stay valid YAML.
- Both writers: flag off → output byte-identical to today; flag on → block
  prepended before the heading.
- CLI: `--frontmatter` reaches the writers (patch or tmp-dir integration).
- Web: `frontmatter` form field is parsed and forwarded.

All existing tests must still pass. Output with the flag off is unchanged, so
no expected values change; tests that reach the moved YAML helpers through
`AdversaryBankWriter` internals may need only their import/attribute paths
updated.

## Decisions made

- Shared formatter module rather than a wrapper writer or a post-processing
  pass: one place defines the field set, both formats stay consistent.
- Frontmatter drops the page number; the code block keeps it. The two
  serve different purposes (filtering vs. reading).
- Field set follows the user's sample minus the page number; `thresholds` and
  `xp` are excluded from frontmatter (present in the code block).
- Flag default is off in both CLI and web UI.

## Out of scope

- Prettifying filename-derived source names (e.g.
  `undeadadversaries-compressed` → `Undead Adversaries`). Renaming the source
  file before converting achieves this today.
- Frontmatter for `Adversaries_Index.md` or the JSON library.
- Any change to the ```` ```daggerheart ```` block or `BeastvaultWriter`
  output.
