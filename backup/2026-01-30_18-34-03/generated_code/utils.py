"""
Utility functions for the rule extraction agent.
"""

import re
import json
from typing import Dict, List, Optional, Any
from pathlib import Path


def generate_variable_name(field_name: str) -> str:
    """
    Generate a variable name from a field name.

    Args:
        field_name: Human-readable field name

    Returns:
        Variable name like _fieldName123_
    """
    # Remove special characters, convert to camelCase
    words = re.sub(r'[^\w\s]', '', field_name).split()
    if not words:
        return "_unknown_"

    # First word lowercase, rest title case
    result = words[0].lower()
    for word in words[1:]:
        result += word.title()

    # Add underscores and truncate
    result = f"_{result[:20]}_"
    return result


def normalize_field_name(name: str) -> str:
    """Normalize a field name for comparison."""
    return re.sub(r'[^\w\s]', '', name.lower()).strip()


def load_json_file(path: str) -> Dict:
    """Load a JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


def save_json_file(path: str, data: Any, indent: int = 2):
    """Save data to a JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=indent)


def extract_field_name_from_logic(logic_text: str) -> Optional[str]:
    """
    Extract a field name referenced in logic text.

    Args:
        logic_text: Logic text that may contain field references

    Returns:
        Field name or None
    """
    if not logic_text:
        return None

    # Pattern: "field 'X'" or "field \"X\""
    patterns = [
        r"field\s+['\"]([^'\"]+)['\"]",
        r"the\s+field\s+['\"]([^'\"]+)['\"]",
        r"from\s+['\"]([^'\"]+)['\"]",
    ]

    for pattern in patterns:
        match = re.search(pattern, logic_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_conditional_value_from_logic(logic_text: str) -> Optional[str]:
    """
    Extract a conditional value from logic text.

    Args:
        logic_text: Logic text that may contain conditional values

    Returns:
        Conditional value or None
    """
    if not logic_text:
        return None

    patterns = [
        r"(?:value\s+is|is)\s+['\"]?([^'\"]+?)['\"]?\s+then",
        r"selected\s+as\s+['\"]?([^'\"]+?)['\"]?",
        r"=\s*['\"]?([^'\"]+?)['\"]?\s+then",
    ]

    for pattern in patterns:
        match = re.search(pattern, logic_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value.lower() not in ["then", "otherwise", "and", "or"]:
                return value

    return None


def detect_ocr_document_type(logic_text: str) -> Optional[str]:
    """
    Detect OCR document type from logic text.

    Args:
        logic_text: Logic text mentioning OCR

    Returns:
        Document type (PAN, GSTIN, etc.) or None
    """
    if not logic_text:
        return None

    logic_lower = logic_text.lower()

    patterns = [
        (r"pan\s+(?:from\s+)?ocr|get\s+pan\s+from\s+ocr", "PAN"),
        (r"gstin?\s+(?:from\s+)?ocr|get\s+gstin?\s+from\s+ocr", "GSTIN"),
        (r"aadhaar\s+(?:front\s+)?ocr|aadhar\s+(?:front\s+)?ocr", "AADHAAR_FRONT"),
        (r"aadhaar\s+back\s+ocr|aadhar\s+back\s+ocr", "AADHAAR_BACK"),
        (r"cheque\s+ocr|cancelled\s+cheque\s+ocr", "CHEQUE"),
        (r"msme\s+ocr|udyam\s+ocr", "MSME"),
        (r"cin\s+ocr", "CIN"),
    ]

    for pattern, doc_type in patterns:
        if re.search(pattern, logic_lower):
            return doc_type

    return None


def detect_verify_document_type(logic_text: str) -> Optional[str]:
    """
    Detect verification document type from logic text.

    Args:
        logic_text: Logic text mentioning validation/verification

    Returns:
        Document type (PAN, GSTIN, etc.) or None
    """
    if not logic_text:
        return None

    logic_lower = logic_text.lower()

    patterns = [
        (r"pan\s+validation|validate\s+pan|pan\s+verify", "PAN"),
        (r"gstin?\s+validation|validate\s+gstin?|gstin?\s+verify", "GSTIN"),
        (r"bank\s+(?:account\s+)?validation|validate\s+bank", "BANK"),
        (r"msme\s+validation|validate\s+msme|udyam\s+validation", "MSME"),
        (r"cin\s+validation|validate\s+cin", "CIN"),
        (r"tan\s+validation|validate\s+tan", "TAN"),
    ]

    for pattern, doc_type in patterns:
        if re.search(pattern, logic_lower):
            return doc_type

    return None


def is_verify_destination_field(logic_text: str) -> bool:
    """
    Check if a field is a destination of verification (not a source).

    Fields with "Data will come from X validation" are destinations.

    Args:
        logic_text: Logic text

    Returns:
        True if this is a verification destination field
    """
    if not logic_text:
        return False

    patterns = [
        r"data\s+will\s+come\s+from\s+\w+\s+(?:validation|verification)",
        r"auto-derived\s+(?:from|via)\s+\w+\s+(?:validation|verification)",
        r"populated\s+(?:from|by)\s+\w+\s+(?:validation|verification)",
    ]

    for pattern in patterns:
        if re.search(pattern, logic_text, re.IGNORECASE):
            return True

    return False


def is_disabled_field(logic_text: str) -> bool:
    """
    Check if a field should be disabled/non-editable.

    Args:
        logic_text: Logic text

    Returns:
        True if field should be disabled
    """
    if not logic_text:
        return False

    patterns = [
        r"non-editable",
        r"non\s+editable",
        r"read-only",
        r"readonly",
        r"not\s+editable",
        r"disabled",
    ]

    for pattern in patterns:
        if re.search(pattern, logic_text, re.IGNORECASE):
            return True

    return False


def merge_rules_by_source(rules_list: List[Dict]) -> List[Dict]:
    """
    Merge rules with the same source and action type.

    Args:
        rules_list: List of rule dictionaries

    Returns:
        Merged list of rules
    """
    from collections import defaultdict

    # Group by (actionType, source_ids, conditionalValues)
    groups = defaultdict(list)

    for rule in rules_list:
        key = (
            rule.get('actionType'),
            tuple(rule.get('sourceIds', [])),
            tuple(rule.get('conditionalValues', [])),
            rule.get('condition'),
        )
        groups[key].append(rule)

    merged = []
    for key, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            # Merge destination IDs
            base_rule = group[0].copy()
            all_dest_ids = set()
            for rule in group:
                all_dest_ids.update(rule.get('destinationIds', []))
            base_rule['destinationIds'] = list(all_dest_ids)
            merged.append(base_rule)

    return merged
