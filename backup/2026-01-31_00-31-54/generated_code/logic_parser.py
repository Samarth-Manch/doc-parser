"""
Logic Parser Module

Parses natural language logic statements from BUD documents into structured data
for rule extraction.
"""

import re
from typing import List, Tuple, Optional, Dict, Any

try:
    from .models import (
        ParsedLogic,
        RuleSelection,
        DOCUMENT_TO_VERIFY_SOURCE,
        DOCUMENT_TO_OCR_SOURCE,
        VERIFY_SCHEMA_IDS,
        OCR_SCHEMA_IDS
    )
except ImportError:
    from models import (
        ParsedLogic,
        RuleSelection,
        DOCUMENT_TO_VERIFY_SOURCE,
        DOCUMENT_TO_OCR_SOURCE,
        VERIFY_SCHEMA_IDS,
        OCR_SCHEMA_IDS
    )


# Patterns that should be skipped (expression rules, execute rules)
SKIP_PATTERNS = [
    r"mvi\s*\(",              # mvi('fieldName')
    r"mm\s*\(",               # mm('fieldName')
    r"expr-eval",             # expr-eval expressions
    r"expr\s*:",              # expr: syntax
    r"\$\{.*\}",              # ${expression} syntax
    r"\bEXECUTE\b",           # EXECUTE keyword
    r"execute\s+rule",        # execute rule
    r"execute\s+script",      # execute script
    r"custom\s+script",       # custom script
    r"\b\w+\s*\(\s*['\"].*['\"]\s*\)\s*[\+\-\*\/]",  # func('x') + ...
]

