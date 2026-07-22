# Hope & Fear Support — Design

Date: 2026-07-22

## Problem

`PDFParser` extracts **zero** records from the Daggerheart *Hope and Fear*
adversaries/environments chapter. Four distinct issues, plus a new record type.

### 1. Tier numbers are Private Use Area glyphs

The tier line extracts as `Tier  Skulk`. The digit is present but mapped to a PUA
codepoint in the `QuestaSlab-BoldItalic` subset font:

| Codepoint | Digit | Evidence |
| --------- | ----- | -------- |
| `U+E53F`  | 0     | rendered `Tier 4 Horde (10/HP)` |
| `U+E541`  | 1     | rendered; 32 tier lines under `TIER 1` header |
| `U+E542`  | 2     | rendered `Tier 2 Horde (5/HP)`; 33 lines under `TIER 2` |
| `U+E543`  | 3     | 28 lines under `TIER 3` header |
| `U+E544`  | 4     | 20 lines under `TIER 4` header |
| `U+E545`  | 5     | rendered `Tier 2 Horde (5/HP)` |
| `U+E546`  | 6     | rendered `Tier 4 Horde (6/HP)` |
| `U+E547`  | 7     | inferred from the contiguous run |
| `U+E548`  | 8     | rendered `Tier 1 Horde (8/HP)` |
| `U+E549`  | 9     | inferred from the contiguous run |

Cross-validating all 113 tier lines against their `TIER n ADVERSARIES` /
`TIER n ENVIRONMENTS` section headers produced zero mismatches.

Because `_split_into_adversary_blocks` requires `Tier\s+\d+` to identify a block
start, and the ALL-CAPS fallback also requires a nearby `Tier\s+\d+`, every block
fails to start. The same glyphs also break `Horde (3/HP)`, `Minion (3)`, and
`Countdown (4)` inside feature text.

### 2. Ligatures split words

pdfplumber emits `fi`/`fl` ligatures as separate words with a **zero** x-gap:
`Ruffi` (x1=373.5) + `ans` (x0=373.5). `_group_words_into_lines` joins every word
with a space, producing `Ruffi ans`, `fi nd`, `fl ying`, `off er`,
`battlefi eld`. `TextCleaner` special-cases `Diffi culty` and `fl ail` only.

### 3. Label/value lines swap

`round(top / 5) * 5` bucketing splits one visual line into two when its bold and
light runs differ slightly in `top`, and the value sorts above its label:

```
Avoid, escape, misdirect
Motives & Tactics:
```

### 4. Environments are a new record type

~30 blocks across tiers 1–4, types Traversal / Exploration / Event, with fields
the parser does not read: `Impulses:` (only `Motives & Tactics` is matched),
`Potential Adversaries:`, bulleted lists inside features, and italic GM question
prompts trailing each feature. Today those prompts would be silently glued onto
the end of the feature description.

### 5. Minor

`Thresholds: None` on minions, and decorative name art repeats the block name as
a stray line (`AHUIZOTL`, `BUGBOAR` twice on page 2).

## Key insight: fonts classify lines

Font name and size identify every line unambiguously, so question prompts and
name-art artifacts are detected by style rather than by guessing at regexes.

| Font | Size | Meaning |
| ---- | ---- | ------- |
| `EvelethCleanRegular` | 12 | Block name, and `TIER n ADVERSARIES/ENVIRONMENTS` header |
| `QuestaSlab-BoldItalic` | 9 | Tier/type line |
| `QuestaSans-LightItalic` | 8 | Flavor description |
| `QuestaSans-Bold` | 8 | Stat labels (`Impulses:`, `Difficulty:`) |
| `QuestaSans-BoldItalic` | 8 | Feature name + type |
| `QuestaSlab-Italic` | 7.5 | GM question prompts |
| `EllisHandRegular` | 7 | Decorative name art (duplicate-name artifact) |
| `EvelethCleanRegular` | 7.5 | Page number |

## Design

### Extraction layer — `parsers/pdf_text.py` (new)

Moves `_extract_page_with_columns`, `_detect_columns`, and
`_group_words_into_lines` out of `pdf_parser.py` (606 lines, currently doing
extraction, block splitting, and field parsing).

