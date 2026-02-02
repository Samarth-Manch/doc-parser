"""
Logic Parser - Parse natural language logic statements from BUD documents.

This module extracts structured information from BUD logic/rules text, including:
- Keywords (visible, mandatory, validate, OCR, etc.)
- Conditions (if/then/else)
- Field references
- Document types
"""

import re
from typing import List, Optional, Tuple, Dict
from .models import ParsedLogic, Condition


class LogicParser:
    """Parse natural language logic statements into structured data."""

    # Patterns for different rule categories
    VISIBILITY_PATTERNS = [
        (r"(?:make\s+)?visible\s+(?:if|when)", "visible", 0.95),
        (r"(?:make\s+)?invisible|hide", "invisible", 0.95),
        (r"then\s+visible", "visible", 0.90),
        (r"show\s+(?:this|field)", "visible", 0.90),
        (r"otherwise\s+invisible", "invisible", 0.90),
    ]

    MANDATORY_PATTERNS = [
        (r"(?:make\s+)?mandatory\s+(?:if|when)", "mandatory", 0.95),
        (r"then\s+(?:visible\s+and\s+)?mandatory", "mandatory", 0.95),
        (r"non[-\s]?mandatory|optional", "non_mandatory", 0.90),
        (r"otherwise\s+(?:invisible\s+and\s+)?non[-\s]?mandatory", "non_mandatory", 0.90),
        (r"required\s+(?:if|when)", "mandatory", 0.85),
    ]

    DISABLE_PATTERNS = [
        (r"non[-\s]?editable", "disabled", 0.95),
        (r"disable", "disabled", 0.95),
        (r"read[-\s]?only", "disabled", 0.90),
    ]

    VERIFY_PATTERNS = [
        (r"perform\s+(\w+)\s+validation", "verify", 0.95),
        (r"validate\s+(\w+)", "verify", 0.95),
        (r"(\w+)\s+validation", "verify", 0.90),
        (r"verify\s+(\w+)", "verify", 0.90),
        (r"verification", "verify", 0.85),
    ]

    OCR_PATTERNS = [
        (r"(?:get|from)\s+(\w+)\s+(?:from\s+)?ocr", "ocr", 0.95),
        (r"ocr\s+rule", "ocr", 0.95),
        (r"data\s+will\s+come\s+from\s+(\w+)\s+ocr", "ocr", 0.90),
        (r"extract\s+from\s+(?:image|document)", "ocr", 0.85),
    ]

    VERIFY_DESTINATION_PATTERNS = [
        (r"data\s+will\s+come\s+from\s+(\w+)\s+validation", "verify_destination", 0.95),
        (r"data\s+will\s+come\s+from\s+(\w+)\s+verification", "verify_destination", 0.95),
        (r"populated?\s+from\s+(\w+)\s+validation", "verify_destination", 0.90),
    ]

    EXT_DROPDOWN_PATTERNS = [
        (r"external\s+dropdown", "ext_dropdown", 0.95),
        (r"dropdown\s+values?\s+(?:from|based\s+on)", "ext_dropdown", 0.90),
        (r"reference\s+table", "ext_dropdown", 0.85),
        (r"parent\s+dropdown\s+field", "ext_dropdown", 0.90),
        (r"cascading\s+dropdown", "ext_dropdown", 0.90),
        (r"dependent\s+on\s+(?:field|dropdown)", "ext_dropdown", 0.85),
        (r"\.xlsx?\b", "ext_dropdown", 0.80),
    ]

    # Patterns to skip (expression rules, execute rules)
    SKIP_PATTERNS = [
        r"mvi\s*\(",
        r"mm\s*\(",
        r"expr[-\s]?eval",
        r"expr\s*:",
        r"\$\{.*\}",
        r"\bEXECUTE\b",
        r"execute\s+rule",
        r"execute\s+script",
        r"custom\s+script",
        r"ctfd\s*\(",
        r"replaceRange\s*\(",
        r"asdff\s*\(",
        r"vo\s*\(",
    ]

    # Document type keywords
    DOCUMENT_TYPES = {
        "pan": "PAN",
        "gstin": "GSTIN",
        "gst": "GSTIN",
        "bank": "BANK",
        "ifsc": "BANK",
        "msme": "MSME",
        "udyam": "MSME",
        "cin": "CIN",
        "tan": "TAN",
        "fssai": "FSSAI",
        "aadhaar": "AADHAAR",
        "aadhar": "AADHAAR",
        "cheque": "CHEQUE",
    }

    # Condition field extraction patterns
    CONDITION_PATTERNS = [
        # "if the field 'X' value(s) is Y then ..."
        r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value|values?)\s+(?:is|are)\s+([^\s,]+)",
        # "if 'X' is Y then ..."
        r"if\s+['\"]([^'\"]+)['\"]\s+is\s+([^\s,]+)",
        # "if X is selected as Y then ..."
        r"if\s+([^'\"]+?)\s+is\s+selected\s+as\s+([^\s,]+)",
        # "when X equals Y ..."
        r"when\s+['\"]?([^'\"]+?)['\"]?\s+equals?\s+['\"]?([^'\"]+?)['\"]?",
    ]

    def __init__(self):
        """Initialize the logic parser."""
        pass

    def parse(self, logic_text: str) -> ParsedLogic:
        """
        Parse a logic statement into structured data.

        Args:
            logic_text: Raw logic text from BUD

        Returns:
            ParsedLogic with extracted information.
        """
        if not logic_text:
            return ParsedLogic(original_text="")

        result = ParsedLogic(original_text=logic_text)
        logic_lower = logic_text.lower()

        # Check if should skip (expression/execute rules)
        result.should_skip = self._should_skip(logic_text)
        if result.should_skip:
            return result

        # Extract keywords
        result.keywords = self._extract_keywords(logic_lower)

        # Extract conditions
        result.conditions = self._extract_conditions(logic_text)

        # Extract actions
        result.actions = self._extract_actions(logic_lower)

        # Extract field references
        result.field_references = self._extract_field_references(logic_text)

        # Detect document type
        result.document_type = self._detect_document_type(logic_lower)

        # Detect rule types
        result.is_ocr = self._is_ocr_rule(logic_lower)
        result.is_verify = self._is_verify_rule(logic_lower)
        result.is_verify_destination = self._is_verify_destination(logic_lower)
        result.is_non_editable = self._is_non_editable(logic_lower)

        # Calculate confidence
        result.confidence = self._calculate_confidence(result)

        return result

    def _should_skip(self, logic_text: str) -> bool:
        """Check if logic statement should be skipped."""
        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, logic_text, re.IGNORECASE):
                return True
        return False

    def _extract_keywords(self, logic_lower: str) -> List[str]:
        """Extract action keywords from logic text."""
        keywords = []

        keyword_list = [
            "visible", "invisible", "mandatory", "non-mandatory",
            "editable", "non-editable", "disable", "enable",
            "validate", "validation", "verify", "verification",
            "ocr", "extract", "scan",
            "copy", "derive", "auto-fill", "populate",
            "dropdown", "reference table", "external",
            "if", "then", "otherwise", "else", "when",
        ]

        for kw in keyword_list:
            if kw in logic_lower:
                keywords.append(kw)

        return keywords

    def _extract_conditions(self, logic_text: str) -> List[Condition]:
        """Extract conditions from logic text."""
        conditions = []

        for pattern in self.CONDITION_PATTERNS:
            matches = re.finditer(pattern, logic_text, re.IGNORECASE)
            for match in matches:
                field_name = match.group(1).strip()
                value = match.group(2).strip().strip("'\"")

                conditions.append(Condition(
                    source_field_name=field_name,
                    operator="==",
                    value=value,
                    value_list=[value],
                ))

        return conditions

    def _extract_actions(self, logic_lower: str) -> List[str]:
        """Extract actions from logic text."""
        actions = []

        # Check visibility
        if re.search(r"then\s+visible|make\s+visible|show\s+", logic_lower):
            actions.append("make_visible")
        if re.search(r"invisible|hide", logic_lower):
            actions.append("make_invisible")

        # Check mandatory
        if re.search(r"then\s+(?:visible\s+and\s+)?mandatory|make\s+mandatory|required", logic_lower):
            actions.append("make_mandatory")
        if re.search(r"non[-\s]?mandatory|optional", logic_lower):
            actions.append("make_non_mandatory")

        # Check editability
        if re.search(r"non[-\s]?editable|disable|read[-\s]?only", logic_lower):
            actions.append("make_disabled")
        if re.search(r"editable|enable", logic_lower) and "non" not in logic_lower:
            actions.append("make_enabled")

        # Check validation
        if re.search(r"perform\s+\w+\s+validation|validate\s+\w+", logic_lower):
            if not re.search(r"data\s+will\s+come\s+from", logic_lower):
                actions.append("verify")

        # Check OCR
        if re.search(r"ocr\s+rule|from\s+ocr|get\s+\w+\s+from\s+ocr", logic_lower):
            actions.append("ocr")

        # Check uppercase
        if re.search(r"upper\s*case|uppercase", logic_lower):
            actions.append("convert_to_upper")

        return actions

    def _extract_field_references(self, logic_text: str) -> List[str]:
        """Extract field references from logic text."""
        references = []

        # Pattern: 'field name' or "field name"
        matches = re.findall(r"['\"]([^'\"]+)['\"]", logic_text)
        references.extend(matches)

        # Pattern: field 'field name'
        matches = re.findall(r"field\s+['\"]([^'\"]+)['\"]", logic_text, re.IGNORECASE)
        references.extend(matches)

        # Deduplicate
        return list(set(references))

    def _detect_document_type(self, logic_lower: str) -> Optional[str]:
        """Detect document type from logic text."""
        for keyword, doc_type in self.DOCUMENT_TYPES.items():
            if keyword in logic_lower:
                return doc_type
        return None

    def _is_ocr_rule(self, logic_lower: str) -> bool:
        """Check if this is an OCR rule."""
        return bool(re.search(r"ocr\s+rule|from\s+ocr|get\s+\w+\s+from\s+ocr", logic_lower))

    def _is_verify_rule(self, logic_lower: str) -> bool:
        """Check if this is a VERIFY rule (source, not destination)."""
        # Must have validation keywords
        if not re.search(r"perform\s+\w+\s+validation|validate\s+\w+", logic_lower):
            return False
        # Must NOT be a destination ("Data will come from X validation")
        if re.search(r"data\s+will\s+come\s+from", logic_lower):
            return False
        return True

    def _is_verify_destination(self, logic_lower: str) -> bool:
        """Check if this field is a VERIFY destination (not source)."""
        return bool(re.search(r"data\s+will\s+come\s+from\s+\w+\s+validation", logic_lower))

    def _is_non_editable(self, logic_lower: str) -> bool:
        """Check if field should be non-editable."""
        return bool(re.search(r"non[-\s]?editable|read[-\s]?only", logic_lower))

    def _calculate_confidence(self, result: ParsedLogic) -> float:
        """Calculate confidence score for the parsed result."""
        confidence = 0.0

        # Add confidence for each detected pattern
        if result.is_ocr:
            confidence = max(confidence, 0.90)
        if result.is_verify:
            confidence = max(confidence, 0.90)
        if result.is_verify_destination:
            confidence = max(confidence, 0.85)
        if result.is_non_editable:
            confidence = max(confidence, 0.85)
        if result.conditions:
            confidence = max(confidence, 0.80)
        if result.actions:
            confidence = max(confidence, 0.70)

        return confidence

    def detect_visibility_rule_type(self, logic_text: str) -> Optional[Tuple[str, str, str]]:
        """
        Detect if this is a visibility-controlled field.

        Returns:
            Tuple of (source_field_name, conditional_value, action_type) or None.
        """
        if not logic_text:
            return None

        logic_lower = logic_text.lower()

        # Pattern: "if the field 'X' value is Y then visible"
        match = re.search(
            r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value|values?)\s+(?:is|are)\s+([^\s,]+)\s+then\s+(visible|mandatory)",
            logic_lower
        )
        if match:
            source_field = match.group(1)
            value = match.group(2).strip("'\"")
            action = match.group(3)
            return (source_field, value, f"make_{action}")

        return None

    def extract_all_conditional_values(self, logic_text: str) -> List[str]:
        """Extract all conditional values from logic text."""
        if not logic_text:
            return []

        values = []

        # Pattern variations
        patterns = [
            r"value\s+(?:is|are)\s+['\"]?([^'\"]+?)['\"]?\s+then",
            r"selected\s+as\s+['\"]?([^'\"]+?)['\"]?",
            r"equals?\s+['\"]?([^'\"]+?)['\"]?",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, logic_text, re.IGNORECASE)
            values.extend(m.strip() for m in matches)

        return list(set(values))


