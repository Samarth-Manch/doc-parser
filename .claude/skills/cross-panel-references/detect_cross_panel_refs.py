#!/usr/bin/env python3
"""Cross-panel reference detection skill — standalone driver.

Parses a BUD .docx, builds a global field index, then spawns one fresh `claude -p`
session per panel to detect cross-panel field references using the bundled
cross_panel_ref_agent.md prompt. Aggregates results, writes a JSON artifact and
a self-contained HTML report.

Exit codes:
  0 — success (even if some panels had zero refs or isolated failures)
  1 — every panel failed LLM detection
  2 — malformed input (docx missing / unreadable, or parser error)
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SKILL_DIR
# Walk up until we find the project root (contains doc_parser/ package).
for candidate in [SKILL_DIR] + list(SKILL_DIR.parents):
    if (candidate / "doc_parser").is_dir():
        PROJECT_ROOT = candidate
        break
sys.path.insert(0, str(PROJECT_ROOT))

from doc_parser import DocumentParser  # noqa: E402


AGENT_MD = SKILL_DIR / "cross_panel_ref_agent.md"

VALID_RELATIONSHIPS = {
    "copy_operation", "visibility_control", "mandatory_control", "validation",
    "enable_disable", "default_value", "clear_operation", "conditional", "other",
}
VALID_RESOLUTIONS = {"explicit", "inferred", "ambiguous"}
VALID_OPERATIONS = {"incoming", "outgoing"}


# ─────────────────────────────────────────────────────────────────────────────
# Parsing + index building
# ─────────────────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s).strip("_").lower() or "panel"


def load_agent_prompt() -> str:
    """Read the bundled agent markdown, strip frontmatter, return the body."""
    text = AGENT_MD.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    return text.lstrip("\n")


def group_fields_by_panel(parsed_doc) -> dict[str, list[dict]]:
    """Walk all_fields in order, tracking current PANEL. Each panel's list
    includes its PANEL header entry at position 0 so downstream can analyze
    panel-level logic.

    Fields with a missing variable_name get a synthesized one (derived from the
    field name, scoped per-panel with a numeric suffix on collision) so they
    still land in the global index and can be resolved as cross-panel targets.
    """
    panels: dict[str, list[dict]] = defaultdict(list)
    current = "default_panel"
    used_per_panel: dict[str, set[str]] = defaultdict(set)

    def synth_varname(panel: str, field_name: str) -> str:
        base = re.sub(r"[^a-z0-9]", "", (field_name or "").lower()) or "field"
        candidate = f"__{base}__"
        used = used_per_panel[panel]
        if candidate not in used:
            used.add(candidate)
            return candidate
        i = 2
        while f"__{base}_{i}__" in used:
            i += 1
        out = f"__{base}_{i}__"
        used.add(out)
        return out

    for fld in parsed_doc.all_fields:
        ftype = fld.field_type.value if hasattr(fld.field_type, "value") else str(fld.field_type)
        entry = {
            "field_name": fld.name or "",
            "variable_name": fld.variable_name or "",
            "field_type": ftype,
            "logic": fld.logic or "",
            "mandatory": bool(fld.is_mandatory),
        }
        if ftype == "PANEL":
            current = fld.name or current
            if not entry["variable_name"]:
                entry["variable_name"] = "_" + re.sub(r"[^a-z0-9]", "", current.lower()) + "_"
            used_per_panel[current].add(entry["variable_name"])
            panels[current].append(entry)
        else:
            if not entry["variable_name"] and entry["field_name"]:
                entry["variable_name"] = synth_varname(current, entry["field_name"])
            elif entry["variable_name"]:
                used_per_panel[current].add(entry["variable_name"])
            panels[current].append(entry)
    return dict(panels)


def build_global_index(fields_by_panel: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Compact index: {panel: [{field_name, variable_name, field_type}, ...]}."""
    index: dict[str, list[dict]] = {}
    for panel, fields in fields_by_panel.items():
        index[panel] = [
            {
                "field_name": f["field_name"],
                "variable_name": f["variable_name"],
                "field_type": f["field_type"],
            }
            for f in fields
            if f.get("variable_name") and f.get("field_name")
        ]
    return index


# ─────────────────────────────────────────────────────────────────────────────
# Per-panel LLM worker
# ─────────────────────────────────────────────────────────────────────────────

