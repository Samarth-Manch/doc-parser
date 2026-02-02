"""
Logic Parser - Parses natural language logic statements into structured data.

Handles patterns like:
- "if field 'X' is Y then visible and mandatory otherwise invisible"
- "Perform PAN Validation"
- "Get PAN from OCR rule"
- "Data will come from GSTIN verification. Non-Editable"
"""

import re
from typing import List, Optional, Tuple, Dict
try:
    from .models import ParsedLogic, ParsedCondition
except ImportError:
    from models import ParsedLogic, ParsedCondition


# Patterns to skip (expression rules, execute rules)
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
]

# Document type detection patterns
DOCUMENT_TYPE_PATTERNS = {
    "PAN": [
        r"\bPAN\b",
        r"PAN\s+(?:card|number|validation|verify|OCR)",
        r"(?:PAN|pan)\s+(?:holder|type|status)",
    ],
    "GSTIN": [
        r"\bGSTIN?\b",
        r"GST\s+(?:number|validation|verify|OCR|option)",
        r"GSTIN\s+(?:IMAGE|verification|OCR)",
    ],
    "BANK": [
        r"\bbank\s+(?:account|validation|verify)\b",
        r"\bIFSC\b",
        r"\bcheque\b",
        r"(?:cancelled|canceled)\s+cheque",
    ],
    "MSME": [
        r"\bMSME\b",
        r"\bSSI\b",
        r"udyam\s+registration",
    ],
    "CIN": [
        r"\bCIN\b",
        r"company\s+identification",
    ],
    "TAN": [
        r"\bTAN\b",
        r"tax\s+(?:deduction|account)\s+number",
    ],
    "AADHAAR": [
        r"\bAadhaar\b",
        r"\bAadhar\b",
        r"aadhaar\s+(?:front|back|OCR)",
    ],
}

