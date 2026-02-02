"""
Logic Parser - Parses natural language logic statements into structured data.
"""

import re
from typing import List, Optional, Tuple, Dict, Any
from .models import ParsedLogic, Condition, ReferenceType


# Patterns that indicate logic should be skipped (expression/execute rules)
SKIP_PATTERNS = [
    r"mvi\s*\(",
    r"mm\s*\(",
    r"expr-eval",
    r"\bEXECUTE\b",
    r"execute\s+rule",
    r"execute\s+script",
    r"expression\s+rule",
]

# Visibility keywords
VISIBILITY_KEYWORDS = [
    'visible', 'invisible', 'hide', 'hidden', 'show', 'display', 'appear', 'disappear'
]

# Mandatory keywords
MANDATORY_KEYWORDS = [
    'mandatory', 'required', 'optional', 'non-mandatory', 'non mandatory'
]

# Disabled/Editable keywords
DISABLED_KEYWORDS = [
    'non-editable', 'noneditable', 'not editable', 'read-only', 'readonly',
    'disable', 'disabled', 'editable'
]

# Validation keywords
VALIDATION_KEYWORDS = [
    'validation', 'validate', 'verify', 'verification', 'check', 'perform.*validation'
]

# OCR keywords
OCR_KEYWORDS = [
    'ocr', 'ocr rule', 'from ocr', 'get.*from ocr', 'extract', 'scan'
]

# External dropdown keywords
EXT_DROPDOWN_KEYWORDS = [
    'external dropdown', 'dropdown values from', 'reference table',
    'parent dropdown', 'cascading dropdown', 'dependent on', 'filter by parent',
    r'\.xlsx?\b', 'master data', 'master table', 'lookup table', 'lookup from'
]

# Document types for validation/OCR
DOCUMENT_TYPES = {
    'pan': {'verify': 'PAN_NUMBER', 'ocr': 'PAN_IMAGE'},
    'gstin': {'verify': 'GSTIN', 'ocr': 'GSTIN_IMAGE'},
    'gst': {'verify': 'GSTIN', 'ocr': 'GSTIN_IMAGE'},
    'aadhaar': {'verify': None, 'ocr': 'AADHAR_IMAGE'},
    'aadhar': {'verify': None, 'ocr': 'AADHAR_IMAGE'},
    'aadhaar front': {'verify': None, 'ocr': 'AADHAR_IMAGE'},
    'aadhaar back': {'verify': None, 'ocr': 'AADHAR_BACK_IMAGE'},
    'bank': {'verify': 'BANK_ACCOUNT_NUMBER', 'ocr': 'CHEQUEE'},
    'cheque': {'verify': 'BANK_ACCOUNT_NUMBER', 'ocr': 'CHEQUEE'},
    'cancelled cheque': {'verify': 'BANK_ACCOUNT_NUMBER', 'ocr': 'CHEQUEE'},
    'ifsc': {'verify': 'BANK_ACCOUNT_NUMBER', 'ocr': None},
    'msme': {'verify': 'MSME_UDYAM_REG_NUMBER', 'ocr': 'MSME'},
    'udyam': {'verify': 'MSME_UDYAM_REG_NUMBER', 'ocr': 'MSME'},
    'cin': {'verify': 'CIN_ID', 'ocr': 'CIN'},
    'tan': {'verify': 'TAN_NUMBER', 'ocr': None},
    'fssai': {'verify': 'FSSAI', 'ocr': None},
}


