# Daggerheart Adversary Converter

Converts Daggerheart TTRPG adversary stat blocks from PDF and multi-adversary Markdown sources into standardized individual Markdown files and BeastVault-compatible JSON. Includes tools for normalization, source attribution, and index generation.

## Directory Structure

```
dhadvconverter/
├── models/
│   └── adversary.py          # Adversary, Attack, Feature dataclasses
├── parsers/
│   ├── md_parser.py          # Parses standardized + Menagerie MD formats
│   ├── pdf_parser.py         # PDF extraction with gap-based column detection
│   └── text_cleaner.py       # Unicode normalization, OCR fixes, artifact removal
├── writers/
│   ├── __init__.py            # Package init (exports MarkdownWriter, IndexGenerator)
│   ├── markdown_writer.py    # Writes standardized adversary format
│   ├── beastvault_writer.py  # Writes BeastVault-compatible JSON export
│   └── index_generator.py    # Generates master/type index files
├── output/                    # Generated data only (gitignored)
├── utils/
│   └── source_finder.py      # Source attribution lookup in PDFs/MDs
├── sources/                   # Reference source files (do not modify)
│   ├── Age-of-Umbra-Adversaries.pdf
│   ├── Adversaries-Environments-v1.5-.pdf
│   ├── martialadversaries-compressed.pdf
│   ├── undeadadversaries-compressed.pdf
│   └── Menagerie_of_Mayhem-MUnderwood.md
├── convert.py                 # CLI: Parse sources → .md files + BeastVault JSON
├── normalize.py               # CLI: Re-format existing .md files to standard
├── app.py                     # Web UI: Local HTTP server (stdlib only)
├── index.html                 # Web UI: Single-file browser interface
├── Start Converter (Mac).command       # macOS: Double-click launcher for web UI
├── Start Converter (Windows).bat       # Windows: Double-click launcher for web UI
├── _SAMPLE.md                 # Reference: standardized output format (SRD content)
├── LICENSE                    # CC BY-SA 4.0
├── .gitignore                 # Python + project-specific ignores
└── requirements.txt           # pdfplumber
```

## CLI Tools

### convert.py — Convert source files to individual adversary files

```bash
python convert.py source.pdf -o output/           # Convert PDF
python convert.py source.md -o output/            # Convert multi-adversary MD
python convert.py source.pdf --list               # List adversaries without converting
python convert.py source.pdf --report             # Show validation report
python convert.py source.md -o output/ --index    # Also generate master index
python convert.py source.pdf -o output/ --overwrite  # Overwrite existing files
python convert.py source.pdf --beastvault           # Export BeastVault JSON only
python convert.py source.pdf -o output/ --beastvault  # MD files + BeastVault JSON
python convert.py source.pdf --beastvault custom.json  # Custom JSON filename
```

Flags: `-o/--output`, `--list/-l`, `--report`, `--index/-i`, `--overwrite`, `--quiet/-q`, `--beastvault [FILENAME]`

### normalize.py — Re-normalize existing adversary files

```bash
python normalize.py .                    # Normalize all .md files in current dir
python normalize.py . --backup           # Create .bak before modifying
python normalize.py . --dry-run          # Preview changes without writing
python normalize.py . --add-sources      # Add source attribution from sources/
python normalize.py . --report           # Validation report only
```

Flags: `--backup/-b`, `--dry-run/-n`, `--add-sources/-s`, `--report/-r`, `--quiet/-q`

### Web UI — Browser-based converter (no terminal required)

```bash
# macOS: Double-click "Start Converter (Mac).command" in Finder
# Or launch manually:
python3 app.py                  # Start server on port 8742, auto-opens browser
python3 app.py --port 9000      # Custom port
python3 app.py --no-browser     # Don't auto-open browser
```

`app.py` is a stdlib-only HTTP server (no new dependencies) serving `index.html` at `http://127.0.0.1:8742`. It imports and calls the same pipeline functions as the CLI tools.

**Routes:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve `index.html` |
| GET | `/api/sources` | List files in `sources/` with display names |
| POST | `/api/convert` | Upload/select source → parse → write output files |

**Key design:**
- `parse_source_safe()` wraps `parse_source()` to raise exceptions instead of `sys.exit(1)`
- Manual multipart parser (stdlib, no `cgi` module — removed in Python 3.13)
- File uploads saved to `tempfile.NamedTemporaryFile`, cleaned up in `finally`
- Existing sources read directly from `sources/` (no upload needed)
- Default output: `output/web-convert/`

## Data Model (models/adversary.py)

- **Adversary**: name, tier, adversary_type, description, motives_tactics, difficulty, threshold_minor/major, hp, stress, attack, experience, features, source_name/page
- **Attack**: modifier ("+4"), weapon_name, range, damage — parsed from pipe-separated string
- **Feature**: name, feature_type (Passive/Action/Reaction/Evolution), description

