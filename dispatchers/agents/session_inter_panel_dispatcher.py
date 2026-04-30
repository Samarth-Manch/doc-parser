#!/usr/bin/env python3
"""
Session Inter-Panel Dispatcher (Stage 7.5)

Runs AFTER session_based_dispatcher and BEFORE convert_to_api_format.

Handles cross-panel session/party-scoped behavior from BUD sections 4.5.1
(Initiator Behaviour, FIRST_PARTY) and 4.5.2 (Vendor Behaviour, SECOND_PARTY)
that the per-panel session agent dropped because the controller field lives
in another panel (08_session_based_agent.md Rule 16).

Two-phase architecture (mirrors inter_panel_dispatcher):
  Phase 1: Per-panel LLM detection — for each panel, the BUD-table rows for
           4.5.1 and 4.5.2 are passed to the detection agent along with the
           all-panels index. The agent identifies which rows have cross-panel
           controllers and outputs structured refs.
  Phase 2: Deterministic emission — Python builds Expression (Client) rules
           using sbmvi/sbminvi/dis/en/mm/mnm + pt() for each ref, places them
           on the controller field, and consolidates by (controller, condition,
           action, party) so multiple destinations collapse into one rule.
  Phase 3: Validate, dedupe, expand panel vars (for mandatory/enable_disable),
           merge into output.
"""

import argparse
import copy
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print

PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from doc_parser import DocumentParser
from inter_panel_utils import (
    build_variablename_index,
    expand_panel_variables_in_expressions,
)
from session_based_dispatcher import (
    extract_session_table_data,
    _normalize_field_name,
)


_SCHEMA_PATH = Path(PROJECT_ROOT) / "dispatchers" / "agents" / "schemas" / "session_inter_panel_refs.schema.json"
with open(_SCHEMA_PATH, "r") as _f:
    _SCHEMA_JSON = _f.read()


# ── Logging ───────────────────────────────────────────────────────────────────
_master_log: Optional[Path] = None
_log_lock = threading.Lock()


def log(msg: str, also_print: bool = True):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _log_lock:
        if also_print:
            print(line, flush=True)
        if _master_log:
            with open(_master_log, "a") as fh:
                fh.write(line + "\n")


def elapsed_str(start: float) -> str:
    secs = time.time() - start
    if secs < 60:
        return f"{secs:.1f}s"
    return f"{int(secs // 60)}m {secs % 60:.1f}s"


def _norm_var(v: str) -> str:
    """Normalize __varname__ or _varname_ to _varname_ for index lookups."""
    if not isinstance(v, str):
        return ""
    s = v.strip("_")
    return f"_{s}_" if s else v


def _double_underscore(v: str) -> str:
    """Convert a variableName to the double-underscore source_fields form."""
    if not isinstance(v, str):
        return ""
    s = v.strip("_")
    return f"__{s}__" if s else v


# ── Build per-panel BUD logic for the agent ──────────────────────────────────

