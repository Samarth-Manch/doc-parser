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


def build_compact_single_panel_text(panel_name: str, panel_fields: List[Dict]) -> str:
    """
    Build compact one-line-per-field representation of a SINGLE panel.
    Used as input to Phase 1 per-panel reference detection agent.

    Format:
        field_name | type | variableName | logic

    Args:
        panel_name: Name of the panel
        panel_fields: Fields in the panel

    Returns:
        Compact text representation of the panel's fields
    """
    lines = []
    for field in panel_fields:
        name = field.get('field_name', '?')
        ftype = field.get('type', '?')
        var = field.get('variableName', '?')
        logic = field.get('logic', '')
        # Collapse multiline logic to single line
        logic_oneline = ' '.join(logic.split()) if logic else ''
        lines.append(f"{name} | {ftype} | {var} | {logic_oneline}")
    return '\n'.join(lines)


def group_complex_refs_by_source_panel(
    all_complex_refs: List[Dict],
) -> Dict[str, List[Dict]]:
    """
    Group complex cross-panel references by their source (referenced) panel.

    Refs with the same source panel likely share context and benefit from
    being processed in the same agent call.

    Args:
        all_complex_refs: Flat list of complex reference records from Phase 1

    Returns:
        Dict mapping source_panel_name -> list of complex ref records
    """
    groups: Dict[str, List[Dict]] = {}
    for ref in all_complex_refs:
        source_panel = ref.get('referenced_panel', 'unknown')
        if source_panel not in groups:
            groups[source_panel] = []
        groups[source_panel].append(ref)
    return groups


def group_complex_refs_by_source_field(
    all_complex_refs: List[Dict],
) -> Dict[str, List[Dict]]:
    """
    Group complex cross-panel references by the ACTION SOURCE field — the field
    where the rule will be placed (field_variableName), NOT the destination
    field being affected (referenced_field_variableName).

    This ensures that when a single field (e.g., "Vendor Name and Code") triggers
    clearing of 22 fields across 2 target panels, all 22 refs are sent in ONE
    agent call. The agent then produces consolidated rules (e.g., one clearing
    rule per target panel) instead of 22 near-identical rules.

    Args:
        all_complex_refs: Flat list of complex reference records from Phase 1

    Returns:
        Dict mapping field_variableName (action source) -> list of complex ref records
    """
    groups: Dict[str, List[Dict]] = {}
    for ref in all_complex_refs:
        # field_variableName = the field with the logic (where the rule is placed)
        source_field = ref.get('field_variableName', '')
        if not source_field:
            # Fallback to referenced_field_variableName if field_variableName missing
            source_field = ref.get('referenced_field_variableName', 'unknown')
        if source_field not in groups:
            groups[source_field] = []
        groups[source_field].append(ref)
    return groups


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


# ── Deterministic dedup of subset Expression (Client) rules ────────────────

_TARGET_VAR_RE = re.compile(r'"(_[a-z0-9_]+_)"')


def _extract_expression_targets(conditional_value: str) -> Set[str]:
    """Extract all target variableNames from an expression string."""
    return set(_TARGET_VAR_RE.findall(conditional_value))


