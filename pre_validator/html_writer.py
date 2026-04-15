"""
html_writer.py
Generates a single-file HTML validation report with embedded CSS.
Uses dataclass introspection to render results generically.
"""

import dataclasses
import html as html_mod


# ── Severity colours (matching Excel) ────────────────────────────────────────

SEVERITY_COLORS = {
    "FAIL":    "#FFC7CE",
    "WARNING": "#FFEB9C",
    "PASS":    "#C6EFCE",
    "INFO":    "#BDD7EE",
    "N/A":     "#D9D9D9",
}

SEVERITY_TEXT_COLORS = {
    "FAIL":    "#9C0006",
    "WARNING": "#9C6500",
    "PASS":    "#006100",
    "INFO":    "#1F4E79",
    "N/A":     "#595959",
}


# ── Field name formatting ────────────────────────────────────────────────────

def _field_to_header(name: str) -> str:
    """Convert snake_case dataclass field name to a readable header."""
    mapping = {
        "field_name": "Field Name",
        "missing_fields": "Missing Fields",
        "missing_in": "Missing In Sections",
        "is_mandatory": "Mandatory",
        "field_type": "Field Type",
        "invalid_type": "Invalid Type",
        "condition_text": "Condition Text",
        "referenced_table": "Referenced Table",
        "table_name": "Table Name",
        "referenced_field": "Referenced Field",
        "referenced_field_panel": "Referenced Field Panel",
        "detection_tier": "Detection Tier",
        "field_a": "Field A",
        "section_a": "Section A",
        "rule_a": "Rule A",
        "field_b": "Field B",
        "section_b": "Section B",
        "rule_b": "Rule B",
        "row_index": "Row Index",
        "duplicate_panels": "Duplicate Panel Names",
        "suggestion": "Suggestion",
    }
    if name in mapping:
        return mapping[name]
    return name.replace("_", " ").title()