def run_panel(
    panel_name: str,
    panel_fields: list[dict],
    all_panels_index_file: Path,
    temp_dir: Path,
    log_file: Path,
    agent_body: str,
    model: str,
    skip_empty_logic: bool,
    timeout: int,
) -> tuple[str, dict | None, str | None]:
    """Run one panel's detection. Returns (panel_name, result_dict, error_msg)."""
    slug = slugify(panel_name)
    input_file = temp_dir / f"panel_{slug}_input.json"
    output_file = temp_dir / f"panel_{slug}_output.json"

    fields_for_agent = panel_fields
    if skip_empty_logic:
        fields_for_agent = [
            f for f in panel_fields
            if (f.get("logic") or "").strip()
            or (f.get("field_type") == "PANEL")  # keep panel headers for context
        ]

    input_payload = {"panel_name": panel_name, "fields": fields_for_agent}
    input_file.write_text(json.dumps(input_payload, indent=2), encoding="utf-8")

    header = (
        f"## Runtime variables (substitute into the agent prompt below)\n\n"
        f"- $PANEL_NAME = {panel_name}\n"
        f"- $PANEL_FIELDS_FILE = {input_file}\n"
        f"- $ALL_PANELS_INDEX_FILE = {all_panels_index_file}\n"
        f"- $OUTPUT_FILE = {output_file}\n"
        f"- $LOG_FILE = {log_file}\n\n"
        f"Follow the agent instructions below exactly. Read the two input files, "
        f"analyze each field in this panel, and write the final JSON object to "
        f"$OUTPUT_FILE. Do not print JSON to stdout — only write to the output file.\n\n"
        f"---\n\n"
    )
    prompt = header + agent_body

    t0 = time.time()
    try:
        proc = subprocess.run(
            ["claude", "--model", model, "-p", prompt,
             "--agent", str(AGENT_MD),
             "--allowedTools", "Read,Write"],
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return panel_name, None, f"timeout after {timeout}s"
    except FileNotFoundError:
        return panel_name, None, "claude CLI not found on PATH"

    elapsed = time.time() - t0
    if not output_file.exists():
        msg = f"no output file (exit {proc.returncode}); stderr head: {proc.stderr[:200]!r}"
        return panel_name, None, msg

    try:
        raw = json.loads(output_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return panel_name, None, f"invalid JSON in output: {e}"

    if not isinstance(raw, dict) or "cross_panel_references" not in raw:
        return panel_name, None, f"malformed output schema (keys={list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__})"

    # Attach elapsed for reporting
    raw.setdefault("_elapsed_sec", round(elapsed, 2))
    return panel_name, raw, None


# ─────────────────────────────────────────────────────────────────────────────
# Validation + aggregation
# ─────────────────────────────────────────────────────────────────────────────

def validate_ref(ref: dict, panel_name: str, global_index: dict[str, list[dict]]) -> str | None:
    """Return an error string if the ref is invalid, else None."""
    if not isinstance(ref, dict):
        return "not a dict"
    src = ref.get("source_field") or {}
    tgt = ref.get("target_field") or {}
    det = ref.get("reference_details") or {}
    if not isinstance(src, dict) or not isinstance(tgt, dict) or not isinstance(det, dict):
        return "source_field / target_field / reference_details not dicts"

    src_panel = src.get("panel", "")
    tgt_panel = tgt.get("panel", "")
    if not src_panel or not tgt_panel:
        return "missing panel"
    if src_panel == tgt_panel:
        return "intra-panel (source_panel == target_panel)"

    # Verify referenced variable_name actually exists in the declared panel
    for role, side in (("source", src), ("target", tgt)):
        vn = side.get("variable_name", "")
        p = side.get("panel", "")
        known = {f["variable_name"] for f in global_index.get(p, [])}
        if vn and vn not in known:
            return f"{role}.variable_name {vn!r} not in panel {p!r} index"

    rel = det.get("relationship_type", "")
    if rel not in VALID_RELATIONSHIPS:
        return f"invalid relationship_type {rel!r}"
    res = det.get("panel_resolution", "")
    if res not in VALID_RESOLUTIONS:
        return f"invalid panel_resolution {res!r}"
    op = det.get("operation_type", "")
    if op not in VALID_OPERATIONS:
        return f"invalid operation_type {op!r}"
    return None


def aggregate(
    per_panel: dict[str, dict],
    errors: list[dict],
    global_index: dict[str, list[dict]],
    fields_by_panel: dict[str, list[dict]],
    docx_path: Path,
) -> dict:
    all_refs: list[dict] = []
    panel_summary: list[dict] = []

    emitted_by_panel: dict[str, int] = defaultdict(int)
    fields_with_refs_by_panel: dict[str, set[str]] = defaultdict(set)

    for panel, fields in fields_by_panel.items():
        result = per_panel.get(panel) or {}
        refs = result.get("cross_panel_references") or []
        kept: list[dict] = []
        for ref in refs:
            err = validate_ref(ref, panel, global_index)
            if err:
                errors.append({"panel": panel, "message": f"dropped ref: {err}"})
                continue
            kept.append(ref)
            emitted_by_panel[panel] += 1
            # a ref "belongs" to a panel for summary purposes via whichever side matches
            src = ref["source_field"]["variable_name"]
            tgt = ref["target_field"]["variable_name"]
            if ref["source_field"]["panel"] == panel:
                fields_with_refs_by_panel[panel].add(src)
            if ref["target_field"]["panel"] == panel:
                fields_with_refs_by_panel[panel].add(tgt)
        all_refs.extend(kept)

    # Global dedup across panels
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for ref in all_refs:
        key = (
            ref["source_field"].get("variable_name", ""),
            ref["target_field"].get("variable_name", ""),
            ref["reference_details"].get("relationship_type", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)

    for panel, fields in fields_by_panel.items():
        panel_summary.append({
            "panel_name": panel,
            "field_count": len(fields),
            "fields_with_cross_panel_refs": len(fields_with_refs_by_panel[panel]),
            "references_emitted_here": emitted_by_panel[panel],
        })

    # Relationship summary
    rel_summary = {k: 0 for k in VALID_RELATIONSHIPS}
    for ref in deduped:
        rel = ref["reference_details"].get("relationship_type", "other")
        if rel not in rel_summary:
            rel_summary[rel] = 0
        rel_summary[rel] += 1

    # Dependency graph
    source_panels: dict[str, dict] = {}
    target_panels: dict[str, dict] = {}
    for ref in deduped:
        sp = ref["source_field"]["panel"]
        tp = ref["target_field"]["panel"]
        source_panels.setdefault(sp, {"affects_panels": set(), "reference_count": 0})
        source_panels[sp]["affects_panels"].add(tp)
        source_panels[sp]["reference_count"] += 1
        target_panels.setdefault(tp, {"affected_by_panels": set(), "reference_count": 0})
        target_panels[tp]["affected_by_panels"].add(sp)
        target_panels[tp]["reference_count"] += 1
    for node in source_panels.values():
        node["affects_panels"] = sorted(node["affects_panels"])
    for node in target_panels.values():
        node["affected_by_panels"] = sorted(node["affected_by_panels"])

    total_fields = sum(len(fs) for fs in fields_by_panel.values())
    return {
        "document_info": {
            "file_name": docx_path.name,
            "file_path": str(docx_path),
            "extraction_timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_fields": total_fields,
            "total_panels": len(fields_by_panel),
        },
        "panel_summary": panel_summary,
        "cross_panel_references": deduped,
        "relationship_summary": rel_summary,
        "dependency_graph": {
            "source_panels": source_panels,
            "target_panels": target_panels,
        },
        "errors": errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML rendering
# ─────────────────────────────────────────────────────────────────────────────

REL_COLOR = {
    "copy_operation": "#2e7d32",
    "visibility_control": "#1565c0",
    "mandatory_control": "#6a1b9a",
    "validation": "#ef6c00",
    "enable_disable": "#00838f",
    "default_value": "#558b2f",
    "clear_operation": "#c62828",
    "conditional": "#4e342e",
    "other": "#546e7a",
}

RES_COLOR = {
    "explicit": "#2e7d32",
    "inferred": "#f9a825",
    "ambiguous": "#c62828",
}


def render_html(result: dict) -> str:
    def esc(s: Any) -> str:
        return html.escape("" if s is None else str(s))

    doc = result["document_info"]
    refs = result["cross_panel_references"]
    rel_summary = result["relationship_summary"]
    dep = result["dependency_graph"]
    errors = result.get("errors", [])

    rel_pills = "".join(
        f'<span class="pill" style="background:{REL_COLOR.get(k, "#777")}">{esc(k)}: {v}</span>'
        for k, v in sorted(rel_summary.items()) if v > 0
    ) or '<em>none</em>'

    res_counts: dict[str, int] = defaultdict(int)
    for r in refs:
        res_counts[r["reference_details"].get("panel_resolution", "explicit")] += 1
    res_pills = "".join(
        f'<span class="pill" style="background:{RES_COLOR.get(k, "#777")}">{esc(k)}: {v}</span>'
        for k, v in sorted(res_counts.items())
    ) or '<em>none</em>'

    # Dependency graph section
    src_rows = "".join(
        f"<tr><td>{esc(p)}</td><td>{esc(', '.join(d['affects_panels']))}</td>"
        f"<td>{d['reference_count']}</td></tr>"
        for p, d in sorted(dep["source_panels"].items())
    ) or '<tr><td colspan=3><em>none</em></td></tr>'
    tgt_rows = "".join(
        f"<tr><td>{esc(p)}</td><td>{esc(', '.join(d['affected_by_panels']))}</td>"
        f"<td>{d['reference_count']}</td></tr>"
        for p, d in sorted(dep["target_panels"].items())
    ) or '<tr><td colspan=3><em>none</em></td></tr>'

    # Panel summary rows
    panel_rows = "".join(
        f"<tr><td>{esc(p['panel_name'])}</td><td>{p['field_count']}</td>"
        f"<td>{p['fields_with_cross_panel_refs']}</td>"
        f"<td>{p['references_emitted_here']}</td></tr>"
        for p in result["panel_summary"]
    ) or '<tr><td colspan=4><em>none</em></td></tr>'

    # Main ref table — include data-* attrs for client-side filtering
    ref_rows = []
    for i, r in enumerate(refs):
        s = r["source_field"]; t = r["target_field"]; d = r["reference_details"]
        raw = d.get("raw_expression", "")
        short = raw if len(raw) <= 140 else raw[:137] + "…"
        cand = d.get("candidate_panels") or []
        cand_html = ""
        if cand:
            bits = [f"<code>{esc(c.get('panel',''))}·{esc(c.get('variable_name',''))}</code>"
                    for c in cand]
            cand_html = f"<br><span class='cand'>candidates: {', '.join(bits)}</span>"
        ref_rows.append(
            f'<tr data-src-panel="{esc(s["panel"])}" data-tgt-panel="{esc(t["panel"])}" '
            f'data-rel="{esc(d.get("relationship_type",""))}" '
            f'data-res="{esc(d.get("panel_resolution",""))}">'
            f'<td>{i+1}</td>'
            f'<td><strong>{esc(s["panel"])}</strong><br>{esc(s["field_name"])}<br>'
            f'<code>{esc(s["variable_name"])}</code></td>'
            f'<td><strong>{esc(t["panel"])}</strong><br>{esc(t["field_name"])}<br>'
            f'<code>{esc(t["variable_name"])}</code></td>'
            f'<td><span class="pill" style="background:{REL_COLOR.get(d.get("relationship_type",""),"#777")}">'
            f'{esc(d.get("relationship_type",""))}</span><br>'
            f'<small>{esc(d.get("operation_type",""))}</small></td>'
            f'<td><span class="pill" style="background:{RES_COLOR.get(d.get("panel_resolution",""),"#777")}">'
            f'{esc(d.get("panel_resolution",""))}</span>{cand_html}</td>'
            f'<td><em>{esc(d.get("matched_text",""))}</em><br>'
            f'<details><summary>{esc(short)}</summary>'
            f'<pre style="white-space:pre-wrap">{esc(raw)}</pre></details></td>'
            f'</tr>'
        )
    ref_rows_html = "".join(ref_rows) or '<tr><td colspan=6><em>No cross-panel references detected.</em></td></tr>'

    # Filter option sets
    src_panels = sorted({r["source_field"]["panel"] for r in refs})
    tgt_panels = sorted({r["target_field"]["panel"] for r in refs})

    def opts(vals): return "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vals)

    errors_html = ""
    if errors:
        rows = "".join(
            f"<tr><td>{esc(e.get('panel',''))}</td><td>{esc(e.get('message',''))}</td></tr>"
            for e in errors
        )
        errors_html = f"""
<h2>Errors ({len(errors)})</h2>
<table><thead><tr><th>Panel</th><th>Message</th></tr></thead><tbody>{rows}</tbody></table>
"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Cross-Panel References — {esc(doc['file_name'])}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color:#222; max-width: 1400px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; border-bottom: 1px solid #eaecef; padding-bottom: 6px; margin-top: 32px; }}
  .meta {{ color:#666; font-size: 13px; margin-bottom: 20px; }}
  .cards {{ display:flex; gap:12px; margin: 16px 0 24px; flex-wrap: wrap; }}
  .card {{ flex:1; min-width: 180px; border:1px solid #e1e4e8; border-radius:8px; padding:14px; background:#fafbfc; }}
  .card .n {{ font-size: 28px; font-weight:700; }}
  .card .l {{ font-size: 12px; text-transform: uppercase; color:#586069; letter-spacing: 0.5px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ text-align:left; padding: 8px 10px; border-bottom: 1px solid #eaecef; vertical-align: top; }}
  th {{ background:#f6f8fa; font-weight:600; }}
  code {{ font-family: SFMono-Regular, Consolas, monospace; background:#f6f8fa; padding:1px 4px; border-radius:3px; font-size: 12px; }}
  .pill {{ display:inline-block; color:#fff; padding: 2px 8px; border-radius: 10px; font-size:11px; font-weight:600; margin-right:4px; }}
  .cand {{ font-size:11px; color:#555; }}
  .filters {{ display:flex; gap:8px; margin: 12px 0; flex-wrap: wrap; align-items:center; }}
  .filters select, .filters input {{ padding: 4px 6px; font-size: 13px; }}
  details summary {{ cursor: pointer; color:#333; }}
  pre {{ background:#f6f8fa; padding: 8px; border-radius:4px; font-size:12px; margin: 6px 0 0; }}
</style></head><body>

<h1>Cross-Panel Reference Report</h1>
<div class="meta">
  <strong>Document:</strong> {esc(doc['file_name'])}<br>
  <strong>Path:</strong> <code>{esc(doc['file_path'])}</code><br>
  <strong>Generated:</strong> {esc(doc['extraction_timestamp'])}
</div>

<div class="cards">
  <div class="card"><div class="n">{doc['total_fields']}</div><div class="l">Total fields</div></div>
  <div class="card"><div class="n">{doc['total_panels']}</div><div class="l">Panels</div></div>
  <div class="card"><div class="n">{len(refs)}</div><div class="l">Cross-panel refs</div></div>
  <div class="card"><div class="n">{len(errors)}</div><div class="l">Errors</div></div>
</div>

<h2>Relationship types</h2>
<div>{rel_pills}</div>

<h2>Panel resolution</h2>
<div>{res_pills}</div>

<h2>Panel summary</h2>
<table><thead><tr><th>Panel</th><th>Fields</th><th>Fields w/ refs</th><th>Refs emitted</th></tr></thead>
<tbody>{panel_rows}</tbody></table>

<h2>Dependency graph — source panels</h2>
<table><thead><tr><th>Source panel</th><th>Affects panels</th><th>Refs</th></tr></thead>
<tbody>{src_rows}</tbody></table>

<h2>Dependency graph — target panels</h2>
<table><thead><tr><th>Target panel</th><th>Affected by panels</th><th>Refs</th></tr></thead>
<tbody>{tgt_rows}</tbody></table>

<h2>References ({len(refs)})</h2>
<div class="filters">
  <label>Source panel <select id="f-src"><option value="">(any)</option>{opts(src_panels)}</select></label>
  <label>Target panel <select id="f-tgt"><option value="">(any)</option>{opts(tgt_panels)}</select></label>
  <label>Relationship <select id="f-rel"><option value="">(any)</option>{opts(sorted(VALID_RELATIONSHIPS))}</select></label>
  <label>Resolution <select id="f-res"><option value="">(any)</option>{opts(sorted(VALID_RESOLUTIONS))}</select></label>
  <label>Search <input id="f-q" type="search" placeholder="filter on text..."></label>
</div>
<table id="reftable"><thead><tr><th>#</th><th>Source</th><th>Target</th><th>Relationship</th>
<th>Resolution</th><th>Matched / raw logic</th></tr></thead>
<tbody>{ref_rows_html}</tbody></table>

{errors_html}

<script>
(function(){{
  const rows = Array.from(document.querySelectorAll('#reftable tbody tr'));
  const f = {{
    src: document.getElementById('f-src'),
    tgt: document.getElementById('f-tgt'),
    rel: document.getElementById('f-rel'),
    res: document.getElementById('f-res'),
    q:   document.getElementById('f-q')
  }};
  function apply(){{
    const q = (f.q.value || '').toLowerCase();
    rows.forEach(r=>{{
      const ok = (!f.src.value || r.dataset.srcPanel === f.src.value)
              && (!f.tgt.value || r.dataset.tgtPanel === f.tgt.value)
              && (!f.rel.value || r.dataset.rel === f.rel.value)
              && (!f.res.value || r.dataset.res === f.res.value)
              && (!q || r.textContent.toLowerCase().includes(q));
      r.style.display = ok ? '' : 'none';
    }});
  }}
  Object.values(f).forEach(el => el.addEventListener('input', apply));
}})();
</script>
</body></html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bud", required=True, help="Path to the BUD .docx")
    ap.add_argument("--output", default="output/cross_panel_references",
                    help="Output root (default: output/cross_panel_references)")
    ap.add_argument("--max-workers", type=int, default=4,
                    help="Parallel per-panel LLM workers (default: 4)")
    ap.add_argument("--model", default="haiku", help="Claude model (default: haiku)")
    ap.add_argument("--skip-empty-logic", action="store_true",
                    help="Drop fields with empty logic before sending to LLM")
    ap.add_argument("--timeout", type=int, default=600,
                    help="Per-panel LLM timeout seconds (default: 600)")
    args = ap.parse_args(argv)

    bud = Path(args.bud).expanduser().resolve()
    if not bud.is_file():
        print(f"error: BUD file not found: {bud}", file=sys.stderr)
        return 2

    stem = bud.stem
    out_root = Path(args.output).expanduser().resolve() / stem
    temp_dir = out_root / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_root / "run.log"
    log_file.write_text(f"# Run started {datetime.now().isoformat()}\n", encoding="utf-8")

    def log(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log(f"BUD: {bud}")
    log(f"Output: {out_root}")

    try:
        parsed = DocumentParser().parse(str(bud))
    except Exception as e:
        print(f"error: DocumentParser failed: {e}", file=sys.stderr)
        return 2

    fields_by_panel = group_fields_by_panel(parsed)
    if not fields_by_panel:
        print("error: no panels found in BUD", file=sys.stderr)
        return 2

    global_index = build_global_index(fields_by_panel)
    all_panels_index_file = temp_dir / "all_panels_index.json"
    all_panels_index_file.write_text(json.dumps(global_index, indent=2), encoding="utf-8")
    log(f"Parsed {sum(len(v) for v in fields_by_panel.values())} fields across {len(fields_by_panel)} panels")

    agent_body = load_agent_prompt()

    per_panel: dict[str, dict] = {}
    errors: list[dict] = []
    panels_list = list(fields_by_panel.items())

    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
        futures = {
            pool.submit(
                run_panel, name, fields, all_panels_index_file, temp_dir,
                log_file, agent_body, args.model, args.skip_empty_logic, args.timeout,
            ): name
            for name, fields in panels_list
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                pname, result, err = fut.result()
            except Exception as e:
                errors.append({"panel": name, "message": f"worker crashed: {e}"})
                log(f"  [{name}] worker crashed: {e}")
                continue
            if err or not result:
                errors.append({"panel": pname, "message": err or "unknown failure"})
                log(f"  [{pname}] FAILED: {err}")
                continue
            n = len(result.get("cross_panel_references", []))
            log(f"  [{pname}] {n} refs ({result.get('_elapsed_sec', '?')}s)")
            per_panel[pname] = result

    if not per_panel and panels_list:
        print("error: every panel failed", file=sys.stderr)
        # Still write an (empty) report so the failure is inspectable
        aggregated = aggregate(per_panel, errors, global_index, fields_by_panel, bud)
        json_path = out_root / f"{stem}_cross_panel_references.json"
        html_path = out_root / f"{stem}_cross_panel_references.html"
        json_path.write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
        html_path.write_text(render_html(aggregated), encoding="utf-8")
        print(f"JSON: {json_path}")
        print(f"HTML: {html_path}")
        return 1

    aggregated = aggregate(per_panel, errors, global_index, fields_by_panel, bud)

    json_path = out_root / f"{stem}_cross_panel_references.json"
    html_path = out_root / f"{stem}_cross_panel_references.html"
    json_path.write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
    html_path.write_text(render_html(aggregated), encoding="utf-8")

    n_refs = len(aggregated["cross_panel_references"])
    log(f"Wrote {n_refs} refs")
    print(f"JSON: {json_path}")
    print(f"HTML: {html_path}")
    print(f"Refs: {n_refs}  Errors: {len(errors)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
