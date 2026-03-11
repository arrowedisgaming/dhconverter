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

    data_json = json.dumps(rows, default=str)
    filter_json = json.dumps(filter_options)
    headers_json = json.dumps(headers)
    display_json = json.dumps(display_names)
    dropdowns_json = json.dumps(dropdowns)
    numerics_json = json.dumps(numerics)
    ranges_json = json.dumps(ranges)
    texts_json = json.dumps(texts)
    srd_links_json = json.dumps(srd_links)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daggerheart Adversaries</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    min-height: 100vh;
}}

.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 1rem;
}}

h1 {{
    text-align: center;
    color: #c9a84c;
    font-size: 1.8rem;
    margin-bottom: 1rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}}

.controls {{
    background: #16213e;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: end;
}}

.control-group {{
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}}

.control-group label {{
    font-size: 0.75rem;
    color: #8899aa;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
}}

.search-group {{
    flex: 1 1 250px;
}}

#search {{
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid #2a3a5e;
    border-radius: 6px;
    background: #0f1a30;
    color: #e0e0e0;
    font-size: 0.95rem;
    outline: none;
    transition: border-color 0.2s;
}}

#search:focus {{
    border-color: #c9a84c;
}}

select, .filter-input {{
    padding: 0.5rem 0.75rem;
    border: 1px solid #2a3a5e;
    border-radius: 6px;
    background: #0f1a30;
    color: #e0e0e0;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.2s;
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
    min-width: 55px;
    padding: 0.5rem 0.3rem;
    font-size: 0.8rem;
}}

.range-filter .filter-input {{
    width: 65px;
}}

select:focus, .filter-input:focus {{
    border-color: #c9a84c;
}}

.count {{
    font-size: 0.85rem;
    color: #8899aa;
    padding: 0.5rem 0;
    align-self: end;
    white-space: nowrap;
}}

.table-wrap {{
    overflow-x: auto;
    border-radius: 8px;
    border: 1px solid #2a3a5e;
    -webkit-overflow-scrolling: touch;
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
    background: #16213e;
    color: #c9a84c;
    padding: 0.6rem 0.75rem;
    text-align: left;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    border-bottom: 2px solid #c9a84c;
    font-weight: 600;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    transition: background 0.15s;
}}

th:hover {{
    background: #1e2d52;
}}

th .sort-arrow {{
    margin-left: 4px;
    opacity: 0.3;
    font-size: 0.7rem;
}}

th.sort-asc .sort-arrow,
th.sort-desc .sort-arrow {{
    opacity: 1;
}}

td {{
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #1e2d4a;
    white-space: nowrap;
}}

tr:hover td {{
    background: #1a2744;
}}

tr:nth-child(even) td {{
    background: #111b30;
}}

tr:nth-child(even):hover td {{
    background: #1a2744;
}}

td:first-child {{
    font-weight: 600;
    color: #e8d5a3;
}}

td:first-child a {{
    color: #e8d5a3;
    text-decoration: none;
    border-bottom: 1px dotted #c9a84c55;
    transition: border-color 0.2s, color 0.2s;
}}

td:first-child a:hover {{
    color: #c9a84c;
    border-bottom-color: #c9a84c;
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
    padding: 2rem;
    color: #667;
    font-style: italic;
}}

footer {{
    margin-top: 2rem;
    padding: 1.5rem;
    background: #16213e;
    border-radius: 8px;
    font-size: 0.8rem;
    line-height: 1.6;
    color: #8899aa;
}}

footer p {{
    margin-bottom: 0.75rem;
}}

footer p:last-child {{
    margin-bottom: 0;
}}

footer a {{
    color: #c9a84c;
    text-decoration: none;
    border-bottom: 1px dotted #c9a84c55;
}}

footer a:hover {{
    border-bottom-color: #c9a84c;
}}

footer .attribution {{
    border-top: 1px solid #2a3a5e;
    padding-top: 0.75rem;
    margin-top: 0.75rem;
}}

@media (max-width: 600px) {{
    h1 {{ font-size: 1.3rem; }}
    .controls {{ padding: 0.75rem; gap: 0.5rem; }}
    .control-group {{ flex: 1 1 45%; }}
    .search-group {{ flex: 1 1 100%; }}
    table {{ font-size: 0.8rem; }}
    th, td {{ padding: 0.4rem 0.5rem; }}
}}
</style>
</head>
<body>
<div class="container">
    <h1>Daggerheart Adversaries</h1>
    <div class="controls" id="controls"></div>
    <div class="count" id="count"></div>
    <div class="table-wrap">
        <table>
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
</div>
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
    buildControls();
    buildHeader();
    render();
}}