## Standardized Output Format

```markdown
# ADVERSARY NAME

***Tier X Type***
*Optional description.*
**Motives & Tactics:** Description text

> **Difficulty:** N | **Thresholds:** minor/major | **HP:** N | **Stress:** N
> **ATK:** +mod | **Weapon:** Range | damage
> **Experience:** Skill +N, Skill +N

## FEATURES

***Feature Name - Type:*** Description text.

---

*Source: Source Name, p. N*
```

Key formatting rules:
- Name is UPPERCASE in `#` header
- Tier line uses `***triple bold***` with two trailing spaces for line break
- Description is `*italic*` with trailing spaces (only if present)
- Stats use `>` blockquote with `|` pipe separators and trailing spaces
- ATK line only appears if attack data exists; Experience only if present
- Features use `***Name - Type:***` format (triple bold, hyphen separator)
- Source attribution is optional, separated by `---` horizontal rule

## Source Configuration (utils/source_finder.py)

```python
SOURCE_CONFIGS = {
    'Age-of-Umbra-Adversaries.pdf': {'display_name': 'Age of Umbra Adversaries', 'type': 'pdf'},
    'Adversaries-Environments-v1.5-.pdf': {'display_name': 'Adversaries: Environments v1.5', 'type': 'pdf'},
    'Menagerie_of_Mayhem-MUnderwood.md': {'display_name': 'Menagerie of Mayhem', 'type': 'md'},
    'martialadversaries-compressed.pdf': {'display_name': 'Martial Adversaries', 'type': 'pdf'},
    'undeadadversaries-compressed.pdf': {'display_name': 'Undead Adversaries', 'type': 'pdf'},
}
```

Attribution format: `*Source: Display Name, p. X*` or `*Source: Display Name*` (no page for MD sources)

## Skip Lists (normalize.py)

```python
SKIP_FILES = {'_SAMPLE.md', 'Adversaries_Master_Index.md', 'README.md', 'CLAUDE.md'}
SKIP_DIRS = {'environments', 'sources', '.claude', 'martial', 'undead', 'age-of-umbra', 'misc'}
```

Also skips files starting with `_` and `output/` subdirectories.

## Known Gotchas

### PDF Text Extraction
- **Unicode minus sign**: pdfplumber extracts `−` (U+2212) not `-` (U+002D). TextCleaner normalizes this, but be aware when adding new character handling.
- **En-dash/em-dash**: Also normalized to hyphens by TextCleaner (`–` → `-`, `—` → `-`).
- **Column detection**: Uses gap-based splitting (finds largest x-position gap in center 60% of page). Previous midpoint heuristic caused column interleaving.
- **Ligature splitting**: PDF text often has `fi` → `fi ` (e.g., "fi re" instead of "fire"). TextCleaner handles some cases.
- **Adversary names with commas/colons**: Names like "XERO, CASTLE KILLER" require comma in the ALL-CAPS detection regex. Colons also allowed for names like "DRAGON LICH: DECAY-BRINGER".
- **Title Case names**: Martial/Undead PDFs use Title Case names (e.g., "Bone Swarm") instead of ALL CAPS. Block splitting uses Tier-line backward lookup (primary) with ALL-CAPS as fallback.
- **Multi-line names**: Some names span two lines (e.g., "Dragon Lich:" + "Decay-Bringer"). `_parse_adversary_block` detects trailing colons and concatenates the next line.
- **Front/back matter noise**: PDFs with "Credits", "Adversary Stat Blocks", or "Encounter" pages produce a few garbage entries (all with 5 validation issues). These are harmless.

### Feature Parsing
- **PDF features**: Regex requires colon after type keyword (`- Passive:`) to prevent lazy quantifier from stopping too early.
- **MD features**: Menagerie uses `*Name - Type*:` (single asterisk); standardized uses `***Name - Type:***` (triple). Both are handled.
- **"Evolution" type**: Some adversaries (Mountain Troll) have Evolution features with inline stat blocks that can confuse the parser.

### Data Format Edge Cases
- **Non-dice damage**: Some attacks use "1 Stress" instead of dice notation — `Attack.from_string()` has a fallback for this.
- **Weapon/range separator**: Most use colon (`Wand: Far`), but some PDFs use hyphen (`Staff - Far`). Both are handled.
- **Environments**: Grand Feast, Heist, Crystal Wasteland, City of Portals are "Environment" stat blocks that intentionally lack HP/Stress/Thresholds. Their validation issues are expected. Environment types include Traversal, Event, and Exploration.
- **Horde types**: Include parenthetical like `Horde (3/HP)` or `Horde (1d4+1/HP)` — the Tier regex captures the full string including parenthetical.

## Dependencies

- **Python 3.10+** (uses `list[]` type hints, dataclasses)
- **pdfplumber** (optional, required only for PDF parsing): `pip install pdfplumber`
