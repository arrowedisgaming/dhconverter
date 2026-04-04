#!/usr/bin/env python3
"""Generate adversaries.html from daggerheart_adversaries.xlsx.

Usage:
    python3 generate_adversaries_html.py [path/to/file.xlsx]
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

import openpyxl

SRD_BASE_URL = "https://callmepartario.github.io/og-dhsrd/"

# Manual overrides for name mismatches between spreadsheet and SRD
SLUG_OVERRIDES = {
    "Outer Realms Corrupter": "outer-realms-corruptor",
}


def load_data(xlsx_path: str) -> tuple[list[str], list[dict]]:
    """Load adversary data from Excel, returning (headers, rows_as_dicts)."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb["daggerheart_adversaries"]
    raw = list(ws.iter_rows(values_only=True))
    wb.close()

    headers = [str(h) for h in raw[0]]
    rows = []
    for row in raw[1:]:
        record = {}
        for h, val in zip(headers, row):
            if val is None:
                record[h] = ""
            else:
                record[h] = val
        rows.append(record)
    return headers, rows


def slugify(name: str) -> str:
    """Convert an adversary name to a URL slug matching the SRD pattern."""
    if name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name]
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch_srd_slugs() -> set[str]:
    """Fetch the SRD page and extract all individual adversary anchor slugs."""
    print("Fetching SRD page for adversary links...")
    try:
        req = urllib.request.Request(SRD_BASE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Warning: Could not fetch SRD page ({e}). Names will not be linked.")
        return set()

    # Extract href targets like #define-adversary-cave-ogre
    raw_links = re.findall(r'href="#(define-adversary-[^"]+)"', html)

    # Filter out section headers (action, benchmarks, type, etc.)
    section_suffixes = {
        "action", "action-list", "benchmarks", "benchmarks-experiences",
        "benchmarks-hit-points", "type", "feature", "conditions",
        "fear-features", "fear-gain", "hope-loss", "passive-list",
        "reaction-list",
    }
    slugs = set()
    for link in raw_links:
        suffix = link.removeprefix("define-adversary-")
        if suffix in section_suffixes or suffix.startswith("benchmarks-type-"):
            continue
        slugs.add(suffix)

    print(f"  Found {len(slugs)} adversary anchors in SRD")
    return slugs


def build_srd_links(names: list[str], srd_slugs: set[str]) -> dict[str, str]:
    """Build a mapping of adversary name -> full SRD URL for names that exist in the SRD."""
    links = {}
    for name in names:
        slug = slugify(name)
        if slug in srd_slugs:
            links[name] = f"{SRD_BASE_URL}#define-adversary-{slug}"
    return links


# Dropdown filters (select element with "All" option)
DROPDOWN_FILTERS = ["tier", "type", "difficulty"]

# Numeric exact-match text input filters
NUMERIC_FILTERS = ["atk_bonus"]

# Range filters (above / below / exactly comparison)
RANGE_FILTERS = ["hp", "stress", "low_threshold", "high_threshold"]

# Text substring-match text input filters
TEXT_FILTERS = ["damage_dice"]

# Columns to exclude from the output
EXCLUDED_COLUMNS = ["battle_points"]


def get_dropdown_options(headers: list[str], rows: list[dict]) -> dict:
    """Build sorted unique values for each dropdown filter column."""
    options = {}
    for col in DROPDOWN_FILTERS:
        if col not in headers:
            continue
        vals = sorted(set(r[col] for r in rows if r[col] != ""),
                      key=lambda x: (isinstance(x, str), x))
        options[col] = [str(v) for v in vals]
    return options


def safe_json_embed(obj, **kwargs):
    """JSON-encode for embedding inside <script> — escapes </ to prevent tag breakout."""
    return json.dumps(obj, **kwargs).replace("</", "<\\/")


def generate_html(headers: list[str], rows: list[dict], srd_links: dict[str, str]) -> str:
    """Generate the complete HTML string."""
    # Remove excluded columns
    headers = [h for h in headers if h not in EXCLUDED_COLUMNS]

    filter_options = get_dropdown_options(headers, rows)

    # Only include filters for columns that actually exist
    dropdowns = [c for c in DROPDOWN_FILTERS if c in headers]
    numerics = [c for c in NUMERIC_FILTERS if c in headers]
    ranges = [c for c in RANGE_FILTERS if c in headers]
    texts = [c for c in TEXT_FILTERS if c in headers]

    display_names = {h: h.replace("_", " ").title() for h in headers}

    data_json = safe_json_embed(rows, default=str)
    filter_json = safe_json_embed(filter_options)
    headers_json = safe_json_embed(headers)
    display_json = safe_json_embed(display_names)
    dropdowns_json = safe_json_embed(dropdowns)
    numerics_json = safe_json_embed(numerics)
    ranges_json = safe_json_embed(ranges)
    texts_json = safe_json_embed(texts)
    srd_links_json = safe_json_embed(srd_links)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daggerheart Adversaries</title>
<style>
/* ── Theme tokens ────────────────────────────── */
:root {{
    --bg-deep: #1a1614;
    --bg-card: #231f1b;
    --bg-inset: #2a2420;
    --bg-hover: #342e28;
    --border: #3d3530;
    --border-accent: #d4a93444;
    --text: #ede4d6;
    --text-dim: #9a8e80;
    --text-muted: #7a6f63;
    --accent: #d4a934;
    --accent-glow: #d4a93433;
    --accent-dim: #b8922a;
    --accent-secondary: #a04040;
    --danger: #c45a4a;
    --success: #6b8a6b;
    --radius: 8px;
    --radius-sm: 5px;
    --shadow: 0 2px 12px #00000040;
    --shadow-lg: 0 8px 32px #00000060;
    --transition: 0.2s ease;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif;
    --font-display: Georgia, "Palatino Linotype", "Book Antiqua", serif;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
    font-family: var(--font-sans);
    background: var(--bg-deep);
    color: var(--text);
    line-height: 1.5;
    min-height: 100vh;
}}

/* subtle grain overlay */
body::before {{
    content: '';
    position: fixed;
    inset: 0;
    opacity: 0.025;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    background-size: 256px;
    pointer-events: none;
    z-index: 9999;
}}

.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 1rem;
}}

