# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.1] - 2026-07-22

### Fixed

- Adversaries whose description or motives contained the word "attack" lost their entire ATK line. Only the first case-insensitive match for the label was considered, so "defends itself from **attack**ers" was found before the real `ATK:` line and, carrying no pipe separators, silently discarded the attack. Every labelled candidate is now considered and the first one carrying pipes wins. In *Hope and Fear* this affected the Fungispunj Sporeling, Entombed Cat Beast, Sprite, and Lamia; all 135 adversaries now convert with an attack.
- `Attack.from_string` now accepts a negative modifier typeset with a Unicode minus sign (U+2212) or a dash rather than a hyphen, normalising it to ASCII instead of reading it as a nameless weapon. Both file-reading paths already stripped these characters during text cleanup, so no source converted differently before; this hardens the shared grammar itself, which callers reach directly. Only a field that is entirely a modifier is rewritten, so dashes in weapon and damage text are untouched.

## [0.4] - 2026-07-22

### Added

- Support for the *Hope and Fear* expansion, which the parser previously extracted **zero** records from. All 163 stat blocks (135 adversaries, 28 environments) now convert with no validation warnings.
- Environments are a first-class record type. `models/environment.py` adds `Environment` and `EnvironmentFeature`, carrying `impulses`, `potential_adversaries`, and the italic GM question prompts that follow each feature.
- Environments are written to an `environments/` subfolder of the output directory, so an Obsidian library can point at adversaries, environments, or both. They also get their own section in the generated index and are appended to the combined JSON export.
- `parsers/pdf_text.py` — font-aware extraction layer, split out of `pdf_parser.py`. Classifies each line by its typography, which is what makes GM question prompts and decorative name art distinguishable from body text.
- `models/parse_result.py` — `ParseResult`, the shared return type for both parsers.
- `tests/test_pdf_text.py`, `tests/test_environment_parsing.py`, and `tests/test_hope_and_fear_integration.py`. The integration test skips unless the source PDF is present, since `docs/` is git-ignored.
- `writers/adversary_bank_writer.py` — new Markdown writer that emits Arrow's Adversary Bank YAML code blocks. Uses a stdlib-only YAML emitter (JSON-encoded scalars) to keep the project zero-dependency.
- `tests/test_adversary_bank_writer.py` — covers escape correctness, dict-list indentation, variable attack modifiers, and empty-field handling.

### Changed

