#!/usr/bin/env python3
"""
Context Optimization Utilities for Rule Extraction Pipeline

Strips irrelevant rules from field data before passing to mini agents,
and restores them after the agent completes. This reduces context window
usage for later-stage agents where accumulated rules from earlier stages
bloat the input.

Usage pattern in dispatchers:

    # Before agent call:
    stripped_fields, stored_rules = strip_all_rules(panel_fields)
    # Write stripped_fields to temp file, call agent, read result

    # After agent call:
    result = restore_all_rules(result, stored_rules)
"""

import copy
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


# ── variableName normalization ─────────────────────────────────────────────
# Canonical form: "_name_" (single underscore each side, lowercase alphanumeric
# inside). LLMs occasionally drift to "__name__" (double) in source_fields /
# destination_fields / conditionalValues. This utility collapses the wrappers
# back to the canonical single-underscore form without touching the interior.

_DOUBLE_UNDERSCORE_TOKEN = re.compile(r'_{2,}([a-z0-9]+)_{2,}')


def _normalize_var_string(s: str) -> str:
    """Collapse '__name__' → '_name_' in any string. Leaves '_name_' and non-
    variable strings untouched. Handles bare tokens and embedded references
    inside expression strings like vo("__name__") → vo("_name_")."""
    if not isinstance(s, str):
        return s
    return _DOUBLE_UNDERSCORE_TOKEN.sub(lambda m: f"_{m.group(1)}_", s)


