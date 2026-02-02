"""
Utilities for the Rule Extraction Agent.
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .models import GeneratedRule


def generate_output_path(input_path: str, output_dir: str = "rules_populated") -> str:
    """
    Generate output path from input path.

    Args:
        input_path: Input file path.
        output_dir: Output directory name.

    Returns:
        Generated output path.
    """
    input_path = Path(input_path)
    parent = input_path.parent.parent  # Go up from complete_format

    output_dir_path = parent / output_dir
    output_dir_path.mkdir(parents=True, exist_ok=True)

    return str(output_dir_path / input_path.name)


def consolidate_rules(all_rules: List[GeneratedRule]) -> List[GeneratedRule]:
    """
    Consolidate and deduplicate rules.

    CRITICAL: Reference uses single rule with multiple destinationIds.
    This merges rules with same (actionType, sourceIds, condition, conditionalValues).

    Args:
        all_rules: List of all generated rules.

    Returns:
        Consolidated list of rules.
    """
    GROUPABLE_ACTIONS = [
        'MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE',
        'MAKE_MANDATORY', 'MAKE_NON_MANDATORY', 'MAKE_ENABLED'
    ]

    rule_groups: Dict[tuple, List[GeneratedRule]] = defaultdict(list)
    non_groupable: List[GeneratedRule] = []

    for rule in all_rules:
        if rule.action_type in GROUPABLE_ACTIONS:
            key = (
                rule.action_type,
                tuple(sorted(rule.source_ids)),
                rule.condition,
                tuple(sorted(rule.conditional_values))
            )
            rule_groups[key].append(rule)
        else:
            non_groupable.append(rule)

    # Merge grouped rules
    consolidated = []
    for key, rules in rule_groups.items():
        if len(rules) == 1:
            consolidated.append(rules[0])
        else:
            # Merge: combine all destinationIds
            merged = rules[0]
            all_dest_ids = set()
            for r in rules:
                all_dest_ids.update(r.destination_ids)
            merged.destination_ids = sorted(list(all_dest_ids))
            consolidated.append(merged)

    # Deduplicate non-groupable rules by (actionType, sourceType, sourceIds)
    # This removes duplicate VERIFY/OCR rules for the same field
    seen_non_groupable = {}
    for rule in non_groupable:
        key = (
            rule.action_type,
            rule.source_type or '',
            tuple(sorted(rule.source_ids))
        )
        if key not in seen_non_groupable:
            seen_non_groupable[key] = rule
        else:
            # Keep the one with more destination IDs
            existing = seen_non_groupable[key]
            if len(rule.destination_ids) > len(existing.destination_ids):
                seen_non_groupable[key] = rule

    consolidated.extend(seen_non_groupable.values())

    # Remove exact duplicates
    seen = set()
    deduplicated = []
    for rule in consolidated:
        key = (
            rule.action_type,
            rule.source_type or '',
            tuple(sorted(rule.source_ids)),
            tuple(sorted(rule.destination_ids)),
            rule.condition,
            tuple(sorted(rule.conditional_values))
        )
        if key not in seen:
            seen.add(key)
            deduplicated.append(rule)

    return deduplicated


def link_ocr_to_verify_rules(all_rules: List[GeneratedRule]) -> None:
    """
    Link OCR rules to corresponding VERIFY rules via postTriggerRuleIds.

    CRITICAL: OCR rules must trigger VERIFY rules for the extracted data.

    Args:
        all_rules: List of all generated rules (modified in place).
    """
    # Build index of VERIFY rules by source field
    verify_by_source: Dict[int, GeneratedRule] = {}
    for rule in all_rules:
        if rule.action_type == 'VERIFY':
            for source_id in rule.source_ids:
                verify_by_source[source_id] = rule

    # Link OCR rules to VERIFY rules
    for rule in all_rules:
        if rule.action_type == 'OCR':
            # OCR destinationIds[0] is the field being populated
            if rule.destination_ids:
                dest_field_id = rule.destination_ids[0]
                if dest_field_id in verify_by_source:
                    verify_rule = verify_by_source[dest_field_id]
                    if verify_rule.id not in rule.post_trigger_rule_ids:
                        rule.post_trigger_rule_ids.append(verify_rule.id)


def populate_schema_with_rules(
    schema: Dict,
    rules_by_field: Dict[int, List[GeneratedRule]]
) -> Dict:
    """
    Populate schema with generated rules.

    Args:
        schema: Original schema JSON.
        rules_by_field: Dict mapping field ID to list of rules.

    Returns:
        Updated schema with formFillRules populated.
    """
    schema = json.loads(json.dumps(schema))  # Deep copy

    doc_types = schema.get('template', {}).get('documentTypes', [])
    for doc_type in doc_types:
        metadatas = doc_type.get('formFillMetadatas', [])
        for meta in metadatas:
            field_id = meta.get('id')
            if field_id in rules_by_field:
                rules = rules_by_field[field_id]
                meta['formFillRules'] = [r.to_dict() for r in rules]

    return schema


def extract_conditional_values(logic: str) -> List[str]:
    """
    Extract conditional values from logic text.

    Args:
        logic: Logic text.

    Returns:
        List of conditional values.
    """
    values = []

    # Pattern: value is X
    pattern1 = r"values?\s+is\s+([^\s,\.]+)"
    for match in re.finditer(pattern1, logic, re.IGNORECASE):
        values.append(match.group(1))

    # Pattern: selected as X
    pattern2 = r"selected\s+as\s+([^\s,\.]+)"
    for match in re.finditer(pattern2, logic, re.IGNORECASE):
        values.append(match.group(1))

    # Pattern: "Yes" or "No"
    pattern3 = r"['\"]?(Yes|No|TRUE|FALSE)['\"]?"
    for match in re.finditer(pattern3, logic, re.IGNORECASE):
        values.append(match.group(1))

    return list(set(values))


def normalize_field_name(name: str) -> str:
    """
    Normalize field name for matching.

    Args:
        name: Field name.

    Returns:
        Normalized name.
    """
    name = name.lower()
    name = re.sub(r'^(upload|select|enter|the|please)\s+', '', name)
    name = re.sub(r'\s+(field|number|code|id)$', '', name)
    name = ' '.join(name.split())
    return name


def create_report(
    result,
    output_path: str,
    schema_path: str,
    bud_path: Optional[str] = None
) -> Dict:
    """
    Create extraction report.

    Args:
        result: ExtractionResult object.
        output_path: Output file path.
        schema_path: Input schema path.
        bud_path: BUD document path.

    Returns:
        Report dictionary.
    """
    report = {
        "extraction_timestamp": datetime.now().isoformat(),
        "input_schema": schema_path,
        "bud_document": bud_path,
        "output_file": output_path,
        "summary": result.to_dict(),
        "rules_by_type": result.rules_by_type,
        "unmatched_fields": result.unmatched_fields[:20],  # First 20
        "errors": result.errors[:20],
        "warnings": result.warnings[:20],
    }

    return report


def save_json(data: Any, path: str) -> None:
    """Save data as JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(path: str) -> Dict:
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