- **Breaking:** `PDFParser.parse_file` and `MDParser.parse_file` now return a `ParseResult` with separate `adversaries` and `environments` lists instead of a flat list. `MDParser.parse_adversaries` still returns a plain list for callers that only want adversaries.
- `Adversary` gains `thresholds_raw`, preserving thresholds the book prints as text. Minions print `Thresholds: None` and adversaries destroyed at Major print a half pair such as `5/None`; neither survives as two integers, and both previously registered as missing data.
- `BeastvaultWriter` formats environments from `Environment` objects rather than inferring them from absent HP, replacing a heuristic that disagreed with the one in `PDFParser`.
- **Breaking:** Output filenames now contain only `A-Z`, `a-z`, `0-9` and `_`, so they need no quoting in a shell and survive any filesystem or sync tool. Spaces and punctuation become single underscores and apostrophes are dropped, so `ALCHEMIST'S ABANDONED WORKSHOP` is written as `Alchemists_Abandoned_Workshop.md` rather than `Alchemists Abandoned Workshop.md`. Accented letters degrade to ASCII (`Café` becomes `Cafe`) instead of being deleted. The collision suffix changed to match: `Name_1.md`, not `Name (1).md`. Re-converting an existing library produces renamed files; delete the old output folder first to avoid keeping both.
- Filename generation moved to `models/naming.py`, shared by `Adversary` and `Environment` instead of being duplicated in each.
- Raised the web UI upload limit from 50 MB to 60 MB. The *Hope and Fear* adversaries chapter is ~57 MB, so uploading it through the browser previously failed; it now converts without having to route the file through `sources/`.
- **Breaking:** Default per-adversary Markdown output now emits a `daggerheart`-fenced YAML code block readable by [Arrow's Adversary Bank](https://github.com/arrowedisgaming/arroweds-adversary-bank/) in Obsidian. Pass `--readable-markdown` to restore the previous human-readable stat-block format.
- Renamed the JSON export flag to `--adversary-bank`; `--beastvault` is kept as a deprecated alias and now prints a one-line warning on stderr.
- Web UI labels updated: "Markdown files" → "Arrow's Adversary Bank Markdown"; "BeastVault JSON" → "Combined JSON library". The internal form field name `beastvault` is preserved for API stability.
- Launcher scripts (`Start Converter (Mac).command`, `Start Converter (Windows).bat`) now bootstrap a local `.venv` and install dependencies on first run.

### Fixed

- PDF digits rendered from the Private Use Area are now decoded. Display fonts in *Hope and Fear* map tier numbers, horde and minion counts, and countdown values to `U+E53F` and `U+E541`–`U+E549` with no `ToUnicode` entry, so `Tier 1 Skulk` extracted as `Tier  Skulk` and every block failed to start.
- Ligatures no longer split words. pdfplumber emits `fi`/`fl` ligatures as separate words with a zero x-gap, producing `Ruffi ans`, `fi nd`, and `battlefi eld`. Words are now joined by measured gap rather than unconditionally spaced, replacing a per-word blocklist.
- Bold labels no longer separate from their values. Fixed-bucket line grouping split one visual line in two and sorted the value above its label, yielding `Avoid, escape, misdirect` above `Motives & Tactics:`.
- Text parked outside the page box is discarded. *Hope and Fear* page 27 carries a hidden duplicate of the Roc at negative x, which never renders but interleaved with the real columns and corrupted both stat blocks on the page.
- Feature names are matched at line start instead of anywhere in the block, so a name can no longer begin mid-sentence and absorb preceding damage text — `...1d8+1 phy` followed by `Double Swipe - Action:` produced a feature named `phy Double Swipe`. The name pattern also accepts typographic apostrophes and hyphens, which previously truncated `Into the Spider's Web` to `s Web`.
- Running feet with a leading folio (`86 Chapter 3: Tier 3 Adversaries`) are dropped rather than appended to the preceding feature's description.
- `Stress: None` parses as zero rather than missing data, so adversaries that can never mark Stress (Spellbound Armor) are no longer discarded as incomplete.
- Environment difficulties that aren't numbers are preserved — the Duel event prints `Difficulty: Special (see "Relative Strength")`.
- Names wrapping across two heading lines are rejoined, so `ALCHEMIST'S ABANDONED WORKSHOP` no longer truncates to its first line.
- The font-aware extraction path no longer skips the cleanup the plain-text path performs. It had stopped removing bare page numbers and repeated running heads, and stopped rejoining words hyphenated across a line break (`under-` / `ground`), affecting every PDF rather than only *Hope and Fear*. Cleanup now runs per column, so a hyphen at the foot of one column cannot join to the head of the next.
- A labelled environment field no longer swallows the next label when column extraction puts both on one line: `Difficulty: 11 Potential Adversaries: Merchant, Guard` previously parsed the whole remainder as the difficulty and dropped the roster, while still passing validation.
- An adversary/environment section header carried over from an earlier page no longer overrides an unambiguous field shape. A stale `TIER n ADVERSARIES` header caused a `Social` environment to be parsed as an adversary and then silently discarded for lacking HP.
- Feature names containing a colon (`Phase 1: The Trap`) are matched instead of rejected. A block whose only features were named that way was dropped entirely.
- `--report` now includes environments; their validation issues were previously omitted from the report.
- `Attack.from_string` now recognizes variable attack modifiers like `+2d4` and `+2d4+1`; both the JSON and Markdown writers preserve them as strings instead of dropping them.
- `MDParser._parse_features` no longer absorbs trailing source footer text (`---`, `*Source:`, `*This stat block is...`) into the last feature's description.
- **`normalize.py` no longer destroys Arrow's Adversary Bank files.** `MDParser` reads only the heading from a `daggerheart` block, so normalizing one rewrote it as an empty stat block and discarded everything else. Because that format is now the default output, running `normalize.py` over a converted library — the workflow the README describes — silently destroyed it. Such files are detected and skipped.
- `normalize.py` no longer rewrites files that are not stat blocks at all. The generated index was destroyed because `SKIP_FILES` named `Adversaries_Master_Index.md` while `IndexGenerator` writes `Adversaries_Index.md`, and campaign notes containing a `## FEATURES` heading lost their surrounding prose. Normalizing now requires two independent core stats before touching a file, rather than relying on a filename list.
- Variable attack modifiers survive the PDF path. `ATK: +2d4 | …` parsed the modifier with a plain `\d+` and silently truncated it to `+2`, contradicting the support added for `Attack.from_string`. Both paths now share one grammar, and unsigned modifiers (`ATK: 2 | …`) are still accepted.
- A section header sitting between two stat blocks is no longer swept into the preceding block, where it was appended to that block's last feature description.
- The web UI accepts a quoted multipart boundary (`boundary="…"`, permitted by RFC 2045). The quotes were left in place, so the delimiter never matched and the upload was silently corrupted. A body whose delimiter is absent is now rejected rather than parsed into garbage.
- YAML scalars escape DEL and the C1 control block (`\x7f`–`\x9f`). `json.dumps` passes those through literally and YAML forbids them, so a single stray character made a whole stat block unparseable.
- Empty lists and dicts emit `[]` and `{}` instead of a bare key, which parsed back as `null`.
- An adversary and an environment sharing a name no longer collapse to one entry in the returned write map, which under-reported the converted file count.

## [0.3] - 2026-04-04

### Changed

- Redesigned adversaries page with warm dark palette (brown-toned backgrounds, parchment-white text, rich gold accents)
- Added subtle grain texture overlay for tactile quality
- Serif italic title with crossed swords icon and decorative gold rule
- Grouped filter controls into Classification and Statistics sections with visual dividers
- Search input now features a magnifying glass icon and larger hit area
- Subtler table row striping with gold left-accent on hover
- More prominent adversary name column styling
- Deep red table header border for visual separation
- Simplified footer from card to border-top separator
- Refactored filter control building from innerHTML to safe DOM methods

## [0.2] - 2026-03-14

### Changed

- Security, accessibility, and design system improvements
- Accessibility and security fixes
- Filter fixes

## [0.1] - 2026-02-22

### Added

- Initial release with adversary HTML generator
- Filterable and sortable adversary table
- SRD link integration