def _format_value(value) -> str:
    """Format a value for HTML display."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if value is None:
        return ""
    return str(value)


def _is_severity_field(name: str) -> bool:
    """Check if a field name represents a status column."""
    return name == "status"


# ── Table extraction from results ────────────────────────────────────────────

def _extract_tables(validator_name: str, results: list) -> list[dict]:
    """
    Extract one or more tables from a validator's results.
    Returns list of {"title": str, "headers": list[str], "rows": list[list[str]],
                      "severity_indices": list[int]}
    """
    from models import FieldUniquenessResult

    if not results:
        return [{"title": validator_name, "headers": [], "rows": [],
                 "severity_indices": [], "pass_message": "PASS - No issues found."}]

    # Special case: FieldUniquenessResult wraps two sub-tables
    if len(results) == 1 and isinstance(results[0], FieldUniquenessResult):
        result = results[0]
        tables = []

        # Table 1: Field Duplicates
        if result.field_duplicates:
            fields = dataclasses.fields(result.field_duplicates[0])
            headers = [_field_to_header(f.name) for f in fields]
            sev_indices = [i for i, f in enumerate(fields) if _is_severity_field(f.name)]
            rows = []
            for r in result.field_duplicates:
                rows.append([_format_value(getattr(r, f.name)) for f in fields])
            tables.append({"title": "Field Duplicates", "headers": headers,
                          "rows": rows, "severity_indices": sev_indices})
        else:
            tables.append({"title": "Field Duplicates", "headers": [], "rows": [],
                          "severity_indices": [], "pass_message": "PASS - No duplicate fields found."})

        # Table 2: Panel Uniqueness
        if result.panel_uniqueness:
            fields = dataclasses.fields(result.panel_uniqueness[0])
            headers = [_field_to_header(f.name) for f in fields]
            sev_indices = [i for i, f in enumerate(fields) if _is_severity_field(f.name)]
            rows = []
            for r in result.panel_uniqueness:
                rows.append([_format_value(getattr(r, f.name)) for f in fields])
            tables.append({"title": "Panel Uniqueness", "headers": headers,
                          "rows": rows, "severity_indices": sev_indices})
        else:
            tables.append({"title": "Panel Uniqueness", "headers": [], "rows": [],
                          "severity_indices": [], "pass_message": "PASS - No duplicate panels found."})

        return tables

    # Generic case: introspect the first result's dataclass fields
    first = results[0]
    if not dataclasses.is_dataclass(first):
        return [{"title": validator_name, "headers": ["Value"], "rows": [[str(r)] for r in results],
                 "severity_indices": []}]

    fields = dataclasses.fields(first)
    headers = [_field_to_header(f.name) for f in fields]
    severity_indices = [i for i, f in enumerate(fields) if _is_severity_field(f.name)]

    rows = []
    for r in results:
        rows.append([_format_value(getattr(r, f.name)) for f in fields])

    return [{"title": validator_name, "headers": headers, "rows": rows,
             "severity_indices": severity_indices}]


# ── HTML generation ──────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return html_mod.escape(str(text))


def _severity_style(value: str) -> str:
    """Return inline CSS for a severity/status cell."""
    bg = SEVERITY_COLORS.get(value, "")
    fg = SEVERITY_TEXT_COLORS.get(value, "")
    if bg:
        return f'style="background-color:{bg};color:{fg};font-weight:600;text-align:center"'
    return ""


def _count_issues(results: list) -> dict:
    """Count severity/status occurrences across all results."""
    from models import FieldUniquenessResult
    counts = {"FAIL": 0, "WARNING": 0, "PASS": 0, "INFO": 0, "N/A": 0}

    items = results
    if len(results) == 1 and isinstance(results[0], FieldUniquenessResult):
        items = results[0].field_duplicates + results[0].panel_uniqueness

    for r in items:
        if not dataclasses.is_dataclass(r):
            continue
        for f in dataclasses.fields(r):
            if _is_severity_field(f.name):
                val = getattr(r, f.name, "")
                if val in counts:
                    counts[val] += 1
    return counts


def _generate_nav_item(validator_name: str, anchor: str, results: list, counts: dict | None = None) -> str:
    """Generate a sidebar navigation item with status badge."""
    if counts is None:
        counts = _count_issues(results)
    has_errors = counts["FAIL"] > 0
    has_warnings = counts["WARNING"] > 0
    all_pass = not has_errors and not has_warnings

    if not results:
        badge_class = "badge-pass"
        badge_text = "PASS"
    elif has_errors:
        badge_class = "badge-error"
        badge_text = f'{counts["FAIL"]}'
    elif has_warnings:
        badge_class = "badge-warning"
        badge_text = f'{counts["WARNING"]}'
    else:
        badge_class = "badge-pass"
        badge_text = "PASS"

    return f'''<a href="#{anchor}" class="nav-item" title="{_esc(validator_name)}">
        <span class="nav-text">{_esc(validator_name)}</span>
        <span class="badge {badge_class}">{badge_text}</span>
    </a>'''


def _generate_table_html(table: dict) -> str:
    """Generate HTML for a single result table."""
    parts = []

    if table.get("title") and table["title"] != table.get("parent_title", ""):
        parts.append(f'<h4 class="sub-table-title">{_esc(table["title"])}</h4>')

    # Pass message for empty results
    if not table["rows"] and not table["headers"]:
        msg = table.get("pass_message", "PASS - No issues found.")
        parts.append(f'<div class="pass-banner">{_esc(msg)}</div>')
        return "\n".join(parts)

    parts.append('<div class="table-wrapper"><table>')

    # Header
    parts.append("<thead><tr>")
    for h in table["headers"]:
        parts.append(f"<th>{_esc(h)}</th>")
    parts.append("</tr></thead>")

    # Body
    parts.append("<tbody>")
    for row in table["rows"]:
        parts.append("<tr>")
        for col_idx, cell in enumerate(row):
            if col_idx in table["severity_indices"]:
                style = _severity_style(cell)
                parts.append(f"<td {style}>{_esc(cell)}</td>")
            else:
                parts.append(f"<td>{_esc(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></div>")

    return "\n".join(parts)


def _make_anchor(name: str) -> str:
    """Generate a URL-safe anchor from a validator name."""
    return name.lower().replace(" ", "-").replace("_", "-")


CSS = """
:root {
    --bg: #f5f6fa;
    --sidebar-bg: #1e293b;
    --sidebar-hover: #334155;
    --sidebar-text: #cbd5e1;
    --sidebar-active: #3b82f6;
    --card-bg: #ffffff;
    --border: #e2e8f0;
    --text: #1e293b;
    --text-muted: #64748b;
    --header-bg: #4472C4;
    --header-text: #ffffff;
    --shadow: 0 1px 3px rgba(0,0,0,0.08);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
    min-height: 100vh;
}