class LogicParser:
    """Parses natural language logic statements into structured data."""

    def __init__(self):
        self.visibility_pattern = self._compile_patterns(VISIBILITY_KEYWORDS)
        self.mandatory_pattern = self._compile_patterns(MANDATORY_KEYWORDS)
        self.disabled_pattern = self._compile_patterns(DISABLED_KEYWORDS)
        self.validation_pattern = self._compile_patterns(VALIDATION_KEYWORDS)
        self.ocr_pattern = self._compile_patterns(OCR_KEYWORDS)
        self.ext_dropdown_pattern = self._compile_patterns(EXT_DROPDOWN_KEYWORDS)

    def _compile_patterns(self, keywords: List[str]) -> re.Pattern:
        """Compile list of keywords into a single regex pattern."""
        pattern = '|'.join(keywords)
        return re.compile(pattern, re.IGNORECASE)

    def parse(self, logic_text: str) -> ParsedLogic:
        """Parse logic text into structured data."""
        if not logic_text or not logic_text.strip():
            return ParsedLogic(original_text="", should_skip=True)

        logic = logic_text.strip()

        # Check if should skip
        should_skip = self._should_skip(logic)

        # Extract keywords
        keywords = self._extract_keywords(logic)

        # Extract actions
        actions = self._extract_actions(logic)

        # Extract conditions
        conditions = self._extract_conditions(logic)

        # Extract field references
        field_refs = self._extract_field_references(logic)

        # Extract document types
        doc_types = self._extract_document_types(logic)

        # Determine rule types
        is_visibility = bool(self.visibility_pattern.search(logic))
        is_mandatory = bool(self.mandatory_pattern.search(logic))
        is_disabled = bool(self.disabled_pattern.search(logic))
        is_validation = self._is_validation_rule(logic)
        is_ocr = self._is_ocr_rule(logic)
        is_ext_dropdown = bool(self.ext_dropdown_pattern.search(logic))

        # Calculate confidence
        confidence = self._calculate_confidence(
            logic, keywords, conditions, is_visibility, is_mandatory,
            is_validation, is_ocr, is_disabled
        )

        return ParsedLogic(
            original_text=logic,
            keywords=keywords,
            actions=actions,
            conditions=conditions,
            field_refs=field_refs,
            document_types=doc_types,
            is_visibility_rule=is_visibility,
            is_mandatory_rule=is_mandatory,
            is_validation_rule=is_validation,
            is_ocr_rule=is_ocr,
            is_disabled_rule=is_disabled,
            is_ext_dropdown_rule=is_ext_dropdown,
            should_skip=should_skip,
            confidence=confidence
        )

    def _should_skip(self, logic: str) -> bool:
        """Check if logic should be skipped (expression/execute rules)."""
        for pattern in SKIP_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                return True
        return False

    def _extract_keywords(self, logic: str) -> List[str]:
        """Extract action keywords from logic text."""
        keywords = []
        logic_lower = logic.lower()

        # Check each keyword category
        for keyword in VISIBILITY_KEYWORDS:
            if keyword in logic_lower:
                keywords.append(keyword)

        for keyword in MANDATORY_KEYWORDS:
            if keyword in logic_lower:
                keywords.append(keyword)

        for keyword in DISABLED_KEYWORDS:
            if keyword in logic_lower:
                keywords.append(keyword)

        # Check for conditional keywords
        if 'if' in logic_lower:
            keywords.append('if')
        if 'otherwise' in logic_lower or 'else' in logic_lower:
            keywords.append('else')
        if 'then' in logic_lower:
            keywords.append('then')

        return list(set(keywords))

    def _extract_actions(self, logic: str) -> List[str]:
        """Extract actions to perform from logic text."""
        actions = []
        logic_lower = logic.lower()

        # Visibility actions
        if 'visible' in logic_lower and 'invisible' not in logic_lower:
            actions.append('MAKE_VISIBLE')
        if 'invisible' in logic_lower or 'hidden' in logic_lower:
            actions.append('MAKE_INVISIBLE')

        # Mandatory actions
        if 'mandatory' in logic_lower and 'non-mandatory' not in logic_lower and 'non mandatory' not in logic_lower:
            actions.append('MAKE_MANDATORY')
        if 'non-mandatory' in logic_lower or 'non mandatory' in logic_lower or 'optional' in logic_lower:
            actions.append('MAKE_NON_MANDATORY')

        # Editable actions
        if any(kw in logic_lower for kw in ['non-editable', 'noneditable', 'not editable', 'read-only', 'readonly', 'disabled']):
            actions.append('MAKE_DISABLED')
        if 'editable' in logic_lower and 'non' not in logic_lower:
            actions.append('MAKE_ENABLED')

        # Validation/OCR
        if self._is_validation_rule(logic):
            actions.append('VERIFY')
        if self._is_ocr_rule(logic):
            actions.append('OCR')

        return list(set(actions))

    def _extract_conditions(self, logic: str) -> List[Condition]:
        """Extract conditions from logic text."""
        conditions = []

        # Pattern: if field 'X' value is Y
        pattern1 = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value\s+)?is\s+([^\s,\.]+)"
        for match in re.finditer(pattern1, logic, re.IGNORECASE):
            conditions.append(Condition(
                field_name=match.group(1),
                operator='==',
                value=match.group(2),
                original_text=match.group(0)
            ))

        # Pattern: if 'X' is selected as Y
        pattern2 = r"if\s+['\"]?([^'\"]+)['\"]?\s+is\s+selected\s+as\s+([^\s,\.]+)"
        for match in re.finditer(pattern2, logic, re.IGNORECASE):
            conditions.append(Condition(
                field_name=match.group(1),
                operator='==',
                value=match.group(2),
                original_text=match.group(0)
            ))

        # Pattern: if X == Y or X = Y
        pattern3 = r"if\s+([^=]+?)\s*[=]+\s*['\"]?([^'\"]+)['\"]?"
        for match in re.finditer(pattern3, logic, re.IGNORECASE):
            conditions.append(Condition(
                field_name=match.group(1).strip(),
                operator='==',
                value=match.group(2).strip(),
                original_text=match.group(0)
            ))

        return conditions

    def _extract_field_references(self, logic: str) -> List[str]:
        """Extract field references from logic text."""
        field_refs = []

        # Pattern: field 'X' or "X"
        pattern1 = r"field\s+['\"]([^'\"]+)['\"]"
        for match in re.finditer(pattern1, logic, re.IGNORECASE):
            field_refs.append(match.group(1))

        # Pattern: from X validation / from X OCR
        pattern2 = r"from\s+([A-Za-z]+)\s+(?:validation|OCR|verification)"
        for match in re.finditer(pattern2, logic, re.IGNORECASE):
            field_refs.append(match.group(1))

        return list(set(field_refs))

    def _extract_document_types(self, logic: str) -> List[str]:
        """Extract document types (PAN, GSTIN, etc.) from logic text."""
        doc_types = []
        logic_lower = logic.lower()

        for doc_type in DOCUMENT_TYPES.keys():
            if doc_type in logic_lower:
                doc_types.append(doc_type)

        return list(set(doc_types))

    def _is_validation_rule(self, logic: str) -> bool:
        """Check if logic describes a validation rule."""
        logic_lower = logic.lower()

        # Must have validation keywords
        if not self.validation_pattern.search(logic):
            return False

        # But NOT "data will come from X validation" (destination field)
        if re.search(r"data\s+will\s+come\s+from", logic_lower):
            return False

        return True

    def _is_ocr_rule(self, logic: str) -> bool:
        """Check if logic describes an OCR rule."""
        logic_lower = logic.lower()

        # Check for OCR keywords
        if not self.ocr_pattern.search(logic):
            return False

        # Must mention OCR explicitly or be an upload/file field
        if 'ocr' in logic_lower:
            return True

        # Check for patterns like "Get X from OCR"
        if re.search(r"get\s+\w+\s+from\s+ocr", logic_lower):
            return True

        return False

    def _calculate_confidence(
        self,
        logic: str,
        keywords: List[str],
        conditions: List[Condition],
        is_visibility: bool,
        is_mandatory: bool,
        is_validation: bool,
        is_ocr: bool,
        is_disabled: bool
    ) -> float:
        """Calculate confidence score for the parsed logic."""
        confidence = 0.5  # Base confidence

        # More keywords = higher confidence
        if len(keywords) >= 3:
            confidence += 0.1
        if len(keywords) >= 5:
            confidence += 0.1

        # Clear conditions = higher confidence
        if conditions:
            confidence += 0.1
        if len(conditions) >= 2:
            confidence += 0.1

        # Clear rule type = higher confidence
        if is_visibility or is_mandatory or is_validation or is_ocr or is_disabled:
            confidence += 0.1

        # Short, clear logic = higher confidence
        if len(logic) < 100:
            confidence += 0.1

        return min(confidence, 1.0)