class LogicPatternMatcher:
    """Match logic text to specific rule patterns."""

    # High-confidence patterns with rule types
    PATTERNS = {
        "visibility": [
            (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
            (r"(?:make\s+)?invisible|hide", "MAKE_INVISIBLE", 0.95),
            (r"then\s+visible", "MAKE_VISIBLE", 0.90),
            (r"otherwise\s+invisible", "MAKE_INVISIBLE", 0.90),
        ],
        "mandatory": [
            (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
            (r"then\s+(?:visible\s+and\s+)?mandatory", "MAKE_MANDATORY", 0.90),
            (r"non[-\s]?mandatory|optional", "MAKE_NON_MANDATORY", 0.90),
            (r"otherwise\s+(?:invisible\s+and\s+)?non[-\s]?mandatory", "MAKE_NON_MANDATORY", 0.90),
        ],
        "disable": [
            (r"non[-\s]?editable", "MAKE_DISABLED", 0.95),
            (r"disable", "MAKE_DISABLED", 0.95),
            (r"read[-\s]?only", "MAKE_DISABLED", 0.90),
        ],
        "verify": [
            (r"perform\s+pan\s+validation", "VERIFY", 0.95),
            (r"perform\s+gstin?\s+validation", "VERIFY", 0.95),
            (r"perform\s+bank\s+validation", "VERIFY", 0.95),
            (r"perform\s+msme\s+validation", "VERIFY", 0.95),
            (r"validate\s+(?:pan|gstin?|bank|msme)", "VERIFY", 0.95),
        ],
        "ocr": [
            (r"(?:get|from)\s+\w+\s+(?:from\s+)?ocr", "OCR", 0.95),
            (r"ocr\s+rule", "OCR", 0.95),
            (r"data\s+will\s+come\s+from\s+\w+\s+ocr", "OCR", 0.90),
        ],
        "edv": [
            (r"dropdown\s+values?\s+(?:from|based)", "EXT_DROP_DOWN", 0.90),
            (r"reference\s+table", "EXT_DROP_DOWN", 0.85),
            (r"external\s+data", "EXT_VALUE", 0.85),
            (r"parent\s+dropdown\s+field", "EXT_DROP_DOWN", 0.90),
        ],
    }

    def match(self, logic_text: str) -> List[Tuple[str, str, float]]:
        """
        Match logic text to rule patterns.

        Returns:
            List of (category, action_type, confidence) tuples.
        """
        if not logic_text:
            return []

        logic_lower = logic_text.lower()
        matches = []

        for category, patterns in self.PATTERNS.items():
            for pattern, action_type, confidence in patterns:
                if re.search(pattern, logic_lower):
                    matches.append((category, action_type, confidence))

        return matches