def build_panel_bud_logic(
    panel_name: str,
    initiator_panel_data: Dict[str, Dict],
    vendor_panel_data: Dict[str, Dict],
    panel_fields: List[Dict],
) -> List[Dict]:
    """
    Build a list of BUD-table rows for one panel. Each row carries the field's
    variableName (resolved from the session_based-stage panel fields by name),
    and one entry per party that has logic for that field.

    A panel-level row is included when the BUD table has a PANEL-type entry for
    this panel. Its field_variableName is the PANEL field's variableName from
    the session_based output (so cross-panel destinations point at the panel).
    """
    rows: List[Dict] = []

    # Index session_based-stage fields by normalized name
    name_to_field: Dict[str, Dict] = {}
    panel_field_var: Optional[str] = None
    for fld in panel_fields:
        fname = fld.get("field_name", "")
        ftype = (fld.get("type") or "").upper()
        if ftype == "PANEL":
            panel_field_var = fld.get("variableName") or panel_field_var
            continue
        if fname:
            name_to_field[_normalize_field_name(fname)] = fld

    # Panel-level entry: synthesize from the BUD table's PANEL row (if present)
    # The BUD logic for a PANEL is stored under the panel itself in the parser's
    # current shape — handled separately below by walking each table.
    # extract_session_table_data() does NOT preserve PANEL-row logic; it only
    # stores child fields. We need to re-walk the raw BUD tables to get the
    # PANEL row's logic. We do this by re-parsing and looking up table rows
    # via _read_panel_row_logic() at the call site instead, then merging here.
    # For now: do not synthesize — caller will inject panel-level rows.

    # Build child rows for each party
    parties = [
        ("FIRST_PARTY", initiator_panel_data),
        ("SECOND_PARTY", vendor_panel_data),
    ]
    for party, table_data in parties:
        if not table_data:
            continue
        for normalized_name, entry in table_data.items():
            if normalized_name.startswith("__"):
                continue  # skip injected metadata keys (e.g. __panel_logic__)
            if not isinstance(entry, dict):
                continue
            logic = (entry.get("logic") or "").strip()
            if not logic:
                continue
            field = name_to_field.get(normalized_name)
            if not field:
                continue  # field exists in BUD table but not in session output
            rows.append({
                "field_name": field.get("field_name", entry.get("original_name", "")),
                "field_variableName": _norm_var(field.get("variableName", "")),
                "field_type": (field.get("type") or "").upper(),
                "party": party,
                "mandatory": entry.get("mandatory", ""),
                "logic": logic,
            })

    # Panel-level rows (use the panel's own variableName)
    if panel_field_var:
        for party, panel_logic in (
            ("FIRST_PARTY", initiator_panel_data.get("__panel_logic__")),
            ("SECOND_PARTY", vendor_panel_data.get("__panel_logic__")),
        ):
            if panel_logic:
                rows.append({
                    "field_name": panel_name,
                    "field_variableName": _norm_var(panel_field_var),
                    "field_type": "PANEL",
                    "party": party,
                    "mandatory": "",
                    "logic": panel_logic,
                })

    return rows


