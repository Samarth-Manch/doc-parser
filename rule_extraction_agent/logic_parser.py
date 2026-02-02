"""Parse natural language logic statements into structured data."""

import re
from typing import List, Dict, Optional, Tuple
from .models import ParsedLogic, Condition


# Patterns to skip (expression/execute rules)
SKIP_PATTERNS = [
    r"mvi\s*\(",
    r"mm\s*\(",
    r"expr-eval",
    r"\bEXECUTE\b",
    r"execute\s+rule",
    r"execute\s+script",
]

# Keyword patterns for different rule types
VISIBILITY_KEYWORDS = [
    "visible", "invisible", "show", "hide", "display", "hidden"
]

MANDATORY_KEYWORDS = [
    "mandatory", "non-mandatory", "required", "optional"
]

VALIDATION_KEYWORDS = [
    "validate", "validation", "verify", "verification", "check"
]

OCR_KEYWORDS = [
    "ocr", "extract", "scan", "get from image", "from file"
]

DISABLE_KEYWORDS = [
    "disable", "disabled", "non-editable", "read-only", "readonly", "non editable"
]

# Document type patterns for validation
DOC_TYPE_PATTERNS = {
    "pan": ["pan", "permanent account number"],
    "gstin": ["gstin", "gst", "goods and services tax"],
    "bank": ["bank", "ifsc", "account number"],
    "msme": ["msme", "udyam", "udyog"],
    "cin": ["cin", "corporate identification"],
    "tan": ["tan", "tax deduction"],
    "fssai": ["fssai", "food safety"],
    "aadhaar": ["aadhaar", "aadhar", "uid"],
}


