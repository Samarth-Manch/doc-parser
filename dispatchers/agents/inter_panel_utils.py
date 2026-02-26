#!/usr/bin/env python3
"""
Inter-Panel Reference Utilities (v2 — Two-Pass Architecture)

Shared utilities for the two-pass inter-panel dispatcher:
- Pass 1: Global analysis (compact panels text, variableName index)
- Pass 2: Complex rules (involved panels extraction)
- Pass 3: Merge + validate (rule merging, variableName validation)
"""

import copy
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def build_compact_panels_text(all_panels_data: Dict[str, List[Dict]]) -> str:
    """
    Build compact one-line-per-field representation of ALL panels.
    Used as input to Pass 1 analysis agent for global view.

    Format:
        === Panel: Panel Name ===
        field_name | type | variableName | logic

    Args:
        all_panels_data: All panels data (panel name -> field list)

    Returns:
        Compact text representation of all panels
    """
    lines = []
    for panel_name, fields in all_panels_data.items():
        lines.append(f"=== Panel: {panel_name} ===")
        for field in fields:
            name = field.get('field_name', '?')
            ftype = field.get('type', '?')
            var = field.get('variableName', '?')
            logic = field.get('logic', '')
            # Collapse multiline logic to single line
            logic_oneline = ' '.join(logic.split()) if logic else ''
            lines.append(f"{name} | {ftype} | {var} | {logic_oneline}")
        lines.append("")  # blank line between panels
    return '\n'.join(lines)


def build_variablename_index(all_panels_data: Dict[str, List[Dict]]) -> Dict[str, str]:
    """
    Build variableName -> panel_name lookup map across all panels.
    Used for validation and quick panel identification.

    Args:
        all_panels_data: All panels data (panel name -> field list)

    Returns:
        Dict mapping variableName -> panel_name
    """
    index = {}
    for panel_name, fields in all_panels_data.items():
        for field in fields:
            var = field.get('variableName', '')
            if var:
                index[var] = panel_name
    return index


def quick_cross_panel_scan(input_data: Dict[str, List[Dict]]) -> bool:
    """
    Fast regex check if ANY cross-panel references exist across all panels.
    Used for early exit — if no cross-panel refs found, skip the entire stage.

    Checks for patterns like:
    - (from X Panel) / (from X)
    - "from X Panel" / "from 'X'"
    - Direct mentions of other panel names in logic text

    Args:
        input_data: All panels data (panel name -> field list)

    Returns:
        True if cross-panel references likely exist, False otherwise
    """
    all_panel_names = list(input_data.keys())

    if len(all_panel_names) <= 1:
        return False

    # Collect all logic text
    all_logic_parts = []
    for panel_fields in input_data.values():
        for field in panel_fields:
            logic = field.get('logic', '')
            if logic:
                all_logic_parts.append(logic)

    if not all_logic_parts:
        return False

    combined_logic = '\n'.join(all_logic_parts)

    # Check for explicit cross-panel patterns
    explicit_patterns = [
        r'\(from\s+.+?\s*(?:panel)?\s*\)',  # (from X Panel) or (from X)
        r'from\s+[\'"].+?[\'"]\s*panel',      # from 'X' panel
    ]
    for pattern in explicit_patterns:
        if re.search(pattern, combined_logic, re.IGNORECASE):
            return True

    # Check if any other panel name is mentioned in any field's logic
    for panel_name in all_panel_names:
        # Build pattern that matches panel name as a distinct phrase
        escaped = re.escape(panel_name)
        pattern = re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)
        for other_panel, panel_fields in input_data.items():
            if other_panel == panel_name:
                continue  # Skip self-references
            for field in panel_fields:
                logic = field.get('logic', '')
                if logic and pattern.search(logic):
                    return True

    return False


def _norm_var(v: str) -> str:
    """Normalize __varname__ or _varname_ to _varname_ for index lookups."""
    s = v.strip('_')
    return f'_{s}_' if s else v