/* ── Sidebar ─────────────────────────────── */
.sidebar {
    width: 280px;
    min-width: 280px;
    background: var(--sidebar-bg);
    color: var(--sidebar-text);
    padding: 0;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    overflow-y: auto;
    z-index: 100;
    display: flex;
    flex-direction: column;
}

.sidebar-header {
    padding: 20px 18px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

.sidebar-header h2 {
    font-size: 16px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.3px;
}

.sidebar-header .subtitle {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
}

.sidebar-nav {
    flex: 1;
    padding: 8px 0;
    overflow-y: auto;
}

.nav-section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #64748b;
    padding: 16px 18px 6px;
}

.nav-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 18px;
    text-decoration: none;
    color: var(--sidebar-text);
    font-size: 13px;
    transition: background 0.15s;
    border-left: 3px solid transparent;
}

.nav-item:hover {
    background: var(--sidebar-hover);
    border-left-color: var(--sidebar-active);
    color: #fff;
}

.nav-item.active {
    background: var(--sidebar-hover);
    border-left-color: var(--sidebar-active);
    color: #fff;
    font-weight: 600;
}

.nav-text {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-right: 8px;
}

.badge {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    flex-shrink: 0;
}

.badge-error { background: #FFC7CE; color: #9C0006; }
.badge-warning { background: #FFEB9C; color: #9C6500; }
.badge-pass { background: #C6EFCE; color: #006100; }
.badge-info { background: #BDD7EE; color: #1F4E79; }

/* ── Main content ────────────────────────── */
.main {
    margin-left: 280px;
    flex: 1;
    padding: 28px 36px;
    max-width: 100%;
    overflow-x: hidden;
}

.page-header {
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 2px solid var(--border);
}

.page-header h1 {
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
}

.page-header .meta {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 4px;
}

.summary-bar {
    display: flex;
    gap: 12px;
    margin-bottom: 28px;
    flex-wrap: wrap;
}

.summary-card {
    background: var(--card-bg);
    border-radius: 8px;
    padding: 14px 22px;
    box-shadow: var(--shadow);
    border-left: 4px solid #ccc;
    min-width: 120px;
}

.summary-card.error { border-left-color: #dc2626; }
.summary-card.warning { border-left-color: #f59e0b; }
.summary-card.pass { border-left-color: #16a34a; }
.summary-card.info { border-left-color: #3b82f6; }

.summary-card .count {
    font-size: 26px;
    font-weight: 700;
}

.summary-card .label {
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Validation sections ─────────────────── */
.validation-section {
    background: var(--card-bg);
    border-radius: 8px;
    box-shadow: var(--shadow);
    margin-bottom: 20px;
    overflow: hidden;
}

.section-header {
    padding: 14px 20px;
    background: var(--header-bg);
    color: var(--header-text);
    font-size: 15px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.section-header .result-count {
    font-size: 12px;
    font-weight: 400;
    opacity: 0.85;
}

.section-body {
    padding: 16px 20px;
}

.sub-table-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin: 12px 0 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border);
}

.sub-table-title:first-child { margin-top: 0; }

/* ── Tables ──────────────────────────────── */
.table-wrapper {
    overflow-x: auto;
    margin: 8px 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

thead th {
    background: #f1f5f9;
    color: var(--text);
    font-weight: 600;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

tbody td {
    padding: 9px 12px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
    max-width: 400px;
    word-wrap: break-word;
}

tbody tr:hover { background: #f8fafc; }

tbody tr:last-child td { border-bottom: none; }

.section-description {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 12px;
    font-style: italic;
}

.pass-banner {
    background: #C6EFCE;
    color: #006100;
    padding: 12px 16px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 13px;
    margin: 4px 0;
}

/* ── Scrollbar ───────────────────────────── */
.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }

/* ── Responsive ──────────────────────────── */
@media (max-width: 900px) {
    .sidebar { width: 220px; min-width: 220px; }
    .main { margin-left: 220px; padding: 20px; }
}
"""


def write_html_report(output_path: str, results: dict[str, list], doc_name: str = "") -> None:
    """Write all validation results to a single HTML file."""
    from validators.registry import ValidatorRegistry

    validators = ValidatorRegistry.all()
    # Pre-compute per-validator counts (used for both summary and nav)
    counts_map = {v.name: _count_issues(results.get(v.name, [])) for v in validators}
    total_counts = {"FAIL": 0, "WARNING": 0, "PASS": 0, "INFO": 0}
    for counts in counts_map.values():
        for k in total_counts:
            total_counts[k] += counts.get(k, 0)

    # Build HTML
    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BUD Validation Report{' — ' + _esc(doc_name) if doc_name else ''}</title>
<style>{CSS}</style>
</head>
<body>
""")

    # ── Sidebar ──────────────────────────────
    parts.append('<nav class="sidebar">')
    parts.append('<div class="sidebar-header">')
    parts.append('<h2>BUD Validator</h2>')
    if doc_name:
        parts.append(f'<div class="subtitle">{_esc(doc_name)}</div>')
    parts.append('</div>')
    parts.append('<div class="sidebar-nav">')
    parts.append('<div class="nav-section-label">Validations</div>')

    for v in validators:
        anchor = _make_anchor(v.name)
        nav_html = _generate_nav_item(v.name, anchor, results.get(v.name, []), counts_map[v.name])
        parts.append(nav_html)

    parts.append('</div></nav>')

    # ── Main content ─────────────────────────
    parts.append('<main class="main">')

    # Page header
    parts.append('<div class="page-header">')
    parts.append('<h1>Validation Report</h1>')
    if doc_name:
        parts.append(f'<div class="meta">{_esc(doc_name)}</div>')
    parts.append('</div>')

    # Summary bar
    parts.append('<div class="summary-bar">')
    error_total = total_counts["FAIL"]
    for label, count, cls in [
        ("Errors", error_total, "error"),
        ("Warnings", total_counts["WARNING"], "warning"),
        ("Passed", total_counts["PASS"], "pass"),
        ("Info", total_counts["INFO"], "info"),
    ]:
        parts.append(f'''<div class="summary-card {cls}">
            <div class="count">{count}</div>
            <div class="label">{label}</div>
        </div>''')
    parts.append('</div>')

    # Validation sections
    for v in validators:
        anchor = _make_anchor(v.name)
        v_results = results.get(v.name, [])
        tables = _extract_tables(v.name, v_results)

        row_count = sum(len(t["rows"]) for t in tables)
        count_text = f"{row_count} issue{'s' if row_count != 1 else ''}" if row_count else "No issues"

        parts.append(f'<section class="validation-section" id="{anchor}">')
        parts.append(f'<div class="section-header">')
        parts.append(f'<span>{_esc(v.name)}</span>')
        parts.append(f'<span class="result-count">{count_text}</span>')
        parts.append('</div>')
        parts.append('<div class="section-body">')

        if v.description:
            parts.append(f'<p class="section-description">{_esc(v.description)}</p>')

        for table in tables:
            table["parent_title"] = v.name
            parts.append(_generate_table_html(table))

        parts.append('</div></section>')

    parts.append('</main>')

    # ── Scroll-spy script ────────────────────
    parts.append("""<script>
document.addEventListener("DOMContentLoaded", function() {
    const sections = document.querySelectorAll(".validation-section");
    const navItems = document.querySelectorAll(".nav-item");

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                navItems.forEach(function(item) {
                    item.classList.toggle("active", item.getAttribute("href") === "#" + id);
                });
            }
        });
    }, { rootMargin: "-20% 0px -70% 0px" });

    sections.forEach(function(section) { observer.observe(section); });
});
</script>""")

    parts.append('</body></html>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
