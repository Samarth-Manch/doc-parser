"""
Logic Parser - Parse natural language logic from BUD fields.

Extracts:
- Action keywords (visible, mandatory, validate, OCR, etc.)
- Document types (PAN, GSTIN, Bank, MSME, etc.)
- Conditions (if field X is Y then...)
- Source and destination field references
"""

import re
from typing import List, Optional, Tuple, Dict
from .models import ParsedLogic, ParsedCondition


class LogicParser:
    """Parse natural language logic statements from BUD fields."""

    # Patterns to SKIP (expression rules, execute rules)
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

    # OCR detection patterns
    OCR_PATTERNS = [
        (r"(?:from|using)\s+OCR", 0.95),
        (r"OCR\s+rule", 0.95),
        (r"Get\s+(\w+)\s+from\s+OCR", 0.95),
        (r"OCR\s+will\s+(?:be\s+)?perform", 0.90),
        (r"data\s+will\s+come\s+from\s+.*OCR", 0.90),
        (r"extract\s+from\s+(?:image|document)", 0.85),
    ]

    # VERIFY detection patterns
    VERIFY_PATTERNS = [
        (r"Perform\s+(\w+)\s+[Vv]alidation", 0.95),
        (r"(\w+)\s+validation\b", 0.90),
        (r"[Vv]alidate\s+(\w+)", 0.90),
        (r"[Vv]erify\s+(\w+)", 0.90),
        (r"(\w+)\s+verification\b", 0.85),
    ]

    # VERIFY DESTINATION patterns (these fields receive data, NOT trigger validation)
    VERIFY_DESTINATION_PATTERNS = [
        r"[Dd]ata\s+will\s+come\s+from\s+(\w+)\s+validation",
        r"[Dd]ata\s+will\s+come\s+from\s+(\w+)\s+verification",
        r"[Aa]uto-?derived\s+(?:via|from)\s+(\w+)\s+[Vv]alidation",
        r"[Pp]opulated?\s+from\s+(\w+)\s+validation",
        r"[Ff]rom\s+(\w+)\s+(?:validation|verification)\s+response",
    ]

    # Visibility detection patterns
    VISIBILITY_PATTERNS = [
        (r"(?:make\s+)?visible\s+(?:if|when)", 0.95),
        (r"(?:make\s+)?invisible", 0.95),
        (r"then\s+visible", 0.95),
        (r"otherwise\s+invisible", 0.95),
        (r"show\s+(?:this|field|when)", 0.90),
        (r"hide\s+(?:this|field|when)", 0.90),
        (r"hidden", 0.85),
    ]

    # Mandatory detection patterns
    MANDATORY_PATTERNS = [
        (r"(?:make\s+)?mandatory\s+(?:if|when)", 0.95),
        (r"then\s+(?:visible\s+and\s+)?mandatory", 0.95),
        (r"non-mandatory", 0.90),
        (r"otherwise.*non-mandatory", 0.90),
        (r"required\s+(?:if|when)", 0.85),
        (r"optional", 0.80),
    ]

    # Disabled/Non-editable patterns
    DISABLED_PATTERNS = [
        (r"[Nn]on-?[Ee]ditable", 0.95),
        (r"[Rr]ead-?[Oo]nly", 0.95),
        (r"[Dd]isable", 0.90),
        (r"[Nn]ot\s+editable", 0.90),
    ]

    # External dropdown patterns
    EXT_DROPDOWN_PATTERNS = [
        (r"external\s+dropdown", 0.95),
        (r"dropdown\s+values?\s+from\s+(?:table|excel|reference)", 0.90),
        (r"reference\s+table\s*:", 0.90),
        (r"parent\s+dropdown\s+field", 0.90),
        (r"values?\s+from\s+(?:sheet|excel)", 0.85),
        (r"cascading\s+dropdown", 0.85),
        (r"dependent\s+on\s+(?:field|dropdown)", 0.85),
        (r"filter(?:ed)?\s+by\s+parent", 0.85),
        (r"\.(xlsx?|xls)\b", 0.80),
        (r"master\s+(?:data|table|list)", 0.80),
        (r"lookup\s+(?:table|from)", 0.80),
    ]

    # External value patterns
    EXT_VALUE_PATTERNS = [
        (r"external\s+(?:data\s+)?value", 0.90),
        (r"value\s+from\s+(?:table|excel|external)", 0.85),
        (r"edv\s+rule", 0.90),
        (r"lookup\s+value", 0.85),
        (r"data\s+from\s+(?:reference|master)", 0.85),
        (r"auto-?populate\s+from", 0.80),
        (r"fetch\s+(?:from|value)", 0.80),
    ]

    # Document type detection - Only for actual VERIFY/OCR document types
    DOC_TYPE_PATTERNS = {
        "PAN": [r"\bPAN\b", r"pan\s+(?:number|validation|image|card)"],
        "GSTIN": [r"\bGSTIN?\b", r"gst\s+(?:number|validation|image)", r"\bGST\b(?!\s+Non)"],
        "BANK": [r"\bbank\b", r"ifsc", r"account\s+number", r"cancelled\s+cheque", r"cheque"],
        "MSME": [r"\bMSME\b", r"\bSSI\b", r"udyam", r"msme\s+(?:certificate|registration)"],
        "CIN": [r"\bCIN\b(?!\s+is)", r"cin\s+(?:number|validation)"],
        "AADHAAR": [r"\baadhaa?r\b", r"aadhar"],
        # Note: PIN_CODE is NOT a VERIFY document type - removed to prevent false positives
    }

    # Condition patterns for visibility/mandatory rules
    CONDITION_PATTERNS = [
        # "if the field 'X' value is Y then..."
        r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value\s+)?is\s+([^,\s]+(?:\s+or\s+[^,\s]+)*)\s+then",
        # "if field 'X' values is Y then..."
        r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+values?\s+is\s+([^,\s]+(?:\s+or\s+[^,\s]+)*)\s+then",
        # "if 'X' is Y then..."
        r"if\s+['\"]([^'\"]+)['\"]\s+is\s+([^,\s]+(?:\s+or\s+[^,\s]+)*)\s+then",
        # "when X is Y"
        r"when\s+['\"]?([^'\"]+)['\"]?\s+is\s+([^,\s]+)",
        # "if X is selected as Y"
        r"if\s+([^'\"]+?)\s+is\s+selected\s+as\s+([^,\s]+)",
        # "Make visible if X is Yes"
        r"[Mm]ake\s+(?:visible|mandatory)\s+if\s+['\"]([^'\"]+)['\"]\s+is\s+([^,\s]+)",
    ]

    def __init__(self):
        pass

    def should_skip(self, logic: str) -> bool:
        """
        Check if logic statement should be skipped (expression/execute rules).

        Args:
            logic: Logic text from BUD field

        Returns:
            True if the logic should be skipped
        """
        if not logic:
            return True

        for pattern in self.SKIP_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                return True
        return False

    def parse(self, logic: str, field_name: str = "", field_type: str = "") -> ParsedLogic:
        """
        Parse a logic statement from a BUD field.

        Args:
            logic: Logic text from the BUD field
            field_name: Name of the field (helps with context)
            field_type: Type of the field (FILE, TEXT, DROPDOWN, etc.)

        Returns:
            ParsedLogic with extracted information
        """
        result = ParsedLogic(original_text=logic or "")

        if not logic:
            return result

        logic_lower = logic.lower()

        # Check for VERIFY DESTINATION first (these don't trigger validation)
        for pattern in self.VERIFY_DESTINATION_PATTERNS:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                result.is_destination_only = True
                result.document_type = self._normalize_doc_type(match.group(1))
                break

        # Detect OCR
        for pattern, confidence in self.OCR_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                result.is_ocr = True
                result.confidence = max(result.confidence, confidence)
                result.action_keywords.append("OCR")
                break

        # Detect VERIFY (but not if it's a destination field)
        if not result.is_destination_only:
            for pattern, confidence in self.VERIFY_PATTERNS:
                match = re.search(pattern, logic, re.IGNORECASE)
                if match:
                    result.is_verify = True
                    result.confidence = max(result.confidence, confidence)
                    result.action_keywords.append("VERIFY")
                    # Extract document type from match
                    if match.groups():
                        result.document_type = self._normalize_doc_type(match.group(1))
                    break

        # Detect visibility rules
        for pattern, confidence in self.VISIBILITY_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                result.is_visibility = True
                result.confidence = max(result.confidence, confidence)
                if "invisible" in logic_lower:
                    result.action_keywords.append("MAKE_INVISIBLE")
                if "visible" in logic_lower and "invisible" not in logic_lower:
                    result.action_keywords.append("MAKE_VISIBLE")
                break

        # Detect mandatory rules
        for pattern, confidence in self.MANDATORY_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                result.is_mandatory = True
                result.confidence = max(result.confidence, confidence)
                if "non-mandatory" in logic_lower or "non mandatory" in logic_lower:
                    result.action_keywords.append("MAKE_NON_MANDATORY")
                elif "mandatory" in logic_lower:
                    result.action_keywords.append("MAKE_MANDATORY")
                break

        # Detect disabled/non-editable
        for pattern, confidence in self.DISABLED_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                result.is_disabled = True
                result.confidence = max(result.confidence, confidence)
                result.action_keywords.append("MAKE_DISABLED")
                break

        # Detect external dropdown
        if field_type in ["DROPDOWN", "MULTI_DROPDOWN", "EXTERNAL_DROP_DOWN",
                          "EXTERNAL_DROP_DOWN_VALUE", "EXTERNAL_DROP_DOWN_MULTISELECT"]:
            for pattern, confidence in self.EXT_DROPDOWN_PATTERNS:
                if re.search(pattern, logic, re.IGNORECASE):
                    result.is_ext_dropdown = True
                    result.confidence = max(result.confidence, confidence)
                    result.action_keywords.append("EXT_DROP_DOWN")
                    break

        # Detect external value
        for pattern, confidence in self.EXT_VALUE_PATTERNS:
            if re.search(pattern, logic, re.IGNORECASE):
                result.is_ext_value = True
                result.confidence = max(result.confidence, confidence)
                result.action_keywords.append("EXT_VALUE")
                break

        # Detect document type if not already found
        if not result.document_type:
            result.document_type = self._detect_document_type(logic, field_name)

        # Extract conditions for visibility/mandatory rules
        result.conditions = self._extract_conditions(logic)

        # Extract source field from conditions
        if result.conditions:
            result.source_field_name = result.conditions[0].source_field_name

        return result

    def _normalize_doc_type(self, doc_type: str) -> Optional[str]:
        """Normalize document type string."""
        if not doc_type:
            return None

        doc_type_upper = doc_type.upper().strip()

        # Direct mappings
        mappings = {
            "PAN": "PAN",
            "GSTIN": "GSTIN",
            "GST": "GSTIN",
            "BANK": "BANK",
            "MSME": "MSME",
            "SSI": "MSME",
            "CIN": "CIN",
            "AADHAAR": "AADHAAR",
            "AADHAR": "AADHAAR",
            "PIN": "PIN_CODE",
        }

        for key, value in mappings.items():
            if key in doc_type_upper:
                return value

        return doc_type_upper

    def _detect_document_type(self, logic: str, field_name: str = "") -> Optional[str]:
        """Detect document type from logic text or field name."""
        combined = f"{logic} {field_name}".upper()

        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return doc_type

        return None

    def _extract_conditions(self, logic: str) -> List[ParsedCondition]:
        """Extract conditions from logic text."""
        conditions = []

        for pattern in self.CONDITION_PATTERNS:
            matches = re.finditer(pattern, logic, re.IGNORECASE)
            for match in matches:
                field_name = match.group(1).strip()
                value_str = match.group(2).strip()

                # Parse multiple values (e.g., "yes or no")
                values = [v.strip() for v in re.split(r'\s+or\s+', value_str)]

                conditions.append(ParsedCondition(
                    source_field_name=field_name,
                    operator='in',
                    values=values
                ))

        return conditions

    def detect_ocr_source_type(self, logic: str, field_name: str) -> Optional[str]:
        """
        Detect the OCR source type from field name and logic.

        Returns sourceType like "PAN_IMAGE", "GSTIN_IMAGE", etc.
        """
        combined = f"{field_name} {logic}".lower()

        # Patterns for OCR source type detection
        ocr_type_patterns = {
            "PAN_IMAGE": [r"upload\s*pan", r"pan\s*(?:image|upload|file|copy)"],
            "GSTIN_IMAGE": [r"upload\s*gstin", r"gstin?\s*(?:image|upload|file|copy)"],
            "AADHAR_IMAGE": [r"aadhaa?r\s*front", r"front\s*aadhaa?r", r"aadhaa?r\s*(?:image|upload|copy)(?!\s*back)"],
            "AADHAR_BACK_IMAGE": [r"aadhaa?r\s*back", r"back\s*aadhaa?r"],
            "CHEQUEE": [r"cheque", r"cancelled\s*cheque", r"cancel\s*cheque"],
            "CIN": [r"cin\s*(?:image|upload|file|copy)", r"upload\s*cin"],
            "MSME": [r"msme\s*(?:image|upload|file|copy|certificate)", r"upload\s*msme", r"udyam\s*(?:image|upload)"],
        }

        for source_type, patterns in ocr_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined):
                    return source_type

        return None

    def detect_verify_source_type(self, logic: str, field_name: str) -> Optional[str]:
        """
        Detect the VERIFY source type from field name and logic.

        Returns sourceType like "PAN_NUMBER", "GSTIN", etc.

        IMPORTANT: Only detects actual VERIFY rules for key document types.
        PIN_CODE validation is NOT a VERIFY rule - it's handled differently.
        """
        combined = f"{field_name} {logic}".lower()

        # Skip if this is a destination field (data comes FROM validation)
        if re.search(r"data\s+will\s+come\s+from|auto-?derived\s+(?:from|via)", logic, re.IGNORECASE):
            return None

        # Patterns for VERIFY source type detection
        # ONLY include actual VERIFY rules that exist in Rule-Schemas.json
        verify_type_patterns = {
            "PAN_NUMBER": [
                r"perform\s+pan\s+validation",
                r"pan\s+validation\b(?!\s+response)",  # Not "pan validation response"
                r"validate\s+pan\b",
                r"verify\s+pan\b"
            ],
            "GSTIN": [
                r"perform\s+gstin?\s+validation",
                r"gstin?\s+validation\b(?!\s+response)",
                r"validate\s+gstin?\b",
                r"verify\s+gstin?\b"
            ],
            "BANK_ACCOUNT_NUMBER": [
                r"perform\s+bank\s+(?:account\s+)?validation",
                r"bank\s+(?:account\s+)?validation\b(?!\s+response)",
                r"validate\s+bank\b",
                r"verify\s+bank\b"
            ],
            "MSME_UDYAM_REG_NUMBER": [
                r"perform\s+msme\s+validation",
                r"msme\s+validation\b(?!\s+response)",
                r"validate\s+msme\b",
                r"verify\s+msme\b",
                r"udyam\s+validation\b"
            ],
            "CIN_ID": [
                r"perform\s+cin\s+validation",
                r"cin\s+validation\b(?!\s+response)",
                r"validate\s+cin\b",
                r"verify\s+cin\b"
            ],
            # PIN_CODE is NOT a VERIFY rule - it's a different rule type
            # Do NOT include it here
        }

        for source_type, patterns in verify_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined):
                    return source_type

        return None

    def extract_conditional_values(self, logic: str) -> Tuple[List[str], str]:
        """
        Extract conditional values and the condition type from logic.

        Returns:
            Tuple of (conditional_values, condition_type)
            condition_type is "IN" or "NOT_IN"
        """
        values = []
        condition_type = "IN"

        # Common value patterns
        value_patterns = [
            r"is\s+(?:selected\s+as\s+)?['\"]?([^'\"]+)['\"]?\s+then",
            r"value\s+is\s+['\"]?([^'\"]+)['\"]?\s+then",
            r"values?\s+is\s+['\"]?([^'\"]+)['\"]?\s+then",
        ]

        for pattern in value_patterns:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                value_str = match.group(1).strip()
                # Handle "yes or no" style
                values = [v.strip() for v in re.split(r'\s+or\s+', value_str)]
                break

        # Check if this is a "NOT" condition
        if re.search(r"otherwise|else|not\s+equal|!=", logic.lower()):
            # The primary condition uses IN, the else part uses NOT_IN
            pass

        return values, condition_type


def extract_controlling_field_name(logic: str) -> Optional[str]:
    """
    Extract the controlling field name from visibility/mandatory logic.

    Logic like: "if the field 'Please select GST option' values is yes then visible"
    Returns: "Please select GST option"
    """
    patterns = [
        r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]",
        r"if\s+['\"]([^'\"]+)['\"]\s+is",
        r"when\s+['\"]([^'\"]+)['\"]\s+is",
        r"Make\s+(?:visible|mandatory)\s+if\s+['\"]([^'\"]+)['\"]",
    ]

    for pattern in patterns:
        match = re.search(pattern, logic, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None