def validate_inter_panel_rules(rules_by_panel: Dict[str, List[Dict]],
                                var_index: Dict[str, str]) -> Tuple[Dict[str, List[Dict]], int]:
    """
    Validate inter-panel rules: check variableNames exist, strip invalid rules.

    Args:
        rules_by_panel: Rules grouped by panel {panel: [{target_field_variableName, rules_to_add}]}
        var_index: variableName -> panel_name lookup

    Returns:
        Tuple of (validated_rules, stripped_count)
    """
    validated = {}
    stripped_count = 0

    for panel_name, field_rules_list in rules_by_panel.items():
        valid_entries = []
        for entry in field_rules_list:
            target_var = entry.get('target_field_variableName', '')

            # Check that the target field exists (normalize __x__ -> _x_ for lookup)
            if _norm_var(target_var) not in var_index:
                print(f"  Validation: target_field '{target_var}' not found in any panel, stripping")
                stripped_count += 1
                continue

            # Check that the target field is in the expected panel
            actual_panel = var_index[_norm_var(target_var)]
            if actual_panel.lower() != panel_name.lower():
                print(f"  Validation: target_field '{target_var}' is in '{actual_panel}', "
                      f"not '{panel_name}' — relocating")
                # Relocate to the correct panel
                if actual_panel not in validated:
                    validated[actual_panel] = []
                validated[actual_panel].append(entry)
                continue

            # Validate source_fields and destination_fields in rules
            valid_rules = []
            for rule in entry.get('rules_to_add', []):
                # Check source_fields exist (normalize __x__ -> _x_ for lookup)
                src_fields = rule.get('source_fields', [])
                dst_fields = rule.get('destination_fields', [])

                invalid_src = [f for f in src_fields if _norm_var(f) not in var_index]
                invalid_dst = [f for f in dst_fields if _norm_var(f) not in var_index]

                if invalid_src:
                    print(f"  Validation: rule '{rule.get('rule_name', '?')}' has invalid source_fields: "
                          f"{invalid_src}, stripping")
                    stripped_count += 1
                    continue

                if invalid_dst:
                    # Remove invalid destinations but keep valid ones
                    valid_dsts = [f for f in dst_fields if _norm_var(f) in var_index]
                    if valid_dsts:
                        rule['destination_fields'] = valid_dsts
                        print(f"  Validation: rule '{rule.get('rule_name', '?')}' — removed invalid "
                              f"destination_fields: {invalid_dst}")
                    else:
                        print(f"  Validation: rule '{rule.get('rule_name', '?')}' has NO valid "
                              f"destination_fields, stripping")
                        stripped_count += 1
                        continue

                valid_rules.append(rule)

            if valid_rules:
                entry['rules_to_add'] = valid_rules
                valid_entries.append(entry)

        if valid_entries:
            if panel_name not in validated:
                validated[panel_name] = []
            validated[panel_name].extend(valid_entries)

    return validated, stripped_count


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
            # Deduplicate: check if an identical rule already exists.
            # For Expression (Client) rules, also compare conditionalValues because
            # multiple expression rules can legitimately share the same source/destination
            # fields but have different expressions (different conditionalValues).
            is_duplicate = False
            for existing in existing_rules:
                if isinstance(existing, str):
                    if existing == rule.get('rule_name', ''):
                        is_duplicate = True
                        break
                elif existing.get('rule_name') == rule.get('rule_name'):
                    if rule.get('rule_name') == 'Expression (Client)':
                        # For expression rules: duplicate only if conditionalValues also match
                        if (existing.get('source_fields') == rule.get('source_fields') and
                                existing.get('conditionalValues') == rule.get('conditionalValues')):
                            is_duplicate = True
                            break
                    else:
                        if (existing.get('source_fields') == rule.get('source_fields') and
                                existing.get('destination_fields') == rule.get('destination_fields')):
                            is_duplicate = True
                            break

            if not is_duplicate:
                # Assign next available rule ID
                max_id = max((r.get('id', 0) for r in existing_rules if isinstance(r, dict)), default=0)
                rule['id'] = max_id + 1
                rule['_inter_panel_source'] = 'cross-panel'
                existing_rules.append(rule)
                merge_count += 1

        panel_fields[field_idx]['rules'] = existing_rules

    return merge_count


def merge_all_rules_into_output(input_data: Dict[str, List[Dict]],
                                 pass1_rules: Dict[str, List[Dict]],
                                 pass2_rules: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, List[Dict]]:
    """
    Deep copy input data and merge both Pass 1 and Pass 2 rules into the correct panels/fields.

    Args:
        input_data: Original stage 7 output (panel name -> field list)
        pass1_rules: Direct rules from Pass 1 {panel: [{target_field_variableName, rules_to_add}]}
        pass2_rules: Complex rules from Pass 2 (same format), or None

    Returns:
        Deep copy of input_data with all inter-panel rules merged in
    """
    output = copy.deepcopy(input_data)

    total_merged = 0

    # Merge Pass 1 rules
    if pass1_rules:
        for panel_name, field_rules_list in pass1_rules.items():
            if panel_name in output:
                count = _merge_rules_into_panel(output[panel_name], field_rules_list, panel_name)
                total_merged += count
                if count > 0:
                    print(f"  Pass 1: Merged {count} rules into panel '{panel_name}'")
            else:
                print(f"  Warning: Pass 1 targets panel '{panel_name}' which doesn't exist in input")

    # Merge Pass 2 rules
    if pass2_rules:
        for panel_name, field_rules_list in pass2_rules.items():
            if panel_name in output:
                count = _merge_rules_into_panel(output[panel_name], field_rules_list, panel_name)
                total_merged += count
                if count > 0:
                    print(f"  Pass 2: Merged {count} rules into panel '{panel_name}'")
            else:
                print(f"  Warning: Pass 2 targets panel '{panel_name}' which doesn't exist in input")

    print(f"  Total rules merged: {total_merged}")
    return output


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


def read_complex_refs(path: Path) -> Optional[List[Dict]]:
    """
    Read complex references file written by Pass 1.

    Args:
        path: Path to the complex refs JSON file

    Returns:
        List of complex reference records, or None if file doesn't exist
    """
    if not path.exists():
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return None
    except (json.JSONDecodeError, IOError):
        return None


def get_involved_panels(complex_refs: List[Dict],
                         all_panels_data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Extract full panel data for panels involved in complex references.

    Args:
        complex_refs: List of complex reference records from Pass 1
        all_panels_data: All panels data

    Returns:
        Dict of involved panel name -> full field list
    """
    involved_names = set()
    for ref in complex_refs:
        for key in ('source_panel', 'target_panel'):
            val = ref.get(key, '')
            if isinstance(val, list):
                involved_names.update(v for v in val if isinstance(v, str) and v)
            elif isinstance(val, str) and val:
                involved_names.add(val)

    result = {}
    for name in involved_names:
        if name in all_panels_data:
            result[name] = all_panels_data[name]
        else:
            # Case-insensitive fallback
            for actual_name in all_panels_data:
                if actual_name.lower() == name.lower():
                    result[actual_name] = all_panels_data[actual_name]
                    break

    return result
