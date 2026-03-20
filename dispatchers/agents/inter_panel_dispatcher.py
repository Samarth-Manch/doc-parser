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
import copy
import json
import subprocess
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print
from typing import Dict, List, Optional, Tuple

from context_optimization import strip_all_rules_multi_panel
from context_optimization import print_context_report
from inter_panel_utils import (
    build_compact_single_panel_text,
    build_compact_panels_text,
    build_variablename_index,
    deduplicate_complex_refs,
    deduplicate_expression_rules,
    ensure_full_panel_in_clearing,
    expand_panel_variables_in_expressions,
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
    VALID_CLASSIFICATIONS = {'copy_to', 'visibility', 'derivation', 'edv', 'validate_edv', 'clearing'}
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
        # Handle multi-target format: source_field + target_panels[] / target_fields[]
        # Detection agents may output a single ref with arrays of targets — expand into
        # individual refs (one per target panel) so downstream processing works correctly.
        elif isinstance(ref.get('target_panels'), list) and len(ref.get('target_panels', [])) > 0:
            source_var = ref.get('source_field', '')
            source_name = ref.get('source_field_name', '')
            target_panels = ref.get('target_panels', [])
            target_fields = ref.get('target_fields', [])
            for i, tpanel in enumerate(target_panels):
                tfield = target_fields[i] if i < len(target_fields) else ''
                expanded = dict(ref)
                # Remove array keys, set single-target keys
                expanded.pop('target_panels', None)
                expanded.pop('target_fields', None)
                expanded.pop('source_panel', None)  # avoid mis-mapping as referenced_panel
                expanded['referenced_panel'] = tpanel
                expanded['referenced_field_variableName'] = tfield
                expanded['field_variableName'] = source_var
                expanded['field_name'] = source_name
                # Map 'type' key to 'classification' if it holds a classification value
                if expanded.get('type') in ('visibility', 'clearing', 'derivation',
                                             'copy_to', 'edv', 'validate_edv'):
                    expanded['classification'] = expanded['type']
                    expanded['type'] = 'complex'
                norm = _normalize_single_ref(expanded, valid_panel_set)
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
    VALID_CLASSIFICATIONS = {'copy_to', 'visibility', 'derivation', 'edv', 'validate_edv', 'clearing'}

    # Handle nested object format: {source_field: {...}, referenced_field: {...}, target_field: {...}}
    if isinstance(ref.get('referenced_field'), dict):
        rf = ref['referenced_field']
        ref.setdefault('referenced_panel', rf.get('panel', ''))
        ref.setdefault('referenced_field_variableName', rf.get('variableName', ''))
        ref.setdefault('referenced_field_name', rf.get('field_name', ''))
    if isinstance(ref.get('target_field'), dict):
        tf = ref['target_field']
        ref.setdefault('referenced_field_variableName', tf.get('variableName', ''))
        ref.setdefault('referenced_field_name', tf.get('field_name', ''))
    if isinstance(ref.get('source_field'), dict):
        sf = ref['source_field']
        ref.setdefault('field_variableName', sf.get('variableName', ''))
        ref.setdefault('field_name', sf.get('field_name', ''))
        # Replace dict with string so downstream code doesn't see a dict
        ref['source_field'] = sf.get('variableName', '')

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
    original_classification = classification
    if classification not in VALID_CLASSIFICATIONS:
        # Map common variants
        if classification in ('multiple', 'visibility_condition', 'visibility_and_derivation',
                              'visibility_state', 'visibility/state', 'panel_visibility'):
            classification = 'visibility'
        elif classification in ('copy', 'copy_to_field', 'cross_panel_field_copy'):
            classification = 'copy_to'
        elif classification in ('derive', 'value_population'):
            classification = 'derivation'
        elif 'validate_edv' in classification or 'validation_edv' in classification:
            classification = 'validate_edv'
        elif 'edv' in classification and 'deriv' in classification:
            # e.g. 'edv_derivation', 'derivation_edv' — derivation from reference table = validate_edv
            classification = 'validate_edv'
        elif 'edv' in classification:
            classification = 'edv'
        elif 'clearing' in classification or 'complex_clearing' in classification:
            classification = 'clearing'
        elif 'depend' in classification or 'data' in classification:
            # e.g. 'data_dependency', 'edv_dependency' — check text for EDV patterns below
            classification = 'derivation'
        else:
            classification = 'visibility'  # default to complex/visibility

    # Deterministic reclassification: if classified as 'derivation' or fell through
    # to a default, check the text for EDV / reference table / attribute patterns.
    # LLMs are inconsistent with classification names — this catches misclassifications.
    if classification in ('derivation', 'visibility'):
        text_to_check = ' '.join([
            ref.get('logic_snippet', ref.get('logic_excerpt', ref.get('reference_text', ''))),
            ref.get('description', ref.get('notes', '')),
            original_classification,
        ]).lower()
        edv_patterns = ['edv', 'reference table', 'ref table', 'attribute ', 'vc_', 'validation']
        if any(p in text_to_check for p in edv_patterns):
            classification = 'validate_edv'

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
        ref.get('source_field') or  # multi-target format from detection agent
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
        '_original_classification': original_classification,
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
    VALID = {'copy_to', 'visibility', 'derivation', 'edv', 'validate_edv', 'clearing'}
    if classification not in VALID:
        if 'copy' in classification:
            classification = 'copy_to'
        elif 'validate_edv' in classification or 'validation_edv' in classification:
            classification = 'validate_edv'
        elif 'edv' in classification and 'deriv' in classification:
            classification = 'validate_edv'
        elif 'edv' in classification:
            classification = 'edv'
        elif 'clearing' in classification:
            classification = 'clearing'
        elif 'depend' in classification or 'data' in classification:
            classification = 'derivation'
        elif 'visibility' in classification or 'condition' in classification:
            classification = 'visibility'
        elif 'deriv' in classification:
            classification = 'derivation'
        else:
            classification = 'visibility'

    # Deterministic reclassification: check text for EDV / reference table patterns
    if classification in ('derivation', 'visibility'):
        text_to_check = ' '.join([
            det.get('reference_text', ''),
            det.get('description', ''),
            classification,
        ]).lower()
        edv_patterns = ['edv', 'reference table', 'ref table', 'attribute ', 'vc_', 'validation']
        if any(p in text_to_check for p in edv_patterns):
            classification = 'validate_edv'

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

        safe_name = re.sub(r'[^\w\-]', '_', panel_name)
        stream_log = temp_dir / f"detect_{safe_name}_stream.log"
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--agent", "mini/inter_panel_detect_refs",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        stream_and_print(process, verbose=True, log_file_path=stream_log)
        process.wait()

        if process.returncode != 0:
            log(f"  Phase 1: Detection FAILED for '{panel_name}' "
                f"(exit code {process.returncode}) after {elapsed_str(t0)}")
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


def _norm_var(v: str) -> str:
    """Normalize __varname__ or _varname_ to _varname_ for index lookups."""
    s = v.strip('_')
    return f'_{s}_' if s else v


# ══════════════════════════════════════════════════════════════════════════════
# Ref-to-Rule Reconciliation
# ══════════════════════════════════════════════════════════════════════════════

def extract_rule_coverage(
    complex_rules: Dict[str, List[Dict]],
) -> set:
    """
    Extract (source_field, destination_field) pairs from all generated rules.
    Handles Expression (Client), Copy To, and Make Mandatory rule formats.
    """
    covered = set()

    for panel_name, entries in complex_rules.items():
        for entry in entries:
            placement_field = _norm_var(entry.get('target_field_variableName', ''))

            for rule in entry.get('rules_to_add', []):
                source = placement_field
                if rule.get('source_fields'):
                    source = _norm_var(rule['source_fields'][0])

                # Method 1: destination_fields is populated (Copy To, Make Mandatory)
                for dest in rule.get('destination_fields', []):
                    norm_dest = _norm_var(dest)
                    if norm_dest and norm_dest != source:
                        covered.add((source, norm_dest))

                # Method 2: parse conditionalValues for Expression (Client)
                if rule.get('conditionValueType') == 'EXPR':
                    for expr in rule.get('conditionalValues', []):
                        # Extract ALL _variablename_ patterns from expression string
                        all_vars = set(re.findall(r'"(_[a-zA-Z0-9_]+_)"', expr))
                        for var in all_vars:
                            norm = _norm_var(var)
                            if norm and norm != source:
                                covered.add((source, norm))

    return covered


def reconcile_refs_to_rules(
    all_refs: List[Dict],
    complex_rules: Dict[str, List[Dict]],
) -> Tuple[List[Dict], int]:
    """
    Compare Phase 1 refs against Phase 2 generated rules.
    Returns (unmatched_refs, edv_skipped_count).
    """
    covered_pairs = extract_rule_coverage(complex_rules)

    unmatched = []
    edv_skipped = 0
    for ref in all_refs:
        # EDV/Validate EDV refs are handled by Phase 4, skip
        if ref.get('classification') in ('edv', 'validate_edv'):
            edv_skipped += 1
            continue

        source = _norm_var(ref.get('referenced_field_variableName', ''))
        dest = _norm_var(ref.get('field_variableName', ''))

        if not source or not dest:
            unmatched.append({**ref, 'reason': 'Missing source or destination variableName'})
            continue

        if (source, dest) not in covered_pairs:
            unmatched.append({**ref, 'reason': 'No matching rule found in Phase 2 output'})

    return unmatched, edv_skipped


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

        stream_log = log_file.parent / f"{log_file.stem}_stream.log"
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--agent", "mini/expression_rule_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        stream_and_print(process, verbose=True, log_file_path=stream_log)

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
# Phase 4c: Patch cross-panel Validate EDV destinations
# ══════════════════════════════════════════════════════════════════════════════

def _parse_edv_table_from_logic(logic: str) -> Optional[str]:
    """Extract EDV table name from field logic text (e.g., 'VC_BASIC_DETAILS')."""
    # Match patterns like "Staging Data (VC_BASIC_DETAILS)" or "staging data : VC_COMPANY_DETAILS"
    m = re.search(r'(?:Staging\s*Data\s*[:(]\s*|staging\s*data\s*:\s*)([A-Z_][A-Z0-9_]+)', logic, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Match "EDV : TABLE_NAME" or "EDV: TABLE_NAME"
    m = re.search(r'EDV\s*:\s*([A-Z_][A-Z0-9_]+)', logic, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Match quoted or bare "TABLE_NAME" followed by "reference table" (must check before
    # the generic "reference table X" pattern to avoid capturing "attribute" as table name)
    m = re.search(r'["\']?([A-Z][A-Z0-9]*_[A-Z0-9_]+)["\']?\s+(?:reference|table|EDV)', logic)
    if m:
        return m.group(1).upper()
    # Match "reference table -TABLE_NAME" or "reference table TABLE_NAME"
    # Require underscore in captured name to avoid false positives like "attribute"
    m = re.search(r'reference\s+table\s*[-–—:]*\s*([A-Z_]*[A-Z][A-Z0-9]*_[A-Z0-9_]+)', logic, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Match bare VC_ prefixed name anywhere (common EDV table naming convention)
    m = re.search(r'["\']?(VC_[A-Z0-9_]+)["\']?', logic)
    if m:
        return m.group(1).upper()
    return None


def _parse_column_from_logic(logic: str) -> Optional[int]:
    """Extract column number from field logic text (e.g., '7th column' -> 7, 'attribute 7' -> 7)."""
    m = re.search(r'(\d+)(?:st|nd|rd|th)\s+column', logic, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Match "attribute 7" or "attribute7"
    m = re.search(r'attribute\s*(\d+)', logic, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Match standalone EDV column notation "a7"
    m = re.search(r'\ba(\d+)\b', logic)
    if m:
        return int(m.group(1))
    return None


def patch_cross_panel_vedv_destinations(
    all_results: Dict[str, List[Dict]],
    vedv_refs: List[Dict],
    var_index: Dict[str, str],
) -> int:
    """
    After Phase 4b, patch Validate EDV rules to include cross-panel destination fields.

    For each validate_edv ref where destination field is in panel B but the source field
    is in panel A:
      1. Get the destination field's logic to determine EDV table and column number
      2. Find the Validate EDV rule on the source field in panel A for that table
      3. Replace -1 at the correct column position with the destination variableName
      4. If no Validate EDV rule exists for that table, create one

    Returns the number of cross-panel destinations patched.
    """
    patched = 0
    created = 0

    # Build a lookup: variableName -> (panel_name, field_dict)
    field_lookup: Dict[str, Tuple[str, Dict]] = {}
    # Also build name+panel -> variableName for resolving missing variableNames
    name_panel_lookup: Dict[Tuple[str, str], str] = {}
    for panel_name, fields in all_results.items():
        for field in fields:
            var = field.get('variableName', '')
            fname = field.get('field_name', '')
            if var:
                field_lookup[var] = (panel_name, field)
                if fname:
                    name_panel_lookup[(fname.lower().strip(), panel_name)] = var

    # Group refs by source field variableName (the field where the Validate EDV rule lives)
    # In detection output:
    #   field_variableName = destination (the field in the analyzed panel, being populated)
    #   referenced_field_variableName = source (the cross-panel trigger field)
    # So we group by referenced_field_variableName (source/trigger).
    source_groups: Dict[str, List[Dict]] = {}
    for ref in vedv_refs:
        src_var = ref.get('referenced_field_variableName', '')
        if not src_var or src_var == 'unknown':
            ref_name = ref.get('referenced_field_name', '').lower().strip()
            for (name_key, panel_key), var in name_panel_lookup.items():
                if name_key == ref_name:
                    src_var = var
                    break
        if src_var and src_var != 'unknown':
            source_groups.setdefault(src_var, []).append(ref)

    for source_var, refs in source_groups.items():
        if source_var not in field_lookup:
            continue
        source_panel, source_field = field_lookup[source_var]

        # Group cross-panel destinations by EDV table
        # table_name -> [(col_num, dest_variableName)]
        table_dests: Dict[str, List[Tuple[int, str]]] = {}

        for ref in refs:
            # field_variableName = the destination field being populated
            dest_var = ref.get('field_variableName', '')
            if not dest_var or dest_var == 'unknown' or dest_var not in field_lookup:
                continue
            dest_panel, dest_field = field_lookup[dest_var]

            # Skip if destination is in the same panel as source (already handled)
            if dest_panel == source_panel:
                continue

            logic = dest_field.get('logic', '')
            table_name = _parse_edv_table_from_logic(logic)
            col_num = _parse_column_from_logic(logic)

            if not table_name or not col_num:
                # Try from the ref description as fallback
                desc = ref.get('description', '')
                if not table_name:
                    table_name = _parse_edv_table_from_logic(desc)
                if not col_num:
                    col_num = _parse_column_from_logic(desc)

            if table_name and col_num:
                table_dests.setdefault(table_name, []).append((col_num, dest_var))

        # Now patch or create Validate EDV rules for each table
        for table_name, dests in table_dests.items():
            # Find existing Validate EDV rule on source field for this table
            vedv_rule = None
            for rule in source_field.get('rules', []):
                if rule.get('rule_name') != 'Validate EDV (Server)':
                    continue
                params = rule.get('params', '')
                if isinstance(params, str) and params.upper() == table_name:
                    vedv_rule = rule
                    break
                elif isinstance(params, dict) and str(params.get('param', '')).upper() == table_name:
                    vedv_rule = rule
                    break

            if vedv_rule:
                # Patch existing rule's destination_fields
                dest_fields = vedv_rule.get('destination_fields', [])
                for col_num, dest_var in dests:
                    dest_idx = col_num - 2  # a1 is skipped, so a2->idx 0, a3->idx 1, etc.
                    if dest_idx < 0:
                        continue
                    # Extend array if needed
                    while len(dest_fields) <= dest_idx:
                        dest_fields.append('-1')
                    # Only patch if currently unmapped
                    if dest_fields[dest_idx] == '-1':
                        dest_fields[dest_idx] = dest_var
                        patched += 1
                vedv_rule['destination_fields'] = dest_fields
            else:
                # Create a new Validate EDV rule for this table
                max_col = max(col for col, _ in dests)
                dest_fields = ['-1'] * (max_col - 1)  # a2 to a(max_col)
                for col_num, dest_var in dests:
                    dest_idx = col_num - 2
                    if 0 <= dest_idx < len(dest_fields):
                        dest_fields[dest_idx] = dest_var
                        patched += 1

                new_rule = {
                    'rule_name': 'Validate EDV (Server)',
                    'source_fields': [source_var],
                    'destination_fields': dest_fields,
                    'params': table_name,
                    '_reasoning': (
                        f'Cross-panel Validate EDV: source {source_field.get("field_name", "")} '
                        f'in {source_panel} looks up {table_name}. '
                        f'Destinations: {", ".join(f"a{c}->{v}" for c, v in dests)}.'
                    ),
                    '_inter_panel_source': 'cross-panel',
                }
                source_field.setdefault('rules', []).append(new_rule)
                created += 1

    return patched, created


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
        default="opus",
        help="Claude model for Phase 1 reference detection (default: opus)"
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
    failed_panels: List[Dict] = []  # {panel_name, phase, field_count, error}

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
                failed_panels.append({
                    'panel_name': panel_name,
                    'phase': 'Phase 1',
                    'field_count': len(input_data.get(panel_name, [])),
                    'error': str(e),
                })

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

    # ── Deterministic reclassification: check field's own logic for EDV patterns ──
    # The LLM is non-deterministic with edv/validate_edv/derivation classifications.
    # Identical logic patterns get different labels across panels. This pass checks
    # the actual field logic text to force-reclassify derivation → validate_edv
    # when EDV-related keywords are present, making classification deterministic.
    edv_keywords = ['edv', 'vc_', 'reference table', 'ref table', 'attribute ']
    reclass_count = 0
    for ref in all_refs:
        if ref.get('classification') not in ('derivation',):
            continue
        field_var = _norm_var(ref.get('field_variableName', ''))
        field_panel = var_index.get(field_var, '')
        if not field_panel or field_panel not in input_data:
            continue
        # Find the field and check its own logic text directly
        for f in input_data[field_panel]:
            if _norm_var(f.get('variableName', '')) == field_var:
                logic = f.get('logic', '').lower()
                if any(kw in logic for kw in edv_keywords):
                    ref['_original_classification'] = ref.get('classification')
                    ref['classification'] = 'validate_edv'
                    reclass_count += 1
                break
    if reclass_count:
        log(f"  Deterministic reclassification: {reclass_count} derivation refs "
            f"→ validate_edv (field logic contains EDV keywords)")
        # Re-sort complex vs simple after reclassification
        complex_refs = [r for r in complex_refs if r.get('field_variableName')]
        # Log updated breakdown
        classification_counts2: Dict[str, int] = {}
        for ref in all_refs:
            cls = ref.get('classification', 'unknown')
            classification_counts2[cls] = classification_counts2.get(cls, 0) + 1
        breakdown2 = ', '.join(f"{cls}: {cnt}" for cls, cnt in sorted(classification_counts2.items()))
        log(f"  Updated breakdown: {breakdown2}")

    # ── Track panels with edv/validate_edv-classified refs (for Phase 4) ──
    edv_panels = set()       # panels needing Phase 4a (EDV Dropdown agent)
    vedv_panels = set()      # panels needing Phase 4b (Validate EDV agent)
    for ref in all_refs:
        cls = ref.get('classification', '')
        if cls in ('edv', 'validate_edv'):
            field_var = ref.get('field_variableName', '')
            norm = _norm_var(field_var)
            field_panel = var_index.get(norm, '') if norm else ''
            ref_panel = ref.get('referenced_panel', '')

            if cls == 'edv':
                # EDV: include both destination and source panels
                if field_panel:
                    edv_panels.add(field_panel)
                if ref_panel and ref_panel in input_data:
                    edv_panels.add(ref_panel)
            else:
                # validate_edv: add BOTH source and destination panels.
                # Source panel (referenced_panel) has the trigger field (e.g., Vendor Number).
                # Destination panel (field_variableName's panel) has the field being populated
                # and needs Phase 4b to place Validate EDV rules on its own fields
                # (e.g., Company Code triggering lookup for "block old" sibling fields).
                # Phase 4c still handles cross-panel destination patching afterwards.
                if ref_panel and ref_panel in input_data:
                    vedv_panels.add(ref_panel)
                if field_panel:
                    vedv_panels.add(field_panel)
    # EDV panels also need Validate EDV — EDV sets up dropdown options,
    # Validate EDV sets up lookup/auto-population. They're complementary.
    vedv_panels |= edv_panels
    if edv_panels:
        log(f"  EDV-classified panels (for Phase 4a): {', '.join(sorted(edv_panels))}")
    if vedv_panels:
        log(f"  Validate-EDV-classified panels (for Phase 4b): {', '.join(sorted(vedv_panels))}")

    # ── Save all refs for Phase 4c cross-panel Validate EDV destination patching ──
    # Include all classifications (not just validate_edv) because some derivation-classified
    # refs also need Validate EDV rules — the detection agent may output empty descriptions,
    # preventing reclassification to validate_edv. The patching function is safe: it only
    # patches when it can parse a valid table name and column number from the field logic.
    all_refs_for_vedv_patch = list(all_refs)

    # ── Filter edv/validate_edv-classified refs from Phase 2 (handled by Phase 4) ──
    pre_edv_filter = len(complex_refs)
    complex_refs = [r for r in complex_refs if r.get('classification') not in ('edv', 'validate_edv')]
    edv_filtered = pre_edv_filter - len(complex_refs)
    if edv_filtered:
        log(f"  Filtered {edv_filtered} edv/validate_edv-classified refs from Phase 2 (handled by Phase 4)")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2: All Rules via Expression Agent (copy_to uses ctfd with on("change"))
    # ══════════════════════════════════════════════════════════════════════
    complex_rules: Dict[str, List[Dict]] = {}
    complex_rule_count = 0

    # Merge simple refs into complex refs — expression agent handles copy_to via ctfd + on("change")
    if simple_refs:
        log(f"PHASE 2: Merging {len(simple_refs)} copy_to refs into complex refs (agent will use ctfd + on(\"change\"))")
        complex_refs.extend(simple_refs)

    if complex_refs:
        log(f"PHASE 2: EXPRESSION RULES — {len(complex_refs)} references (including {len(simple_refs)} copy_to)")
        t0 = time.time()

        # Fix B: Deduplicate refs before grouping — re-key PANEL-targeted refs
        # to the controlling field so they merge into the same group
        pre_dedup = len(complex_refs)
        complex_refs = deduplicate_complex_refs(complex_refs, input_data)
        if len(complex_refs) < pre_dedup:
            log(f"  Dedup: {pre_dedup} -> {len(complex_refs)} refs")

        # Group complex refs by source field (not panel) to consolidate
        # rules when multiple panels reference the same source field
        groups = group_complex_refs_by_source_field(complex_refs)
        log(f"  Grouped into {len(groups)} source field groups: "
            f"{', '.join(f'{k} ({len(v)} refs)' for k, v in groups.items())}")

        MAX_REFS_PER_CALL = 20

        # Build all work items first, then execute in parallel
        phase2_work_items = []  # [(batch, involved_panels, group_label, source_field_var)]

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

            # Batch splitting: prevent output truncation on large groups
            if len(refs_group) > MAX_REFS_PER_CALL:
                batches = [refs_group[i:i+MAX_REFS_PER_CALL]
                           for i in range(0, len(refs_group), MAX_REFS_PER_CALL)]
                log(f"  Phase 2: Splitting '{source_field_var}' into {len(batches)} batches "
                    f"({len(refs_group)} refs, max {MAX_REFS_PER_CALL} per call)")
            else:
                batches = [refs_group]

            for batch_idx, batch in enumerate(batches):
                # Use the action source field's name for a readable label
                source_field_name = batch[0].get('field_name', source_field_var)
                if len(batches) > 1:
                    group_label = f"{source_field_name} ({source_field_var}) batch {batch_idx+1}/{len(batches)}"
                else:
                    group_label = f"{source_field_name} ({source_field_var})"

                phase2_work_items.append((batch, involved_panels, group_label, source_field_var))

        # Execute all Phase 2 work items in parallel
        log(f"  Phase 2: Launching {len(phase2_work_items)} parallel agent calls "
            f"(max {args.max_workers} workers)...")

        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {}
            for batch, involved_panels, group_label, source_field_var in phase2_work_items:
                future = executor.submit(
                    call_complex_rules_agent,
                    batch, involved_panels, temp_dir,
                    group_label=group_label, model=args.model,
                )
                futures[future] = (group_label, source_field_var, len(batch))

            for future in as_completed(futures):
                group_label, source_field_var, batch_size = futures[future]
                try:
                    group_rules = future.result()
                    if not group_rules:
                        failed_panels.append({
                            'panel_name': source_field_var,
                            'phase': 'Phase 2',
                            'field_count': batch_size,
                            'error': 'empty output',
                        })

                    # Merge group rules into overall complex_rules
                    for panel_name, entries in group_rules.items():
                        if panel_name not in complex_rules:
                            complex_rules[panel_name] = []
                        complex_rules[panel_name].extend(entries)
                except Exception as e:
                    log(f"  Phase 2: Exception for '{group_label}': {e}")
                    failed_panels.append({
                        'panel_name': source_field_var,
                        'phase': 'Phase 2',
                        'field_count': batch_size,
                        'error': str(e),
                    })

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

    # -- Ref-to-Rule Reconciliation ----------------------------------------
    unmatched_refs, edv_skipped = reconcile_refs_to_rules(all_refs, complex_rules)
    phase2_scope = len(all_refs) - edv_skipped
    if unmatched_refs:
        log(f"  Reconciliation WARNING: {len(unmatched_refs)}/{phase2_scope} Phase 2 refs "
            f"did not produce rules (+ {edv_skipped} EDV refs handled by Phase 4):")
        for ref in unmatched_refs:
            log(f"    - {ref.get('referenced_field_variableName')} -> "
                f"{ref.get('field_variableName')} ({ref.get('classification')}) "
                f"-- {ref.get('reason')}")
        unmatched_file = temp_dir / "unmatched_refs.json"
        with open(unmatched_file, 'w') as f:
            json.dump(unmatched_refs, f, indent=2)
        log(f"  Written to: {unmatched_file}")
    else:
        log(f"  Reconciliation: all {phase2_scope} Phase 2 refs covered by generated rules "
            f"(+ {edv_skipped} EDV refs handled by Phase 4)")

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

    # Deduplicate subset Expression (Client) rules across agent groups
    if complex_rules:
        complex_rules, dedup_count = deduplicate_expression_rules(complex_rules)
        if dedup_count:
            log(f"  Dedup: dropped {dedup_count} subset expression rules")

    # Merge all rules into output
    log("Merging rules into output...")
    all_results = merge_all_rules_into_output(input_data, {}, complex_rules)

    # Fix D: Expand PANEL variableNames in expression function arguments
    # to their child fields (e.g., mm(cond, "_panelVar_") -> mm(cond, "_child1_", "_child2_"))
    # NOTE: Does NOT expand mvi/minvi — platform cascades visibility automatically
    panel_expansions = expand_panel_variables_in_expressions(all_results, input_data)
    if panel_expansions:
        log(f"  Fix D: Expanded {panel_expansions} PANEL variables to child fields in expressions")

    # Fix E: When clearing expressions reference fields from a cross-panel,
    # ensure ALL non-structural fields from that panel are included
    # (fixes missing ARRAY_HDR and other fields the LLM didn't list)
    clearing_expansions = ensure_full_panel_in_clearing(all_results, input_data)
    if clearing_expansions:
        log(f"  Fix E: Added missing panel fields to {clearing_expansions} clearing expressions")

    # NOTE: collapse_children_to_panel_in_visibility is DISABLED.
    # It was incorrectly collapsing intra-panel visibility rules (e.g., Company Code
    # Type toggling ARRAY sub-sections) by replacing child field lists with the PANEL
    # variable. The regex matched variables inside vo() conditions as field arguments,
    # causing the entire panel to be hidden instead of just the target fields.
    # Inter-panel agents already emit PANEL variables directly, so this is not needed.

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

    # Combine both sets to decide if Phase 4 should run at all
    all_phase4_panels = edv_panels | vedv_panels

    if all_phase4_panels:
        log(f"PHASE 4: CROSS-PANEL EDV PROCESSING — "
            f"{len(edv_panels)} edv panels, {len(vedv_panels)} validate_edv panels")
        t0 = time.time()

        # Parse BUD to extract reference tables
        log(f"  Parsing BUD for reference tables: {args.bud}")
        bud_parser = DocumentParser()
        parsed_doc = bud_parser.parse(args.bud)
        all_reference_tables = extract_reference_tables_from_parser(parsed_doc)
        log(f"  Found {len(all_reference_tables)} reference tables")

        # Reuse existing all_panels_index_file (written in Phase 1)
        # It has the same field_name/variableName data since merge only adds rules

        # Phase 4a: EDV Dropdown Rules (only panels with 'edv' classification)
        if edv_panels:
            log(f"  Phase 4a: EDV Rules on {len(edv_panels)} panels (parallel)...")

            def _run_edv_agent(panel_name):
                panel_fields = all_results[panel_name]
                referenced_tables = get_referenced_tables_for_panel(panel_fields, all_reference_tables)
                log(f"    EDV agent: '{panel_name}' ({len(panel_fields)} fields, "
                    f"{len(referenced_tables)} ref tables)")
                return call_edv_mini_agent(
                    panel_fields, referenced_tables, panel_name, temp_dir,
                    context_usage=args.context_usage,
                    verbose=True,
                    model=args.model,
                    all_panels_index_file=all_panels_index_file,
                )

            edv_panel_list = [p for p in sorted(edv_panels) if p in all_results]
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                futures = {executor.submit(_run_edv_agent, p): p for p in edv_panel_list}
                for future in as_completed(futures):
                    panel_name = futures[future]
                    try:
                        result = future.result()
                        if result:
                            all_results[panel_name] = result
                            phase4_edv_panels += 1
                            log(f"    EDV agent: '{panel_name}' — success ({len(result)} fields)")
                        else:
                            log(f"    EDV agent: '{panel_name}' — FAILED (keeping existing data)")
                    except Exception as e:
                        log(f"    EDV agent: '{panel_name}' — EXCEPTION: {e}")
        else:
            log("  Phase 4a skipped — no edv-classified panels")

        # Phase 4b: Validate EDV Rules (only panels with 'validate_edv' classification)
        if vedv_panels:
            log(f"  Phase 4b: Validate EDV on {len(vedv_panels)} panels (parallel)...")

            def _run_vedv_agent(panel_name):
                panel_fields = all_results[panel_name]

                # Deep copy fields so we can strip Validate EDV rules without
                # mutating the original. If the agent fails, we keep the original.
                stripped_fields = copy.deepcopy(panel_fields)

                # Strip existing Validate EDV rules so the agent re-creates them
                # with cross-panel context (ALL_PANELS_INDEX). Stage 4 placed these
                # rules without cross-panel awareness, so source fields may be wrong.
                stripped_vedv_count = 0
                for field in stripped_fields:
                    original_rules = field.get('rules', [])
                    kept_rules = [r for r in original_rules
                                  if not (isinstance(r, dict) and
                                          r.get('rule_name') == 'Validate EDV (Server)')]
                    stripped_vedv_count += len(original_rules) - len(kept_rules)
                    field['rules'] = kept_rules
                if stripped_vedv_count:
                    log(f"    Stripped {stripped_vedv_count} existing Validate EDV rules "
                        f"for re-creation with cross-panel context")

                referenced_tables = get_referenced_tables_for_panel(stripped_fields, all_reference_tables)
                log(f"    Validate EDV: '{panel_name}' ({len(stripped_fields)} fields, "
                    f"{len(referenced_tables)} ref tables)")

                return call_validate_edv_mini_agent(
                    stripped_fields, referenced_tables, panel_name, temp_dir,
                    context_usage=args.context_usage,
                    verbose=True,
                    model=args.model,
                    all_panels_index_file=all_panels_index_file,
                )

            vedv_panel_list = [p for p in sorted(vedv_panels) if p in all_results]
            with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
                futures = {executor.submit(_run_vedv_agent, p): p for p in vedv_panel_list}
                for future in as_completed(futures):
                    panel_name = futures[future]
                    try:
                        result = future.result()
                        if result:
                            all_results[panel_name] = result
                            phase4_vedv_panels += 1
                            log(f"    Validate EDV: '{panel_name}' — success ({len(result)} fields)")
                        else:
                            # Keep original (un-stripped) data on failure
                            log(f"    Validate EDV: '{panel_name}' — FAILED (keeping existing data)")
                    except Exception as e:
                        log(f"    Validate EDV: '{panel_name}' — EXCEPTION: {e}")
        else:
            log("  Phase 4b skipped — no validate_edv-classified panels")

        # Phase 4c: Deterministic patching of cross-panel Validate EDV destinations
        if all_refs_for_vedv_patch:
            log(f"  Phase 4c: Patching cross-panel Validate EDV destinations "
                f"({len(all_refs_for_vedv_patch)} refs)...")
            patched_count, created_count = patch_cross_panel_vedv_destinations(
                all_results, all_refs_for_vedv_patch, var_index,
            )
            log(f"  Phase 4c: Patched {patched_count} cross-panel destinations, "
                f"created {created_count} new Validate EDV rules")

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
        log("Phase 4 skipped — no EDV/Validate-EDV-classified cross-panel references")

    # ══════════════════════════════════════════════════════════════════════
    # Write output
    # ══════════════════════════════════════════════════════════════════════
    log(f"Writing output to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    total_time = elapsed_str(pipeline_start)

    # Per-rule-type stats for cross-panel rules
    rule_type_counts: Dict[str, int] = {}
    for panel_fields_list in all_results.values():
        for field in panel_fields_list:
            for rule in field.get('rules', []):
                if not isinstance(rule, dict) or rule.get('_inter_panel_source') != 'cross-panel':
                    continue
                if rule.get('_expressionRuleType'):
                    rtype = rule['_expressionRuleType']
                else:
                    rtype = rule.get('rule_name', 'unknown')
                rule_type_counts[rtype] = rule_type_counts.get(rtype, 0) + 1

    rule_type_lines = '\n'.join(f"    {rt}: {cnt}" for rt, cnt in sorted(rule_type_counts.items()))
    if not rule_type_lines:
        rule_type_lines = '    (none)'

    # Classification-to-rule-type imbalance warnings
    classification_counts: Dict[str, int] = {}
    for ref in all_refs:
        if ref.get('classification') not in ('edv', 'validate_edv'):
            cls = ref.get('classification', 'unknown')
            classification_counts[cls] = classification_counts.get(cls, 0) + 1

    imbalance_warnings = []
    cls_to_rule_types = {
        'copy_to': ['copy_to'],
        'derivation': ['derivation'],
        'visibility': ['visibility'],
        'clearing': ['clear_field'],
    }
    for cls, expected_types in cls_to_rule_types.items():
        if classification_counts.get(cls, 0) > 0:
            has_rules = any(rule_type_counts.get(rt, 0) > 0 for rt in expected_types)
            if not has_rules:
                imbalance_warnings.append(
                    f"    WARNING: {classification_counts[cls]} '{cls}' refs but 0 matching rules")

    imbalance_lines = '\n'.join(imbalance_warnings) if imbalance_warnings else '    (none)'

    # Failed panels summary
    if failed_panels:
        failed_lines = '\n'.join(
            f"    {fp['phase']}: \"{fp['panel_name']}\" ({fp['field_count']} fields/refs) -- {fp['error']}"
            for fp in failed_panels
        )
    else:
        failed_lines = '    No failures'

    # Coverage metrics (EDV-aware)
    coverage_pct = (
        ((phase2_scope - len(unmatched_refs)) / phase2_scope * 100)
        if phase2_scope else 100
    )

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
  Input refs: {pre_edv_filter + len(simple_refs)} (complex: {pre_edv_filter}, copy_to: {len(simple_refs)})
  EDV-filtered (Phase 4): {edv_filtered}
  Processed: {len(complex_refs)}
  Rules created: {complex_rule_count}
Phase 3 — Validate + Merge:
  Cross-panel rules added: {cross_panel_rule_count}
Phase 4 — Cross-Panel EDV Processing:
  EDV-classified panels (4a): {len(edv_panels)}
  Validate-EDV-classified panels (4b): {len(vedv_panels)}
  EDV processed: {phase4_edv_panels}, Validate EDV processed: {phase4_vedv_panels}
  Rules delta: {output_rule_count - pre_phase4_rule_count}
Reconciliation:
  Refs detected: {len(all_refs)}
  EDV/Validate-EDV refs (Phase 4): {edv_skipped}
  Phase 2 scope: {phase2_scope}
  Covered by rules: {phase2_scope - len(unmatched_refs)}
  Unmatched refs: {len(unmatched_refs)}
  Coverage: {coverage_pct:.1f}%
Cross-Panel Rules by Type:
{rule_type_lines}
Classification-to-Rule Imbalances:
{imbalance_lines}
Failed Panels:
{failed_lines}
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
