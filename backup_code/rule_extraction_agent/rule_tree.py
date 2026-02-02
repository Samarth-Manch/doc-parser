"""
Rule Selection Tree - Deterministically select rules based on keywords and patterns.
"""

import re
from typing import List, Optional, Dict, Tuple
from .models import ParsedLogic, RuleSelection


# Pattern configurations with confidence scores
PATTERNS = {
    "visibility": [
        (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
        (r"then\s+visible", "MAKE_VISIBLE", 0.95),
        (r"(?:make\s+)?invisible|hide|hidden", "MAKE_INVISIBLE", 0.95),
        (r"show\s+(?:this|the|field)", "MAKE_VISIBLE", 0.90),
        (r"otherwise\s+invisible", "MAKE_INVISIBLE", 0.90),
    ],
    "mandatory": [
        (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
        (r"then\s+mandatory", "MAKE_MANDATORY", 0.95),
        (r"non-mandatory|optional", "MAKE_NON_MANDATORY", 0.90),
        (r"required\s+(?:if|when)", "MAKE_MANDATORY", 0.85),
        (r"otherwise\s+(?:non-mandatory|optional)", "MAKE_NON_MANDATORY", 0.90),
    ],
    "disable": [
        (r"non-editable|noneditable|not editable", "MAKE_DISABLED", 0.95),
        (r"read-only|readonly", "MAKE_DISABLED", 0.95),
        (r"disable(?:d)?(?:\s+field)?", "MAKE_DISABLED", 0.90),
    ],
    "verify": [
        (r"perform\s+(?:PAN|GSTIN|GST|bank|MSME|CIN)\s+validation", "VERIFY", 0.95),
        (r"(?:PAN|GSTIN|GST|bank|MSME|CIN)\s+validation", "VERIFY", 0.90),
        (r"validate\s+(?:PAN|GSTIN|GST|bank|MSME|CIN)", "VERIFY", 0.90),
        (r"verify\s+(?:PAN|GSTIN|GST|bank|MSME|CIN)", "VERIFY", 0.90),
        (r"perform\s+\w+\s+verification", "VERIFY", 0.85),
    ],
    "ocr": [
        (r"(?:get|from|using)\s+OCR", "OCR", 0.95),
        (r"OCR\s+rule", "OCR", 0.95),
        (r"extract\s+(?:from\s+)?(?:image|document)", "OCR", 0.85),
        (r"data\s+will\s+come\s+from\s+.*OCR", "OCR", 0.90),
        (r"perform\s+.*OCR", "OCR", 0.90),
    ],
    "ext_dropdown": [
        (r"dropdown\s+values?\s+(?:from|based)", "EXT_DROP_DOWN", 0.90),
        (r"reference\s+table", "EXT_DROP_DOWN", 0.85),
        (r"external\s+data", "EXT_VALUE", 0.85),
        (r"parent\s+dropdown\s+field", "EXT_DROP_DOWN", 0.90),
        (r"cascading\s+dropdown", "EXT_DROP_DOWN", 0.90),
    ],
    "copy": [
        (r"copy\s+(?:from|to)", "COPY_TO", 0.85),
        (r"derive(?:d)?\s+(?:from|as)", "COPY_TO", 0.80),
        (r"auto-?populate", "COPY_TO", 0.85),
    ],
    "convert": [
        (r"upper\s*case", "CONVERT_TO", 0.90),
        (r"convert\s+to", "CONVERT_TO", 0.85),
    ],
}

# VERIFY source type mappings
VERIFY_SOURCE_TYPES = {
    'pan': ('PAN_NUMBER', 360),
    'gstin': ('GSTIN', 355),
    'gst': ('GSTIN', 355),
    'bank': ('BANK_ACCOUNT_NUMBER', 361),
    'ifsc': ('BANK_ACCOUNT_NUMBER', 361),
    'msme': ('MSME_UDYAM_REG_NUMBER', 337),
    'udyam': ('MSME_UDYAM_REG_NUMBER', 337),
    'cin': ('CIN_ID', 349),
    'tan': ('TAN_NUMBER', 322),
    'fssai': ('FSSAI', 356),
}

# OCR source type mappings
OCR_SOURCE_TYPES = {
    'pan': ('PAN_IMAGE', 344),
    'upload pan': ('PAN_IMAGE', 344),
    'gstin': ('GSTIN_IMAGE', 347),
    'gstin image': ('GSTIN_IMAGE', 347),
    'gst': ('GSTIN_IMAGE', 347),
    'aadhaar front': ('AADHAR_IMAGE', 359),
    'aadhar front': ('AADHAR_IMAGE', 359),
    'aadhaar back': ('AADHAR_BACK_IMAGE', 348),
    'aadhar back': ('AADHAR_BACK_IMAGE', 348),
    'cheque': ('CHEQUEE', 269),
    'cancelled cheque': ('CHEQUEE', 269),
    'msme': ('MSME', 214),
    'cin': ('CIN', None),
}


class RuleTree:
    """Decision tree for rule selection."""

    def __init__(self):
        self.patterns = PATTERNS
        self.verify_sources = VERIFY_SOURCE_TYPES
        self.ocr_sources = OCR_SOURCE_TYPES

    def select_rules(self, parsed_logic: ParsedLogic) -> List[RuleSelection]:
        """
        Select rules based on parsed logic.

        Args:
            parsed_logic: Parsed logic from LogicParser.

        Returns:
            List of RuleSelection objects for matching rules.
        """
        if parsed_logic.should_skip:
            return []

        selections = []
        logic = parsed_logic.original_text

        # Check each pattern category
        for category, patterns in self.patterns.items():
            for pattern, action_type, confidence in patterns:
                if re.search(pattern, logic, re.IGNORECASE):
                    selection = RuleSelection(
                        action_type=action_type,
                        confidence=confidence,
                        match_reason=f"Matched pattern: {pattern}"
                    )

                    # Enhance with source type for VERIFY/OCR
                    if action_type == "VERIFY":
                        self._add_verify_source(selection, logic)
                    elif action_type == "OCR":
                        self._add_ocr_source(selection, logic)

                    # Check if needs LLM fallback
                    if confidence < 0.7:
                        selection.needs_llm_fallback = True

                    selections.append(selection)

        # Deduplicate by action type (keep highest confidence)
        return self._deduplicate_selections(selections)

    def _add_verify_source(self, selection: RuleSelection, logic: str):
        """Add source type for VERIFY rule."""
        logic_lower = logic.lower()

        for keyword, (source_type, schema_id) in self.verify_sources.items():
            if keyword in logic_lower:
                selection.source_type = source_type
                selection.schema_id = schema_id
                break

    def _add_ocr_source(self, selection: RuleSelection, logic: str):
        """Add source type for OCR rule."""
        logic_lower = logic.lower()

        for keyword, (source_type, schema_id) in self.ocr_sources.items():
            if keyword in logic_lower:
                selection.source_type = source_type
                selection.schema_id = schema_id
                break

    def _deduplicate_selections(self, selections: List[RuleSelection]) -> List[RuleSelection]:
        """Deduplicate selections by action type, keeping highest confidence."""
        by_action: Dict[str, RuleSelection] = {}

        for selection in selections:
            key = f"{selection.action_type}:{selection.source_type or ''}"
            if key not in by_action or selection.confidence > by_action[key].confidence:
                by_action[key] = selection

        return list(by_action.values())

    def select_from_keywords(self, keywords: List[str]) -> List[RuleSelection]:
        """
        Select rules based on extracted keywords.

        Args:
            keywords: List of keywords from logic.

        Returns:
            List of RuleSelection objects.
        """
        selections = []
        keywords_lower = [k.lower() for k in keywords]

        # Visibility keywords
        if 'visible' in keywords_lower and 'invisible' not in keywords_lower:
            selections.append(RuleSelection(
                action_type="MAKE_VISIBLE",
                confidence=0.85,
                match_reason="Keyword: visible"
            ))
        if 'invisible' in keywords_lower or 'hidden' in keywords_lower:
            selections.append(RuleSelection(
                action_type="MAKE_INVISIBLE",
                confidence=0.85,
                match_reason="Keyword: invisible/hidden"
            ))

        # Mandatory keywords
        if 'mandatory' in keywords_lower and 'non-mandatory' not in ' '.join(keywords_lower):
            selections.append(RuleSelection(
                action_type="MAKE_MANDATORY",
                confidence=0.85,
                match_reason="Keyword: mandatory"
            ))
        if 'optional' in keywords_lower or 'non-mandatory' in ' '.join(keywords_lower):
            selections.append(RuleSelection(
                action_type="MAKE_NON_MANDATORY",
                confidence=0.85,
                match_reason="Keyword: optional/non-mandatory"
            ))

        # Disabled keywords
        if any(kw in keywords_lower for kw in ['disable', 'disabled', 'non-editable', 'readonly']):
            selections.append(RuleSelection(
                action_type="MAKE_DISABLED",
                confidence=0.85,
                match_reason="Keyword: disable/non-editable"
            ))

        return selections


class DeterministicMatcher:
    """Deterministic pattern matcher for rule extraction."""

    def __init__(self):
        self.rule_tree = RuleTree()

    def match(self, logic_text: str) -> RuleSelection:
        """
        Match logic text to a rule using deterministic patterns.

        Args:
            logic_text: Natural language logic text.

        Returns:
            RuleSelection with matched rule or fallback indicator.
        """
        from .logic_parser import LogicParser

        # Parse the logic
        parser = LogicParser()
        parsed = parser.parse(logic_text)

        # Check if should skip
        if parsed.should_skip:
            return RuleSelection(
                action_type="SKIP",
                confidence=1.0,
                match_reason="Expression/Execute rule - skipped"
            )

        # Get selections from tree
        selections = self.rule_tree.select_rules(parsed)

        if not selections:
            # No match - needs LLM fallback
            return RuleSelection(
                action_type="UNKNOWN",
                confidence=0.0,
                match_reason="No pattern match",
                needs_llm_fallback=True,
                possible_action_types=parsed.actions
            )

        # Return highest confidence selection
        best = max(selections, key=lambda s: s.confidence)
        return best

    def match_all(self, logic_text: str) -> List[RuleSelection]:
        """
        Match logic text to all applicable rules.

        Args:
            logic_text: Natural language logic text.

        Returns:
            List of all matching RuleSelections.
        """
        from .logic_parser import LogicParser

        parser = LogicParser()
        parsed = parser.parse(logic_text)

        if parsed.should_skip:
            return []

        return self.rule_tree.select_rules(parsed)


def is_destination_field_logic(logic: str) -> bool:
    """
    Check if logic indicates this field is a destination (not source).

    Fields with "Data will come from X validation" are destinations,
    not sources of VERIFY rules.
    """
    if re.search(r"data\s+will\s+come\s+from", logic, re.IGNORECASE):
        return True

    if re.search(r"auto-?derived\s+(?:from|via)", logic, re.IGNORECASE):
        return True

    if re.search(r"populated?\s+from", logic, re.IGNORECASE):
        return True

    return False


def detect_visibility_source(logic: str) -> Optional[str]:
    """
    Detect the controlling field for a visibility rule.

    Returns field name that controls visibility, or None.
    """
    # Pattern: if field 'X' value is Y then visible
    pattern = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]"
    match = re.search(pattern, logic, re.IGNORECASE)
    if match:
        return match.group(1)

    return None