def should_skip_logic(logic_text: str) -> bool:
    """Check if logic should be skipped (expression/execute rules)."""
    if not logic_text:
        return True

    for pattern in SKIP_PATTERNS:
        if re.search(pattern, logic_text, re.IGNORECASE):
            return True

    return False


def detect_document_type(logic: str, field_name: str = "") -> Optional[Tuple[str, str, str]]:
    """
    Detect document type from logic or field name.

    Returns: (doc_type_key, verify_source_type, ocr_source_type) or None
    """
    combined = f"{field_name} {logic}".lower()

    for doc_type, sources in DOCUMENT_TYPES.items():
        if doc_type in combined:
            return (doc_type, sources.get('verify'), sources.get('ocr'))

    return None


def parse_visibility_condition(logic: str) -> Optional[Dict[str, Any]]:
    """
    Parse visibility condition from logic.

    Returns dict with:
    - controlling_field: field that controls visibility
    - conditional_values: values that trigger visibility
    - action: 'visible' or 'invisible'
    """
    # Pattern: if field 'X' values is Y then visible
    pattern = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+values?\s+is\s+([^\s,]+)\s+then\s+(visible|invisible|mandatory)"

    match = re.search(pattern, logic, re.IGNORECASE)
    if match:
        return {
            'controlling_field': match.group(1),
            'conditional_values': [match.group(2)],
            'action': match.group(3).upper()
        }

    return None