h1 {{
    text-align: center;
    color: var(--accent);
    font-family: var(--font-display);
    font-style: italic;
    font-size: 2rem;
    margin-bottom: 1.25rem;
    font-weight: 700;
    text-shadow: 0 2px 8px #d4a93440;
}}

h1 .dagger {{
    font-style: normal;
    font-size: 1.1em;
    margin-right: 0.15em;
}}

h1::after {{
    content: '';
    display: block;
    width: 60px;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent);
    margin: 0.5rem auto 0;
    border-radius: 1px;
}}

.controls {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-top: 2px solid var(--accent);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: end;
    box-shadow: var(--shadow);
}}

.filter-section {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: end;
    padding-right: 1.25rem;
    border-right: 1px solid var(--border);
}}

.filter-section:last-of-type {{
    border-right: none;
    padding-right: 0;
}}

.control-group {{
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}}

.control-group label {{
    font-size: 0.8rem;
    color: var(--text-dim);
    font-weight: 600;
}}

.search-group {{
    flex: 1 1 250px;
}}

#search {{
    width: 100%;
    padding: 0.6rem 1rem 0.6rem 2.25rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-inset) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%239a8e80' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") no-repeat 0.75rem center;
    color: var(--text);
    font-size: 1rem;
    outline: none;
    transition: border-color var(--transition);
}}

#search:focus {{
    border-color: var(--accent);
}}

select, .filter-input {{
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-inset);
    color: var(--text);
    font-size: 0.9rem;
    font-family: var(--font-sans);
    outline: none;
    transition: border-color var(--transition);
}}

select {{
    cursor: pointer;
    min-width: 100px;
}}

.filter-input {{
    width: 80px;
}}

/* Hide number input spinners */
.filter-input[type="number"] {{
    -moz-appearance: textfield;
    appearance: textfield;
}}
.filter-input[type="number"]::-webkit-inner-spin-button,
.filter-input[type="number"]::-webkit-outer-spin-button {{
    -webkit-appearance: none;
    margin: 0;
}}