class LogicParser:
    """Parse natural language logic statements into structured data."""

    def __init__(self):
        self.skip_patterns = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]

    def parse(self, logic_text: str) -> ParsedLogic:
        """
        Parse a logic statement into structured data.

        Args:
            logic_text: Natural language logic statement

        Returns:
            ParsedLogic with extracted keywords, actions, conditions, etc.
        """
        if not logic_text:
            return ParsedLogic(
                raw_text="",
                should_skip=True,
                skip_reason="Empty logic text"
            )

        # Check if should skip
        skip_reason = self._should_skip(logic_text)
        if skip_reason:
            return ParsedLogic(
                raw_text=logic_text,
                should_skip=True,
                skip_reason=skip_reason
            )

        # Extract components
        keywords = self._extract_keywords(logic_text)
        actions = self._determine_actions(logic_text, keywords)
        condition = self._extract_condition(logic_text)
        field_refs = self._extract_field_references(logic_text)
        doc_type = self._detect_doc_type(logic_text)

        # Calculate confidence
        confidence = self._calculate_confidence(
            logic_text, keywords, actions, condition
        )

        return ParsedLogic(
            raw_text=logic_text,
            keywords=keywords,
            actions=actions,
            condition=condition,
            field_refs=field_refs,
            doc_type=doc_type,
            confidence=confidence,
            should_skip=False,
        )

    def _should_skip(self, logic_text: str) -> Optional[str]:
        """Check if logic should be skipped."""
        for pattern in self.skip_patterns:
            if pattern.search(logic_text):
                return f"Matches skip pattern: {pattern.pattern}"
        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract action keywords from text."""
        keywords = []
        text_lower = text.lower()

        # Check visibility keywords
        for kw in VISIBILITY_KEYWORDS:
            if kw in text_lower:
                keywords.append(kw)

        # Check mandatory keywords
        for kw in MANDATORY_KEYWORDS:
            if kw in text_lower:
                keywords.append(kw)

        # Check validation keywords
        for kw in VALIDATION_KEYWORDS:
            if kw in text_lower:
                keywords.append(kw)

        # Check OCR keywords
        for kw in OCR_KEYWORDS:
            if kw in text_lower:
                keywords.append(kw)

        # Check disable keywords
        for kw in DISABLE_KEYWORDS:
            if kw in text_lower:
                keywords.append(kw)

        return list(set(keywords))

    def _determine_actions(self, text: str, keywords: List[str]) -> List[str]:
        """Determine rule action types based on text and keywords."""
        actions = []
        text_lower = text.lower()

        # OCR detection
        if any(kw in keywords for kw in OCR_KEYWORDS):
            if re.search(r"(from|using)\s+ocr|ocr\s+rule|get\s+\w+\s+from\s+ocr", text_lower):
                actions.append("OCR")

        # VERIFY detection (not destination fields)
        if any(kw in keywords for kw in VALIDATION_KEYWORDS):
            # Skip if this is a destination field
            if not re.search(r"data\s+will\s+come\s+from", text_lower):
                if re.search(r"perform\s+\w+\s+validation|validate\s+\w+", text_lower):
                    actions.append("VERIFY")

        # Visibility detection
        if "visible" in keywords or "show" in keywords:
            if "invisible" not in text_lower and "hidden" not in text_lower:
                actions.append("MAKE_VISIBLE")

        if "invisible" in keywords or "hide" in keywords or "hidden" in keywords:
            actions.append("MAKE_INVISIBLE")

        # Mandatory detection
        if "mandatory" in keywords or "required" in keywords:
            if "non-mandatory" not in text_lower and "non mandatory" not in text_lower:
                actions.append("MAKE_MANDATORY")

        if "non-mandatory" in text_lower or "non mandatory" in text_lower or "optional" in keywords:
            actions.append("MAKE_NON_MANDATORY")

        # Disabled detection
        if any(kw in keywords for kw in DISABLE_KEYWORDS):
            actions.append("MAKE_DISABLED")

        # Convert to upper case detection
        if "upper case" in text_lower or "uppercase" in text_lower:
            actions.append("CONVERT_TO_UPPER")

        return list(set(actions))

    def _extract_condition(self, text: str) -> Optional[Condition]:
        """Extract conditional logic from text."""
        # Pattern: "if field 'X' is/values is Y then ..."
        patterns = [
            # "if the field 'X' values is Y then"
            r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value[s]?\s+is|is)\s+([^,\s]+(?:\s+[^,\s]+)?)\s+then",
            # "if 'X' is Y then"
            r"if\s+['\"]([^'\"]+)['\"]\s+is\s+([^,\s]+)\s+then",
            # "when field 'X' is Y"
            r"when\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+is\s+([^,\s]+)",
            # "based on X selection"
            r"based\s+on\s+(?:the\s+)?['\"]?([^'\"]+?)['\"]?\s+selection",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return Condition(
                        field=groups[0].strip(),
                        operator="==",
                        value=groups[1].strip(),
                        raw_text=match.group(0)
                    )
                elif len(groups) == 1:
                    return Condition(
                        field=groups[0].strip(),
                        operator="depends_on",
                        value=None,
                        raw_text=match.group(0)
                    )

        return None

    def _extract_field_references(self, text: str) -> List[str]:
        """Extract field names referenced in the logic."""
        field_refs = []

        # Pattern: field names in quotes
        quoted_fields = re.findall(r"['\"]([^'\"]+)['\"]", text)
        field_refs.extend(quoted_fields)

        # Pattern: "field X" or "the X field"
        field_patterns = [
            r"field\s+([A-Z][a-zA-Z\s]+)",
            r"the\s+([A-Z][a-zA-Z\s]+)\s+field",
        ]

        for pattern in field_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            field_refs.extend(matches)

        # Clean and dedupe
        cleaned = []
        for ref in field_refs:
            ref = ref.strip()
            if ref and len(ref) > 2 and ref not in cleaned:
                cleaned.append(ref)

        return cleaned

    def _detect_doc_type(self, text: str) -> Optional[str]:
        """Detect document type mentioned in logic."""
        text_lower = text.lower()

        for doc_type, patterns in DOC_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return doc_type.upper()

        return None

    def _calculate_confidence(
        self,
        text: str,
        keywords: List[str],
        actions: List[str],
        condition: Optional[Condition]
    ) -> float:
        """Calculate confidence score for the parsing result."""
        confidence = 0.5  # Base confidence

        # More keywords = higher confidence
        if keywords:
            confidence += min(len(keywords) * 0.1, 0.3)

        # Matched actions = higher confidence
        if actions:
            confidence += min(len(actions) * 0.15, 0.3)

        # Condition extracted = higher confidence
        if condition:
            confidence += 0.1

        # Penalize for ambiguity
        if len(actions) > 3:
            confidence -= 0.1

        return min(max(confidence, 0.0), 1.0)

    def parse_visibility_logic(self, text: str) -> Dict:
        """
        Parse visibility-specific logic.

        Returns dict with:
        - controlling_field: Field that controls visibility
        - visible_when: Value(s) for visible
        - invisible_when: Value(s) for invisible
        """
        result = {
            "controlling_field": None,
            "visible_when": [],
            "invisible_when": [],
        }

        # Extract controlling field
        field_match = re.search(
            r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]",
            text, re.IGNORECASE
        )
        if field_match:
            result["controlling_field"] = field_match.group(1)

        # Extract visible values
        visible_match = re.search(
            r"(?:values?\s+is|is)\s+([^,]+?)\s+then\s+visible",
            text, re.IGNORECASE
        )
        if visible_match:
            result["visible_when"].append(visible_match.group(1).strip())

        # Extract invisible values
        invisible_match = re.search(
            r"otherwise\s+invisible|(?:if|when).*?([^,]+?)\s+then\s+invisible",
            text, re.IGNORECASE
        )
        if invisible_match:
            if invisible_match.group(0).startswith("otherwise"):
                result["invisible_when"].append("otherwise")
            else:
                result["invisible_when"].append(invisible_match.group(1).strip())

        return result

    def is_destination_field(self, text: str) -> bool:
        """Check if this field is a destination of another rule."""
        patterns = [
            r"data\s+will\s+come\s+from",
            r"populated\s+from",
            r"derived\s+from",
            r"auto-?fill(?:ed)?\s+from",
            r"value\s+(?:comes?|derived)\s+from",
        ]

        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def detect_ocr_source_type(self, text: str, field_name: str) -> Optional[str]:
        """Detect OCR source type from logic and field name."""
        combined = f"{field_name} {text}".lower()

        # OCR source type mappings
        ocr_mappings = [
            (r"upload\s*pan|pan\s*(?:image|upload|file)", "PAN_IMAGE"),
            (r"upload\s*gstin|gstin\s*(?:image|upload|file)", "GSTIN_IMAGE"),
            (r"aadhaa?r\s*front|front\s*aadhaa?r", "AADHAR_IMAGE"),
            (r"aadhaa?r\s*back|back\s*aadhaa?r", "AADHAR_BACK_IMAGE"),
            (r"cheque|cancelled\s*cheque", "CHEQUEE"),
            (r"cin\s*(?:image|upload|file)|upload\s*cin", "CIN"),
            (r"msme\s*(?:image|upload|file)|upload\s*msme|udyam", "MSME"),
        ]

        for pattern, source_type in ocr_mappings:
            if re.search(pattern, combined, re.IGNORECASE):
                return source_type

        return None

    def detect_verify_source_type(self, text: str, field_name: str) -> Optional[str]:
        """Detect VERIFY source type from logic and field name."""
        combined = f"{field_name} {text}".lower()

        # Skip destination fields
        if self.is_destination_field(text):
            return None

        # VERIFY source type mappings
        verify_mappings = [
            (r"pan\s+validation|validate\s+pan", "PAN_NUMBER"),
            (r"gstin?\s+validation|validate\s+gstin?", "GSTIN"),
            (r"bank\s+(?:account\s+)?validation|validate\s+bank|ifsc\s+validation", "BANK_ACCOUNT_NUMBER"),
            (r"msme\s+validation|validate\s+msme|udyam\s+validation", "MSME_UDYAM_REG_NUMBER"),
            (r"cin\s+validation|validate\s+cin", "CIN_ID"),
            (r"tan\s+validation|validate\s+tan", "TAN_NUMBER"),
            (r"fssai\s+validation|validate\s+fssai", "FSSAI"),
        ]

        for pattern, source_type in verify_mappings:
            if re.search(pattern, combined, re.IGNORECASE):
                return source_type

        return None
