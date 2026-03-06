#!/usr/bin/env python3
"""
Inter-Panel Cross-Panel Rules Dispatcher (v3 — Panel-by-Panel Architecture)

This script:
1. Quick scan: checks if any cross-panel references exist (early exit if none)
2. Phase 1: Per-panel reference detection — for each panel independently (parallel),
   calls a lightweight LLM to detect and classify cross-panel references
3. Phase 2: Rule generation — all refs (copy_to, visibility, derivation, clearing)
   grouped by source panel, sent to expression rule agent with only the involved panels.
   Copy To refs use ctfd expressions with on("change") wrapping.
   EDV-classified refs are excluded from Phase 2 (handled by Phase 4).
4. Phase 3: Validate + merge — deterministic Python merges all rules into output,
   validates variableNames, deduplicates, tags _inter_panel_source
"""

import argparse
import json
import subprocess
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from context_optimization import strip_all_rules_multi_panel
from context_optimization import print_context_report
from inter_panel_utils import (
    build_compact_single_panel_text,
    build_compact_panels_text,
    build_variablename_index,
    group_complex_refs_by_source_field,
    group_complex_refs_by_source_panel,
    quick_cross_panel_scan,
    validate_inter_panel_rules,
    merge_all_rules_into_output,
    read_inter_panel_output,
    translate_expression_agent_output,
)

from edv_rule_dispatcher import (
    call_edv_mini_agent,
    extract_reference_tables_from_parser,
    get_referenced_tables_for_panel,
)
from validate_edv_dispatcher import call_validate_edv_mini_agent
from doc_parser import DocumentParser


PROJECT_ROOT = str(Path(__file__).parent.parent.parent)

# Master log file — set in main(), used by log() globally
_master_log: Optional[Path] = None

# Thread lock for log writes
import threading
_log_lock = threading.Lock()


def log(msg: str, also_print: bool = True):
    """Log a timestamped message to master log file and optionally to stdout."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with _log_lock:
        if also_print:
            print(line, flush=True)
        if _master_log:
            with open(_master_log, 'a') as f:
                f.write(line + '\n')


def elapsed_str(start: float) -> str:
    """Return human-readable elapsed time string."""
    secs = time.time() - start
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    remaining = secs % 60
    return f"{mins}m {remaining:.1f}s"


def query_context_usage(pass_name: str) -> Optional[str]:
    """Query the last claude agent session for context/token usage."""
    usage_prompt = (
        "Report the context window usage for this conversation. "
        "Include: (1) number of input tokens used, "
        "(2) number of output tokens used, "
        "(3) total tokens used, and "
        "(4) percentage of the context window (200K tokens) that is filled. "
        "Format as a brief one-line summary."
    )

    try:
        process = subprocess.run(
            ["claude", "--continue", "-p", usage_prompt],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )

        if process.returncode == 0 and process.stdout.strip():
            return process.stdout.strip()
        return None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Phase 1: Per-Panel Reference Detection
# ══════════════════════════════════════════════════════════════════════════════

def build_all_panels_index(input_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Build a compact index of all panels' fields: {panel_name: [{field_name, variableName}]}.
    Used by detection agents to resolve referenced field variableNames.
    """
    index = {}
    for panel_name, fields in input_data.items():
        index[panel_name] = [
            {
                'field_name': f.get('field_name', ''),
                'variableName': f.get('variableName', ''),
            }
            for f in fields
            if f.get('variableName')
        ]
    return index