.filter-input.text-filter {{
    width: 100px;
}}

.range-filter {{
    display: flex;
    gap: 0.25rem;
}}

.range-filter select {{
    min-width: 65px;
    padding: 0.5rem 0.3rem;
    font-size: 0.85rem;
}}

.range-filter .filter-input {{
    width: 80px;
}}

select:focus, .filter-input:focus {{
    border-color: var(--accent);
}}

/* ── Focus indicators (WCAG 2.4.7) ───────────── */
select:focus-visible, .filter-input:focus-visible, #search:focus-visible {{
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}}

.btn-clear:focus-visible {{
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}}

/* ── Clear Filters button ─────────────────────── */
.btn-clear {{
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-inset);
    color: var(--text-dim);
    font-size: 0.8rem;
    font-family: var(--font-sans);
    cursor: pointer;
    align-self: end;
    transition: background var(--transition), color var(--transition), border-color var(--transition);
    white-space: nowrap;
}}

.btn-clear:hover {{
    background: var(--bg-hover);
    color: var(--text);
    border-color: var(--text-muted);
}}

.count {{
    font-size: 0.85rem;
    color: var(--text-dim);
    padding: 0.5rem 0;
    text-align: right;
    white-space: nowrap;
}}

/* ── Table scroll affordance ──────────────────── */
.table-wrap {{
    overflow-x: auto;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    -webkit-overflow-scrolling: touch;
    position: relative;
    box-shadow: var(--shadow);
}}

.table-wrap.has-overflow {{
    mask-image: linear-gradient(to right, black calc(100% - 2rem), transparent);
    -webkit-mask-image: linear-gradient(to right, black calc(100% - 2rem), transparent);
}}

.table-wrap.scrolled {{
    mask-image: none;
    -webkit-mask-image: none;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    min-width: 800px;
    font-size: 0.9rem;
}}

thead {{
    position: sticky;
    top: 0;
    z-index: 10;
}}

th {{
    background: var(--bg-card);
    color: var(--text);
    padding: 0.6rem 0.85rem;
    text-align: left;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    border-bottom: 2px solid var(--accent-secondary);
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    transition: background var(--transition);
}}

th:hover {{
    background: var(--bg-hover);
}}

th .sort-arrow {{
    margin-left: 4px;
    opacity: 0.5;
    font-size: 0.7rem;
    transition: opacity var(--transition);
}}

th:hover .sort-arrow {{
    opacity: 0.8;
}}

th.sort-asc .sort-arrow,
th.sort-desc .sort-arrow {{
    opacity: 1;
}}

td {{
    padding: 0.55rem 0.85rem;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}}

tr:hover td {{
    background: var(--bg-hover);
}}

tr:hover td:first-child {{
    box-shadow: inset 3px 0 0 var(--accent);
}}

tr:nth-child(even) td {{
    background: rgba(255, 255, 255, 0.015);
}}

tr:nth-child(even):hover td {{
    background: var(--bg-hover);
}}

td:first-child {{
    font-weight: 600;
    color: var(--text);
    font-size: 0.95rem;
}}

td:first-child a {{
    color: var(--accent);
    text-decoration: none;
    border-bottom: 1px solid transparent;
    transition: border-color var(--transition), color var(--transition);
}}

td:first-child a:hover {{
    border-bottom-color: var(--accent);
}}

td.num {{
    text-align: right;
    font-variant-numeric: tabular-nums;
}}

th.num {{
    text-align: right;
}}

.no-results {{
    text-align: center;
    padding: 3rem 2rem;
    color: var(--text-muted);
    font-style: italic;
    font-size: 1rem;
}}

/* ── Loading placeholder ──────────────────────── */
.loading-msg {{
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-dim);
    font-size: 0.95rem;
}}

footer {{
    margin-top: 2rem;
    padding: 1.25rem 1.5rem;
    border-top: 1px solid var(--border);
    font-size: 0.78rem;
    line-height: 1.6;
    color: var(--text-muted);
}}

footer p {{
    margin-bottom: 0.75rem;
}}

footer p:last-child {{
    margin-bottom: 0;
}}

