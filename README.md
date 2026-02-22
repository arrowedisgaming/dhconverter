# Daggerheart Adversary Converter

A Python toolkit for converting [Daggerheart](https://www.daggerheart.com/) TTRPG stat blocks from PDF and multi-adversary Markdown sources into standardized, individual Markdown files.

## What It Does

Daggerheart adversary stat blocks are typically published in dense PDFs or large multi-entry Markdown documents. This tool:

- **Extracts** adversary stat blocks from PDFs (with smart two-column layout detection)
- **Parses** multi-adversary Markdown files (both community and standardized formats)
- **Converts** each adversary into its own clean, consistently-formatted Markdown file
- **Normalizes** existing adversary files to a standard format
- **Attributes** sources by searching original PDFs/MDs for each adversary name and page number
- **Exports** BeastVault-compatible JSON for use with the [BeastVault](https://github.com/ly0va/beastvault) community tool
- **Generates** master index files across all converted adversaries

### Example Output

Each adversary gets its own file in a readable, consistent format:

```markdown
# JAGGED KNIFE LACKEY

***Tier 1 Minion***
*A thief with simple clothes and small daggers, eager to prove themselves.*
**Motives & Tactics:** Escape, profit, throw smoke

> **Difficulty:** 9 | **Thresholds:** None | **HP:** 1 | **Stress:** 1
> **ATK:** -2 | **Daggers:** Melee | 2 phy
> **Experience:** Thief +2

## FEATURES

***Minion (3) - Passive:*** The Lackey is defeated when they take
any damage. For every 3 damage a PC deals to the Lackey, defeat
an additional Minion within range the attack would succeed against.

***Group Attack - Action:*** Spend a Fear to choose a target and
spotlight all Jagged Knife Lackeys within Close range of them.
Those Minions move into Melee range of the target and make one
shared attack roll. On a success, they deal 2 physical damage
each. Combine this damage.

---

*Source: Daggerheart System Reference Document*
```

## Getting Started

### Requirements

- **Python 3.10+**
- **pdfplumber** (only required for PDF parsing)

### Installation

```bash
pip install -r requirements.txt
```

No other dependencies.

### Convert a source file to individual adversary files

```bash
python convert.py source.pdf -o output/folder/         # Convert a PDF
python convert.py source.md -o output/folder/           # Convert a multi-adversary Markdown file
python convert.py source.pdf --list                     # List detected adversaries without writing files
python convert.py source.pdf --report                   # Show a validation report
python convert.py source.pdf -o output/ --index         # Also generate a master index
python convert.py source.pdf -o output/ --overwrite     # Overwrite existing files
python convert.py source.pdf --beastvault               # Export BeastVault JSON only
python convert.py source.pdf -o output/ --beastvault    # MD files + BeastVault JSON
python convert.py source.pdf --beastvault custom.json   # Custom JSON filename
```

### Normalize existing adversary files

```bash
python normalize.py directory/              # Re-format all .md files to the standard format
python normalize.py directory/ --backup     # Create .bak files before modifying
python normalize.py directory/ --dry-run    # Preview changes without writing
python normalize.py directory/ --add-sources  # Add source attribution from source files
python normalize.py directory/ --report     # Validation report only
```

### Web UI — Browser-based converter

No terminal required. Double-click the launcher for your OS:

- **Mac:** `Start Converter (Mac).command`
- **Windows:** `Start Converter (Windows).bat`

Or launch manually from a terminal:

```bash
python3 app.py                  # Start server on port 8742, auto-opens browser
python3 app.py --port 9000      # Custom port
python3 app.py --no-browser     # Don't auto-open browser
```

The web UI runs a local server at `http://127.0.0.1:8742` using only the Python standard library (no extra dependencies beyond pdfplumber for PDF parsing). It provides the same conversion pipeline as the CLI tools through a browser interface.

You must supply your own source files in the `sources/` directory. The `output/` directory is created automatically during conversion.

## Project Structure

```
dhadvconverter/
├── convert.py                          # CLI: Parse sources -> individual .md files
├── normalize.py                        # CLI: Re-format existing .md files to standard
├── app.py                              # Web UI: Local HTTP server (stdlib only)
├── index.html                          # Web UI: Single-file browser interface
├── Start Converter (Mac).command       # macOS: Double-click launcher for web UI
├── Start Converter (Windows).bat       # Windows: Double-click launcher for web UI
├── _SAMPLE.md                          # Reference: standardized output format (SRD content)
├── models/
│   └── adversary.py                    # Adversary, Attack, Feature dataclasses
├── parsers/
│   ├── pdf_parser.py                   # PDF extraction with column detection
│   ├── md_parser.py                    # Markdown format parsing
│   └── text_cleaner.py                 # Unicode normalization, OCR artifact removal
├── writers/
│   ├── markdown_writer.py              # Writes standardized adversary format
│   ├── beastvault_writer.py            # Writes BeastVault-compatible JSON export
│   └── index_generator.py              # Generates master/type index files
├── output/                             # Converted adversary files (gitignored)
├── utils/
│   └── source_finder.py                # Source attribution lookup
├── LICENSE                             # CC BY-SA 4.0
├── .gitignore
└── requirements.txt
```

## License

The **code** in this project (all `.py` files, documentation, and project configuration) is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/). You are free to share and adapt the code, provided you give appropriate credit and distribute any derivative works under the same license. See [LICENSE](CC-BY-SA4.txt) for the full legal text.

The **sample stat block** (`_SAMPLE.md`) contains Daggerheart SRD content used under the Darrington Press Community Gaming License (CGL). This content is not covered by the CC BY-SA 4.0 license — it remains © Darrington Press, and its use is governed by the CGL terms.

*This work includes material taken from the Daggerheart System Reference Document by Darrington Press. Daggerheart is © Darrington Press. All rights reserved.*

## Content Ownership

**This tool is a format converter, not a content source.** It is designed to help you convert adversary stat blocks that **you already own or have the right to use** into a more convenient format for personal use at the table.

- Do **not** use this tool to redistribute copyrighted content you do not have rights to share.
- Daggerheart is a product of Darrington Press. Adversary stat blocks from official Daggerheart publications are the intellectual property of their respective creators.
- Community-created adversary content is the intellectual property of its respective authors. Respect their licensing terms.

**Use this tool responsibly and only on content you own or are licensed to convert.**
