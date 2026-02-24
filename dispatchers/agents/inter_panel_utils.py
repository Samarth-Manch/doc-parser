#!/usr/bin/env python3
"""
Inter-Panel Reference Utilities

Shared utilities for detecting cross-panel field references in BUD logic,
providing referenced panel context to agents, and merging inter-panel rules
back into the correct target panels.

Used by all 8 dispatchers in the rule extraction pipeline.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


def detect_referenced_panels(panel_fields: List[Dict],
                             all_panel_names: List[str],
                             current_panel: str) -> Set[str]:
    """
    Detect which other panels are referenced in the current panel's field logic.
    Uses regex-based detection on field logic text.

    Args:
        panel_fields: List of field dicts for the current panel
        all_panel_names: List of all panel names in the dataset
        current_panel: Name of the current panel being processed

    Returns:
        Set of referenced panel names (excludes current panel)
    """
    referenced = set()

    # Collect all logic text from the panel
    all_logic = []
    for field in panel_fields:
        logic = field.get('logic', '')
        if logic:
            all_logic.append(logic)

    if not all_logic:
        return referenced

    combined_logic = '\n'.join(all_logic)
    logic_lower = combined_logic.lower()

    # Pattern 1: "(from X Panel)" or "(from X panel)"
    for match in re.finditer(r'\(from\s+(.+?)\s+panel\)', combined_logic, re.IGNORECASE):
        panel_ref = match.group(1).strip()
        referenced.add(panel_ref)

    # Pattern 2: "(from X)" where X matches a known panel name
    for match in re.finditer(r'\(from\s+(.+?)\)', combined_logic, re.IGNORECASE):
        candidate = match.group(1).strip()
        # Check if candidate matches a known panel name (case-insensitive)
        for panel_name in all_panel_names:
            if candidate.lower() == panel_name.lower():
                referenced.add(panel_name)
                break

    # Pattern 3: "from 'X' panel" or 'from "X" panel'
    for match in re.finditer(r'from\s+[\'"](.+?)[\'"]\s+panel', combined_logic, re.IGNORECASE):
        panel_ref = match.group(1).strip()
        referenced.add(panel_ref)

    # Pattern 4: "in X Panel" or "in X panel"
    for match in re.finditer(r'\bin\s+(.+?)\s+panel\b', combined_logic, re.IGNORECASE):
        candidate = match.group(1).strip()
        # Avoid false positives like "in this panel"
        if candidate.lower() in ('this', 'the', 'each', 'every', 'same'):
            continue
        for panel_name in all_panel_names:
            if candidate.lower() == panel_name.lower():
                referenced.add(panel_name)
                break

    # Pattern 5: Direct panel name mentions in logic
    for panel_name in all_panel_names:
        if panel_name.lower() == current_panel.lower():
            continue
        # Only match if panel name appears as a distinct phrase (word boundaries)
        pattern = re.compile(r'\b' + re.escape(panel_name) + r'\b', re.IGNORECASE)
        if pattern.search(combined_logic):
            referenced.add(panel_name)

    # Normalize: match to actual panel names (case-insensitive)
    normalized = set()
    for ref in referenced:
        for actual_name in all_panel_names:
            if ref.lower() == actual_name.lower():
                normalized.add(actual_name)
                break

    # Exclude current panel
    normalized.discard(current_panel)

    return normalized


def get_referenced_panel_fields(referenced_panels: Set[str],
                                all_panels_data: Dict[str, List[Dict]],
                                all_results: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, List[Dict]]:
    """
    Extract field data for referenced panels, preferring current-stage output
    over previous-stage input for already-processed panels.

    Args:
        referenced_panels: Set of panel names to extract
        all_panels_data: Input data from previous stage (panel name -> field list)
        all_results: Current stage's already-processed output (panel name -> field list).
                     If provided, already-processed panels use this (more up-to-date rules).

    Returns:
        Dict mapping referenced panel name -> list of field dicts
    """
    result = {}
    for panel_name in referenced_panels:
        if all_results and panel_name in all_results:
            # Already processed this stage — use current output (has latest rules)
            result[panel_name] = all_results[panel_name]
        elif panel_name in all_panels_data:
            # Not yet processed — use previous stage input
            result[panel_name] = all_panels_data[panel_name]
    return result


def _merge_rules_into_panel(panel_fields: List[Dict],
                            field_rules_list: List[Dict],
                            target_panel: str) -> int:
    """
    Merge inter-panel rules into a single panel's field list. Mutates in place.
    Preserves all existing rules — only appends new ones.

    Args:
        panel_fields: The target panel's field list (mutated in place)
        field_rules_list: List of {target_field_variableName, rules_to_add}
        target_panel: Panel name (for logging only)

    Returns:
        Number of rules merged
    """
    # Build variableName -> field index map for quick lookup
    var_to_idx = {}
    for idx, field in enumerate(panel_fields):
        var_name = field.get('variableName', '')
        if var_name:
            var_to_idx[var_name] = idx

    merge_count = 0

    for entry in field_rules_list:
        target_var = entry.get('target_field_variableName', '')
        rules_to_add = entry.get('rules_to_add', [])

        if not target_var or not rules_to_add:
            continue

        if target_var not in var_to_idx:
            print(f"  Warning: inter-panel target field '{target_var}' not found in panel '{target_panel}', skipping")
            continue

        field_idx = var_to_idx[target_var]
        existing_rules = panel_fields[field_idx].get('rules', [])

        for rule in rules_to_add:
            # Deduplicate: check if same rule_name + source_fields + destination_fields exists
            is_duplicate = False
            for existing in existing_rules:
                # Handle both dict rules and string rules (Stage 1 uses strings)
                if isinstance(existing, str):
                    # String rule — only compare by name
                    if existing == rule.get('rule_name', ''):
                        is_duplicate = True
                        break
                elif (existing.get('rule_name') == rule.get('rule_name') and
                    existing.get('source_fields') == rule.get('source_fields') and
                    existing.get('destination_fields') == rule.get('destination_fields')):
                    is_duplicate = True
                    break

            if not is_duplicate:
                # Assign next available rule ID (skip string rules which have no 'id')
                max_id = max((r.get('id', 0) for r in existing_rules if isinstance(r, dict)), default=0)
                rule['id'] = max_id + 1
                rule['_inter_panel_source'] = 'cross-panel'
                existing_rules.append(rule)
                merge_count += 1

        panel_fields[field_idx]['rules'] = existing_rules

    return merge_count


def merge_inter_panel_rules_immediate(inter_panel_rules: Dict[str, List[Dict]],
                                       all_results: Dict[str, List[Dict]],
                                       deferred_rules: Dict[str, List[Dict]]) -> None:
    """
    Merge inter-panel rules into current output or defer for later.
    Called after EACH panel is processed.

    For each target panel in inter_panel_rules:
      - If already processed (exists in all_results) → merge into all_results
        immediately (edits the already-generated output)
      - If NOT yet processed → defer by adding to deferred_rules dict
        (will be merged after the target panel is processed)

    This ensures no rules are lost: rules always end up in all_results (current
    output), never in input_data where agents might overwrite them.

    Args:
        inter_panel_rules: Rules from the just-processed panel
            Format: {target_panel: [{target_field_variableName, rules_to_add}]}
        all_results: Panels already processed this stage (mutated in place)
        deferred_rules: Dict to accumulate rules for not-yet-processed panels
            (mutated in place). Format: {target_panel: [field_rules_entries]}
    """
    if not inter_panel_rules:
        return

    for target_panel, field_rules_list in inter_panel_rules.items():
        if target_panel in all_results:
            # Panel already processed → merge into its output immediately
            count = _merge_rules_into_panel(
                all_results[target_panel], field_rules_list, target_panel
            )
            if count > 0:
                print(f"  -> Merged {count} cross-panel rules into already-processed panel '{target_panel}'")
        else:
            # Panel not yet processed → defer until it's processed
            if target_panel not in deferred_rules:
                deferred_rules[target_panel] = []
            deferred_rules[target_panel].extend(field_rules_list)
            total_rules = sum(len(e.get('rules_to_add', [])) for e in field_rules_list)
            print(f"  -> Deferred {total_rules} cross-panel rules for pending panel '{target_panel}'")


def apply_deferred_rules(deferred_rules: Dict[str, List[Dict]],
                         panel_name: str,
                         panel_fields: List[Dict]) -> None:
    """
    Apply any deferred cross-panel rules targeting a just-processed panel.
    Called immediately after storing a panel's result in all_results.

    Args:
        deferred_rules: Dict of deferred rules (mutated — removes applied entries)
        panel_name: Name of the panel that was just processed
        panel_fields: The panel's field list in all_results (mutated in place)
    """
    if panel_name not in deferred_rules:
        return

    field_rules_list = deferred_rules.pop(panel_name)
    count = _merge_rules_into_panel(panel_fields, field_rules_list, panel_name)
    if count > 0:
        print(f"  -> Applied {count} deferred cross-panel rules to panel '{panel_name}'")


def write_referenced_panels_file(data: Dict[str, List[Dict]], path: Path) -> None:
    """Write referenced panel data to a temp JSON file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def read_inter_panel_output(path: Path) -> Optional[Dict[str, List[Dict]]]:
    """
    Read inter-panel output file written by an agent.

    Args:
        path: Path to the inter-panel output JSON file

    Returns:
        Dict mapping target_panel -> [{target_field_variableName, rules_to_add}],
        or None if file doesn't exist or is invalid
    """
    if not path.exists():
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            return data
        return None
    except (json.JSONDecodeError, IOError):
        return None