footer a {{
    color: var(--accent);
    text-decoration: none;
    border-bottom: 1px dotted var(--border-accent);
}}

footer a:hover {{
    border-bottom-color: var(--accent);
}}

footer .attribution {{
    border-top: 1px solid var(--border);
    padding-top: 0.75rem;
    margin-top: 0.75rem;
}}

th:focus-visible {{
    outline: 2px solid var(--accent);
    outline-offset: -2px;
}}

.sr-only {{
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}}

.skip-link {{
    position: absolute;
    top: -40px;
    left: 0;
    background: var(--accent);
    color: var(--bg-deep);
    padding: 0.5rem 1rem;
    z-index: 100;
    font-weight: 600;
    text-decoration: none;
    border-radius: 0 0 var(--radius-sm) 0;
}}

.skip-link:focus {{
    top: 0;
}}

@media (max-width: 600px) {{
    h1 {{ font-size: 1.3rem; }}
    .controls {{ padding: 0.75rem; gap: 0.5rem; }}
    .filter-section {{
        flex: 1 1 100%;
        padding-right: 0;
        border-right: none;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border);
    }}
    .filter-section:last-of-type {{
        border-bottom: none;
        padding-bottom: 0;
    }}
    .control-group {{ flex: 1 1 45%; }}
    .search-group {{ flex: 1 1 100%; }}
    table {{ font-size: 0.8rem; }}
    th, td {{ padding: 0.4rem 0.5rem; }}
}}
</style>
</head>
<body>
<a class="skip-link" href="#tbody">Skip to adversary table</a>
<main class="container">
    <h1><span class="dagger" aria-hidden="true">&#x2694;</span> Daggerheart Adversaries</h1>
    <h2 class="sr-only">Filters</h2>
    <div class="controls" id="controls"></div>
    <div class="count" id="count" aria-live="polite" role="status"></div>
    <div class="loading-msg" id="loading">Loading adversary data&hellip;</div>
    <div class="table-wrap" id="table-wrap">
        <table>
            <caption class="sr-only">Daggerheart adversary statistics</caption>
            <thead><tr id="thead"></tr></thead>
            <tbody id="tbody"></tbody>
        </table>
    </div>
    <footer>
        <p>Adversary stat block links courtesy of <a href="https://callmepartario.github.io/og-dhsrd/" target="_blank" rel="noopener">Old Gus&rsquo;s Daggerheart SRD</a>. Thank you to Old Gus for his incredible work compiling and maintaining the SRD.</p>
        <div class="attribution">
            <p>This product includes materials from the Daggerheart System Reference Document 1.0, &copy; Critical Role, LLC. under the terms of the <a href="https://darringtonpress.com/license/" target="_blank" rel="noopener">Darrington Press Community Gaming (DPCGL) License</a>. More information can be found at <a href="https://www.daggerheart.com" target="_blank" rel="noopener">daggerheart.com</a>. This material has been reorganized and reformatted into a searchable reference. There are no previous modifications by others.</p>
        </div>
    </footer>
</main>
<script>
const DATA = {data_json};
const HEADERS = {headers_json};
const DISPLAY = {display_json};
const DROPDOWNS = {dropdowns_json};
const NUMERIC_FILTERS = {numerics_json};
const RANGE_FILTERS = {ranges_json};
const TEXT_FILTERS = {texts_json};
const FILTER_OPTIONS = {filter_json};
const SRD_LINKS = {srd_links_json};
const NUMERIC_COLS = new Set();
HEADERS.forEach(h => {{
    if (h === 'name' || h === 'damage_dice') return;
    const isNum = DATA.every(r => r[h] === '' || r[h] === null || typeof r[h] === 'number');
    if (isNum) NUMERIC_COLS.add(h);
}});

let sortCol = null;
let sortAsc = true;
let searchTerm = '';
let dropdownFilters = {{}};
let numericFilters = {{}};
let rangeFilters = {{}};
let textFilters = {{}};
let debounceTimer = null;

