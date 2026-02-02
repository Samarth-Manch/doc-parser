"""Deterministic pattern-based matcher."""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class MatchResult:
    """Result of pattern matching."""
    action_type: str
    source_type: Optional[str] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    pattern_matched: str = ""
    conditional_values: List[str] = None
    condition: str = ""

    def __post_init__(self):
        if self.conditional_values is None:
            self.conditional_values = []


class DeterministicMatcher:
    """Pattern-based deterministic matcher for rule extraction."""

    def __init__(self):
        self._build_patterns()

    def _build_patterns(self):
        """Build all matching patterns."""
        # Visibility patterns
        self.patterns = {
            "visibility": [
                (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
                (r"then\s+visible", "MAKE_VISIBLE", 0.90),
                (r"show\s+(?:this|field)", "MAKE_VISIBLE", 0.85),
                (r"(?:make\s+)?invisible|hide", "MAKE_INVISIBLE", 0.95),
                (r"otherwise\s+invisible", "MAKE_INVISIBLE", 0.90),
            ],
            "mandatory": [
                (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
                (r"then\s+(?:visible\s+and\s+)?mandatory", "MAKE_MANDATORY", 0.90),
                (r"required\s+(?:if|when)", "MAKE_MANDATORY", 0.85),
                (r"non-?mandatory", "MAKE_NON_MANDATORY", 0.90),
                (r"otherwise\s+(?:invisible\s+and\s+)?non-?mandatory", "MAKE_NON_MANDATORY", 0.85),
            ],
            "disable": [
                (r"non-?editable", "MAKE_DISABLED", 0.95),
                (r"read-?only", "MAKE_DISABLED", 0.95),
                (r"disable|disabled", "MAKE_DISABLED", 0.90),
                (r"system\s+generated", "MAKE_DISABLED", 0.85),
            ],
            "verify": [
                (r"(?:PAN|pan)\s+(?:validation|verify)", "VERIFY:PAN_NUMBER", 0.95),
                (r"(?:perform|do)\s+(?:PAN|pan)\s+validation", "VERIFY:PAN_NUMBER", 0.95),
                (r"validate\s+(?:PAN|pan)", "VERIFY:PAN_NUMBER", 0.95),
                (r"(?:GSTIN?|gst)\s+(?:validation|verify)", "VERIFY:GSTIN", 0.95),
                (r"(?:perform|do)\s+(?:GSTIN?|gst)\s+validation", "VERIFY:GSTIN", 0.95),
                (r"validate\s+(?:GSTIN?|gst)", "VERIFY:GSTIN", 0.95),
                (r"bank\s+(?:account\s+)?validation", "VERIFY:BANK_ACCOUNT_NUMBER", 0.95),
                (r"validate\s+bank", "VERIFY:BANK_ACCOUNT_NUMBER", 0.90),
                (r"(?:MSME|msme|udyam)\s+validation", "VERIFY:MSME_UDYAM_REG_NUMBER", 0.95),
                (r"(?:CIN|cin)\s+validation", "VERIFY:CIN_ID", 0.95),
                (r"(?:TAN|tan)\s+validation", "VERIFY:TAN_NUMBER", 0.95),
                (r"(?:FSSAI|fssai)\s+validation", "VERIFY:FSSAI", 0.95),
            ],
            "ocr": [
                (r"(?:from|using)\s+OCR", "OCR", 0.95),
                (r"OCR\s+rule", "OCR", 0.95),
                (r"[Gg]et\s+\w+\s+from\s+OCR", "OCR", 0.95),
                (r"extract\s+from\s+(?:image|document)", "OCR", 0.85),
            ],
        }

        # OCR source type patterns
        self.ocr_source_patterns = [
            (r"upload\s*pan|pan\s*(?:image|upload|file)", "PAN_IMAGE"),
            (r"upload\s*gstin|gstin\s*(?:image|upload|file)", "GSTIN_IMAGE"),
            (r"aadhaa?r\s*front|front\s*aadhaa?r", "AADHAR_IMAGE"),
            (r"aadhaa?r\s*back|back\s*aadhaa?r", "AADHAR_BACK_IMAGE"),
            (r"cheque|cancelled\s*cheque", "CHEQUEE"),
            (r"cin\s*(?:image|upload|file)|upload\s*cin", "CIN"),
            (r"msme\s*(?:image|upload|file)|upload\s*msme|udyam", "MSME"),
        ]

        # Patterns that indicate destination field
        self.destination_patterns = [
            r"data\s+will\s+come\s+from",
            r"populated\s+from",
            r"derived\s+from",
            r"auto-?fill(?:ed)?\s+from",
        ]

    def match(self, logic_text: str, field_name: str = "") -> List[MatchResult]:
        """
        Match logic text to rule patterns.

        Args:
            logic_text: Natural language logic statement
            field_name: Name of the field (helps with context)

        Returns:
            List of MatchResult objects
        """
        if not logic_text:
            return []

        results = []
        text_lower = logic_text.lower()
        combined = f"{field_name} {logic_text}".lower()

        # Check if destination field
        is_destination = self._is_destination(text_lower)

        # Match visibility patterns
        for pattern, action, conf in self.patterns["visibility"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                results.append(MatchResult(
                    action_type=action,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Match mandatory patterns
        for pattern, action, conf in self.patterns["mandatory"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                results.append(MatchResult(
                    action_type=action,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Match disable patterns
        for pattern, action, conf in self.patterns["disable"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                results.append(MatchResult(
                    action_type=action,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Match verify patterns (only if not destination)
        if not is_destination:
            for pattern, action_source, conf in self.patterns["verify"]:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    parts = action_source.split(":")
                    results.append(MatchResult(
                        action_type=parts[0],
                        source_type=parts[1] if len(parts) > 1 else None,
                        confidence=conf,
                        pattern_matched=pattern,
                    ))

        # Match OCR patterns
        for pattern, action, conf in self.patterns["ocr"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Detect OCR source type
                source_type = self._detect_ocr_source(combined)
                results.append(MatchResult(
                    action_type=action,
                    source_type=source_type,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Check for CONVERT_TO upper case
        if re.search(r"upper\s*case", text_lower):
            results.append(MatchResult(
                action_type="CONVERT_TO",
                source_type="UPPER_CASE",
                confidence=0.90,
                pattern_matched="upper case",
            ))

        # Extract conditional values if present
        for result in results:
            if result.action_type in ["MAKE_VISIBLE", "MAKE_INVISIBLE", "MAKE_MANDATORY", "MAKE_NON_MANDATORY"]:
                cond_values, condition = self._extract_condition(logic_text)
                result.conditional_values = cond_values
                result.condition = condition

        return results

    def _is_destination(self, text: str) -> bool:
        """Check if this is a destination field."""
        for pattern in self.destination_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _detect_ocr_source(self, text: str) -> Optional[str]:
        """Detect OCR source type."""
        for pattern, source_type in self.ocr_source_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return source_type
        return None

    def _extract_condition(self, text: str) -> Tuple[List[str], str]:
        """Extract conditional values and condition type."""
        # Pattern: "if field 'X' is/values is Y"
        match = re.search(
            r"(?:value[s]?\s+is|is)\s+([^,\s]+(?:\s+[^,\s]+)?)\s+then",
            text, re.IGNORECASE
        )

        if match:
            value = match.group(1).strip().strip("'\"")
            return [value], "IN"

        # Check for NOT_IN pattern
        match = re.search(
            r"otherwise|not\s+(?:equal|in)",
            text, re.IGNORECASE
        )

        if match:
            return [], "NOT_IN"

        return [], ""

    def get_confidence(self, results: List[MatchResult]) -> float:
        """Get overall confidence from results."""
        if not results:
            return 0.0
        return max(r.confidence for r in results)

    def needs_llm(self, results: List[MatchResult], threshold: float = 0.7) -> bool:
        """Check if LLM fallback is needed."""
        return self.get_confidence(results) < threshold
