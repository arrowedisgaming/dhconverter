# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- **Breaking:** Default per-adversary Markdown output now emits a `daggerheart`-fenced YAML code block readable by [Arrow's Adversary Bank](https://github.com/arrowedisgaming/arroweds-adversary-bank/) in Obsidian. Pass `--readable-markdown` to restore the previous human-readable stat-block format.
- Renamed the JSON export flag to `--adversary-bank`; `--beastvault` is kept as a deprecated alias and now prints a one-line warning on stderr.
- Web UI labels updated: "Markdown files" → "Arrow's Adversary Bank Markdown"; "BeastVault JSON" → "Combined JSON library". The internal form field name `beastvault` is preserved for API stability.
- Launcher scripts (`Start Converter (Mac).command`, `Start Converter (Windows).bat`) now bootstrap a local `.venv` and install dependencies on first run.

### Added

- `writers/adversary_bank_writer.py` — new Markdown writer that emits Arrow's Adversary Bank YAML code blocks. Uses a stdlib-only YAML emitter (JSON-encoded scalars) to keep the project zero-dependency.
- `tests/test_adversary_bank_writer.py` — covers escape correctness, dict-list indentation, variable attack modifiers, and empty-field handling.

### Fixed

- `Attack.from_string` now recognizes variable attack modifiers like `+2d4` and `+2d4+1`; both the JSON and Markdown writers preserve them as strings instead of dropping them.
- `MDParser._parse_features` no longer absorbs trailing source footer text (`---`, `*Source:`, `*This stat block is...`) into the last feature's description.
- PDF validation no longer silently drops environment-style records (`Traversal`, `Event`, `Exploration`): HP/Stress are now required only for combat adversaries, since environments have neither by design.

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
