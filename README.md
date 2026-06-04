# Daggerheart Adversary Converter

A local converter for turning [Daggerheart](https://www.daggerheart.com/) adversary stat blocks from PDF or Markdown sources into files that [Arrow's Adversary Bank](https://github.com/arrowedisgaming/arroweds-adversary-bank/) can read from an Obsidian library folder.

## What It Does

Daggerheart adversary stat blocks are typically published in dense PDFs or large multi-entry Markdown documents. This tool:

- **Extracts** adversary stat blocks from PDFs (with smart two-column layout detection)
- **Parses** multi-adversary Markdown files (both community and standardized formats)
- **Converts** each adversary into its own Arrow's Adversary Bank-readable Markdown file
- **Normalizes** existing adversary files to a standard format
- **Attributes** sources by searching original PDFs/MDs for each adversary name and page number
- **Exports** optional combined JSON for Arrow's Adversary Bank and older BeastVault-style workflows
- **Generates** master index files across all converted adversaries

### Example Output

Each adversary gets its own `.md` file with a `daggerheart` YAML code block. Arrow's Adversary Bank scans these from the library folders you choose in Obsidian.

````markdown
# JAGGED KNIFE LACKEY

```daggerheart
name: "JAGGED KNIFE LACKEY"
tier: 1
type: "Minion"
desc: "A thief with simple clothes and small daggers, eager to prove themselves."
difficulty: 9
attack: -2
weapon: "Daggers"
range: "Melee"
damage: "2 phy"
hp: 1
stress: 1
xp: "Thief +2"
motives: "Escape, profit, throw smoke"
features:
  - name: "Minion (3)"
    type: "Passive"
    desc: "The Lackey is defeated when they take any damage."
```
````

## Getting Started

### Easy install

1. Download this project as a ZIP from GitHub.
2. Unzip it somewhere stable, like `Documents`, `Desktop`, or your RPG tools folder.
3. Open the unzipped folder.
4. Run the quickstart for your OS:
   - Mac: double-click `Start Converter (Mac).command`
   - Windows: double-click `Start Converter (Windows).bat`
5. On first run, the quickstart creates `.venv` and installs `pdfplumber` and `openpyxl`.
6. Your browser opens the converter at `http://127.0.0.1:8742`.
7. Drag in a `.pdf` or `.md` file.
8. Keep `Arrow's Adversary Bank Markdown` checked.
9. Click `Convert`.
10. Use the generated files in `output/web-convert`.

### Use the output in Obsidian

1. Install [Arrow's Adversary Bank](https://github.com/arrowedisgaming/arroweds-adversary-bank/) in Obsidian.
2. Copy the generated `.md` files, or the whole generated folder, into your Obsidian vault.
3. In Obsidian, open `Settings` > `Arrow's Adversary Bank`.
4. Under `Homebrew library`, choose the folder that contains the generated files.
5. Run `Refresh library` from Arrow's Adversary Bank.
6. Use `Insert adversary from library` and search for the converted adversaries.

The optional `adversaries.json` export also works as a combined library file, but the generated Markdown files are now the main path.

### Manual setup

If you prefer the terminal:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

On Windows, use:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

### Convert a source file to individual adversary files

```bash
python convert.py source.pdf -o output/folder/         # Convert a PDF
python convert.py source.md -o output/folder/           # Convert a multi-adversary Markdown file
python convert.py source.pdf --list                     # List detected adversaries without writing files
python convert.py source.pdf --report                   # Show a validation report
python convert.py source.pdf -o output/ --index         # Also generate a master index
python convert.py source.pdf -o output/ --overwrite     # Overwrite existing files
python convert.py source.pdf --adversary-bank           # Export combined JSON only
python convert.py source.pdf -o output/ --adversary-bank  # MD files + combined JSON
python convert.py source.pdf --adversary-bank custom.json # Custom JSON filename
python convert.py source.pdf -o output/ --readable-markdown # Older readable stat block files
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
.venv/bin/python app.py                  # Start server on port 8742, auto-opens browser
.venv/bin/python app.py --port 9000      # Custom port
.venv/bin/python app.py --no-browser     # Don't auto-open browser
```

The web UI runs a local server at `http://127.0.0.1:8742`. It provides the same conversion pipeline as the CLI tools through a browser interface.

You must supply your own source files in the `sources/` directory. The `output/` directory is created automatically during conversion.

### Adversary Reference Table

A standalone script that generates a self-contained HTML reference page from an Excel spreadsheet of adversary data. The output (`adversaries.html`) is a dark-themed, single-file web app you can open directly in a browser — no server required.

**Features:**
- Sortable columns (click any header)
- Filter by tier, type, and difficulty (dropdowns), attack bonus and thresholds (exact match), or damage dice (substring match)
- Global text search across all fields
- Automatic linking of adversary names to their entries in [Old Gus's Daggerheart SRD](https://callmepartario.github.io/og-dhsrd/)

```bash
python3 generate_adversaries_html.py                           # Default: sources/daggerheart_adversaries.xlsx
python3 generate_adversaries_html.py path/to/custom.xlsx       # Custom spreadsheet path
```

The spreadsheet must contain a sheet named `daggerheart_adversaries` with headers in the first row. The script fetches the SRD page at build time to resolve adversary links.

## Project Structure

```
dhadvconverter/
├── convert.py                          # CLI: Parse sources -> individual .md files
├── normalize.py                        # CLI: Re-format existing .md files to standard
├── app.py                              # Web UI: Local HTTP server (stdlib only)
├── index.html                          # Web UI: Single-file browser interface
├── Start Converter (Mac).command       # macOS: Double-click launcher for web UI
├── Start Converter (Windows).bat       # Windows: Double-click launcher for web UI
├── generate_adversaries_html.py        # Generates adversaries.html from Excel data
├── adversaries.html                    # Generated: sortable/filterable adversary reference
├── _SAMPLE.md                          # Reference: standardized output format (SRD content)
├── models/
│   └── adversary.py                    # Adversary, Attack, Feature dataclasses
├── parsers/
│   ├── pdf_parser.py                   # PDF extraction with column detection
│   ├── md_parser.py                    # Markdown format parsing
│   └── text_cleaner.py                 # Unicode normalization, OCR artifact removal
├── writers/
│   ├── adversary_bank_writer.py         # Writes Arrow's Adversary Bank Markdown
│   ├── markdown_writer.py              # Writes standardized adversary format
│   ├── beastvault_writer.py            # Writes combined JSON library export
│   └── index_generator.py              # Generates master/type index files
├── output/                             # Converted adversary files (gitignored)
├── utils/
│   └── source_finder.py                # Source attribution lookup
├── LICENSE                             # GNU GPLv3
├── .gitignore
└── requirements.txt
```

## License

The **code** in this project (all `.py` files, documentation, and project configuration) is licensed under the [GNU General Public License v3.0 (GPLv3)](https://www.gnu.org/licenses/gpl-3.0.html). You are free to use, modify, and distribute this software, provided that any derivative works are also distributed under the GPLv3. See [LICENSE](LICENSE) for the full legal text.

The **sample stat block** (`_SAMPLE.md`) contains Daggerheart SRD content used under the Darrington Press Community Gaming License (CGL). This content is not covered by the GPLv3 license — it remains © Darrington Press, and its use is governed by the CGL terms.

*This work includes material taken from the Daggerheart System Reference Document by Darrington Press. Daggerheart is © Darrington Press. All rights reserved.*

## Content Ownership

**This tool is a format converter, not a content source.** It is designed to help you convert adversary stat blocks that **you already own or have the right to use** into a more convenient format for personal use at the table.

- Do **not** use this tool to redistribute copyrighted content you do not have rights to share.
- Daggerheart is a product of Darrington Press. Adversary stat blocks from official Daggerheart publications are the intellectual property of their respective creators.
- Community-created adversary content is the intellectual property of its respective authors. Respect their licensing terms.

**Use this tool responsibly and only on content you own or are licensed to convert.**