def deduplicate_expression_rules(
    rules_by_panel: Dict[str, List[Dict]],
) -> Tuple[Dict[str, List[Dict]], int]:
    """
    Remove Expression (Client) rules whose targets are a strict subset of
    another rule on the same field with the same _expressionRuleType.

    When multiple agent groups produce overlapping rules for the same source
    field (e.g., one group handles all 6 panels, another handles just 1),
    this drops the smaller redundant rule.

    Only drops strict subsets (A ⊂ B). Rules with identical targets or
    non-overlapping targets are kept. Non-Expression rules are never touched.

    Returns:
        Tuple of (deduped rules_by_panel, count of dropped rules)
    """
    dropped_total = 0

    for panel_name, entries in rules_by_panel.items():
        for entry in entries:
            rules = entry.get('rules_to_add', [])
            if len(rules) < 2:
                continue

            # Only consider Expression (Client) rules
            expr_rules = [
                (i, r) for i, r in enumerate(rules)
                if r.get('rule_name') == 'Expression (Client)'
                and r.get('conditionalValues')
            ]
            if len(expr_rules) < 2:
                continue

            # Group by _expressionRuleType
            type_groups: Dict[str, List[Tuple[int, Dict, Set[str]]]] = {}
            for idx, rule in expr_rules:
                rtype = rule.get('_expressionRuleType', 'unknown')
                targets = _extract_expression_targets(rule['conditionalValues'][0])
                # Remove source field(s) from targets — they appear in vo() calls
                # but aren't actual targets
                for src in rule.get('source_fields', []):
                    targets.discard(_norm_var(src))
                if rtype not in type_groups:
                    type_groups[rtype] = []
                type_groups[rtype].append((idx, rule, targets))

            # Find strict subsets within each type group
            drop_indices: Set[int] = set()
            for rtype, group in type_groups.items():
                if len(group) < 2:
                    continue
                for i, (idx_a, rule_a, targets_a) in enumerate(group):
                    if idx_a in drop_indices:
                        continue
                    for j, (idx_b, rule_b, targets_b) in enumerate(group):
                        if i == j or idx_b in drop_indices:
                            continue
                        # Drop B if its targets are a strict subset of A's
                        if targets_b and targets_a and targets_b < targets_a:
                            drop_indices.add(idx_b)
                            print(f"  Dedup: dropping subset {rtype} rule "
                                  f"({len(targets_b)} targets ⊂ {len(targets_a)} targets) "
                                  f"on field in '{panel_name}'")

            if drop_indices:
                entry['rules_to_add'] = [
                    r for i, r in enumerate(rules) if i not in drop_indices
                ]
                dropped_total += len(drop_indices)

    return rules_by_panel, dropped_total


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


def _normalize_varname(v: str) -> str:
    """Normalize a variableName to canonical _varname_ format (single underscores)."""
    if not v:
        return v
    s = v.strip('_')
    return f'_{s}_' if s else v


def _normalize_rule_varnames(rule: Dict) -> Dict:
    """
    Normalize variableNames in a rule's source_fields and destination_fields
    from __varname__ (double underscore) to _varname_ (single underscore).
    """
    for key in ('source_fields', 'destination_fields'):
        fields = rule.get(key, [])
        if fields:
            rule[key] = [_normalize_varname(f) for f in fields]
    return rule