Three fixes land here:

- **PUA decoding.** A `str.translate` table applied to every extracted word.
  Fixes tier numbers, horde/minion counts, and countdown values in one place.
- **Ligature-aware joining.** Insert a space between adjacent words only when
  the x-gap exceeds a fraction of the font size. Generalizes past the current
  per-word blocklist.
- **Baseline clustering.** Replaces `round(top/5)*5` bucketing with greedy
  clustering over sorted `top` values.

Output is `list[PageLine]`, carrying `text` plus a `style` enum derived from the
dominant font/size of the line. `style` is `None` when a caller supplies raw
text, so block parsers degrade to the current regex heuristics and the existing
32 tests keep passing unchanged.

The PUA and ligature fixes are strict improvements for every book in the
Daggerheart line, not just Hope & Fear — both produce garbage in any PDF using
these Questa subset fonts.

### Model — `models/environment.py` (new)

```python
@dataclass
class EnvironmentFeature:
    name: str
    feature_type: str      # Passive | Action | Reaction
    description: str
    questions: list[str]

@dataclass
class Environment:
    name: str
    tier: Optional[int]
    environment_type: Optional[str]   # Traversal | Exploration | Event
    description: Optional[str]
    impulses: Optional[str]
    difficulty: Optional[int]
    potential_adversaries: Optional[str]
    features: list[EnvironmentFeature]
    source_name: Optional[str]
    source_page: Optional[int]
    parse_warnings: list[str]
```

`Adversary` is untouched. Two divergent environment heuristics are deleted:
`PDFParser.ENVIRONMENT_TYPES` / `_is_environment_type` (checks the type keyword)
and `BeastvaultWriter._is_environment` (checks for missing HP). Type identity
replaces both.

### Parsing — `parsers/pdf_parser.py`

`parse_file()` returns `ParseResult(adversaries, environments)`.

Block splitting is shared: find tier lines (digits now decode), track the current
`TIER n ADVERSARIES|ENVIRONMENTS` section header as a tier fallback and as a
routing hint, then dispatch each block by its type keyword to
`_parse_adversary_block` or the new `_parse_environment_block`.

Environment parsing reads `Impulses:`, `Potential Adversaries:`, and
`Difficulty:`; attaches trailing `QuestaSlab-Italic` lines to the preceding
feature as `questions`; and keeps bulleted `•` lines inside the feature
description.

### Writers and entry points

- `AdversaryBankWriter.format_environment()` emits `name`, `tier`, `type`,
  `desc`, `difficulty`, `impulses`, `potential_adversaries`, `source`, and
  `features` (each with `name`, `type`, `desc`, `questions`).
- `AdversaryBankWriter.write_multiple` writes environments to an
  `environments/` subfolder; adversaries stay at the output root.
- `BeastvaultWriter` formats `Environment` objects directly.
- `IndexGenerator` gains an Environments section.
- `convert.py` and `app.py` unpack `ParseResult`. `MDParser.parse_file` returns
  one too, for symmetry.

### Testing

Unit tests follow the existing synthetic-text-fixture style — no PDF binaries in
the repo — covering PUA decoding, ligature rejoining, line clustering,
environment field parsing, question attachment, and writer output.

An integration check runs against the real PDF and reports actual counts. It
skips when `docs/HF-adversariesonly.pdf` is absent, since `docs/` is git-ignored
and never committed.

## Decisions made

- Environments get a separate `Environment` dataclass rather than extending
  `Adversary` or continuing to shoehorn them through `motives_tactics`.
- Environment YAML mirrors the shape `BeastvaultWriter` already emits, extended
  with `potential_adversaries` and per-feature `questions`.
- Environments write to an `environments/` subfolder with their own index
  section, so an Obsidian library can point at either folder independently.
- The extraction layer is fixed rather than adding a Hope & Fear-specific
  parser, because the PUA and ligature bugs affect every book.
- `ParseResult` is a breaking return-type change, accepted deliberately; the CLI
  and web entry points are updated to match.

## Out of scope

- Reworking the two-column detection heuristic beyond the line-grouping fix.
- Changes to `normalize.py` beyond what `ParseResult` requires.