def normalize_detection_output(raw: any, panel_name: str, all_panel_names: List[str]) -> Optional[Dict]:
    """
    Normalize the detection agent's output into the expected format.

    Handles various malformed outputs:
    - Array instead of object
    - Different key names (references, detected_references, refs)
    - Missing panel_name
    - Invalid classification values
    """
    VALID_CLASSIFICATIONS = {'copy_to', 'visibility', 'derivation', 'edv', 'clearing'}
    valid_panel_set = set(all_panel_names)

    # If raw is a list, try to extract refs from it
    if isinstance(raw, list):
        refs = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            # Item might be a field entry with detected_references
            if 'detected_references' in item:
                field_var = item.get('variableName', '')
                field_name = item.get('field_name', '')
                for det in item['detected_references']:
                    if not isinstance(det, dict):
                        continue
                    # Skip same-panel references
                    target_panel = det.get('target_panel', '')
                    if target_panel == panel_name:
                        continue
                    ref = _build_normalized_ref(det, field_var, field_name, valid_panel_set)
                    if ref:
                        refs.append(ref)
            # Item might be a ref directly (flat or nested source_field/referenced_field format)
            elif any(k in item for k in ('referenced_panel', 'reference_type', 'field_variableName',
                                          'source_field', 'referenced_field')):
                # Flatten nested source_field/referenced_field dicts before normalization
                flat_item = dict(item)
                if isinstance(flat_item.get('referenced_field'), dict):
                    rf = flat_item['referenced_field']
                    flat_item.setdefault('referenced_panel', rf.get('panel', ''))
                    flat_item.setdefault('target_field', rf.get('variableName', ''))
                    flat_item.setdefault('referenced_field_name', rf.get('field_name', ''))
                if isinstance(flat_item.get('source_field'), dict):
                    sf = flat_item['source_field']
                    flat_item.setdefault('field_variableName', sf.get('variableName', ''))
                    flat_item.setdefault('field_name', sf.get('field_name', ''))
                ref = _build_normalized_ref(flat_item, flat_item.get('field_variableName', ''),
                                            flat_item.get('field_name', ''), valid_panel_set)
                if ref:
                    refs.append(ref)
        return {'panel_name': panel_name, 'cross_panel_references': refs} if refs else None

    if not isinstance(raw, dict):
        return None

    # Find the refs array under various possible keys
    refs_raw = (
        raw.get('cross_panel_references') or
        raw.get('references') or
        raw.get('detected_references') or
        raw.get('refs') or
        []
    )

    if not refs_raw:
        return None

    # Normalize each ref (handle nested "references" sub-arrays)
    normalized_refs = []
    for ref in refs_raw:
        if not isinstance(ref, dict):
            continue
        # Check for nested format: {field_name, variableName, references: [{referenced_panel, ...}]}
        # Also check for nested source_field/referenced_field dicts (handled by _normalize_single_ref)
        if 'references' in ref and isinstance(ref['references'], list):
            parent_var = ref.get('variableName') or ref.get('field_variableName') or ''
            parent_name = ref.get('field_name') or ref.get('destination_field') or ''
            for sub_ref in ref['references']:
                if not isinstance(sub_ref, dict):
                    continue
                # Merge parent field info into sub-ref for normalization
                merged = dict(sub_ref)
                merged.setdefault('field_variableName', parent_var)
                merged.setdefault('destination_variableName', parent_var)
                merged.setdefault('field_name', parent_name)
                merged.setdefault('destination_field', parent_name)
                norm = _normalize_single_ref(merged, valid_panel_set)
                if norm:
                    normalized_refs.append(norm)
        else:
            norm = _normalize_single_ref(ref, valid_panel_set)
            if norm:
                normalized_refs.append(norm)

    if not normalized_refs:
        return None

    return {'panel_name': panel_name, 'cross_panel_references': normalized_refs}


def _normalize_single_ref(ref: Dict, valid_panel_set: set) -> Optional[Dict]:
    """Normalize a single reference record to the expected schema."""
    VALID_CLASSIFICATIONS = {'copy_to', 'visibility', 'derivation', 'edv', 'clearing'}

    # Handle nested object format: {source_field: {...}, referenced_field: {...}}
    if isinstance(ref.get('referenced_field'), dict):
        rf = ref['referenced_field']
        ref.setdefault('referenced_panel', rf.get('panel', ''))
        ref.setdefault('referenced_field_variableName', rf.get('variableName', ''))
        ref.setdefault('referenced_field_name', rf.get('field_name', ''))
    if isinstance(ref.get('source_field'), dict):
        sf = ref['source_field']
        ref.setdefault('field_variableName', sf.get('variableName', ''))
        ref.setdefault('field_name', sf.get('field_name', ''))

    # Get referenced panel from various possible keys
    referenced_panel = (
        ref.get('referenced_panel') or
        ref.get('target_panel') or
        ref.get('source_panel') or
        ''
    )
    if not referenced_panel or referenced_panel not in valid_panel_set:
        return None

    # Get classification, normalize invalid values
    # If classification is generic (e.g., "simple", "complex"), prefer reference_type
    raw_classification = (ref.get('classification') or '').lower()
    if raw_classification in ('simple', 'complex', ''):
        classification = (
            ref.get('reference_type') or
            ref.get('reference_classification') or
            raw_classification
        ).lower()
    else:
        classification = raw_classification
    if classification not in VALID_CLASSIFICATIONS:
        # Map common variants
        if classification in ('multiple', 'visibility_condition', 'visibility_and_derivation',
                              'visibility_state', 'panel_visibility'):
            classification = 'visibility'
        elif classification in ('copy', 'copy_to_field', 'cross_panel_field_copy'):
            classification = 'copy_to'
        elif classification in ('derive', 'value_population'):
            classification = 'derivation'
        elif 'edv' in classification or 'derivation_edv' in classification:
            classification = 'edv'
        elif 'clearing' in classification or 'complex_clearing' in classification:
            classification = 'clearing'
        else:
            classification = 'visibility'  # default to complex/visibility

    # Determine type
    ref_type = ref.get('type', ref.get('complexity', ''))
    if ref_type not in ('simple', 'complex'):
        ref_type = 'simple' if classification == 'copy_to' else 'complex'

    # Get field variableNames (the field in THIS panel whose logic references another panel)
    # For panel-level visibility refs: target_panel_variableName = the panel being affected
    # For field-level refs: source_variableName = the field whose logic has the cross-panel ref
    field_var = (
        ref.get('field_variableName') or
        ref.get('destination_variableName') or
        ref.get('variable_name') or
        ref.get('field_variable_name') or
        ref.get('variableName') or
        ref.get('target_panel_variableName') or
        ref.get('source_variableName') or
        ''
    )
    # Get referenced field variableName (the field in the OTHER panel)
    referenced_field_var = (
        ref.get('referenced_field_variableName') or
        ref.get('referenced_variableName') or
        ref.get('target_variableName') or
        ref.get('source_variableName') or
        ref.get('target_field') or
        ref.get('source_field') or
        'unknown'
    )

    # Get field name (human-readable)
    field_name = (
        ref.get('field_name') or
        ref.get('destination_field') or
        ''
    )
    # Get referenced field name
    referenced_field_name = (
        ref.get('referenced_field_name') or
        ref.get('referenced_field') or
        ref.get('target_field') or
        ''
    )

    return {
        'field_variableName': field_var,
        'field_name': field_name,
        'referenced_panel': referenced_panel,
        'referenced_field_variableName': referenced_field_var,
        'referenced_field_name': referenced_field_name,
        'type': ref_type,
        'classification': classification,
        'logic_snippet': ref.get('logic_snippet', ref.get('logic_excerpt', ref.get('reference_text', ref.get('logic', '')))),
        'description': ref.get('description', ref.get('notes', '')),
    }