function init() {{
    const loadingEl = document.getElementById('loading');
    if (loadingEl) loadingEl.remove();
    buildControls();
    buildHeader();
    render();
    // Scroll affordance for mobile table
    const wrap = document.getElementById('table-wrap');
    if (wrap) {{
        const checkOverflow = () => {{
            const hasOverflow = wrap.scrollWidth > wrap.clientWidth;
            wrap.classList.toggle('has-overflow', hasOverflow && wrap.scrollLeft < wrap.scrollWidth - wrap.clientWidth - 5);
        }};
        wrap.addEventListener('scroll', () => {{
            wrap.classList.toggle('scrolled', wrap.scrollLeft > 10);
            checkOverflow();
        }});
        window.addEventListener('resize', checkOverflow);
        checkOverflow();
    }}
}}

function buildControls() {{
    const ctrl = document.getElementById('controls');

    // Global search (standalone, full width)
    const sg = document.createElement('div');
    sg.className = 'control-group search-group';
    const searchLabel = document.createElement('label');
    searchLabel.setAttribute('for', 'search');
    searchLabel.textContent = 'Search';
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.id = 'search';
    searchInput.placeholder = 'Search by name\u2026';
    sg.appendChild(searchLabel);
    sg.appendChild(searchInput);
    ctrl.appendChild(sg);

    // Classification section (dropdowns)
    const classSection = document.createElement('div');
    classSection.className = 'filter-section';
    DROPDOWNS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        const lbl = document.createElement('label');
        lbl.setAttribute('for', 'filter-' + col);
        lbl.textContent = DISPLAY[col];
        const sel = document.createElement('select');
        sel.id = 'filter-' + col;
        const allOpt = document.createElement('option');
        allOpt.value = '';
        allOpt.textContent = 'All';
        sel.appendChild(allOpt);
        FILTER_OPTIONS[col].forEach(v => {{
            const o = document.createElement('option');
            o.value = v;
            o.textContent = v;
            sel.appendChild(o);
        }});
        g.appendChild(lbl);
        g.appendChild(sel);
        classSection.appendChild(g);
    }});
    ctrl.appendChild(classSection);

    // Statistics section (numeric, range, text filters)
    const statsSection = document.createElement('div');
    statsSection.className = 'filter-section';

    NUMERIC_FILTERS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        const lbl = document.createElement('label');
        lbl.setAttribute('for', 'filter-' + col);
        lbl.textContent = DISPLAY[col];
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'filter-input';
        inp.id = 'filter-' + col;
        inp.placeholder = 'Any';
        g.appendChild(lbl);
        g.appendChild(inp);
        statsSection.appendChild(g);
    }});

    RANGE_FILTERS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        const lbl = document.createElement('label');
        lbl.setAttribute('for', 'filter-' + col);
        lbl.textContent = DISPLAY[col];
        const rangeDiv = document.createElement('div');
        rangeDiv.className = 'range-filter';
        const modeSel = document.createElement('select');
        modeSel.id = 'filter-' + col + '-mode';
        modeSel.setAttribute('aria-label', DISPLAY[col] + ' comparison mode');
        [['gte', '\u2265'], ['lte', '\u2264'], ['eq', '=']].forEach(([val, txt]) => {{
            const o = document.createElement('option');
            o.value = val;
            o.textContent = txt;
            modeSel.appendChild(o);
        }});
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.className = 'filter-input';
        inp.id = 'filter-' + col;
        inp.placeholder = 'Any';
        rangeDiv.appendChild(modeSel);
        rangeDiv.appendChild(inp);
        g.appendChild(lbl);
        g.appendChild(rangeDiv);
        statsSection.appendChild(g);
    }});

    TEXT_FILTERS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        const lbl = document.createElement('label');
        lbl.setAttribute('for', 'filter-' + col);
        lbl.textContent = DISPLAY[col];
        const inp = document.createElement('input');
        inp.type = 'text';
        inp.className = 'filter-input text-filter';
        inp.id = 'filter-' + col;
        inp.placeholder = 'e.g. d12';
        g.appendChild(lbl);
        g.appendChild(inp);
        statsSection.appendChild(g);
    }});

    ctrl.appendChild(statsSection);

    // Clear Filters button
    const clrBtn = document.createElement('button');
    clrBtn.className = 'btn-clear';
    clrBtn.textContent = 'Clear Filters';
    clrBtn.addEventListener('click', () => {{
        document.getElementById('search').value = '';
        searchTerm = '';
        DROPDOWNS.forEach(col => {{
            const el = document.getElementById('filter-' + col);
            el.value = '';
            dropdownFilters[col] = '';
        }});
        NUMERIC_FILTERS.forEach(col => {{
            const el = document.getElementById('filter-' + col);
            el.value = '';
            numericFilters[col] = '';
        }});
        RANGE_FILTERS.forEach(col => {{
            document.getElementById('filter-' + col).value = '';
            document.getElementById('filter-' + col + '-mode').value = 'gte';
            rangeFilters[col] = {{mode: 'gte', value: ''}};
        }});
        TEXT_FILTERS.forEach(col => {{
            const el = document.getElementById('filter-' + col);
            el.value = '';
            textFilters[col] = '';
        }});
        render();
    }});
    ctrl.appendChild(clrBtn);

    // Event listeners
    document.getElementById('search').addEventListener('input', e => {{
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {{
            searchTerm = e.target.value.toLowerCase();
            render();
        }}, 150);
    }});

    DROPDOWNS.forEach(col => {{
        document.getElementById('filter-' + col).addEventListener('change', e => {{
            dropdownFilters[col] = e.target.value;
            render();
        }});
    }});

    NUMERIC_FILTERS.forEach(col => {{
        document.getElementById('filter-' + col).addEventListener('input', e => {{
            numericFilters[col] = e.target.value;
            render();
        }});
    }});

    RANGE_FILTERS.forEach(col => {{
        document.getElementById('filter-' + col).addEventListener('input', e => {{
            if (!rangeFilters[col]) rangeFilters[col] = {{mode: 'gte', value: ''}};
            rangeFilters[col].value = e.target.value;
            render();
        }});
        document.getElementById('filter-' + col + '-mode').addEventListener('change', e => {{
            if (!rangeFilters[col]) rangeFilters[col] = {{mode: 'gte', value: ''}};
            rangeFilters[col].mode = e.target.value;
            render();
        }});
    }});

    TEXT_FILTERS.forEach(col => {{
        document.getElementById('filter-' + col).addEventListener('input', e => {{
            textFilters[col] = e.target.value.toLowerCase();
            render();
        }});
    }});
}}