def extract_panel_level_logic(bud_path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Re-walk the BUD raw tables to capture each PANEL-row's logic from 4.5.1 and
    4.5.2 (extract_session_table_data only preserves child-field logic).
    Returns (initiator_panel_logic, vendor_panel_logic): {panel_name -> logic}.
    """
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    initiator: Dict[str, str] = {}
    vendor: Dict[str, str] = {}

    for table in parsed.raw_tables:
        ctx = (table.context or "").lower()
        if table.table_type == "initiator_fields" and ("4.5.1" in table.context or "initiator" in ctx):
            target = initiator
        elif table.table_type == "spoc_fields" and ("4.5.2" in table.context or "vendor" in ctx):
            target = vendor
        else:
            continue

        for row in table.rows:
            if not row or not row[0].strip():
                continue
            field_name = row[0].strip()
            field_type = (row[1].strip().upper() if len(row) > 1 else "")
            logic = (row[3].strip() if len(row) > 3 else "")
            if field_type == "PANEL" and logic:
                target[field_name] = logic

    return initiator, vendor


def build_all_panels_index(input_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Build {panel_name: [{field_name, variableName, type}]} for the agent to
    resolve cross-panel controller fields by name.
    """
    out: Dict[str, List[Dict]] = {}
    for panel_name, fields in input_data.items():
        entries: List[Dict] = []
        for f in fields:
            var = f.get("variableName", "")
            if not var:
                continue
            entries.append({
                "field_name": f.get("field_name", ""),
                "variableName": _norm_var(var),
                "type": (f.get("type") or "").upper(),
            })
        out[panel_name] = entries
    return out


# ── Phase 1: per-panel detection ─────────────────────────────────────────────

def detect_cross_panel_session_refs(
    panel_name: str,
    bud_logic_rows: List[Dict],
    all_panels_index_file: Path,
    temp_dir: Path,
    model: str = "opus",
) -> Optional[List[Dict]]:
    """
    Run the LLM detection agent for ONE panel. Returns the agent's
    `cross_panel_session_refs` list, or None on failure.
    """
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", panel_name).lower() or "panel"
    bud_logic_file = temp_dir / f"detect_{safe_name}_bud_logic.json"
    with open(bud_logic_file, "w") as fh:
        json.dump(bud_logic_rows, fh, indent=2)

    prompt = f"""Detect cross-panel session-scoped references for one panel.

## Input
- PANEL_NAME: {panel_name}
- PANEL_BUD_LOGIC_FILE: {bud_logic_file}
- ALL_PANELS_INDEX_FILE: {all_panels_index_file}

Read the BUD logic rows and the all-panels index.
For each row whose logic conditions on a field that lives in another panel,
emit one entry in `cross_panel_session_refs` per the schema. Skip same-panel
and unconditional rows. Output a single JSON object as your final response.
"""

    if not bud_logic_rows:
        log(f"  Phase 1: '{panel_name}' has no BUD-table logic — skipping")
        return []

    try:
        log(f"  Phase 1: Detecting session refs in '{panel_name}' "
            f"({len(bud_logic_rows)} BUD rows)...")
        t0 = time.time()
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--output-format", "json",
                "--agent", "mini/10_session_inter_panel_detect_refs",
                "--allowedTools", "Read",
                "--json-schema", _SCHEMA_JSON,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            log(f"  Phase 1: FAILED for '{panel_name}' "
                f"(exit {process.returncode}) after {elapsed_str(t0)}")
            if stderr:
                log(f"    stderr: {stderr.strip()[:400]}")
            return None
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as e:
            log(f"  Phase 1: bad CLI envelope for '{panel_name}': {e}")
            return None
        raw = envelope.get("structured_output")
        if not isinstance(raw, dict):
            log(f"  Phase 1: missing structured_output for '{panel_name}'")
            return None
        refs = raw.get("cross_panel_session_refs", []) or []
        log(f"  Phase 1: '{panel_name}' — {len(refs)} refs detected ({elapsed_str(t0)})")
        return refs
    except FileNotFoundError:
        log("  Phase 1: 'claude' command not found")
        return None
    except Exception as e:
        log(f"  Phase 1: error for '{panel_name}': {e}")
        return None


# ── Phase 2: deterministic expression emission ──────────────────────────────

PARTY_TO_PT = {"FIRST_PARTY": "FP", "SECOND_PARTY": "SP"}


def _format_value_list(values: List[str]) -> str:
    """Build the bracketed string-array literal for `in` / `not_in` operators."""
    inner = ", ".join(json.dumps(v) for v in values)
    return f"[{inner}]"


def _build_clause(cond: Dict) -> Optional[str]:
    """
    Build the boolean clause for a single controller condition.
    Returns the clause text using the canonical _ctrlvar_ form (single _).
    """
    var = _norm_var(cond.get("controller_field_variableName", ""))
    op = cond.get("operator", "")
    values: List[str] = list(cond.get("values") or [])
    if not var or not op or not values:
        return None
    var_expr = f'vo("{var}")'
    if op == "==":
        return f'{var_expr} == {json.dumps(values[0])}'
    if op == "!=":
        return f'{var_expr} != {json.dumps(values[0])}'
    if op == "in":
        if len(values) == 1:
            return f'{var_expr} == {json.dumps(values[0])}'
        return f'{var_expr} in {_format_value_list(values)}'
    if op == "not_in":
        if len(values) == 1:
            return f'{var_expr} != {json.dumps(values[0])}'
        return f'not({var_expr} in {_format_value_list(values)})'
    return None


def _negate_clause_set(clauses: List[str]) -> str:
    """
    Build the negation of (c1 and c2 and ...) using De Morgan's law.
    The result is a single boolean expression.
    """
    if not clauses:
        return "false"
    if len(clauses) == 1:
        return f"not({clauses[0]})"
    return "not(" + " and ".join(clauses) + ")"


def _join_and(clauses: List[str]) -> str:
    return " and ".join(clauses) if clauses else "true"


def _ref_signature(ref: Dict) -> Tuple:
    """
    Group key for consolidation: refs with the same (party, action, polarity,
    controller-clause set) collapse into ONE rule with multiple destinations.
    """
    conds = []
    for c in ref.get("conditions", []) or []:
        conds.append((
            _norm_var(c.get("controller_field_variableName", "")),
            c.get("operator", ""),
            tuple(c.get("values") or []),
        ))
    return (
        ref.get("party", ""),
        ref.get("action", ""),
        ref.get("polarity", ""),
        tuple(sorted(conds)),
    )


def _placement_field(ref: Dict, var_index: Dict[str, str]) -> Optional[str]:
    """
    Pick the placement field (where the rule will live). We use the FIRST
    controller in the ref's conditions list whose variableName resolves in
    the all-panels index. Returns the canonical _var_ form.
    """
    for c in ref.get("conditions", []) or []:
        var = _norm_var(c.get("controller_field_variableName", ""))
        if var and var in var_index:
            return var
    return None


def emit_expression_rules(
    refs: List[Dict],
    var_index: Dict[str, str],
) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Group refs by (placement_field, signature) and emit consolidated Expression
    (Client) rules. Returns {panel_name: {placement_var: [rules]}}.
    """
    # group_key -> {placement_var, party, action, polarity, clauses, destinations[], snippets[]}
    groups: Dict[Tuple, Dict] = {}

    for ref in refs:
        placement = _placement_field(ref, var_index)
        if not placement:
            continue
        # Resolve the destination variableName (the field affected)
        dest = _norm_var(ref.get("field_variableName", ""))
        if not dest or dest not in var_index:
            continue
        # Build the AND'd clauses
        clauses: List[str] = []
        for c in ref.get("conditions", []) or []:
            cl = _build_clause(c)
            if cl:
                clauses.append(cl)
        if not clauses:
            continue
        # Merge dest's panel into involved-panel set
        sig = (placement,) + _ref_signature(ref)
        bucket = groups.setdefault(sig, {
            "placement": placement,
            "party": ref.get("party", ""),
            "action": ref.get("action", ""),
            "polarity": ref.get("polarity", ""),
            "clauses": clauses,
            "destinations": [],
            "snippets": [],
            "controller_vars": set(),
        })
        if dest not in bucket["destinations"]:
            bucket["destinations"].append(dest)
        snippet = ref.get("logic_snippet", "")
        if snippet and snippet not in bucket["snippets"]:
            bucket["snippets"].append(snippet)
        for c in ref.get("conditions", []) or []:
            v = _norm_var(c.get("controller_field_variableName", ""))
            if v:
                bucket["controller_vars"].add(v)

    # Now emit rules — keyed by panel of the placement field
    out: Dict[str, Dict[str, List[Dict]]] = {}

    for sig, b in groups.items():
        placement = b["placement"]
        party = b["party"]
        action = b["action"]
        polarity = b["polarity"]
        clauses = b["clauses"]
        destinations = b["destinations"]
        snippets = b["snippets"]
        controller_vars: Set[str] = b["controller_vars"]

        cond_pos = _join_and(clauses)
        cond_neg = _negate_clause_set(clauses)
        dest_args = ", ".join(f'"{d}"' for d in destinations)
        sp_or_fp = PARTY_TO_PT.get(party, "FP")

        rules: List[Dict] = []

        if action == "visibility":
            if polarity == "positive":
                expr = (
                    f'sbmvi({cond_pos}, "{party}", {dest_args});'
                    f'sbminvi({cond_neg}, "{party}", {dest_args})'
                )
            else:
                expr = (
                    f'sbminvi({cond_pos}, "{party}", {dest_args});'
                    f'sbmvi({cond_neg}, "{party}", {dest_args})'
                )
            rules.append({
                "rule_name": "Expression (Client)",
                "source_fields": sorted(_double_underscore(v) for v in controller_vars),
                "destination_fields": [],
                "conditionalValues": [expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "session",
                "_session_inter_panel_party": party,
                "_session_inter_panel_action": action,
                "_session_inter_panel_polarity": polarity,
                "_reasoning": (
                    f"Cross-panel session visibility for {party}: "
                    f"{', '.join(destinations)} -- {' / '.join(snippets)[:300]}"
                ),
            })
            # Auto non-mandatory pairing when invisible
            mandatory_expr_when_negative = (
                f'mnm(pt() == "{sp_or_fp}" and {cond_neg if polarity == "positive" else cond_pos}, {dest_args});'
                f'mm(pt() == "{sp_or_fp}" and {cond_pos if polarity == "positive" else cond_neg}, {dest_args})'
            )
            rules.append({
                "rule_name": "Expression (Client)",
                "source_fields": sorted(_double_underscore(v) for v in controller_vars),
                "destination_fields": [],
                "conditionalValues": [mandatory_expr_when_negative],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "mandatory",
                "_session_inter_panel_party": party,
                "_session_inter_panel_action": "mandatory",
                "_session_inter_panel_polarity": "auto_non_mandatory",
                "_reasoning": (
                    f"Auto non-mandatory paired with cross-panel visibility "
                    f"({party}): a hidden field cannot stay mandatory."
                ),
            })
        elif action == "enable_disable":
            if polarity == "positive":
                expr = (
                    f'en(pt() == "{sp_or_fp}" and {cond_pos}, {dest_args});'
                    f'dis(pt() == "{sp_or_fp}" and {cond_neg}, {dest_args})'
                )
            else:
                expr = (
                    f'dis(pt() == "{sp_or_fp}" and {cond_pos}, {dest_args});'
                    f'en(pt() == "{sp_or_fp}" and {cond_neg}, {dest_args})'
                )
            rules.append({
                "rule_name": "Expression (Client)",
                "source_fields": sorted(_double_underscore(v) for v in controller_vars),
                "destination_fields": [],
                "conditionalValues": [expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "enable_disable",
                "_session_inter_panel_party": party,
                "_session_inter_panel_action": action,
                "_session_inter_panel_polarity": polarity,
                "_reasoning": (
                    f"Cross-panel session enable/disable for {party}: "
                    f"{', '.join(destinations)} -- {' / '.join(snippets)[:300]}"
                ),
            })
            # Auto non-mandatory when disabled
            mandatory_expr = (
                f'mnm(pt() == "{sp_or_fp}" and {cond_pos if polarity == "negative" else cond_neg}, {dest_args});'
                f'mm(pt() == "{sp_or_fp}" and {cond_neg if polarity == "negative" else cond_pos}, {dest_args})'
            )
            rules.append({
                "rule_name": "Expression (Client)",
                "source_fields": sorted(_double_underscore(v) for v in controller_vars),
                "destination_fields": [],
                "conditionalValues": [mandatory_expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "mandatory",
                "_session_inter_panel_party": party,
                "_session_inter_panel_action": "mandatory",
                "_session_inter_panel_polarity": "auto_non_mandatory",
                "_reasoning": (
                    f"Auto non-mandatory paired with cross-panel disable "
                    f"({party}): a disabled field cannot stay mandatory."
                ),
            })
        elif action == "mandatory":
            if polarity == "positive":
                expr = (
                    f'mm(pt() == "{sp_or_fp}" and {cond_pos}, {dest_args});'
                    f'mnm(pt() == "{sp_or_fp}" and {cond_neg}, {dest_args})'
                )
            else:
                expr = (
                    f'mnm(pt() == "{sp_or_fp}" and {cond_pos}, {dest_args});'
                    f'mm(pt() == "{sp_or_fp}" and {cond_neg}, {dest_args})'
                )
            rules.append({
                "rule_name": "Expression (Client)",
                "source_fields": sorted(_double_underscore(v) for v in controller_vars),
                "destination_fields": [],
                "conditionalValues": [expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "mandatory",
                "_session_inter_panel_party": party,
                "_session_inter_panel_action": action,
                "_session_inter_panel_polarity": polarity,
                "_reasoning": (
                    f"Cross-panel session mandatory for {party}: "
                    f"{', '.join(destinations)} -- {' / '.join(snippets)[:300]}"
                ),
            })

        # Place under the placement field's panel
        placement_panel = var_index.get(placement)
        if not placement_panel:
            continue
        bucket = out.setdefault(placement_panel, {}).setdefault(placement, [])
        bucket.extend(rules)

    return out


# ── Merge into output ────────────────────────────────────────────────────────

def merge_rules_into_input(
    input_data: Dict[str, List[Dict]],
    rules_by_panel: Dict[str, Dict[str, List[Dict]]],
) -> Tuple[Dict[str, List[Dict]], int]:
    """
    Append the new Expression (Client) rules onto each placement field. Skips
    duplicates (same conditionalValues[0] on the same field).
    """
    output = copy.deepcopy(input_data)
    total = 0

    for panel_name, by_var in rules_by_panel.items():
        if panel_name not in output:
            log(f"  Merge: panel '{panel_name}' missing from input — skipping")
            continue
        # variableName -> field index
        var_to_idx: Dict[str, int] = {}
        for idx, fld in enumerate(output[panel_name]):
            v = _norm_var(fld.get("variableName", ""))
            if v:
                var_to_idx[v] = idx
        for placement_var, new_rules in by_var.items():
            idx = var_to_idx.get(placement_var)
            if idx is None:
                log(f"  Merge: placement var '{placement_var}' not in panel "
                    f"'{panel_name}' — skipping {len(new_rules)} rules")
                continue
            existing = output[panel_name][idx].setdefault("rules", [])
            existing_exprs: Set[str] = set()
            for r in existing:
                if isinstance(r, dict) and r.get("rule_name") == "Expression (Client)":
                    cv = r.get("conditionalValues") or []
                    if cv:
                        existing_exprs.add(cv[0])
            max_id = max(
                (r.get("id", 0) for r in existing if isinstance(r, dict)),
                default=0,
            )
            for rule in new_rules:
                cv = rule.get("conditionalValues") or []
                if cv and cv[0] in existing_exprs:
                    continue  # dedupe
                max_id += 1
                rule["id"] = max_id
                rule["_inter_panel_source"] = "session-inter-panel"
                existing.append(rule)
                existing_exprs.add(cv[0] if cv else "")
                total += 1

    return output, total


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Session Inter-Panel Dispatcher — handle cross-panel "
                    "session/party-scoped behavior from BUD 4.5.1 / 4.5.2."
    )
    parser.add_argument("--input", required=True,
                        help="Path to session_based stage output JSON")
    parser.add_argument("--bud", required=True,
                        help="Path to the BUD document (.docx)")
    parser.add_argument("--output", default="output/session_inter_panel/all_panels_session_inter_panel.json",
                        help="Output file path")
    parser.add_argument("--detect-model", default="opus",
                        help="Claude model for Phase 1 detection (default: opus)")
    parser.add_argument("--max-workers", type=int, default=4,
                        help="Max parallel detection workers (default: 4)")
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: input not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.bud).exists():
        print(f"Error: BUD not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    global _master_log
    _master_log = temp_dir / "session_inter_panel_master.log"
    with open(_master_log, "w") as fh:
        fh.write(f"=== Session Inter-Panel Dispatcher — {datetime.now().isoformat()} ===\n")

    log("=" * 60, also_print=False)
    log("SESSION INTER-PANEL DISPATCHER STARTED")
    log(f"Master log: {_master_log}")
    print(f"  Monitor progress:  tail -f {_master_log}")

    # Load session_based output
    log(f"Loading input: {args.input}")
    with open(args.input, "r") as fh:
        input_data: Dict[str, List[Dict]] = json.load(fh)
    log(f"  {len(input_data)} panels, "
        f"{sum(len(v) for v in input_data.values())} fields")

    # Parse BUD 4.5.1 and 4.5.2 tables (child-field rows + panel-row logic)
    log(f"Parsing BUD: {args.bud}")
    initiator_data, vendor_data = extract_session_table_data(args.bud)
    initiator_panel_logic, vendor_panel_logic = extract_panel_level_logic(args.bud)
    log(f"  4.5.1 panels: {sorted(initiator_data.keys())}")
    log(f"  4.5.2 panels: {sorted(vendor_data.keys())}")

    # Inject panel-row logic into the per-panel data dicts so build_panel_bud_logic sees it
    for pname, plogic in initiator_panel_logic.items():
        initiator_data.setdefault(pname, {})["__panel_logic__"] = plogic
    for pname, plogic in vendor_panel_logic.items():
        vendor_data.setdefault(pname, {})["__panel_logic__"] = plogic

    # Build all-panels index file
    all_panels_index = build_all_panels_index(input_data)
    all_panels_index_file = temp_dir / "all_panels_index.json"
    with open(all_panels_index_file, "w") as fh:
        json.dump(all_panels_index, fh, indent=2)
    log(f"  All-panels index written: {all_panels_index_file}")

    # ── Phase 1: per-panel detection in parallel ────────────────────────────
    log(f"PHASE 1: PER-PANEL SESSION REF DETECTION — "
        f"{len(input_data)} panels, max {args.max_workers} workers, model={args.detect_model}")
    t0 = time.time()

    all_refs: List[Dict] = []
    panel_jobs: List[Tuple[str, List[Dict]]] = []
    for panel_name, panel_fields in input_data.items():
        # Skip the special panel-logic stash key
        ip = {k: v for k, v in initiator_data.get(panel_name, {}).items()
              if k != "__panel_logic__"}
        vp = {k: v for k, v in vendor_data.get(panel_name, {}).items()
              if k != "__panel_logic__"}
        # Inject panel-level rows so build_panel_bud_logic emits them
        if panel_name in initiator_panel_logic:
            ip["__panel_logic__"] = initiator_panel_logic[panel_name]
        if panel_name in vendor_panel_logic:
            vp["__panel_logic__"] = vendor_panel_logic[panel_name]
        rows = build_panel_bud_logic(panel_name, ip, vp, panel_fields)
        if not rows:
            continue
        panel_jobs.append((panel_name, rows))

    log(f"  {len(panel_jobs)} panels have BUD-table logic to scan")

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        future_map = {
            executor.submit(
                detect_cross_panel_session_refs,
                pname, rows, all_panels_index_file, temp_dir, args.detect_model,
            ): pname
            for pname, rows in panel_jobs
        }
        for future in as_completed(future_map):
            pname = future_map[future]
            try:
                refs = future.result()
                if refs:
                    for r in refs:
                        r["_source_panel"] = pname
                    all_refs.extend(refs)
            except Exception as e:
                log(f"  Phase 1: exception for '{pname}': {e}")

    log(f"PHASE 1 COMPLETE — {len(all_refs)} cross-panel session refs in {elapsed_str(t0)}")

    # Persist Phase 1 output
    refs_file = temp_dir / "phase1_refs.json"
    with open(refs_file, "w") as fh:
        json.dump(all_refs, fh, indent=2)
    log(f"  Phase 1 refs persisted: {refs_file}")

    if not all_refs:
        log("No cross-panel session refs detected — copying input to output")
        with open(output_file, "w") as fh:
            json.dump(input_data, fh, indent=2)
        log(f"Output: {output_file}")
        sys.exit(0)

    # ── Phase 2: deterministic emission ─────────────────────────────────────
    log("PHASE 2: DETERMINISTIC EXPRESSION RULE EMISSION")
    t0 = time.time()
    var_index = build_variablename_index(input_data)
    # build_variablename_index uses the field's stored variableName directly
    # (could be __var__ or _var_). Normalize keys to canonical _var_ form so
    # _placement_field()/_norm_var() lookups match.
    var_index = {_norm_var(k): v for k, v in var_index.items()}

    rules_by_panel = emit_expression_rules(all_refs, var_index)
    rule_count = sum(
        sum(len(rules) for rules in by_var.values())
        for by_var in rules_by_panel.values()
    )
    log(f"PHASE 2 COMPLETE — {rule_count} rules emitted across "
        f"{len(rules_by_panel)} panels in {elapsed_str(t0)}")

    # ── Phase 3: merge + post-process ───────────────────────────────────────
    log("PHASE 3: MERGE + POST-PROCESS")
    t0 = time.time()
    output_data, merged = merge_rules_into_input(input_data, rules_by_panel)
    log(f"  Merged {merged} new rules into output")

    # Expand PANEL variableNames in mandatory/enable_disable expressions to
    # their child fields (mvi/minvi cascade automatically — left alone).
    expansions = expand_panel_variables_in_expressions(output_data, input_data)
    if expansions:
        log(f"  Expanded {expansions} PANEL var refs to child fields in mandatory/disable expressions")
    log(f"PHASE 3 COMPLETE in {elapsed_str(t0)}")

    # ── Write ───────────────────────────────────────────────────────────────
    with open(output_file, "w") as fh:
        json.dump(output_data, fh, indent=2)
    log(f"Output written: {output_file}")
    log(f"  Total fields: {sum(len(v) for v in output_data.values())}")
    log(f"  Total rules:  {sum(len(f.get('rules', [])) for v in output_data.values() for f in v)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