# Action type detection patterns with confidence scores
PATTERNS = {
    "visibility": [
        (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
        (r"(?:make\s+)?invisible|hide", "MAKE_INVISIBLE", 0.95),
        (r"show\s+(?:this|field)", "MAKE_VISIBLE", 0.90),
        (r"then\s+visible", "MAKE_VISIBLE", 0.90),
        (r"then\s+invisible", "MAKE_INVISIBLE", 0.90),
        (r"otherwise\s+invisible", "MAKE_INVISIBLE", 0.85),
        (r"otherwise\s+visible", "MAKE_VISIBLE", 0.85),
    ],
    "mandatory": [
        (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
        (r"non-mandatory|non\s+mandatory", "MAKE_NON_MANDATORY", 0.95),
        (r"optional", "MAKE_NON_MANDATORY", 0.80),
        (r"required\s+(?:if|when)", "MAKE_MANDATORY", 0.85),
        (r"then\s+mandatory", "MAKE_MANDATORY", 0.90),
        (r"otherwise\s+(?:non-mandatory|non\s+mandatory)", "MAKE_NON_MANDATORY", 0.85),
    ],
    "disable": [
        (r"disable[d]?", "MAKE_DISABLED", 0.90),
        (r"non-editable|non\s+editable", "MAKE_DISABLED", 0.95),
        (r"read-only|readonly", "MAKE_DISABLED", 0.95),
        (r"not\s+editable", "MAKE_DISABLED", 0.90),
    ],
    "verify": [
        (r"(?:PAN|GSTIN|GST|bank|MSME|CIN|TAN)\s+(?:validation|verify)", "VERIFY", 0.95),
        (r"validate\s+(?:PAN|GSTIN|GST|bank|MSME|CIN|TAN)", "VERIFY", 0.95),
        (r"perform\s+(?:PAN|GSTIN|bank|MSME|CIN|TAN)\s+validation", "VERIFY", 0.95),
        (r"validation\s+and\s+store", "VERIFY", 0.90),
    ],
    "ocr": [
        (r"(?:from|using)\s+OCR", "OCR", 0.95),
        (r"OCR\s+rule", "OCR", 0.95),
        (r"extract\s+from\s+(?:image|document)", "OCR", 0.85),
        (r"get\s+\w+\s+from\s+OCR", "OCR", 0.95),
        (r"data\s+will\s+come\s+from\s+.*OCR", "OCR", 0.90),
    ],
    "edv": [
        (r"dropdown\s+values?\s+(?:from|based|will\s+come)", "EXT_DROP_DOWN", 0.90),
        (r"reference\s+table", "EXT_DROP_DOWN", 0.85),
        (r"external\s+data", "EXT_VALUE", 0.85),
        (r"parent\s+dropdown\s+field", "EXT_DROP_DOWN", 0.90),
        (r"values?\s+from\s+column", "EXT_DROP_DOWN", 0.85),
        (r"cascading\s+dropdown", "EXT_DROP_DOWN", 0.95),
    ],
    "copy": [
        (r"copy\s+(?:from|to)", "COPY_TO", 0.90),
        (r"auto-fill|autofill", "COPY_TO", 0.85),
        (r"derive[d]?\s+(?:from|as|it)", "COPY_TO", 0.80),
        (r"populated\s+by", "COPY_TO", 0.80),
        (r"auto-populated", "COPY_TO", 0.85),
    ],
    "convert": [
        (r"upper\s*case", "CONVERT_TO", 0.95),
        (r"lower\s*case", "CONVERT_TO", 0.95),
        (r"should\s+be\s+upper", "CONVERT_TO", 0.90),
    ],
    "document": [
        (r"delete\s+document", "DELETE_DOCUMENT", 0.95),
        (r"undelete\s+document", "UNDELETE_DOCUMENT", 0.95),
        (r"hide\s+document", "DELETE_DOCUMENT", 0.85),
        (r"show\s+document", "UNDELETE_DOCUMENT", 0.85),
    ],
    "session": [
        (r"first\s+party|second\s+party", "SESSION_BASED", 0.90),
        (r"initiator|spoc|approver", "SESSION_BASED", 0.85),
    ],
}

# Patterns indicating this field is a DESTINATION of verification (not a source)
VERIFY_DESTINATION_PATTERNS = [
    r"data\s+will\s+come\s+from\s+(?:PAN|GSTIN|bank|MSME|CIN)\s+(?:validation|verification)",
    r"auto-derived\s+via\s+(?:PAN|GSTIN|MSME)\s+(?:validation|verification)",
    r"populated\s+(?:from|by)\s+(?:PAN|GSTIN|MSME)\s+(?:validation|verification)",
]


class LogicParser:
    """Parses natural language logic statements from BUD documents."""

    def __init__(self):
        self.skip_patterns = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]
        self.verify_dest_patterns = [re.compile(p, re.IGNORECASE) for p in VERIFY_DESTINATION_PATTERNS]

    def should_skip(self, logic_text: str) -> bool:
        """Check if this logic statement should be skipped (expression/execute rules)."""
        if not logic_text:
            return True
        for pattern in self.skip_patterns:
            if pattern.search(logic_text):
                return True
        return False

    def is_verify_destination(self, logic_text: str) -> bool:
        """Check if this field is a destination of verification, not a source."""
        if not logic_text:
            return False
        for pattern in self.verify_dest_patterns:
            if pattern.search(logic_text):
                return True
        return False

    def detect_document_type(self, logic_text: str) -> Optional[str]:
        """Detect the document type mentioned in the logic."""
        if not logic_text:
            return None

        for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, logic_text, re.IGNORECASE):
                    return doc_type
        return None

    def extract_keywords(self, logic_text: str) -> List[str]:
        """Extract relevant keywords from the logic text."""
        keywords = []
        logic_lower = logic_text.lower()

        keyword_list = [
            "visible", "invisible", "mandatory", "non-mandatory",
            "editable", "non-editable", "disabled", "enabled",
            "validation", "verify", "ocr", "copy", "derive",
            "dropdown", "reference", "external", "upper", "lower",
            "if", "then", "otherwise", "else", "when",
        ]

        for keyword in keyword_list:
            if keyword in logic_lower:
                keywords.append(keyword)

        return keywords

    def extract_field_references(self, logic_text: str) -> List[str]:
        """Extract field names referenced in the logic."""
        if not logic_text:
            return []

        field_refs = []

        # Pattern: "field 'X'" or 'field "X"' or "field 'X'"
        patterns = [
            r"field\s*['\"]([^'\"]+)['\"]",
            r"the\s+field\s+['\"]([^'\"]+)['\"]",
            r"if\s+(?:the\s+)?['\"]([^'\"]+)['\"]",
            r"from\s+['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, logic_text, re.IGNORECASE)
            field_refs.extend(matches)

        return list(set(field_refs))

    def extract_conditional_values(self, logic_text: str) -> List[str]:
        """Extract conditional values from the logic (e.g., 'yes', 'no', 'GST Registered')."""
        if not logic_text:
            return []

        values = []

        # Pattern: "is X then" or "value is X"
        patterns = [
            r"(?:values?\s+is|is\s+(?:selected\s+as)?)\s+['\"]?([^'\"]+?)['\"]?\s+then",
            r"(?:values?\s+is|is)\s+['\"]([^'\"]+)['\"]",
            r"selected\s+as\s+['\"]?([^'\"]+?)['\"]?(?:\s+then|\s*$|\s*,)",
            r"=\s*['\"]?([^'\"]+?)['\"]?(?:\s+then|\s*$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, logic_text, re.IGNORECASE)
            for match in matches:
                # Clean up the value
                value = match.strip()
                if value and value.lower() not in ["then", "otherwise", "else", "and", "or"]:
                    values.append(value)

        return list(set(values))

    def parse_conditions(self, logic_text: str) -> List[ParsedCondition]:
        """Parse conditional statements from the logic."""
        if not logic_text:
            return []

        conditions = []

        # Pattern: "if field 'X' value is Y then ..."
        pattern = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:values?\s+is|is)\s+['\"]?([^'\"]+?)['\"]?\s+then"

        matches = re.findall(pattern, logic_text, re.IGNORECASE)
        for field_name, value in matches:
            conditions.append(ParsedCondition(
                field_name=field_name.strip(),
                operator="IN",
                values=[value.strip()]
            ))

        return conditions

    def detect_action_types(self, logic_text: str) -> List[Tuple[str, float]]:
        """Detect action types and their confidence scores."""
        if not logic_text:
            return []

        actions = []

        for category, patterns_list in PATTERNS.items():
            for pattern, action_type, confidence in patterns_list:
                if re.search(pattern, logic_text, re.IGNORECASE):
                    actions.append((action_type, confidence))

        # Remove duplicates, keeping highest confidence for each action type
        action_dict = {}
        for action_type, confidence in actions:
            if action_type not in action_dict or confidence > action_dict[action_type]:
                action_dict[action_type] = confidence

        return [(action, conf) for action, conf in action_dict.items()]

    def parse(self, logic_text: str) -> ParsedLogic:
        """Parse a logic statement into structured data."""
        if not logic_text:
            return ParsedLogic(
                original_text="",
                keywords=[],
                action_types=[],
                conditions=[],
                field_references=[],
                is_skip=True,
                confidence=0.0
            )

        # Check if should skip
        if self.should_skip(logic_text):
            return ParsedLogic(
                original_text=logic_text,
                keywords=[],
                action_types=[],
                conditions=[],
                field_references=[],
                is_skip=True,
                confidence=0.0
            )

        # Extract components
        keywords = self.extract_keywords(logic_text)
        field_refs = self.extract_field_references(logic_text)
        conditions = self.parse_conditions(logic_text)
        action_types_with_conf = self.detect_action_types(logic_text)
        document_type = self.detect_document_type(logic_text)

        # Check if this is a verify destination
        is_verify_dest = self.is_verify_destination(logic_text)

        # Determine flags
        action_types = [a for a, _ in action_types_with_conf]
        is_ocr = "OCR" in action_types
        is_verify = "VERIFY" in action_types and not is_verify_dest
        is_visibility = "MAKE_VISIBLE" in action_types or "MAKE_INVISIBLE" in action_types
        is_mandatory = "MAKE_MANDATORY" in action_types or "MAKE_NON_MANDATORY" in action_types
        is_disabled = "MAKE_DISABLED" in action_types
        is_ext_dropdown = "EXT_DROP_DOWN" in action_types
        is_ext_value = "EXT_VALUE" in action_types
        is_copy = "COPY_TO" in action_types
        is_session_based = "SESSION_BASED" in action_types
        is_document_rule = "DELETE_DOCUMENT" in action_types or "UNDELETE_DOCUMENT" in action_types

        # Calculate overall confidence
        if action_types_with_conf:
            max_confidence = max(conf for _, conf in action_types_with_conf)
        else:
            max_confidence = 0.3  # Low confidence if no patterns matched

        return ParsedLogic(
            original_text=logic_text,
            keywords=keywords,
            action_types=action_types,
            conditions=conditions,
            field_references=field_refs,
            document_type=document_type,
            is_ocr=is_ocr,
            is_verify=is_verify,
            is_visibility=is_visibility,
            is_mandatory=is_mandatory,
            is_disabled=is_disabled,
            is_ext_dropdown=is_ext_dropdown,
            is_ext_value=is_ext_value,
            is_copy=is_copy,
            is_session_based=is_session_based,
            is_document_rule=is_document_rule,
            is_skip=False,
            confidence=max_confidence
        )

    def parse_visibility_pattern(self, logic_text: str) -> Dict:
        """
        Parse visibility patterns to extract controlling field and conditions.

        Returns dict with:
        - controlling_field: name of the field that controls visibility
        - conditional_values: list of values that trigger visibility
        - is_visible_when: True if visible when condition met, False if invisible
        - is_mandatory_when: True if also makes mandatory
        """
        result = {
            "controlling_field": None,
            "conditional_values": [],
            "is_visible_when": None,
            "is_invisible_when": None,
            "is_mandatory_when": None,
            "is_non_mandatory_when": None,
        }

        if not logic_text:
            return result

        # Pattern: "if the field 'X' values is Y then visible"
        pattern = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:values?\s+is|is)\s+['\"]?([^'\"]+?)['\"]?\s+then\s+(visible|invisible|mandatory)"

        match = re.search(pattern, logic_text, re.IGNORECASE)
        if match:
            result["controlling_field"] = match.group(1).strip()
            result["conditional_values"] = [match.group(2).strip()]

            action = match.group(3).lower()
            if action == "visible":
                result["is_visible_when"] = True
            elif action == "invisible":
                result["is_invisible_when"] = True
            elif action == "mandatory":
                result["is_mandatory_when"] = True

        # Check for combined patterns like "visible and mandatory"
        if result["is_visible_when"] and re.search(r"visible\s+and\s+mandatory", logic_text, re.IGNORECASE):
            result["is_mandatory_when"] = True

        # Check for "otherwise invisible and non-mandatory"
        if re.search(r"otherwise\s+invisible", logic_text, re.IGNORECASE):
            result["is_invisible_when"] = True
        if re.search(r"otherwise\s+(?:non-mandatory|non\s+mandatory)", logic_text, re.IGNORECASE):
            result["is_non_mandatory_when"] = True

        return result