def _build_normalized_ref(det: Dict, field_var: str, field_name: str,
                          valid_panel_set: set) -> Optional[Dict]:
    """Build a normalized ref from a detected_references sub-entry."""
    target_panel = det.get('target_panel', det.get('referenced_panel', ''))
    if not target_panel or target_panel not in valid_panel_set:
        return None

    raw_cls = (det.get('classification') or det.get('reference_classification') or '').lower()
    if raw_cls in ('simple', 'complex', ''):
        classification = (det.get('reference_type') or raw_cls).lower()
    else:
        classification = raw_cls
    VALID = {'copy_to', 'visibility', 'derivation', 'edv', 'clearing'}
    if classification not in VALID:
        if 'copy' in classification:
            classification = 'copy_to'
        elif 'edv' in classification:
            classification = 'edv'
        elif 'clearing' in classification:
            classification = 'clearing'
        elif 'visibility' in classification or 'condition' in classification:
            classification = 'visibility'
        elif 'deriv' in classification:
            classification = 'derivation'
        else:
            classification = 'visibility'

    ref_type = 'simple' if classification == 'copy_to' else 'complex'

    return {
        'field_variableName': field_var,
        'field_name': field_name,
        'referenced_panel': target_panel,
        'referenced_field_variableName': det.get('target_field', 'unknown'),
        'referenced_field_name': det.get('target_field', ''),
        'type': ref_type,
        'classification': classification,
        'logic_snippet': det.get('reference_text', ''),
        'description': det.get('description', ''),
    }