# Visibility pattern detection
VISIBILITY_PATTERNS = [
    (r"then\s+visible", "MAKE_VISIBLE", 0.95),
    (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
    (r"(?:make\s+)?invisible|then\s+invisible", "MAKE_INVISIBLE", 0.95),
    (r"otherwise\s+invisible", "MAKE_INVISIBLE", 0.90),
    (r"show\s+(?:this|field|when)", "MAKE_VISIBLE", 0.90),
    (r"hide\s+(?:this|field|when)", "MAKE_INVISIBLE", 0.90),
]

# Mandatory pattern detection
MANDATORY_PATTERNS = [
    (r"then\s+(?:visible\s+and\s+)?mandatory", "MAKE_MANDATORY", 0.95),
    (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
    (r"non-mandatory|otherwise\s+non-mandatory", "MAKE_NON_MANDATORY", 0.90),
    (r"optional", "MAKE_NON_MANDATORY", 0.85),
    (r"required\s+(?:if|when)", "MAKE_MANDATORY", 0.85),
]

# Disable/Enable patterns
DISABLE_PATTERNS = [
    (r"(?:non-editable|non editable)", "MAKE_DISABLED", 0.95),
    (r"\bdisable[d]?\b", "MAKE_DISABLED", 0.95),
    (r"read-only|readonly", "MAKE_DISABLED", 0.90),
]

# OCR pattern detection
OCR_PATTERNS = [
    (r"get\s+\w+\s+from\s+ocr", "OCR", 0.95),
    (r"(?:from|using)\s+ocr\s*rule", "OCR", 0.95),
    (r"ocr\s+rule", "OCR", 0.95),
    (r"data\s+will\s+come\s+from\s+\w+\s+ocr", "OCR", 0.90),
    (r"extract\s+from\s+(?:image|document)", "OCR", 0.85),
]

# VERIFY pattern detection - only for fields that TRIGGER validation, not receive data
VERIFY_PATTERNS = [
    (r"perform\s+(?:pan|gstin?|gst|bank|msme|cin|tan)\s+validation", "VERIFY", 0.95),
    (r"(?:pan|gstin?|gst|bank|msme|cin|tan)\s+validation\s+(?:and\s+)?(?:store|populate)", "VERIFY", 0.95),
    (r"validate\s+(?:pan|gstin?|gst|bank|msme|cin|tan)(?:\s+and|\s*,)", "VERIFY", 0.95),
    (r"verify\s+(?:pan|gstin?|gst|bank|msme|cin|tan)(?:\s+and|\s*,|\s+number)", "VERIFY", 0.95),
]

# Patterns indicating field is a VERIFY destination (should NOT generate VERIFY rule here)
VERIFY_DESTINATION_PATTERNS = [
    r"data\s+will\s+come\s+from\s+(?:pan|gstin?|gst|bank|msme|cin)\s+(?:validation|verification)",
    r"populated?\s+from\s+(?:pan|gstin?|gst|bank|msme|cin)\s+(?:validation|verification)",
    r"data\s+from\s+(?:pan|gstin?|gst|bank|msme|cin)\s+(?:validation|verification)",
    r"auto-?derived\s+(?:via|from)\s+(?:pan|gstin?|gst|bank|msme|cin)\s+(?:validation|verification)",
    r"will\s+be\s+(?:auto-?)?derived\s+(?:via|from)\s+(?:pan|gstin?|gst|bank|msme|cin)",
    r"non-?editable.*(?:pan|gstin?|gst|bank|msme|cin)\s+(?:validation|verification)",
]

# EXT_DROP_DOWN patterns
EXT_DROPDOWN_PATTERNS = [
    (r"external\s+dropdown", "EXT_DROP_DOWN", 0.95),
    (r"dropdown\s+values?\s+(?:from|based\s+on)", "EXT_DROP_DOWN", 0.90),
    (r"reference\s+table", "EXT_DROP_DOWN", 0.85),
    (r"parent\s+dropdown\s+field", "EXT_DROP_DOWN", 0.90),
    (r"cascading\s+dropdown", "EXT_DROP_DOWN", 0.90),
    (r"dependent\s+on\s+(?:field|dropdown)", "EXT_DROP_DOWN", 0.85),
    (r"\.xlsx?\b", "EXT_DROP_DOWN", 0.80),
]

# EXT_VALUE patterns
EXT_VALUE_PATTERNS = [
    (r"external\s+(?:data\s+)?value", "EXT_VALUE", 0.90),
    (r"value\s+from\s+(?:table|excel|external)", "EXT_VALUE", 0.85),
    (r"edv\s+rule", "EXT_VALUE", 0.90),
    (r"lookup\s+value", "EXT_VALUE", 0.85),
]

# Pattern to extract controlling field from visibility logic
VISIBILITY_SOURCE_PATTERN = re.compile(
    r"if\s+(?:the\s+)?field\s+['\"]?([^'\"]+)['\"]?\s+(?:values?\s+is|is\s+(?:selected\s+as)?)\s+['\"]?(\w+)['\"]?",
    re.IGNORECASE
)

# Alternative pattern for "if X is Y"
CONDITION_PATTERN = re.compile(
    r"if\s+['\"]?([^'\"]+?)['\"]?\s+(?:is|=|==)\s+['\"]?([^'\"]+?)['\"]?\s+then",
    re.IGNORECASE
)

# Pattern to extract document type from logic
DOCUMENT_TYPE_PATTERN = re.compile(
    r"\b(pan|gstin|gst|bank|msme|cin|tan|aadhaar|aadhar|cheque|fssai)\b",
    re.IGNORECASE
)


class LogicParser:
    """
    Parses natural language logic statements into structured data.

    This parser uses pattern-based extraction to identify:
    - Action types (visible, mandatory, disable, verify, ocr, etc.)
    - Conditional logic (if/then/else)
    - Source and destination field references
    - Document types (PAN, GSTIN, etc.)
    """

    def __init__(self):
        """Initialize the logic parser."""
        self.skip_patterns = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]

    def should_skip(self, logic_text: str) -> bool:
        """
        Check if logic statement should be skipped.

        Returns True for:
        - Expression rules (mvi, mm, expr-eval)
        - Execute rules (EXECUTE, custom scripts)
        - Complex calculations
        """
        if not logic_text:
            return True

        for pattern in self.skip_patterns:
            if pattern.search(logic_text):
                return True
        return False

    def parse(self, logic_text: str) -> ParsedLogic:
        """
        Parse a logic statement into structured data.

        Args:
            logic_text: Natural language logic from BUD field

        Returns:
            ParsedLogic object with extracted information
        """
        if not logic_text:
            return ParsedLogic(original_text="", should_skip=True)

        logic_lower = logic_text.lower()

        result = ParsedLogic(
            original_text=logic_text,
            should_skip=self.should_skip(logic_text)
        )

        if result.should_skip:
            return result

        # Extract keywords
        result.keywords = self._extract_keywords(logic_lower)

        # Detect action types
        result.action_types = self._detect_action_types(logic_lower)

        # Extract source field (controlling field)
        source_info = self._extract_source_field(logic_text)
        if source_info:
            result.source_field_name = source_info[0]
            result.conditional_values = [source_info[1]] if source_info[1] else []

        # Check if this is a VERIFY destination
        result.is_verify_destination = self._is_verify_destination(logic_lower)

        # Extract document type
        result.document_type = self._extract_document_type(logic_lower)

        # Determine condition type
        if result.conditional_values:
            result.condition = "IN"

        # Calculate confidence
        result.confidence = self._calculate_confidence(result)

        return result

    def _extract_keywords(self, logic_lower: str) -> List[str]:
        """Extract keywords from logic text."""
        keywords = []

        keyword_patterns = [
            ("visible", r"\bvisible\b"),
            ("invisible", r"\binvisible\b"),
            ("mandatory", r"\bmandatory\b"),
            ("non-mandatory", r"\bnon-mandatory\b"),
            ("editable", r"\beditable\b"),
            ("non-editable", r"\bnon-editable\b"),
            ("disable", r"\bdisable[d]?\b"),
            ("validation", r"\bvalidation\b"),
            ("verify", r"\bverify\b"),
            ("ocr", r"\bocr\b"),
            ("dropdown", r"\bdropdown\b"),
            ("copy", r"\bcopy\b"),
            ("derive", r"\bderive[d]?\b"),
            ("if", r"\bif\b"),
            ("then", r"\bthen\b"),
            ("otherwise", r"\botherwise\b"),
        ]

        for keyword, pattern in keyword_patterns:
            if re.search(pattern, logic_lower):
                keywords.append(keyword)

        return keywords

    def _detect_action_types(self, logic_lower: str) -> List[str]:
        """Detect rule action types from logic text."""
        action_types = []

        # Check visibility patterns
        for pattern, action_type, _ in VISIBILITY_PATTERNS:
            if re.search(pattern, logic_lower):
                if action_type not in action_types:
                    action_types.append(action_type)

        # Check mandatory patterns
        for pattern, action_type, _ in MANDATORY_PATTERNS:
            if re.search(pattern, logic_lower):
                if action_type not in action_types:
                    action_types.append(action_type)

        # Check disable patterns
        for pattern, action_type, _ in DISABLE_PATTERNS:
            if re.search(pattern, logic_lower):
                if action_type not in action_types:
                    action_types.append(action_type)

        # Check OCR patterns
        for pattern, action_type, _ in OCR_PATTERNS:
            if re.search(pattern, logic_lower):
                if action_type not in action_types:
                    action_types.append(action_type)

        # Check VERIFY patterns (but not if it's a destination)
        if not self._is_verify_destination(logic_lower):
            for pattern, action_type, _ in VERIFY_PATTERNS:
                if re.search(pattern, logic_lower):
                    if action_type not in action_types:
                        action_types.append(action_type)

        # Check EXT_DROP_DOWN patterns
        for pattern, action_type, _ in EXT_DROPDOWN_PATTERNS:
            if re.search(pattern, logic_lower):
                if action_type not in action_types:
                    action_types.append(action_type)

        # Check EXT_VALUE patterns
        for pattern, action_type, _ in EXT_VALUE_PATTERNS:
            if re.search(pattern, logic_lower):
                if action_type not in action_types:
                    action_types.append(action_type)

        return action_types

    def _extract_source_field(self, logic_text: str) -> Optional[Tuple[str, str]]:
        """
        Extract source field name and conditional value from logic.

        Returns:
            Tuple of (field_name, conditional_value) or None
        """
        # Try main pattern first
        match = VISIBILITY_SOURCE_PATTERN.search(logic_text)
        if match:
            return (match.group(1).strip(), match.group(2).strip())

        # Try alternative pattern
        match = CONDITION_PATTERN.search(logic_text)
        if match:
            return (match.group(1).strip(), match.group(2).strip())

        return None

    def _is_verify_destination(self, logic_lower: str) -> bool:
        """Check if this field is a destination of a VERIFY rule."""
        for pattern in VERIFY_DESTINATION_PATTERNS:
            if re.search(pattern, logic_lower):
                return True
        return False

    def _extract_document_type(self, logic_lower: str) -> Optional[str]:
        """Extract document type (PAN, GSTIN, etc.) from logic."""
        match = DOCUMENT_TYPE_PATTERN.search(logic_lower)
        if match:
            return match.group(1).lower()
        return None

    def _calculate_confidence(self, result: ParsedLogic) -> float:
        """Calculate confidence score for parsed result."""
        confidence = 0.0

        # Higher confidence if action types detected
        if result.action_types:
            confidence = max(confidence, 0.7)

        # Higher confidence if source field detected
        if result.source_field_name:
            confidence = max(confidence, 0.8)

        # Higher confidence if document type detected for VERIFY/OCR
        if result.document_type and any(a in ["VERIFY", "OCR"] for a in result.action_types):
            confidence = max(confidence, 0.9)

        return confidence

    def detect_verify_source_type(self, logic_text: str, field_name: str = "") -> Optional[Tuple[str, int]]:
        """
        Detect VERIFY source type and schema ID from logic or field name.

        Args:
            logic_text: The logic statement
            field_name: The field name

        Returns:
            Tuple of (source_type, schema_id) or None
        """
        logic_lower = logic_text.lower()
        field_lower = field_name.lower()

        # Priority 1: Look for explicit "Perform X validation" patterns
        perform_patterns = [
            (r"perform\s+gstin?\s+validation", "GSTIN"),
            (r"perform\s+gst\s+validation", "GSTIN"),
            (r"perform\s+pan\s+validation", "PAN_NUMBER"),
            (r"perform\s+bank(?:\s+account)?\s+validation", "BANK_ACCOUNT_NUMBER"),
            (r"perform\s+msme\s+validation", "MSME_UDYAM_REG_NUMBER"),
            (r"perform\s+udyam\s+validation", "MSME_UDYAM_REG_NUMBER"),
            (r"perform\s+cin\s+validation", "CIN_ID"),
            (r"perform\s+tan\s+validation", "TAN_NUMBER"),
        ]

        for pattern, source_type in perform_patterns:
            if re.search(pattern, logic_lower):
                schema_id = VERIFY_SCHEMA_IDS.get(source_type)
                return (source_type, schema_id)

        # Priority 2: Match based on field name (most reliable)
        field_type_map = {
            "gstin": "GSTIN",
            "gst number": "GSTIN",
            "pan": "PAN_NUMBER",
            "pan number": "PAN_NUMBER",
            "ifsc": "BANK_ACCOUNT_NUMBER",
            "account number": "BANK_ACCOUNT_NUMBER",
            "msme": "MSME_UDYAM_REG_NUMBER",
            "udyam": "MSME_UDYAM_REG_NUMBER",
            "cin": "CIN_ID",
            "tan": "TAN_NUMBER",
        }

        for keyword, source_type in field_type_map.items():
            if keyword in field_lower:
                schema_id = VERIFY_SCHEMA_IDS.get(source_type)
                return (source_type, schema_id)

        # Priority 3: Fall back to general document type matching in logic
        # But only if there's a clear validation pattern
        if not re.search(r"validation|verify", logic_lower):
            return None

        for doc_type, source_type in DOCUMENT_TO_VERIFY_SOURCE.items():
            if doc_type in logic_lower:
                schema_id = VERIFY_SCHEMA_IDS.get(source_type)
                return (source_type, schema_id)

        return None

    def detect_ocr_source_type(self, logic_text: str, field_name: str = "") -> Optional[Tuple[str, int]]:
        """
        Detect OCR source type and schema ID from logic or field name.

        Args:
            logic_text: The logic statement
            field_name: The field name

        Returns:
            Tuple of (source_type, schema_id) or None
        """
        combined = f"{logic_text} {field_name}".lower()

        # Check for specific document types
        type_keywords = [
            ("aadhaar back", "AADHAR_BACK_IMAGE"),
            ("aadhar back", "AADHAR_BACK_IMAGE"),
            ("aadhaar front", "AADHAR_IMAGE"),
            ("aadhar front", "AADHAR_IMAGE"),
            ("aadhaar", "AADHAR_IMAGE"),
            ("aadhar", "AADHAR_IMAGE"),
            ("cancelled cheque", "CHEQUEE"),
            ("cheque", "CHEQUEE"),
            ("pan", "PAN_IMAGE"),
            ("gstin", "GSTIN_IMAGE"),
            ("gst", "GSTIN_IMAGE"),
            ("msme", "MSME"),
            ("udyam", "MSME"),
            ("cin", "CIN"),
        ]

        for keyword, source_type in type_keywords:
            if keyword in combined:
                schema_id = OCR_SCHEMA_IDS.get(source_type)
                return (source_type, schema_id)

        return None

    def parse_visibility_conditions(self, logic_text: str) -> List[Dict[str, Any]]:
        """
        Parse visibility conditions to generate both positive and negative rules.

        For logic like "if X is Y then visible otherwise invisible", generates:
        - MAKE_VISIBLE with condition IN [Y]
        - MAKE_INVISIBLE with condition NOT_IN [Y]

        Args:
            logic_text: The logic statement

        Returns:
            List of condition dicts with action_type, condition, conditional_values
        """
        conditions = []
        logic_lower = logic_text.lower()

        source_info = self._extract_source_field(logic_text)
        if not source_info:
            return conditions

        source_field, conditional_value = source_info

        # Check for positive visibility
        if re.search(r"then\s+visible|is\s+\w+\s+then\s+visible", logic_lower):
            conditions.append({
                "action_type": "MAKE_VISIBLE",
                "condition": "IN",
                "conditional_values": [conditional_value],
                "source_field": source_field
            })

        # Check for negative visibility (otherwise invisible)
        if re.search(r"otherwise\s+invisible", logic_lower):
            conditions.append({
                "action_type": "MAKE_INVISIBLE",
                "condition": "NOT_IN",
                "conditional_values": [conditional_value],
                "source_field": source_field
            })

        # Check for positive mandatory
        if re.search(r"then\s+(?:visible\s+and\s+)?mandatory|is\s+\w+\s+then\s+.*mandatory", logic_lower):
            conditions.append({
                "action_type": "MAKE_MANDATORY",
                "condition": "IN",
                "conditional_values": [conditional_value],
                "source_field": source_field
            })

        # Check for negative mandatory (otherwise non-mandatory)
        if re.search(r"otherwise\s+(?:invisible\s+and\s+)?non-mandatory", logic_lower):
            conditions.append({
                "action_type": "MAKE_NON_MANDATORY",
                "condition": "NOT_IN",
                "conditional_values": [conditional_value],
                "source_field": source_field
            })

        return conditions