def classify_cross_panel_reference(logic: str, field: Dict,
                                    referenced_panels: Set[str]) -> str:
    """
    Classify a cross-panel reference as 'simple' or 'complex'.

    Simple (handled directly by inter-panel agent):
      - Copy To / copy from references
      - Visibility/state changes (visible, invisible, enable, disable, mandatory)

    Complex (delegated to specialized agents):
      - Derivation expressions (substring, name splitting, concatenation)
      - EDV / reference table lookups
      - Clearing expressions

    Args:
        logic: The field's logic text
        field: The field dict
        referenced_panels: Set of referenced panel names

    Returns:
        'simple' or 'complex'
    """
    logic_lower = logic.lower()

    # Complex patterns — derivation
    derivation_patterns = [
        r'first\s+word', r'last\s+word', r'substring',
        r'first\s+name\s*=', r'last\s+name\s*=', r'middle\s+name\s*=',
        r'split', r'extract', r'derive[ds]?\s+from',
        r'concatenat', r'combine',
    ]
    for pattern in derivation_patterns:
        if re.search(pattern, logic_lower):
            return 'complex'

    # Complex patterns — EDV / reference table
    edv_patterns = [
        r'reference\s+table', r'edv\s+table', r'lookup\s+table',
        r'table\s+\d+\.\d+', r'based\s+on.*table',
    ]
    for pattern in edv_patterns:
        if re.search(pattern, logic_lower):
            return 'complex'

    # Complex patterns — clearing / expressions
    clearing_patterns = [
        r'\bcf\s*\(', r'\basdff\s*\(', r'\brffdd\s*\(',
        r'\bctfd\s*\(', r'clear\s+child', r'clear\s+fields',
    ]
    for pattern in clearing_patterns:
        if re.search(pattern, logic_lower):
            return 'complex'

    # Everything else is simple (copy, visibility, enable/disable, mandatory)
    return 'simple'