def _normalize_tree(obj: Any) -> Any:
    """Walk an arbitrary JSON-like object and normalize every string leaf."""
    if isinstance(obj, str):
        return _normalize_var_string(obj)
    if isinstance(obj, list):
        return [_normalize_tree(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize_tree(v) for k, v in obj.items()}
    return obj


def normalize_variable_names(fields: List[Dict]) -> List[Dict]:
    """Normalize variableName occurrences across every string in a panel's
    fields list. Defense-in-depth against LLM drift to '__name__' form.
    Returns a new list; does not mutate input."""
    return _normalize_tree(fields)


# ── Rule name classification ──────────────────────────────────────────────

VISIBILITY_RULE_NAMES: Set[str] = {
    "Make Visible (Client)", "Make Invisible (Client)",
    "Make Mandatory (Client)", "Make Non Mandatory (Client)",
    "Enable Field (Client)", "Disable Field (Client)",
}

SESSION_RULE_NAMES: Set[str] = {
    "Make Visible - Session Based (Client)",
    "Make Invisible - Session Based (Client)",
    "Make Mandatory - Session Based (Client)",
    "Make NonMandatory - Session Based (Client)",
    "Enable Field - Session Based (Client)",
    "Make Disable - Session Based (Client)",
}

ALL_VISIBILITY_RULE_NAMES: Set[str] = VISIBILITY_RULE_NAMES | SESSION_RULE_NAMES

# Keys to keep in slimmed rules (for relationship analysis in Stage 7)
SLIM_RULE_KEYS = frozenset({
    'rule_name', 'source_fields', 'destination_fields', '_expressionRuleType',
})


# ── Stripping functions ───────────────────────────────────────────────────

def strip_all_rules(
    panel_fields: List[Dict],
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """
    Strip ALL rules from fields. Agent sees empty rules arrays.

    Use for stages where the agent doesn't need to see ANY existing rules
    (e.g., Stage 5 conditional logic, Stage 6 derivation logic).

    Returns:
        (stripped_fields, stored_rules_by_variableName)
    """
    stripped = copy.deepcopy(panel_fields)
    stored: Dict[str, List[Dict]] = {}

    for field in stripped:
        var_name = field.get('variableName', '')
        rules = field.get('rules', [])
        if rules and var_name:
            stored[var_name] = rules
            field['rules'] = []

    return stripped, stored


def strip_rules_except(
    panel_fields: List[Dict],
    keep_fn: Callable[[Dict], bool],
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """
    Strip rules that DON'T match keep_fn. Agent sees only matching rules.

    Use for stages where the agent needs to see specific rule types
    (e.g., Stage 3-4 EDV agent needs EDV rules, Stage 9 needs session rules).

    Returns:
        (stripped_fields, stored_rules_by_variableName)
    """
    stripped = copy.deepcopy(panel_fields)
    stored: Dict[str, List[Dict]] = {}

    for field in stripped:
        var_name = field.get('variableName', '')
        rules = field.get('rules', [])
        if not rules or not var_name:
            continue

        kept = [r for r in rules if keep_fn(r)]
        removed = [r for r in rules if not keep_fn(r)]
        if removed:
            stored[var_name] = removed
        field['rules'] = kept

    return stripped, stored


def slim_rules_for_relationship_analysis(
    panel_fields: List[Dict],
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """
    Replace rules with slim versions containing only relationship keys
    (rule_name, source_fields, destination_fields, _expressionRuleType).
    Store full rules for later restoration.

    Used by Clear Child Fields agent (Stage 7) which needs to scan
    existing rules to identify parent-child relationships but doesn't
    need params, conditionalValues, condition, etc.

    Returns:
        (slimmed_fields, stored_full_rules_by_variableName)
    """
    slimmed = copy.deepcopy(panel_fields)
    stored: Dict[str, List[Dict]] = {}

    for field in slimmed:
        var_name = field.get('variableName', '')
        rules = field.get('rules', [])
        if not rules or not var_name:
            continue

        stored[var_name] = rules
        field['rules'] = [
            {k: r[k] for k in SLIM_RULE_KEYS if k in r}
            for r in rules
        ]

    return slimmed, stored


def strip_all_rules_multi_panel(
    panels_data: Dict[str, List[Dict]],
) -> Dict[str, List[Dict]]:
    """
    Strip ALL rules from all panels in a multi-panel dict.
    Used for inter-panel Pass 2 involved panels (Stage 8).

    Returns:
        New dict with stripped panel fields (originals unchanged).
    """
    stripped = {}
    for panel_name, fields in panels_data.items():
        panel_stripped, _ = strip_all_rules(fields)
        stripped[panel_name] = panel_stripped
    return stripped


# ── Restoration functions ─────────────────────────────────────────────────

def restore_all_rules(
    agent_output: List[Dict],
    stored_rules: Dict[str, List[Dict]],
) -> List[Dict]:
    """
    Prepend stored rules before agent-added rules.

    Use for stages where ALL rules were stripped and the agent only added
    its own new rules (e.g., derivation logic, session-based).
    Also used for stages where non-matching rules were stripped (EDV stages).
    """
    for field in agent_output:
        var_name = field.get('variableName', '')
        if var_name in stored_rules:
            field['rules'] = stored_rules[var_name] + field.get('rules', [])
    return agent_output


def restore_rules_conditional_logic(
    agent_output: List[Dict],
    stored_rules: Dict[str, List[Dict]],
) -> List[Dict]:
    """
    Stage 5: Restore stored rules EXCLUDING old visibility rules.

    The Conditional Logic agent discards old visibility rules and creates
    new ones from scratch. We stripped ALL rules before the agent call, so
    stored_rules may contain old visibility rules that should NOT be
    restored (they're replaced by the agent's fresh output).
    """
    for field in agent_output:
        var_name = field.get('variableName', '')
        agent_rules = field.get('rules', [])

        if var_name in stored_rules:
            non_visibility = [
                r for r in stored_rules[var_name]
                if r.get('rule_name') not in ALL_VISIBILITY_RULE_NAMES
            ]
            field['rules'] = non_visibility + agent_rules

    return agent_output


def merge_expression_rules(
    original_fields: List[Dict],
    agent_output: List[Dict],
) -> List[Dict]:
    """
    Merge expression rules from agent output INTO the original fields.

    Starts from the original fields (which have all existing rules from
    previous stages intact). For each field, removes old expression/visibility/
    session rules and appends the new ones from the agent output.

    This approach guarantees that:
    - All existing non-expression rules (EDV, Copy To, Validate, etc.) are preserved
    - Fields the agent didn't return keep their original rules untouched
    - Only expression/visibility/session rules are replaced by the agent's output
    """
    EXPRESSION_RULES = {"Expression (Client)"}
    REPLACED = ALL_VISIBILITY_RULE_NAMES | SESSION_RULE_NAMES | EXPRESSION_RULES

    # Build lookup: variableName → new rules from agent
    agent_rules_by_var: Dict[str, List[Dict]] = {}
    for field in agent_output:
        var_name = field.get('variableName', '')
        if var_name:
            new_rules = [r for r in field.get('rules', [])
                         if isinstance(r, dict) and r.get('rule_name') in REPLACED]
            if new_rules:
                agent_rules_by_var[var_name] = new_rules

    # Merge into original fields
    result = copy.deepcopy(original_fields)
    for field in result:
        var_name = field.get('variableName', '')
        if not var_name:
            continue

        if var_name in agent_rules_by_var:
            # Remove old expression/visibility/session rules, keep everything else
            existing = field.get('rules', [])
            kept = [r for r in existing
                    if not (isinstance(r, dict) and r.get('rule_name') in REPLACED)]
            field['rules'] = kept + agent_rules_by_var[var_name]

    return result


def restore_rules_after_slim(
    agent_output: List[Dict],
    stored_rules: Dict[str, List[Dict]],
    new_rule_marker_key: str = '_expressionRuleType',
    new_rule_marker_value: str = 'clear_field',
) -> List[Dict]:
    """
    Stage 7: Restore full originals, keep only newly-added rules from agent.

    After slim_rules_for_relationship_analysis, the agent output contains
    slim pass-throughs (to be discarded) and new rules (identified by
    marker key/value) to be kept. Full originals are restored from stored.
    """
    for field in agent_output:
        var_name = field.get('variableName', '')
        agent_rules = field.get('rules', [])

        # Extract only new rules added by the agent
        new_rules = [
            r for r in agent_rules
            if r.get(new_rule_marker_key) == new_rule_marker_value
        ]

        # Restore: full originals + new agent rules
        field['rules'] = stored_rules.get(var_name, []) + new_rules

    return agent_output


# ── Helper predicates for strip_rules_except ──────────────────────────────

def is_edv_related_rule(rule: Dict) -> bool:
    """Check if a rule is EDV-related (keep for stages 3-4)."""
    name = (rule.get('rule_name', '') or '').upper()
    return any(kw in name for kw in [
        'EDV', 'EXT_DROP_DOWN', 'EXT_VALUE', 'EXTERNAL',
    ])


def is_session_based_rule(rule: Dict) -> bool:
    """Check if a rule is session-based (keep for stage 9)."""
    return rule.get('rule_name', '') in SESSION_RULE_NAMES


# ── Reporting ─────────────────────────────────────────────────────────────

def log_strip_savings(
    original_fields: List[Dict],
    stripped_fields: List[Dict],
    panel_name: str,
) -> None:
    """Print context savings from rule stripping."""
    orig_size = len(json.dumps(original_fields, separators=(',', ':')))
    strip_size = len(json.dumps(stripped_fields, separators=(',', ':')))
    saved = orig_size - strip_size
    if saved > 0:
        pct = saved * 100 // orig_size
        print(f"  Context opt [{panel_name}]: "
              f"{orig_size:,} -> {strip_size:,} chars "
              f"(saved {saved:,}, {pct}%)")


_CONTEXT_WINDOW = 200_000  # tokens


def _path_chars(p: Union[str, Path, None]) -> int:
    """Return file size in chars, 0 if missing."""
    if p is None:
        return 0
    try:
        return Path(p).stat().st_size
    except Exception:
        return 0


def print_context_report(
    label: str,
    agent_files: List[Union[str, Path]],
    prompt_chars: int,
    input_json_chars: int,
    output_file: Union[str, Path],
    extra_read_files: Optional[List[Union[str, Path]]] = None,
) -> None:
    """
    Print a full context-usage breakdown for one agent call.

    Args:
        label:            Panel name or call label shown in the header.
        agent_files:      Paths to the .md agent prompt file(s) (always in context).
        prompt_chars:     len() of the dispatcher prompt string.
        input_json_chars: Size of the primary input JSON file sent to the agent.
        output_file:      Path to the file the agent wrote its result to.
        extra_read_files: Any additional files the agent reads during its run
                          (e.g. reference tables, Rule-Schemas.json).
    """
    output_file = Path(output_file)
    extra_read_files = extra_read_files or []

    agent_chars  = sum(_path_chars(f) for f in agent_files)
    extra_chars  = sum(_path_chars(f) for f in extra_read_files)
    output_chars = _path_chars(output_file)

    agent_tokens  = agent_chars  // 4
    extra_tokens  = extra_chars  // 4
    prompt_tokens = prompt_chars // 4
    input_tokens  = input_json_chars // 4
    output_tokens = output_chars // 4
    total_input   = agent_tokens + extra_tokens + prompt_tokens + input_tokens
    total_tokens  = total_input + output_tokens
    pct           = round(total_input * 100 / _CONTEXT_WINDOW, 1)

    # Count rules in the output file
    total_rules = 0
    try:
        with open(output_file) as f:
            data = json.load(f)
        if isinstance(data, list):
            total_rules = sum(len(field.get('rules', [])) for field in data)
        elif isinstance(data, dict):
            total_rules = sum(
                len(field.get('rules', []))
                for fields in data.values()
                for field in fields
            )
    except Exception:
        pass

    W = 56
    print(f"\n{'─'*W}")
    print(f"  CONTEXT REPORT  [{label}]")
    print(f"{'─'*W}")
    for f in agent_files:
        n = Path(f).name
        c = _path_chars(f)
        print(f"  Agent  {n:<32s} ~{c:>7,} chars (~{c//4:,} tok)")
    for f in extra_read_files:
        n = Path(f).name
        c = _path_chars(f)
        print(f"  Extra  {n:<32s} ~{c:>7,} chars (~{c//4:,} tok)")
    print(f"  Prompt {'':32s} ~{prompt_chars:>7,} chars (~{prompt_tokens:,} tok)")
    print(f"  Input  {'':32s} ~{input_json_chars:>7,} chars (~{input_tokens:,} tok)")
    print(f"  {'─'*(W-2)}")
    print(f"  Total input   ~{total_input:>7,} tok   ({pct}% of {_CONTEXT_WINDOW:,})")
    print(f"  Output (est)  ~{output_tokens:>7,} tok")
    print(f"  Total  (est)  ~{total_tokens:>7,} tok")
    print(f"  Rules in output: {total_rules}")
    print(f"{'─'*W}\n")
