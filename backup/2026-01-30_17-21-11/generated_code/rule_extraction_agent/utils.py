"""
Utility functions for rule extraction agent.
"""

import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


def load_json(path: str) -> Dict:
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Any, path: str, indent: int = 2) -> None:
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def normalize_field_name(name: str) -> str:
    """Normalize field name for comparison."""
    if not name:
        return ""
    # Lowercase
    name = name.lower()
    # Remove common prefixes
    prefixes = ["please select ", "select ", "please choose ", "choose ", "enter "]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    # Remove special characters
    name = re.sub(r'[^\w\s]', '', name)
    # Collapse whitespace
    name = ' '.join(name.split())
    return name.strip()


def extract_field_logic(field_meta: Dict) -> Optional[str]:
    """
    Extract logic text from field metadata.

    Looks in common locations for logic/rules text.
    """
    # Check formFillMetadata fields for logic
    logic_fields = ['logic', 'rules', 'Logic', 'Rules', 'rule', 'Rule']

    for field in logic_fields:
        if field in field_meta:
            return field_meta[field]

    # Check helpText or placeholder
    if field_meta.get('helpText'):
        text = field_meta['helpText']
        # Check if it looks like logic
        if any(kw in text.lower() for kw in ['visible', 'mandatory', 'validation', 'ocr']):
            return text

    return None


def merge_rules(
    existing_rules: List[Dict],
    new_rules: List[Dict],
) -> List[Dict]:
    """
    Merge new rules with existing rules, avoiding duplicates.

    Args:
        existing_rules: Existing formFillRules
        new_rules: New rules to add

    Returns:
        Merged list of rules
    """
    # Index existing by action type and destination
    existing_index = set()
    for rule in existing_rules:
        key = (rule.get('actionType'), tuple(sorted(rule.get('destinationIds', []))))
        existing_index.add(key)

    merged = list(existing_rules)
    for rule in new_rules:
        key = (rule.get('actionType'), tuple(sorted(rule.get('destinationIds', []))))
        if key not in existing_index:
            merged.append(rule)
            existing_index.add(key)

    return merged


def format_timestamp() -> str:
    """Get formatted timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_variable_name(var_name: str) -> Tuple[str, str]:
    """
    Parse variable name to extract readable name.

    Variable names are like "_fieldNa42_" -> "fieldNa"

    Args:
        var_name: Variable name string

    Returns:
        Tuple of (clean_name, suffix)
    """
    if not var_name:
        return "", ""

    # Remove leading/trailing underscores
    name = var_name.strip('_')

    # Try to find number suffix
    match = re.match(r'^(.+?)(\d+)$', name)
    if match:
        return match.group(1), match.group(2)

    return name, ""


def get_field_type_category(field_type: str) -> str:
    """
    Get high-level category for a field type.

    Args:
        field_type: Field type string

    Returns:
        Category: 'input', 'selection', 'file', 'display', 'container'
    """
    type_upper = field_type.upper()

    input_types = {'TEXT', 'NUMBER', 'EMAIL', 'MOBILE', 'DATE'}
    selection_types = {'DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROP_DOWN',
                      'EXTERNAL_DROP_DOWN_VALUE', 'CHECKBOX', 'STATIC_CHECKBOX'}
    file_types = {'FILE'}
    display_types = {'LABEL'}
    container_types = {'PANEL'}

    if type_upper in input_types:
        return 'input'
    elif type_upper in selection_types:
        return 'selection'
    elif type_upper in file_types:
        return 'file'
    elif type_upper in display_types:
        return 'display'
    elif type_upper in container_types:
        return 'container'
    else:
        return 'unknown'


def extract_panel_structure(form_fill_metadatas: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Extract panel structure from formFillMetadatas.

    Args:
        form_fill_metadatas: List of field metadata dicts

    Returns:
        Dict mapping panel names to list of fields in that panel
    """
    panels = {}
    current_panel = "Unassigned"

    for meta in form_fill_metadatas:
        form_tag = meta.get('formTag', {})
        field_type = form_tag.get('type', '')

        if field_type == 'PANEL':
            current_panel = form_tag.get('name', 'Unknown Panel')
            if current_panel not in panels:
                panels[current_panel] = []
        else:
            if current_panel not in panels:
                panels[current_panel] = []
            panels[current_panel].append(meta)

    return panels


def count_rules_by_type(form_fill_metadatas: List[Dict]) -> Dict[str, int]:
    """
    Count rules by action type across all fields.

    Args:
        form_fill_metadatas: List of field metadata dicts

    Returns:
        Dict mapping action type to count
    """
    counts = {}

    for meta in form_fill_metadatas:
        for rule in meta.get('formFillRules', []):
            action_type = rule.get('actionType', 'UNKNOWN')
            counts[action_type] = counts.get(action_type, 0) + 1

    return counts


def validate_field_ids(
    rules: List[Dict],
    valid_ids: set,
) -> List[str]:
    """
    Validate that all field IDs in rules exist.

    Args:
        rules: List of rule dicts
        valid_ids: Set of valid field IDs

    Returns:
        List of validation error messages
    """
    errors = []

    for i, rule in enumerate(rules):
        # Check sourceIds
        for sid in rule.get('sourceIds', []):
            if sid not in valid_ids and sid != -1:
                errors.append(f"Rule {i}: Invalid sourceId {sid}")

        # Check destinationIds
        for did in rule.get('destinationIds', []):
            if did not in valid_ids and did != -1:
                errors.append(f"Rule {i}: Invalid destinationId {did}")

        # Check postTriggerRuleIds (these are rule IDs, not field IDs)
        # Skip validation for now

    return errors


class RuleIdGenerator:
    """Generator for unique rule IDs."""

    def __init__(self, start_id: int = 200000):
        """Initialize with starting ID."""
        self.current_id = start_id

    def next(self) -> int:
        """Get next unique ID."""
        self.current_id += 1
        return self.current_id

    def reset(self, start_id: int = 200000) -> None:
        """Reset to a new starting ID."""
        self.current_id = start_id
