# Daggerheart Adversary Converter

A local converter that turns [Daggerheart](https://www.daggerheart.com/) adversary and environment stat blocks from PDF or Markdown sources into one Markdown file per creature — ready for [Arrow's Adversary Bank](https://github.com/arrowedisgaming/arroweds-adversary-bank/) in Obsidian.

Everything runs on your own machine. Nothing is uploaded anywhere.

## Quick Start (no terminal needed)

1. Download this project as a ZIP from GitHub and unzip it somewhere stable, like `Documents`.
2. Open the unzipped folder and double-click the launcher for your system:
   - **Mac:** `Start Converter (Mac).command`
   - **Windows:** `Start Converter (Windows).bat`
3. On first run it sets up `.venv` and installs `pdfplumber` and `openpyxl`. This takes a minute.
4. Your browser opens the converter at `http://127.0.0.1:8742`.
5. Drag a `.pdf` or `.md` file onto the drop zone.
6. Pick your options (see below), then click **Convert**.
7. Your files appear in `output/web-convert`.

**Leave the terminal window open while you work.** It *is* the converter — closing it stops the
server, and the page will tell you it can't reach it. If port 8742 is already busy the launcher
moves to the next free port and prints the address it actually used; open that one.

### The options in the web page

| Option | What it does |
| ------ | ------------ |
| **Output directory** | Where files are written, relative to the project folder. Default `output/web-convert`. |
| **Arrowed's Adversary Bank Markdown** | The main output: one `.md` file per adversary, each holding a `daggerheart` code block. Leave this checked. |
| **Combined JSON library** | Also write a single `adversaries.json` holding every record. Only needed for older BeastVault-style workflows. |
| **Master Index** | Also write `Adversaries_Index.md`, linking every converted record. |
| **Obsidian properties (YAML frontmatter)** | Adds a properties block to the top of every file so [Obsidian Bases](https://help.obsidian.md/bases) can filter and sort them. See [Obsidian properties](#obsidian-properties-for-bases). |
| **Overwrite existing files** | Replace files already in the output folder. When unchecked, repeat conversions are written alongside as `Name_1.md`, `Name_2.md`, and so on. |

The **Existing Sources** tab lists files you have placed in the project's `sources/` folder, so you
can reconvert a book without dragging it in again. You supply your own source files; none ship with
this tool.

## Use the output in Obsidian

1. Install [Arrow's Adversary Bank](https://github.com/arrowedisgaming/arroweds-adversary-bank/) in Obsidian.
2. Copy the generated files, or the whole generated folder, into your vault.
3. Open `Settings` → `Arrow's Adversary Bank`, and under `Homebrew library` choose the folder holding those files.
4. Run `Refresh library`, then use `Insert adversary from library`.

Sources containing environments write them to an `environments/` subfolder, so you can add
adversaries, environments, or both as library folders independently.

Filenames use only letters, digits, and underscores — `Alchemists_Abandoned_Workshop.md` — so they
are safe on any filesystem. The real name, punctuation and all, is preserved inside the file.

### Obsidian properties (for Bases)

Arrow's Adversary Bank reads the `daggerheart` code block, but Obsidian **Bases** filters on note
*properties*. Turn on **Obsidian properties** in the web page, or pass `--frontmatter` on the command
line, and every file gains a properties block above its heading:

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
source: "Hope and Fear"
feature_count: 4
---
# Accursed Soul

```daggerheart
name: "Accursed Soul"
tier: 4
...
source: "Hope and Fear, p. 16"
...
```
````

The code block is unchanged, so the plugin keeps working exactly as before.

Note that `source` in the **properties** block is the book alone, while the code block keeps the page
number. This is deliberate: with pages included, one book shows up in a Base as dozens of separate
sources (`Undead Adversaries, page 16`, `page 17`, …) instead of one you can filter on.

Environments get the fields that suit them instead: `impulses` and `potential_adversaries` in place
of the combat stats.

## Command line

Everything the web page does is available from the terminal. Use `.venv/bin/python` on Mac and
Linux, or `.venv\Scripts\python.exe` on Windows.

### `convert.py` — sources to individual files

```bash
.venv/bin/python convert.py SOURCE [-o OUTPUT] [flags]
```

`SOURCE` is a `.pdf` or a `.md` file holding many adversaries.

| Flag | What it does |
| ---- | ------------ |
| `-o`, `--output DIR` | Write files to `DIR`. Required unless you only want the JSON export. |
| `--frontmatter` | Prepend the Obsidian properties block to every file, for Obsidian Bases. |
| `--index`, `-i` | Also write `Adversaries_Index.md` in the output folder. |
| `--overwrite` | Replace existing files instead of writing numbered copies alongside them. |
| `--list`, `-l` | List the adversaries found and exit, writing nothing. |
| `--report` | Print a validation report of missing or suspect fields, writing nothing. |
| `--quiet`, `-q` | Don't print a line per file. |
| `--readable-markdown` | Write the older human-readable stat blocks instead of `daggerheart` code blocks. |
| `--adversary-bank [FILE]` | Also export a combined JSON library (default `adversaries.json` in the output folder). |
| `--beastvault [FILE]` | Deprecated alias for `--adversary-bank`. |

Examples:

```bash
# The usual run: one file per record, with an index
.venv/bin/python convert.py book.pdf -o output/book --index

# Same, plus Obsidian properties for Bases, replacing any previous run
.venv/bin/python convert.py book.pdf -o output/book --frontmatter --overwrite

# Look before converting
.venv/bin/python convert.py book.pdf --list
.venv/bin/python convert.py book.pdf --report

# Combined JSON only, no individual files
.venv/bin/python convert.py book.pdf --adversary-bank
```

### `normalize.py` — tidy files you already have

```bash
.venv/bin/python normalize.py [DIRECTORY] [flags]
```

Re-formats existing adversary `.md` files to the standard format. `DIRECTORY` defaults to the current
folder.

| Flag | What it does |
| ---- | ------------ |
| `--dry-run`, `-n` | Show what would change without writing anything. |
| `--backup`, `-b` | Write a `.bak` beside each file before changing it. |
| `--add-sources`, `-s` | Fill in source attribution by searching the `sources/` folder. |
| `--report`, `-r` | Print a validation report only. |
| `--quiet`, `-q` | Don't print a line per file. |

### `app.py` — the web server behind the page

```bash
.venv/bin/python app.py                  # Serve on port 8742 and open a browser
.venv/bin/python app.py --port 9000      # Use a specific port
.venv/bin/python app.py --no-browser     # Don't open a browser
```

If the chosen port is busy the server tries the next three and prints the address it settled on.

### `generate_adversaries_html.py` — standalone reference table

Builds `adversaries.html`, a single self-contained page you can open straight from disk — sortable
columns, filters for tier, type, difficulty, attack, thresholds, and damage, a global search, and
automatic links to [Old Gus's Daggerheart SRD](https://callmepartario.github.io/og-dhsrd/).

```bash
.venv/bin/python generate_adversaries_html.py                       # Uses sources/daggerheart_adversaries.xlsx
.venv/bin/python generate_adversaries_html.py path/to/custom.xlsx   # A different spreadsheet
```

The spreadsheet needs a sheet named `daggerheart_adversaries` with headers in the first row.

## Manual setup

If you would rather not use the launcher:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

On Windows:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

## What it handles

- Adversary and environment stat blocks from PDFs, including two-column layouts, blocks that run
  across a page break, and books that print the difficulty on the tier line.
- Multi-adversary Markdown files in both community and standardized formats.
- Environments as their own record type, keeping Impulses, Potential Adversaries, and each feature's
  GM question prompts.
- Source attribution by name and page number.
- Stat blocks it recognises but cannot parse are reported rather than silently dropped, so a source
  in an unsupported layout tells you what it saw.

## Troubleshooting

**The page says it can't reach the converter.** The terminal window running the server has been
closed, or it restarted on a different port. Run the launcher again and use the address it prints.
If you opened `index.html` by double-clicking it, close that tab — the page needs the launcher's
server to do any work.

**Nothing was found in my PDF.** Some PDFs are page images with no text layer, which this tool
cannot read. Run `convert.py yourfile.pdf --list`: if it reports stat blocks it could not parse,
the layout is one the parser does not recognise yet, and the message names the blocks it saw.

**A `FontBBox` warning appears.** Harmless, and already suppressed in current versions.

## Project structure

```
dhconverter/
├── convert.py                          # CLI: sources -> individual .md files
├── normalize.py                        # CLI: re-format existing .md files
├── app.py                              # Web UI: local HTTP server (stdlib only)
├── index.html                          # Web UI: single-file browser interface
├── Start Converter (Mac).command       # macOS launcher
├── Start Converter (Windows).bat       # Windows launcher
├── generate_adversaries_html.py        # Builds the adversaries.html reference table
├── _SAMPLE.md                          # Reference: standardized output format (SRD content)
├── models/
│   ├── adversary.py                    # Adversary, Attack, Feature
│   ├── environment.py                  # Environment, EnvironmentFeature
│   └── parse_result.py                 # ParseResult: adversaries + environments
├── parsers/
│   ├── pdf_text.py                     # Font-aware page extraction (columns, glyphs, lines)
│   ├── pdf_parser.py                   # Stat-block parsing and record routing
│   ├── md_parser.py                    # Markdown format parsing
│   └── text_cleaner.py                 # Unicode normalization, OCR artifact removal
├── writers/
│   ├── adversary_bank_writer.py        # Arrow's Adversary Bank Markdown
│   ├── markdown_writer.py              # Older readable stat block format
│   ├── frontmatter.py                  # Obsidian properties blocks
│   ├── yaml_format.py                  # Shared YAML/name formatting helpers
│   ├── beastvault_writer.py            # Combined JSON library export
│   └── index_generator.py              # Master and type index files
├── utils/
│   └── source_finder.py                # Source attribution lookup
├── tests/                              # Unit and integration tests
├── output/                             # Converted files (gitignored)
├── LICENSE                             # GNU GPLv3
└── requirements.txt
```

Run the tests with `.venv/bin/python -m unittest discover tests`.

## License

The **code** in this project is licensed under the [GNU General Public License v3.0 (GPLv3)](https://www.gnu.org/licenses/gpl-3.0.html). You are free to use, modify, and distribute this software, provided that any derivative works are also distributed under the GPLv3. See [LICENSE](LICENSE) for the full legal text.

The **sample stat block** (`_SAMPLE.md`) contains Daggerheart SRD content used under the Darrington Press Community Gaming License (CGL). This content is not covered by the GPLv3 — it remains © Darrington Press, and its use is governed by the CGL terms.

*This work includes material taken from the Daggerheart System Reference Document by Darrington Press. Daggerheart is © Darrington Press. All rights reserved.*

## Content ownership

**This tool is a format converter, not a content source.** It converts stat blocks that **you already own or have the right to use** into a more convenient format for personal use at your table.

- Do **not** use this tool to redistribute copyrighted content you do not have rights to share.
- Daggerheart is a product of Darrington Press. Adversary stat blocks from official publications are the intellectual property of their respective creators.
- Community-created content is the intellectual property of its respective authors. Respect their licensing terms.