def build_targeted_field_subset(source_field_var: str,
                                 target_field_var: str,
                                 all_panels_data: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Build a minimal field list containing just the source and target fields.
    Used for delegating to specialized agents with minimal context.

    Args:
        source_field_var: variableName of the source field
        target_field_var: variableName of the target field
        all_panels_data: All panels data (panel -> fields)

    Returns:
        List of field dicts (1-2 entries)
    """
    result = []
    found_source = False
    found_target = False

    for panel_fields in all_panels_data.values():
        for field in panel_fields:
            var = field.get('variableName', '')
            if var == source_field_var and not found_source:
                result.append(field)
                found_source = True
            elif var == target_field_var and not found_target:
                result.append(field)
                found_target = True

            if found_source and found_target:
                return result

    return result


def count_cross_panel_references(panel_fields: List[Dict],
                                  all_panel_names: List[str],
                                  current_panel: str) -> int:
    """
    Count fields that have cross-panel references in their logic.

    Args:
        panel_fields: List of field dicts for the current panel
        all_panel_names: List of all panel names in the dataset
        current_panel: Name of the current panel

    Returns:
        Number of fields with cross-panel references
    """
    count = 0
    other_panels = [p for p in all_panel_names if p.lower() != current_panel.lower()]

    for field in panel_fields:
        logic = field.get('logic', '')
        if not logic:
            continue
        logic_lower = logic.lower()
        for panel_name in other_panels:
            if panel_name.lower() in logic_lower:
                count += 1
                break

    return count


def build_cross_panel_prompt_section(current_panel: str,
                                     referenced_panels: Set[str],
                                     referenced_file: Path,
                                     inter_panel_output_file: Path) -> str:
    """
    Build the cross-panel context section to append to agent prompts.

    Args:
        current_panel: Name of the current panel being processed
        referenced_panels: Set of referenced panel names
        referenced_file: Path to the referenced panels data file
        inter_panel_output_file: Path where agent should write inter-panel rules

    Returns:
        Prompt text to append
    """
    panel_list = ', '.join(sorted(referenced_panels))

    return f"""
## CROSS-PANEL CONTEXT
Referenced panels detected: [{panel_list}]
Referenced panel fields file: {referenced_file}

- CURRENT panel = "{current_panel}". Process its fields normally.
- Referenced panels = context to resolve "(from X Panel)" references.
- If a field's logic says "(from Basic Details Panel)" or similar, look up that field's variableName in the referenced panel data.
- Rules on CURRENT panel fields → add to main output file as normal.
- Rules that must be placed on fields in REFERENCED panels → write to inter-panel output file: {inter_panel_output_file}

Inter-panel output format (write ONLY if there are cross-panel rules to place):
```json
{{
  "<target_panel_name>": [
    {{
      "target_field_variableName": "__fieldname__",
      "rules_to_add": [
        {{
          "rule_name": "Rule Name",
          "source_fields": ["__source__"],
          "destination_fields": ["__dest__"],
          "_reasoning": "Cross-panel: explanation"
        }}
      ]
    }}
  ]
}}
```
Write this to: {inter_panel_output_file}
"""