function esc(s) {{
    if (!s && s !== 0) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}}

function buildHeader() {{
    const tr = document.getElementById('thead');
    HEADERS.forEach(h => {{
        const th = document.createElement('th');
        th.setAttribute('scope', 'col');
        if (NUMERIC_COLS.has(h)) th.className = 'num';
        if (h === 'damage_dice') {{
            th.textContent = DISPLAY[h];
            th.style.cursor = 'default';
        }} else {{
            th.textContent = DISPLAY[h];
            const arrow = document.createElement('span');
            arrow.className = 'sort-arrow';
            arrow.setAttribute('aria-hidden', 'true');
            arrow.textContent = '\u25B2';
            th.appendChild(arrow);
            th.setAttribute('tabindex', '0');
            const doSort = () => {{
                if (sortCol === h) {{
                    sortAsc = !sortAsc;
                }} else {{
                    sortCol = h;
                    sortAsc = true;
                }}
                document.querySelectorAll('th').forEach(el => {{
                    el.classList.remove('sort-asc', 'sort-desc');
                    el.removeAttribute('aria-sort');
                }});
                th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
                th.setAttribute('aria-sort', sortAsc ? 'ascending' : 'descending');
                th.querySelector('.sort-arrow').textContent = sortAsc ? '\u25B2' : '\u25BC';
                render();
            }};
            th.addEventListener('click', doSort);
            th.addEventListener('keydown', e => {{
                if (e.key === 'Enter' || e.key === ' ') {{
                    e.preventDefault();
                    doSort();
                }}
            }});
        }}
        tr.appendChild(th);
    }});
}}

