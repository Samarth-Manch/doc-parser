"""Decision tree for deterministic rule selection."""

import re
from typing import List, Dict, Optional, Tuple
from .models import RuleSelection, ParsedLogic
from .schema_lookup import VERIFY_SCHEMAS, OCR_SCHEMAS


class RuleTree:
    """Decision tree for selecting rules based on keywords and patterns."""

    def __init__(self):
        self._build_patterns()

    def _build_patterns(self):
        """Build pattern matching rules."""
        # Pattern format: (regex, action_type, source_type, confidence)
        self.visibility_patterns = [
            (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", None, 0.95),
            (r"then\s+visible", "MAKE_VISIBLE", None, 0.90),
            (r"show\s+(?:this|field|when)", "MAKE_VISIBLE", None, 0.85),
            (r"(?:make\s+)?invisible|hide(?:n)?", "MAKE_INVISIBLE", None, 0.95),
            (r"otherwise\s+invisible", "MAKE_INVISIBLE", None, 0.90),
        ]

        self.mandatory_patterns = [
            (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", None, 0.95),
            (r"then\s+mandatory", "MAKE_MANDATORY", None, 0.90),
            (r"required\s+(?:if|when)", "MAKE_MANDATORY", None, 0.85),
            (r"non-?mandatory|optional", "MAKE_NON_MANDATORY", None, 0.90),
            (r"otherwise\s+non-?mandatory", "MAKE_NON_MANDATORY", None, 0.85),
        ]

        self.disable_patterns = [
            (r"non-?editable", "MAKE_DISABLED", None, 0.95),
            (r"read-?only", "MAKE_DISABLED", None, 0.95),
            (r"disable(?:d)?", "MAKE_DISABLED", None, 0.90),
            (r"system\s+generated", "MAKE_DISABLED", None, 0.85),
        ]

        self.verify_patterns = [
            (r"pan\s+validation|validate\s+pan|perform\s+pan", "VERIFY", "PAN_NUMBER", 0.95),
            (r"gstin?\s+validation|validate\s+gstin?|perform\s+gstin?", "VERIFY", "GSTIN", 0.95),
            (r"bank\s+(?:account\s+)?validation|validate\s+bank", "VERIFY", "BANK_ACCOUNT_NUMBER", 0.95),
            (r"ifsc\s+validation", "VERIFY", "BANK_ACCOUNT_NUMBER", 0.90),
            (r"msme\s+validation|validate\s+msme|udyam\s+validation", "VERIFY", "MSME_UDYAM_REG_NUMBER", 0.95),
            (r"cin\s+validation|validate\s+cin", "VERIFY", "CIN_ID", 0.95),
            (r"tan\s+validation|validate\s+tan", "VERIFY", "TAN_NUMBER", 0.95),
            (r"fssai\s+validation|validate\s+fssai", "VERIFY", "FSSAI", 0.95),
        ]

        self.ocr_patterns = [
            (r"(?:from|using)\s+ocr", "OCR", None, 0.95),
            (r"ocr\s+rule", "OCR", None, 0.95),
            (r"get\s+\w+\s+from\s+ocr", "OCR", None, 0.95),
            (r"extract\s+from\s+(?:image|document)", "OCR", None, 0.85),
            (r"data\s+will\s+come\s+from\s+.*ocr", "OCR", None, 0.90),
        ]

        # Patterns that indicate this field is a DESTINATION, not source
        self.destination_patterns = [
            r"data\s+will\s+come\s+from",
            r"populated\s+from",
            r"derived\s+from",
            r"auto-?fill(?:ed)?\s+from",
            r"value\s+(?:comes?|derived)\s+from",
            r"store\s+(?:the\s+)?data\s+in",
            r"next\s+fields",
        ]

    def select_rules(self, parsed_logic: ParsedLogic) -> List[RuleSelection]:
        """
        Select rules based on parsed logic.

        Args:
            parsed_logic: Parsed logic statement

        Returns:
            List of RuleSelection objects
        """
        if parsed_logic.should_skip:
            return []

        text = parsed_logic.raw_text.lower()
        selections = []

        # Check if this is a destination field
        is_destination = self._is_destination_field(text)

        # Check visibility patterns
        for pattern, action, source, conf in self.visibility_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                selections.append(RuleSelection(
                    action_type=action,
                    source_type=source,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Check mandatory patterns
        for pattern, action, source, conf in self.mandatory_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                selections.append(RuleSelection(
                    action_type=action,
                    source_type=source,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Check disable patterns
        for pattern, action, source, conf in self.disable_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                selections.append(RuleSelection(
                    action_type=action,
                    source_type=source,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Check VERIFY patterns (only if not a destination field)
        if not is_destination:
            for pattern, action, source, conf in self.verify_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    schema_id = VERIFY_SCHEMAS.get(source)
                    selections.append(RuleSelection(
                        action_type=action,
                        source_type=source,
                        schema_id=schema_id,
                        confidence=conf,
                        pattern_matched=pattern,
                    ))

        # Check OCR patterns
        for pattern, action, source, conf in self.ocr_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                selections.append(RuleSelection(
                    action_type=action,
                    source_type=source,
                    confidence=conf,
                    pattern_matched=pattern,
                ))

        # Check for CONVERT_TO upper case
        if re.search(r"upper\s*case", text, re.IGNORECASE):
            selections.append(RuleSelection(
                action_type="CONVERT_TO",
                source_type="UPPER_CASE",
                confidence=0.90,
                pattern_matched="upper case",
            ))

        # Deduplicate by action_type
        seen = set()
        unique_selections = []
        for sel in selections:
            key = (sel.action_type, sel.source_type)
            if key not in seen:
                seen.add(key)
                unique_selections.append(sel)

        return unique_selections

    def _is_destination_field(self, text: str) -> bool:
        """Check if this field is a destination of another rule."""
        for pattern in self.destination_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def detect_ocr_source_type(self, field_name: str, logic_text: str) -> Optional[str]:
        """Detect OCR source type from field name and logic."""
        combined = f"{field_name} {logic_text}".lower()

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

    def detect_verify_source_type(self, field_name: str, logic_text: str) -> Optional[str]:
        """Detect VERIFY source type from field name and logic."""
        combined = f"{field_name} {logic_text}".lower()

        # Skip destination fields
        if self._is_destination_field(logic_text):
            return None

        # Check patterns
        for pattern, action, source, conf in self.verify_patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return source

        return None

    def get_selection_confidence(self, selections: List[RuleSelection]) -> float:
        """Get overall confidence for a list of selections."""
        if not selections:
            return 0.0
        return max(s.confidence for s in selections)

    def needs_llm_fallback(self, selections: List[RuleSelection], threshold: float = 0.7) -> bool:
        """Check if LLM fallback is needed."""
        if not selections:
            return True
        return self.get_selection_confidence(selections) < threshold


class VisibilityGrouper:
    """Group fields by controlling field for visibility rules."""

    def __init__(self):
        self.groups: Dict[str, List[Dict]] = {}

    def add_field(self, field: Dict, logic_text: str):
        """
        Add a field to visibility groups based on its logic.

        If the logic references another field as controller, group it.
        """
        if not logic_text:
            return

        # Pattern: "if field 'X' is Y then visible"
        match = re.search(
            r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"].*then\s+(visible|mandatory|invisible)",
            logic_text, re.IGNORECASE
        )

        if match:
            controlling_field = match.group(1).strip()
            action = match.group(2).lower()

            if controlling_field not in self.groups:
                self.groups[controlling_field] = []

            self.groups[controlling_field].append({
                "field": field,
                "action": action,
                "logic": logic_text,
            })

    def get_groups(self) -> Dict[str, List[Dict]]:
        """Get all visibility groups."""
        return self.groups

    def get_controlled_fields(self, controlling_field: str) -> List[Dict]:
        """Get all fields controlled by a specific field."""
        return self.groups.get(controlling_field, [])

    def is_controlling_field(self, field_name: str) -> bool:
        """Check if a field controls other fields."""
        # Normalize for comparison
        normalized = field_name.lower().strip()
        for ctrl in self.groups.keys():
            if ctrl.lower().strip() == normalized:
                return True
        return False