def detect_cross_panel_refs(
    panel_name: str,
    panel_fields: List[Dict],
    all_panel_names: List[str],
    all_panels_index_file: Path,
    temp_dir: Path,
    model: str = "haiku",
) -> Optional[Dict]:
    """
    Phase 1: Detect cross-panel references for a single panel via LLM.

    Calls the inter_panel_detect_refs agent with:
    - This panel's fields (compact, rules stripped)
    - All panels index (for variableName resolution)

    Args:
        panel_name: Name of the panel to analyze
        panel_fields: Fields in the panel
        all_panel_names: All panel names in the form
        all_panels_index_file: Path to the shared all-panels index file
        temp_dir: Temporary directory for intermediate files
        model: Claude model to use (default: haiku for speed)

    Returns:
        Detection result dict (normalized), or None on failure
    """
    # Create safe filename from panel name
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', panel_name).lower()

    # Build compact field data (strip rules for context optimization)
    compact_fields = []
    for field in panel_fields:
        compact_fields.append({
            'field_name': field.get('field_name', ''),
            'type': field.get('type', ''),
            'variableName': field.get('variableName', ''),
            'logic': field.get('logic', ''),
        })

    # Write panel fields file
    panel_fields_file = temp_dir / f"detect_{safe_name}_fields.json"
    with open(panel_fields_file, 'w') as f:
        json.dump(compact_fields, f, indent=2)

    # Output file
    output_file = temp_dir / f"detect_{safe_name}_output.json"

    prompt = f"""Detect cross-panel references in this panel's fields.

## Input
- PANEL_FIELDS_FILE: {panel_fields_file}
- PANEL_NAME: {panel_name}
- ALL_PANELS_INDEX_FILE: {all_panels_index_file}
- OUTPUT_FILE: {output_file}

Read the panel fields and the all-panels index.
Check each field's logic for references to other panels.
Use the all-panels index to resolve referenced field variableNames.
Classify each reference and write the structured output to OUTPUT_FILE.
The output MUST be a JSON object with keys "panel_name" and "cross_panel_references".
"""

    try:
        log(f"  Phase 1: Detecting refs in '{panel_name}' ({len(panel_fields)} fields)...")

        t0 = time.time()

        process = subprocess.run(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--agent", "mini/inter_panel_detect_refs",
                "--allowedTools", "Read,Write"
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        if process.returncode != 0:
            log(f"  Phase 1: Detection FAILED for '{panel_name}' "
                f"(exit code {process.returncode}) after {elapsed_str(t0)}")
            if process.stdout:
                log(f"    stdout: {process.stdout[:500]}")
            if process.stderr:
                log(f"    stderr: {process.stderr[:500]}")
            # Fall through to check if output file was still written

        # Read output (check file even on non-zero exit — partial output recovery)
        if not output_file.exists():
            log(f"  Phase 1: No output file for '{panel_name}' after {elapsed_str(t0)}")
            return None

        if process.returncode != 0:
            log(f"  Phase 1: '{panel_name}' CLI failed (exit code {process.returncode}) "
                f"but output file found — recovering")

        with open(output_file, 'r') as f:
            raw_result = json.load(f)

        # Normalize the output to handle format variations
        result = normalize_detection_output(raw_result, panel_name, all_panel_names)

        if result:
            ref_count = len(result.get('cross_panel_references', []))
            log(f"  Phase 1: '{panel_name}' — {ref_count} refs detected ({elapsed_str(t0)})")
        else:
            log(f"  Phase 1: '{panel_name}' — 0 refs detected ({elapsed_str(t0)})")

        return result

    except FileNotFoundError:
        log(f"  Phase 1: 'claude' command not found")
        return None
    except (json.JSONDecodeError, IOError) as e:
        log(f"  Phase 1: Error reading output for '{panel_name}': {e}")
        return None
    except Exception as e:
        log(f"  Phase 1: Error detecting refs for '{panel_name}': {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2a: Simple Copy To Rules (Deterministic)
# ══════════════════════════════════════════════════════════════════════════════

def build_simple_copy_to_rules(
    simple_refs: List[Dict],
    var_index: Dict[str, str],
) -> Dict[str, List[Dict]]:
    """
    Phase 2a: Build Copy To rules deterministically from simple references.

    For each simple copy_to reference, creates a Copy To Form Field (Client) rule
    on the source field, with the destination being the receiving field.

    Args:
        simple_refs: List of simple reference records with classification "copy_to"
        var_index: variableName -> panel_name lookup

    Returns:
        Rules in merge format: {panel: [{target_field_variableName, rules_to_add}]}
    """
    if not simple_refs:
        return {}

    # Group by source field to consolidate destinations
    # Key: (source_panel, source_variableName) -> list of destination variableNames
    source_groups: Dict[Tuple[str, str], List[str]] = {}

    for ref in simple_refs:
        source_var = ref.get('referenced_field_variableName', '')
        source_panel = ref.get('referenced_panel', '')
        dest_var = ref.get('field_variableName', '')

        if not source_var or source_var == 'unknown' or not dest_var:
            log(f"  Phase 2a: Skipping copy_to ref with missing fields: {ref}")
            continue

        # Verify source field exists
        norm_src = _norm_var(source_var)
        if norm_src not in var_index:
            log(f"  Phase 2a: Source field '{source_var}' not found, skipping")
            continue

        # Use the actual panel from the index
        actual_panel = var_index[norm_src]

        key = (actual_panel, source_var)
        if key not in source_groups:
            source_groups[key] = []

        # Avoid duplicate destinations
        if dest_var not in source_groups[key]:
            source_groups[key].append(dest_var)

    # Build rules
    rules_by_panel: Dict[str, List[Dict]] = {}

    for (host_panel, source_var), dest_vars in source_groups.items():
        rule = {
            'rule_name': 'Copy To Form Field (Client)',
            'source_fields': [source_var],
            'destination_fields': dest_vars,
            '_reasoning': f"Cross-panel: Copy {source_var} to {', '.join(dest_vars)}",
            '_inter_panel_source': 'cross-panel',
        }

        entry = {
            'target_field_variableName': source_var,
            'rules_to_add': [rule],
        }

        if host_panel not in rules_by_panel:
            rules_by_panel[host_panel] = []
        rules_by_panel[host_panel].append(entry)

    return rules_by_panel


def _norm_var(v: str) -> str:
    """Normalize __varname__ or _varname_ to _varname_ for index lookups."""
    s = v.strip('_')
    return f'_{s}_' if s else v


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2: Complex Rules via Expression Agent (Targeted Context)
# ══════════════════════════════════════════════════════════════════════════════

def call_complex_rules_agent(
    complex_refs: List[Dict],
    involved_panels: Dict[str, List[Dict]],
    temp_dir: Path,
    group_label: str,
    model: str = "opus",
) -> Dict[str, List[Dict]]:
    """
    Phase 2: Call expression rule agent with targeted context for complex refs.

    Only sends the involved panels (stripped of rules) + complex ref descriptions
    to the agent. Much smaller context than sending all panels.

    Args:
        complex_refs: List of complex reference records for this group
        involved_panels: Only the panels involved in these refs
        temp_dir: Temporary directory
        group_label: Label for logging (e.g., source panel name)
        model: Claude model to use

    Returns:
        Rules in merge format: {panel: [{target_field_variableName, rules_to_add}]}
    """
    safe_label = re.sub(r'[^a-zA-Z0-9_]', '_', group_label).lower()

    # Strip rules from involved panels
    involved_stripped = strip_all_rules_multi_panel(involved_panels)

    # Write involved panels
    involved_file = temp_dir / f"complex_{safe_label}_panels.json"
    with open(involved_file, 'w') as f:
        json.dump(involved_stripped, f, indent=2)

    # Write complex refs
    refs_file = temp_dir / f"complex_{safe_label}_refs.json"
    with open(refs_file, 'w') as f:
        json.dump(complex_refs, f, indent=2)

    # Output and log files
    output_file = temp_dir / f"complex_{safe_label}_rules.json"
    log_file = temp_dir / f"complex_{safe_label}_log.txt"
    with open(log_file, 'w') as f:
        f.write(f"=== Complex Rules Agent ({group_label}) — {datetime.now().isoformat()} ===\n")

    prompt = f"""Process complex cross-panel references for rule generation.

## Input
- COMPLEX_REFS_FILE: {refs_file}
  This JSON array describes the cross-panel references that need Expression (Client) rules.
  Each entry has: type (visibility/derivation/edv/clearing), source and target panels/fields,
  logic snippet, and description.
- FIELDS_JSON: {involved_file}
  This is a JSON object where each key is a panel name and each value is the
  array of fields for that panel. These are the involved panels with full field data.
- LOG_FILE: {log_file}

Read the complex refs to understand what rules are needed.
Read the involved panels to get field details (variableNames, types).
Use the expression_rule_agent instructions to build Expression (Client) rules
for the described cross-panel references.
Write the output to: {output_file}
Output format: JSON object where keys are panel names and values are arrays of fields
with their rules (same format as FIELDS_JSON input but with new rules added).
If no rules could be created, write empty dict {{}} to {output_file}.
"""

    try:
        log(f"  Phase 2: Rules for '{group_label}' "
            f"({len(complex_refs)} refs, {len(involved_panels)} panels)...")
        log(f"    Agent log: {log_file}")

        t0 = time.time()

        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--agent", "mini/expression_rule_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        with open(log_file, 'a') as lf:
            for line in process.stdout:
                print(line, end='', flush=True)
                lf.write(line)

        process.wait()

        if process.returncode != 0:
            log(f"  Phase 2: FAILED for '{group_label}' "
                f"(exit code {process.returncode}) after {elapsed_str(t0)}")
            # Fall through to check if output file was still written

        # Read output (check file even on non-zero exit — partial output recovery)
        if not output_file.exists():
            log(f"  Phase 2: No output file for '{group_label}' after {elapsed_str(t0)}")
            return {}

        if process.returncode != 0:
            log(f"  Phase 2: '{group_label}' CLI failed (exit code {process.returncode}) "
                f"but output file found — recovering")

        raw_output = read_inter_panel_output(output_file)
        result = translate_expression_agent_output(raw_output) if raw_output else {}

        if result:
            rule_count = sum(
                sum(len(e.get('rules_to_add', [])) for e in entries)
                for entries in result.values()
            )
            log(f"  Phase 2: '{group_label}' — {rule_count} rules ({elapsed_str(t0)})")
        else:
            log(f"  Phase 2: '{group_label}' — no rules produced ({elapsed_str(t0)})")
            result = {}

        # Context report
        agent_prompt_file = Path(PROJECT_ROOT) / ".claude" / "agents" / "mini" / "expression_rule_agent.md"
        expr_ref_file = Path(PROJECT_ROOT) / ".claude" / "agents" / "docs" / "expression_rules.md"
        print_context_report(
            label=f"Phase 2: {group_label}",
            agent_files=[agent_prompt_file],
            prompt_chars=len(prompt),
            input_json_chars=involved_file.stat().st_size + refs_file.stat().st_size,
            output_file=output_file,
            extra_read_files=[expr_ref_file] if expr_ref_file.exists() else [],
        )

        return result

    except FileNotFoundError:
        log(f"  Phase 2: 'claude' command not found")
        return {}
    except Exception as e:
        log(f"  Phase 2: Error for '{group_label}': {e}")
        import traceback
        traceback.print_exc()
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Inter-Panel Cross-Panel Rules Dispatcher (v3) — Panel-by-Panel Architecture"
    )
    parser.add_argument(
        "--clear-child-output",
        required=True,
        help="Path to input JSON from previous stage (e.g., expression rules output)"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "--output",
        default="output/inter_panel/all_panels_inter_panel.json",
        help="Output file (default: output/inter_panel/all_panels_inter_panel.json)"
    )
    parser.add_argument(
        "--context-usage",
        action="store_true",
        default=False,
        help="Query and display context window usage after each phase (adds ~30s per phase)"
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude model for complex rule generation (default: opus)"
    )
    parser.add_argument(
        "--detect-model",
        default="haiku",
        help="Claude model for Phase 1 reference detection (default: haiku)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel workers for Phase 1 detection (default: 4)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.clear_child_output).exists():
        print(f"Error: Input not found: {args.clear_child_output}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.bud).exists():
        print(f"Error: BUD document not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Set up master log file
    global _master_log
    _master_log = temp_dir / "inter_panel_master.log"
    with open(_master_log, 'w') as f:
        f.write(f"=== Inter-Panel Dispatcher v3 — {datetime.now().isoformat()} ===\n")

    pipeline_start = time.time()
    log("=" * 60, also_print=False)
    log("INTER-PANEL DISPATCHER v3 STARTED (Panel-by-Panel)")
    log(f"Master log: {_master_log}")
    print(f"  Monitor progress:  tail -f {_master_log}")

    # Load input data
    log(f"Loading input: {args.clear_child_output}")
    with open(args.clear_child_output, 'r') as f:
        input_data = json.load(f)

    all_panel_names = list(input_data.keys())
    input_field_count = sum(len(fields) for fields in input_data.values())
    input_rule_count = sum(
        len(f.get('rules', []))
        for fields in input_data.values()
        for f in fields
    )
    log(f"Found {len(input_data)} panels: {', '.join(all_panel_names)}")
    log(f"Total fields: {input_field_count}, Total rules: {input_rule_count}")

    # ══════════════════════════════════════════════════════════════════════
    # QUICK SCAN: Check if any cross-panel references exist
    # ══════════════════════════════════════════════════════════════════════
    log("Quick cross-panel scan...")
    t0 = time.time()
    has_cross_panel = quick_cross_panel_scan(input_data)
    log(f"Quick scan done in {elapsed_str(t0)} — result: {'refs found' if has_cross_panel else 'no refs'}")

    if not has_cross_panel:
        log("No cross-panel references detected — copying input to output (early exit)")
        with open(output_file, 'w') as f:
            json.dump(input_data, f, indent=2)
        log(f"Output: {output_file} ({input_field_count} fields, unchanged)")
        sys.exit(0)

    log("Cross-panel references detected — proceeding with panel-by-panel analysis")

    # Build variableName index for validation
    var_index = build_variablename_index(input_data)
    log(f"Built variableName index: {len(var_index)} fields across {len(input_data)} panels")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1: Per-Panel Reference Detection (parallel)
    # ══════════════════════════════════════════════════════════════════════
    log(f"PHASE 1: PER-PANEL REFERENCE DETECTION — "
        f"{len(input_data)} panels, max {args.max_workers} workers, model={args.detect_model}")
    t0 = time.time()

    # Build shared all-panels index file (used by all detection agents for variableName resolution)
    all_panels_index = build_all_panels_index(input_data)
    all_panels_index_file = temp_dir / "all_panels_index.json"
    with open(all_panels_index_file, 'w') as f:
        json.dump(all_panels_index, f, indent=2)
    log(f"  All-panels index written: {all_panels_index_file}")

    all_refs: List[Dict] = []       # All detected references (flat list)
    simple_refs: List[Dict] = []    # Simple (copy_to) references
    complex_refs: List[Dict] = []   # Complex references

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {}
        for panel_name, panel_fields in input_data.items():
            future = executor.submit(
                detect_cross_panel_refs,
                panel_name, panel_fields, all_panel_names,
                all_panels_index_file,
                temp_dir, args.detect_model,
            )
            futures[future] = panel_name

        for future in as_completed(futures):
            panel_name = futures[future]
            try:
                result = future.result()
                if result and result.get('cross_panel_references'):
                    refs = result['cross_panel_references']
                    all_refs.extend(refs)
                    for ref in refs:
                        if ref.get('type') == 'simple' and ref.get('classification') == 'copy_to':
                            simple_refs.append(ref)
                        else:
                            complex_refs.append(ref)
            except Exception as e:
                log(f"  Phase 1: Exception for '{panel_name}': {e}")

    log(f"Phase 1 COMPLETE — {len(all_refs)} total refs detected "
        f"({len(simple_refs)} simple, {len(complex_refs)} complex) in {elapsed_str(t0)}")

    if all_refs:
        # Log breakdown by classification
        classification_counts: Dict[str, int] = {}
        for ref in all_refs:
            cls = ref.get('classification', 'unknown')
            classification_counts[cls] = classification_counts.get(cls, 0) + 1
        breakdown = ', '.join(f"{cls}: {cnt}" for cls, cnt in sorted(classification_counts.items()))
        log(f"  Breakdown: {breakdown}")

    if args.context_usage:
        print(f"\n--- Context Usage (Phase 1) ---")
        usage = query_context_usage("Phase 1")
        if usage:
            print(usage)
        else:
            print("(Could not retrieve context usage)")
        print("---")

    # ── Filter garbage refs (empty field_variableName = useless to the agent) ──
    pre_filter = len(all_refs)
    simple_refs = [r for r in simple_refs if r.get('field_variableName')]
    complex_refs = [r for r in complex_refs if r.get('field_variableName')]
    all_refs = [r for r in all_refs if r.get('field_variableName')]
    filtered_out = pre_filter - len(all_refs)
    if filtered_out:
        log(f"  Filtered out {filtered_out} refs with empty field_variableName "
            f"(kept {len(all_refs)})")

    # ── Track panels with edv-classified refs (for Phase 4) ──
    edv_panels = set()
    for ref in all_refs:
        if ref.get('classification') == 'edv':
            # Include the panel containing the field
            field_var = ref.get('field_variableName', '')
            norm = _norm_var(field_var)
            if norm in var_index:
                edv_panels.add(var_index[norm])
            # Include the referenced panel (cross-panel source)
            ref_panel = ref.get('referenced_panel', '')
            if ref_panel and ref_panel in input_data:
                edv_panels.add(ref_panel)
    if edv_panels:
        log(f"  EDV-classified panels (for Phase 4): {', '.join(sorted(edv_panels))}")

    # ── Filter edv-classified refs from Phase 2 (handled by Phase 4) ──
    pre_edv_filter = len(complex_refs)
    complex_refs = [r for r in complex_refs if r.get('classification') != 'edv']
    edv_filtered = pre_edv_filter - len(complex_refs)
    if edv_filtered:
        log(f"  Filtered {edv_filtered} edv-classified refs from Phase 2 (handled by Phase 4)")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2: All Rules via Expression Agent (copy_to uses ctfd with on("change"))
    # ══════════════════════════════════════════════════════════════════════
    copy_to_rules: Dict[str, List[Dict]] = {}
    copy_to_count = 0
    complex_rules: Dict[str, List[Dict]] = {}
    complex_rule_count = 0

    # Merge simple refs into complex refs — expression agent handles copy_to via ctfd + on("change")
    if simple_refs:
        log(f"PHASE 2: Merging {len(simple_refs)} copy_to refs into complex refs (agent will use ctfd + on(\"change\"))")
        complex_refs.extend(simple_refs)

    if complex_refs:
        log(f"PHASE 2: EXPRESSION RULES — {len(complex_refs)} references (including {len(simple_refs)} copy_to)")
        t0 = time.time()

        # Group complex refs by source field (not panel) to consolidate
        # rules when multiple panels reference the same source field
        groups = group_complex_refs_by_source_field(complex_refs)
        log(f"  Grouped into {len(groups)} source field groups: "
            f"{', '.join(f'{k} ({len(v)} refs)' for k, v in groups.items())}")

        for source_field_var, refs_group in groups.items():
            # Collect all involved panels for this group
            involved_panel_names = set()

            # Add the source field's panel (looked up from var_index)
            source_norm = _norm_var(source_field_var)
            if source_norm in var_index:
                involved_panel_names.add(var_index[source_norm])

            for ref in refs_group:
                # Add the panel that has the field with the logic
                field_var = ref.get('field_variableName', '')
                if field_var:
                    norm = _norm_var(field_var)
                    if norm in var_index:
                        involved_panel_names.add(var_index[norm])
                # Also add the referenced panel directly
                ref_panel = ref.get('referenced_panel', '')
                if ref_panel:
                    involved_panel_names.add(ref_panel)

            # Extract involved panels from input data
            involved_panels: Dict[str, List[Dict]] = {}
            for pname in involved_panel_names:
                if pname in input_data:
                    involved_panels[pname] = input_data[pname]
                else:
                    # Case-insensitive fallback
                    for actual_name in input_data:
                        if actual_name.lower() == pname.lower():
                            involved_panels[actual_name] = input_data[actual_name]
                            break

            if not involved_panels:
                log(f"  Phase 2: No involved panels found for group '{source_field_var}', skipping")
                continue

            # Use the source field's name for a readable label
            source_field_name = refs_group[0].get('referenced_field_name', source_field_var)
            group_label = f"{source_field_name} ({source_field_var})"

            group_rules = call_complex_rules_agent(
                refs_group, involved_panels, temp_dir,
                group_label=group_label, model=args.model,
            )

            # Merge group rules into overall complex_rules
            for panel_name, entries in group_rules.items():
                if panel_name not in complex_rules:
                    complex_rules[panel_name] = []
                complex_rules[panel_name].extend(entries)

        complex_rule_count = sum(
            sum(len(e.get('rules_to_add', [])) for e in entries)
            for entries in complex_rules.values()
        )
        log(f"Phase 2b COMPLETE — {complex_rule_count} complex rules in {elapsed_str(t0)}")

        if args.context_usage:
            print(f"\n--- Context Usage (Phase 2b) ---")
            usage = query_context_usage("Phase 2b")
            if usage:
                print(usage)
            else:
                print("(Could not retrieve context usage)")
            print("---")
    else:
        log("Phase 2b skipped — no complex references")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 3: Validate + Merge (deterministic Python)
    # ══════════════════════════════════════════════════════════════════════
    log("PHASE 3: VALIDATE + MERGE — Starting")
    t0 = time.time()

    # Validate rules before merging
    if complex_rules:
        complex_rules, stripped = validate_inter_panel_rules(complex_rules, var_index)
        if stripped > 0:
            log(f"  Validation: stripped {stripped} invalid rules/entries")
        else:
            log(f"  Validation: all rules valid")

    # Merge all rules into output
    log("Merging rules into output...")
    all_results = merge_all_rules_into_output(input_data, {}, complex_rules)

    # Verify field counts
    output_field_count = sum(len(fields) for fields in all_results.values())

    # Rule count audit
    output_rule_count = sum(
        len(f.get('rules', []))
        for fields in all_results.values()
        for f in fields
    )

    # Count new cross-panel rules
    cross_panel_rule_count = 0
    for panel_fields in all_results.values():
        for field in panel_fields:
            for rule in field.get('rules', []):
                if isinstance(rule, dict) and rule.get('_inter_panel_source') == 'cross-panel':
                    cross_panel_rule_count += 1

    # Rule loss check
    if output_rule_count < input_rule_count:
        log(f"  WARNING: Rule loss detected! input={input_rule_count}, output={output_rule_count}")
    else:
        log(f"  Rule audit: input={input_rule_count}, output={output_rule_count}, "
            f"added={output_rule_count - input_rule_count}")

    log(f"Phase 3 COMPLETE — took {elapsed_str(t0)}")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 4: Cross-Panel EDV Processing (targeted panels only)
    # ══════════════════════════════════════════════════════════════════════
    phase4_edv_panels = 0
    phase4_vedv_panels = 0
    pre_phase4_rule_count = output_rule_count

    if edv_panels:
        log(f"PHASE 4: CROSS-PANEL EDV PROCESSING — {len(edv_panels)} panels")
        t0 = time.time()

        # Parse BUD to extract reference tables
        log(f"  Parsing BUD for reference tables: {args.bud}")
        bud_parser = DocumentParser()
        parsed_doc = bud_parser.parse(args.bud)
        all_reference_tables = extract_reference_tables_from_parser(parsed_doc)
        log(f"  Found {len(all_reference_tables)} reference tables")

        # Reuse existing all_panels_index_file (written in Phase 1)
        # It has the same field_name/variableName data since merge only adds rules

        # Phase 4a: EDV Rules
        log(f"  Phase 4a: EDV Rules on {len(edv_panels)} panels...")
        for panel_name in sorted(edv_panels):
            if panel_name not in all_results:
                log(f"    Skipping '{panel_name}' — not in results")
                continue

            panel_fields = all_results[panel_name]
            referenced_tables = get_referenced_tables_for_panel(panel_fields, all_reference_tables)
            log(f"    EDV agent: '{panel_name}' ({len(panel_fields)} fields, "
                f"{len(referenced_tables)} ref tables)")

            result = call_edv_mini_agent(
                panel_fields, referenced_tables, panel_name, temp_dir,
                context_usage=args.context_usage,
                verbose=True,
                model=args.model,
                all_panels_index_file=all_panels_index_file,
            )

            if result:
                all_results[panel_name] = result
                phase4_edv_panels += 1
                log(f"    EDV agent: '{panel_name}' — success ({len(result)} fields)")
            else:
                log(f"    EDV agent: '{panel_name}' — FAILED (keeping existing data)")

        # Phase 4b: Validate EDV Rules
        log(f"  Phase 4b: Validate EDV on {len(edv_panels)} panels...")
        for panel_name in sorted(edv_panels):
            if panel_name not in all_results:
                log(f"    Skipping '{panel_name}' — not in results")
                continue

            panel_fields = all_results[panel_name]
            referenced_tables = get_referenced_tables_for_panel(panel_fields, all_reference_tables)
            log(f"    Validate EDV: '{panel_name}' ({len(panel_fields)} fields, "
                f"{len(referenced_tables)} ref tables)")

            result = call_validate_edv_mini_agent(
                panel_fields, referenced_tables, panel_name, temp_dir,
                context_usage=args.context_usage,
                verbose=True,
                model=args.model,
            )

            if result:
                all_results[panel_name] = result
                phase4_vedv_panels += 1
                log(f"    Validate EDV: '{panel_name}' — success ({len(result)} fields)")
            else:
                log(f"    Validate EDV: '{panel_name}' — FAILED (keeping existing data)")

        # Recount rules after Phase 4
        output_rule_count = sum(
            len(f.get('rules', []))
            for fields in all_results.values()
            for f in fields
        )
        cross_panel_rule_count = 0
        for panel_fields_list in all_results.values():
            for field in panel_fields_list:
                for rule in field.get('rules', []):
                    if isinstance(rule, dict) and rule.get('_inter_panel_source') == 'cross-panel':
                        cross_panel_rule_count += 1

        log(f"Phase 4 COMPLETE — took {elapsed_str(t0)}")
        log(f"  EDV panels: {phase4_edv_panels} ok, Validate EDV panels: {phase4_vedv_panels} ok")
        log(f"  Rules delta: {output_rule_count - pre_phase4_rule_count} "
            f"(pre={pre_phase4_rule_count}, post={output_rule_count})")
    else:
        log("Phase 4 skipped — no EDV-classified cross-panel references")

    # ══════════════════════════════════════════════════════════════════════
    # Write output
    # ══════════════════════════════════════════════════════════════════════
    log(f"Writing output to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    total_time = elapsed_str(pipeline_start)

    # Summary
    summary = f"""
{'='*60}
INTER-PANEL DISPATCHER (v3) COMPLETE — Total: {total_time}
{'='*60}
Total Panels: {len(input_data)}
Phase 1 — Per-Panel Detection (model={args.detect_model}, workers={args.max_workers}):
  Total refs detected: {len(all_refs)}
  Simple (copy_to): {len(simple_refs)}
  Complex: {len(complex_refs)}
Phase 2 — Expression Rules via Agent (model={args.model}):
  Total refs processed: {len(complex_refs)} (including {len(simple_refs)} copy_to)
  Rules created: {complex_rule_count}
Phase 3 — Validate + Merge:
  Cross-panel rules added: {cross_panel_rule_count}
Phase 4 — Cross-Panel EDV Processing:
  EDV-classified panels: {len(edv_panels)}
  EDV processed: {phase4_edv_panels}, Validate EDV processed: {phase4_vedv_panels}
  Rules delta: {output_rule_count - pre_phase4_rule_count}
Rule Audit:
  Input rules: {input_rule_count}
  Output rules: {output_rule_count}
  Added: {output_rule_count - input_rule_count}
  {'WARNING: Rule loss detected!' if output_rule_count < input_rule_count else 'OK: No rule loss'}
Field Counts:
  Input: {input_field_count}
  Output: {output_field_count}
  {'WARNING: Field count mismatch!' if input_field_count != output_field_count else 'OK: Field counts match'}
Output File: {output_file}
Master Log: {_master_log}
{'='*60}"""

    log(summary)

    sys.exit(0)


if __name__ == "__main__":
    main()