function getFiltered() {{
    return DATA.filter(row => {{
        // Name search
        if (searchTerm) {{
            const name = String(row['name']).toLowerCase();
            if (!name.includes(searchTerm)) return false;
        }}
        // Dropdown filters (exact match on string)
        for (const col of DROPDOWNS) {{
            if (dropdownFilters[col] && String(row[col]) !== dropdownFilters[col]) return false;
        }}
        // Numeric filters (exact match on number)
        for (const col of NUMERIC_FILTERS) {{
            if (numericFilters[col] !== undefined && numericFilters[col] !== '') {{
                const target = Number(numericFilters[col]);
                if (row[col] === '' || row[col] === null || Number(row[col]) !== target) return false;
            }}
        }}
        // Range filters (above / below / exactly)
        for (const col of RANGE_FILTERS) {{
            const rf = rangeFilters[col];
            if (rf && rf.value !== undefined && rf.value !== '') {{
                const target = Number(rf.value);
                const val = Number(row[col]);
                if (row[col] === '' || row[col] === null || isNaN(val)) return false;
                if (rf.mode === 'gte' && val < target) return false;
                if (rf.mode === 'lte' && val > target) return false;
                if (rf.mode === 'eq' && val !== target) return false;
            }}
        }}
        // Text filters (substring match)
        for (const col of TEXT_FILTERS) {{
            if (textFilters[col]) {{
                const val = String(row[col]).toLowerCase();
                if (!val.includes(textFilters[col])) return false;
            }}
        }}
        return true;
    }});
}}

function render() {{
    let rows = getFiltered();
    const countEl = document.getElementById('count');
    countEl.textContent = '';
    countEl.appendChild(document.createTextNode('Showing '));
    const strong = document.createElement('strong');
    strong.style.color = 'var(--accent)';
    strong.textContent = rows.length;
    countEl.appendChild(strong);
    countEl.appendChild(document.createTextNode(' of ' + DATA.length + ' adversaries'));

    if (sortCol !== null) {{
        rows.sort((a, b) => {{
            let va = a[sortCol], vb = b[sortCol];
            if (va === '' || va === null) return 1;
            if (vb === '' || vb === null) return -1;
            if (typeof va === 'number' && typeof vb === 'number') {{
                return sortAsc ? va - vb : vb - va;
            }}
            va = String(va).toLowerCase();
            vb = String(vb).toLowerCase();
            if (va < vb) return sortAsc ? -1 : 1;
            if (va > vb) return sortAsc ? 1 : -1;
            return 0;
        }});
    }}

    const tbody = document.getElementById('tbody');
    if (rows.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="' + HEADERS.length + '" class="no-results">&#x2694; No matching adversaries found.</td></tr>';
        return;
    }}

    const html = rows.map(row =>
        '<tr>' + HEADERS.map(h => {{
            const cls = NUMERIC_COLS.has(h) ? ' class="num"' : '';
            const raw = row[h] === '' || row[h] === null ? '\u2014' : row[h];
            const val = esc(raw);
            if (h === 'name' && SRD_LINKS[row[h]]) {{
                return `<td${{cls}}><a href="${{esc(SRD_LINKS[row[h]])}}" target="_blank" rel="noopener">${{val}}</a></td>`;
            }}
            return `<td${{cls}}>${{val}}</td>`;
        }}).join('') + '</tr>'
    ).join('');
    tbody.innerHTML = html;
}}

init();
</script>
</body>
</html>"""


def main():
    xlsx_path = sys.argv[1] if len(sys.argv) > 1 else "sources/daggerheart_adversaries.xlsx"
    if not Path(xlsx_path).exists():
        print(f"Error: File not found: {xlsx_path}")
        sys.exit(1)

    headers, rows = load_data(xlsx_path)

    # Fetch SRD and build name->URL links
    srd_slugs = fetch_srd_slugs()
    names = [r["name"] for r in rows if r.get("name")]
    srd_links = build_srd_links(names, srd_slugs)
    unlinked = [n for n in names if n not in srd_links]

    html = generate_html(headers, rows, srd_links)

    out_path = Path(__file__).parent / "adversaries.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Generated {out_path} with {len(rows)} adversaries")
    print(f"SRD links: {len(srd_links)}/{len(names)} adversaries linked")
    if unlinked:
        print(f"Unlinked: {', '.join(unlinked)}")


if __name__ == "__main__":
    main()