function buildControls() {{
    const ctrl = document.getElementById('controls');

    // Global search
    const sg = document.createElement('div');
    sg.className = 'control-group search-group';
    sg.innerHTML = '<label for="search">Search</label><input type="text" id="search" placeholder="Search by name...">';
    ctrl.appendChild(sg);

    // Dropdown filters
    DROPDOWNS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        let opts = '<option value="">All</option>';
        FILTER_OPTIONS[col].forEach(v => {{
            opts += `<option value="${{v}}">${{v}}</option>`;
        }});
        g.innerHTML = `<label for="filter-${{col}}">${{DISPLAY[col]}}</label><select id="filter-${{col}}">${{opts}}</select>`;
        ctrl.appendChild(g);
    }});

    // Numeric exact-match filters
    NUMERIC_FILTERS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        g.innerHTML = `<label for="filter-${{col}}">${{DISPLAY[col]}}</label><input type="number" class="filter-input" id="filter-${{col}}" placeholder="Any">`;
        ctrl.appendChild(g);
    }});

    // Range filters (above / below / exactly)
    RANGE_FILTERS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        g.innerHTML = `<label for="filter-${{col}}">${{DISPLAY[col]}}</label><div class="range-filter"><select id="filter-${{col}}-mode"><option value="gte">\u2265</option><option value="lte">\u2264</option><option value="eq">=</option></select><input type="number" class="filter-input" id="filter-${{col}}" placeholder="Any"></div>`;
        ctrl.appendChild(g);
    }});

    // Text substring filters
    TEXT_FILTERS.forEach(col => {{
        const g = document.createElement('div');
        g.className = 'control-group';
        g.innerHTML = `<label for="filter-${{col}}">${{DISPLAY[col]}}</label><input type="text" class="filter-input text-filter" id="filter-${{col}}" placeholder="e.g. d12">`;
        ctrl.appendChild(g);
    }});

    // Event listeners
    document.getElementById('search').addEventListener('input', e => {{
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {{
            searchTerm = e.target.value.toLowerCase();
            render();
        }}, 150);
    }});

    DROPDOWNS.forEach(col => {{
        document.getElementById(`filter-${{col}}`).addEventListener('change', e => {{
            dropdownFilters[col] = e.target.value;
            render();
        }});
    }});

    NUMERIC_FILTERS.forEach(col => {{
        document.getElementById(`filter-${{col}}`).addEventListener('input', e => {{
            numericFilters[col] = e.target.value;
            render();
        }});
    }});

    RANGE_FILTERS.forEach(col => {{
        document.getElementById(`filter-${{col}}`).addEventListener('input', e => {{
            if (!rangeFilters[col]) rangeFilters[col] = {{mode: 'gte', value: ''}};
            rangeFilters[col].value = e.target.value;
            render();
        }});
        document.getElementById(`filter-${{col}}-mode`).addEventListener('change', e => {{
            if (!rangeFilters[col]) rangeFilters[col] = {{mode: 'gte', value: ''}};
            rangeFilters[col].mode = e.target.value;
            render();
        }});
    }});

    TEXT_FILTERS.forEach(col => {{
        document.getElementById(`filter-${{col}}`).addEventListener('input', e => {{
            textFilters[col] = e.target.value.toLowerCase();
            render();
        }});
    }});
}}

function buildHeader() {{
    const tr = document.getElementById('thead');
    HEADERS.forEach(h => {{
        const th = document.createElement('th');
        if (NUMERIC_COLS.has(h)) th.className = 'num';
        if (h === 'damage_dice') {{
            th.textContent = DISPLAY[h];
            th.style.cursor = 'default';
        }} else {{
            th.innerHTML = `${{DISPLAY[h]}}<span class="sort-arrow">\u25B2</span>`;
            th.addEventListener('click', () => {{
                if (sortCol === h) {{
                    sortAsc = !sortAsc;
                }} else {{
                    sortCol = h;
                    sortAsc = true;
                }}
                document.querySelectorAll('th').forEach(el => el.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
                th.querySelector('.sort-arrow').textContent = sortAsc ? '\u25B2' : '\u25BC';
                render();
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
    document.getElementById('count').textContent = `Showing ${{rows.length}} of ${{DATA.length}} adversaries`;

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
        tbody.innerHTML = '<tr><td colspan="' + HEADERS.length + '" class="no-results">No matching adversaries found.</td></tr>';
        return;
    }}

    const html = rows.map(row =>
        '<tr>' + HEADERS.map(h => {{
            const cls = NUMERIC_COLS.has(h) ? ' class="num"' : '';
            const val = row[h] === '' ? '\u2014' : row[h];
            if (h === 'name' && SRD_LINKS[row[h]]) {{
                return `<td${{cls}}><a href="${{SRD_LINKS[row[h]]}}" target="_blank" rel="noopener">${{val}}</a></td>`;
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