def translate_expression_agent_output(data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Translate expression_rule_agent output format into the inter-panel merge format.

    expression_rule_agent writes:
        {"Panel": [{"field_name": "...", "variableName": "_var_", "rules": [...]}]}

    Inter-panel merge expects:
        {"Panel": [{"target_field_variableName": "_var_", "rules_to_add": [...]}]}

    Detects which format the data is in by checking the first entry's keys.
    If already in inter-panel format, returns as-is.

    Also normalizes variableNames in source_fields/destination_fields to
    canonical _varname_ format (Fix G: double underscore bug).
    """
    if not data:
        return data

    # Peek at the first entry to detect format
    first_entries = next(iter(data.values()), [])
    if not first_entries:
        return data

    first = first_entries[0]
    # Already in inter-panel format
    if 'target_field_variableName' in first or 'rules_to_add' in first:
        # Still normalize variableNames in rules (Fix G)
        for panel_name, entries in data.items():
            for entry in entries:
                entry['target_field_variableName'] = _normalize_varname(
                    entry.get('target_field_variableName', ''))
                for rule in entry.get('rules_to_add', []):
                    if isinstance(rule, dict):
                        _normalize_rule_varnames(rule)
        return data

    # Translate from expression_rule_agent format
    translated: Dict[str, List[Dict]] = {}
    for panel_name, fields in data.items():
        entries = []
        for field in fields:
            var_name = _normalize_varname(field.get('variableName', ''))
            rules = field.get('rules', [])
            if not var_name or not rules:
                continue
            # Normalize variableNames in each rule (Fix G)
            for rule in rules:
                if isinstance(rule, dict):
                    _normalize_rule_varnames(rule)
            entries.append({
                'target_field_variableName': var_name,
                'rules_to_add': rules,
            })
        if entries:
            translated[panel_name] = entries
    return translated


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


# ── Fix B: Deduplicate refs before Phase 2 grouping ──────────────────────────

def _build_panel_varnames(all_panels_data: Dict[str, List[Dict]]) -> Set[str]:
    """Return the set of variableNames belonging to PANEL-type fields."""
    panel_vars: Set[str] = set()
    for panel_fields in all_panels_data.values():
        for field in panel_fields:
            if field.get('type', '').upper() == 'PANEL':
                var = field.get('variableName', '')
                if var:
                    panel_vars.add(_norm_var(var))
    return panel_vars


def deduplicate_complex_refs(
    complex_refs: List[Dict],
    all_panels_data: Dict[str, List[Dict]],
) -> List[Dict]:
    """
    Deduplicate complex refs before grouping (Fix B).

    When the BUD states visibility logic in multiple places (e.g., on the
    controlling dropdown AND on each target PANEL field), Phase 1 detects
    refs from both directions. This function:
    1. Re-keys refs where referenced_field_variableName is a PANEL-type field
       to use the controlling (non-PANEL) field instead
    2. Removes true duplicates (same field_variableName + referenced_field_variableName
       + classification + referenced_panel)

    Returns:
        Deduplicated list of refs (may be shorter if true duplicates removed).
    """
    panel_vars = _build_panel_varnames(all_panels_data)
    if not panel_vars:
        return complex_refs

    rekey_count = 0
    for ref in complex_refs:
        ref_var = _norm_var(ref.get('referenced_field_variableName', ''))
        field_var = _norm_var(ref.get('field_variableName', ''))

        # If the referenced field is a PANEL and the field is not a PANEL,
        # re-key so grouping uses the controlling (non-PANEL) field
        if ref_var in panel_vars and field_var not in panel_vars and field_var:
            ref['referenced_field_variableName'] = ref.get('field_variableName', '')
            rekey_count += 1

    if rekey_count:
        print(f"  Fix B: Re-keyed {rekey_count} refs from PANEL targets to controller field")

    # Now remove true duplicates (same field_variableName + referenced_field_variableName
    # + classification after re-keying)
    seen: Set[tuple] = set()
    deduped: List[Dict] = []
    removed = 0
    for ref in complex_refs:
        key = (
            _norm_var(ref.get('field_variableName', '')),
            _norm_var(ref.get('referenced_field_variableName', '')),
            ref.get('classification', ''),
            ref.get('referenced_panel', ''),
        )
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        deduped.append(ref)

    if removed:
        print(f"  Fix B: Removed {removed} duplicate refs after re-keying")

    return deduped


# ── Fix D: PANEL variable expansion in expressions ───────────────────────────

# Structural field types that should NOT be expanded
_STRUCTURAL_TYPES = {
    'ARRAY_END', 'GRP_HDR', 'GRP_END',
    'ROW_HDR', 'ROW_END', 'PANEL',
}


def _build_panel_children_map(
    all_panels_data: Dict[str, List[Dict]],
) -> Dict[str, List[str]]:
    """
    Build a map from PANEL variableName -> list of child field variableNames.

    A child field is any non-structural field that appears within a panel's
    field list. We detect PANEL boundaries: fields between a PANEL field
    and the next PANEL field (or end of list) are its children.

    Since each panel in all_panels_data IS a panel already, and PANEL-type
    fields within it represent sub-panels or the panel header, we map each
    PANEL-type field's variableName to all non-structural fields in that
    same panel list.
    """
    panel_children: Dict[str, List[str]] = {}

    for panel_name, fields in all_panels_data.items():
        # Find PANEL-type fields and their children
        panel_field_vars = []
        for field in fields:
            if field.get('type', '').upper() == 'PANEL':
                var = field.get('variableName', '')
                if var:
                    panel_field_vars.append(var)

        if not panel_field_vars:
            continue

        # Collect non-structural child fields for each PANEL variable
        child_vars = []
        for field in fields:
            ftype = field.get('type', '').upper()
            var = field.get('variableName', '')
            if not var or ftype in _STRUCTURAL_TYPES:
                continue
            child_vars.append(var)

        # Map each PANEL variableName to the child fields
        for pvar in panel_field_vars:
            panel_children[_norm_var(pvar)] = child_vars

    return panel_children


def expand_panel_variables_in_expressions(
    all_results: Dict[str, List[Dict]],
    all_panels_data: Dict[str, List[Dict]],
) -> int:
    """
    Post-processing step (Fix D): Expand PANEL variableNames in expression
    function arguments to their child fields.

    When agents generate expressions like mm(condition, "_panelVar_"),
    the PANEL variable has no effect. This function replaces it with
    all child fields of that panel.

    Scans all conditionalValues in Expression (Client) rules and expands
    PANEL variables found as arguments to mm, mnm, cf, mvi, minvi, dis, en,
    asdff, rffdd, rffd.

    Args:
        all_results: The output data (panel name -> field list), mutated in place
        all_panels_data: Original panel data for building child maps

    Returns:
        Number of expansions performed
    """
    panel_children = _build_panel_children_map(all_panels_data)
    if not panel_children:
        return 0

    # Functions whose variableName arguments should be expanded.
    # NOTE: mvi/minvi are EXCLUDED — the platform cascades visibility to
    # children automatically when a PANEL is made visible/invisible.
    # PANEL vars are the CORRECT target for visibility functions.
    expandable_functions = {'mm', 'mnm', 'cf', 'dis', 'en',
                            'asdff', 'rffdd', 'rffd'}

    expansion_count = 0

    for panel_fields in all_results.values():
        for field in panel_fields:
            for rule in field.get('rules', []):
                if not isinstance(rule, dict):
                    continue
                if rule.get('rule_name') != 'Expression (Client)':
                    continue

                cond_vals = rule.get('conditionalValues', [])
                if not cond_vals:
                    continue

                expr = cond_vals[0]
                new_expr = expr

                # Find all quoted variable references like "_varname_"
                # that match a PANEL variableName
                for panel_var, children in panel_children.items():
                    if not children:
                        continue

                    # The expression uses single-underscore format: "_varname_"
                    # Check if this panel var appears in the expression
                    expr_var = f'"{panel_var}"'
                    if expr_var not in new_expr:
                        continue

                    # Build replacement: expand to all child vars
                    child_args = ', '.join(f'"{c}"' for c in children)

                    # Replace in each function call context
                    # Match patterns like: func(..., "_panelVar_")
                    # or func(..., "_panelVar_", ...)
                    # We need to replace just the "_panelVar_" with all children
                    for func_name in expandable_functions:
                        # Pattern: function call containing the panel var
                        # We do a simple string replacement of the panel var
                        # within function call contexts
                        if func_name + '(' in new_expr and expr_var in new_expr:
                            old = new_expr
                            new_expr = new_expr.replace(expr_var, child_args)
                            if new_expr != old:
                                expansion_count += 1
                            break  # Only replace once per panel_var per expr

                if new_expr != expr:
                    rule['conditionalValues'] = [new_expr]

    return expansion_count


def _find_matching_paren(expr: str, open_pos: int) -> int:
    """Find the closing paren that matches the opening paren at open_pos."""
    depth = 0
    for i in range(open_pos, len(expr)):
        if expr[i] == '(':
            depth += 1
        elif expr[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _find_func_calls(expr: str, func_name: str) -> List[Tuple[int, int, str]]:
    """
    Find all calls to func_name in expr, handling nested parentheses.
    Returns list of (start, end, full_match) for each call.
    """
    results = []
    search_start = 0
    while True:
        # Find 'func(' but not 'otherfunc(' — check for word boundary
        idx = expr.find(func_name + '(', search_start)
        if idx == -1:
            break
        # Check it's not part of a longer function name (e.g., 'minvi' vs 'mvi')
        if idx > 0 and expr[idx - 1].isalpha():
            search_start = idx + 1
            continue
        paren_open = idx + len(func_name)
        paren_close = _find_matching_paren(expr, paren_open)
        if paren_close == -1:
            break
        full = expr[idx:paren_close + 1]
        results.append((idx, paren_close + 1, full))
        search_start = paren_close + 1
    return results


def collapse_children_to_panel_in_visibility(
    all_results: Dict[str, List[Dict]],
    all_panels_data: Dict[str, List[Dict]],
) -> int:
    """
    Post-processing: Collapse child field lists back to PANEL variables
    in mvi/minvi function calls.

    When agents list all children of a panel in mvi/minvi instead of using
    the PANEL variable, the platform can't cascade visibility properly.
    This function detects when ALL children of a PANEL are listed as
    arguments to mvi/minvi and replaces them with the single PANEL variable.

    The platform automatically cascades visibility to children when a PANEL
    is made visible/invisible, so using the PANEL variable is both more
    correct and more concise.

    Args:
        all_results: The output data (panel name -> field list), mutated in place
        all_panels_data: Original panel data for building child maps

    Returns:
        Number of collapses performed
    """
    panel_children = _build_panel_children_map(all_panels_data)
    if not panel_children:
        return 0

    collapse_count = 0

    for panel_fields in all_results.values():
        for field in panel_fields:
            for rule in field.get('rules', []):
                if not isinstance(rule, dict):
                    continue
                if rule.get('rule_name') != 'Expression (Client)':
                    continue

                cond_vals = rule.get('conditionalValues', [])
                if not cond_vals:
                    continue

                expr = cond_vals[0]
                if 'mvi(' not in expr and 'minvi(' not in expr:
                    continue

                new_expr = expr

                for panel_var, children in panel_children.items():
                    if not children:
                        continue

                    # Check if all children appear in the expression
                    all_present = all(f'"{c}"' in new_expr for c in children)
                    if not all_present:
                        continue

                    # Process minvi first (longer name), then mvi
                    for func in ('minvi', 'mvi'):
                        calls = _find_func_calls(new_expr, func)
                        if not calls:
                            continue

                        # Process in reverse order to preserve positions
                        for start, end, full_call in reversed(calls):
                            # Extract the inner args (between outermost parens)
                            inner = full_call[len(func) + 1:-1]

                            # Check if this call contains all children
                            call_vars = re.findall(r'"(_[a-z0-9_]+_)"', inner)
                            call_var_set = set(call_vars)
                            children_set = set(children)

                            if not children_set.issubset(call_var_set):
                                continue

                            # Remove all child var args, replace with PANEL var
                            new_inner = inner
                            for child in children:
                                child_q = f'"{child}"'
                                new_inner = new_inner.replace(f', {child_q}', '', 1)
                                if child_q in new_inner:
                                    new_inner = new_inner.replace(f'{child_q}, ', '', 1)
                                if child_q in new_inner:
                                    new_inner = new_inner.replace(child_q, '', 1)

                            # Clean up any trailing commas/spaces
                            new_inner = new_inner.rstrip(', ')
                            new_inner = f'{new_inner}, "{panel_var}"'

                            new_call = f'{func}({new_inner})'
                            new_expr = new_expr[:start] + new_call + new_expr[end:]
                            collapse_count += 1

                if new_expr != expr:
                    rule['conditionalValues'] = [new_expr]

    return collapse_count


# ── Fix E: Ensure full panel coverage in clearing expressions ─────────────

def ensure_full_panel_in_clearing(
    all_results: Dict[str, List[Dict]],
    all_panels_data: Dict[str, List[Dict]],
) -> int:
    """
    Post-processing (Fix E): When a clearing expression references any field
    from a cross-panel, ensure ALL non-structural fields from that panel are
    included in cf/asdff/rffdd/rffd calls.

    Fixes the case where LLM-generated clearing rules list individual child
    fields but miss ARRAY_HDR or other fields in the same panel.

    Args:
        all_results: Output data (panel name -> field list), mutated in place
        all_panels_data: Original panel data for building field maps

    Returns:
        Number of expressions modified
    """
    # Build maps: variableName -> panel, panel -> all non-structural vars
    var_to_panel: Dict[str, str] = {}
    panel_all_vars: Dict[str, List[str]] = {}

    for panel_name, fields in all_panels_data.items():
        non_structural = []
        for field in fields:
            ftype = (field.get('type', '') or '').upper()
            var = field.get('variableName', '')
            if var and ftype not in _STRUCTURAL_TYPES:
                var_to_panel[var] = panel_name
                non_structural.append(var)
        panel_all_vars[panel_name] = non_structural

    expansion_count = 0

    for result_panel_name, panel_fields in all_results.items():
        for field in panel_fields:
            for rule in field.get('rules', []):
                if not isinstance(rule, dict):
                    continue
                if rule.get('rule_name') != 'Expression (Client)':
                    continue
                if rule.get('_expressionRuleType') != 'clear_field':
                    continue

                cond_vals = rule.get('conditionalValues', [])
                if not cond_vals:
                    continue

                expr = cond_vals[0]

                # Extract all variable refs in the expression
                all_vars_in_expr = set(re.findall(r'"(_[a-z0-9_]+_)"', expr))

                # Determine which cross-panels are referenced (exclude own panel)
                target_panels: Set[str] = set()
                for v in all_vars_in_expr:
                    p = var_to_panel.get(v)
                    if p and p != result_panel_name:
                        target_panels.add(p)

                if not target_panels:
                    continue

                # Collect missing vars from each target panel
                missing: List[str] = []
                for pname in target_panels:
                    for pvar in panel_all_vars.get(pname, []):
                        if pvar not in all_vars_in_expr:
                            missing.append(pvar)

                if not missing:
                    continue

                # Inject missing vars into cf, asdff, rffdd, rffd calls
                new_expr = _inject_missing_vars_into_clearing(expr, missing)
                if new_expr != expr:
                    rule['conditionalValues'] = [new_expr]
                    expansion_count += 1

    return expansion_count


def _inject_missing_vars_into_clearing(expr: str, missing_vars: List[str]) -> str:
    """
    Add missing variableNames to cf, asdff, rffdd, rffd function calls
    in a clearing expression.
    """
    additional = ', '.join(f'"{v}"' for v in missing_vars)

    # Collect all replacements: (start, end, new_call)
    replacements: List[Tuple[int, int, str]] = []

    for func_name in ('cf', 'asdff', 'rffdd', 'rffd'):
        calls = _find_func_calls(expr, func_name)
        for start, end, call_str in calls:
            # Insert missing vars before the closing paren
            close_idx = call_str.rfind(')')
            new_call = call_str[:close_idx] + ', ' + additional + ')'
            replacements.append((start, end, new_call))

    if not replacements:
        return expr

    # Apply in reverse position order to keep offsets valid
    replacements.sort(key=lambda x: x[0], reverse=True)
    new_expr = expr
    for start, end, new_call in replacements:
        new_expr = new_expr[:start] + new_call + new_expr[end:]

    return new_expr
