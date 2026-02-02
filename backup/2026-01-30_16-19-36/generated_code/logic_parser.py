"""
Logic parser for extracting structured information from natural language logic text.
"""

import re
from typing import List, Set, Tuple

try:
    from .models import (
        ParsedLogic, Condition, ConditionOperator, ActionType, RelationshipType
    )
except ImportError:
    from models import (
        ParsedLogic, Condition, ConditionOperator, ActionType, RelationshipType
    )


class LogicParser:
    """Main parser for BUD logic/rules text."""

    # Keyword patterns for different rule types
    VISIBILITY_KEYWORDS = [
        'visible', 'invisible', 'show', 'hide', 'hidden', 'display',
        'make visible', 'make invisible'
    ]

    MANDATORY_KEYWORDS = [
        'mandatory', 'non-mandatory', 'required', 'optional',
        'make mandatory', 'make non-mandatory'
    ]

    VALIDATION_KEYWORDS = [
        'validate', 'validation', 'verify', 'check', 'perform'
    ]

    DERIVATION_KEYWORDS = [
        'copy', 'derive', 'derived', 'auto-fill', 'populate', 'auto-derived',
        'will come from', 'data will come', 'based on'
    ]

    OCR_KEYWORDS = [
        'ocr', 'extract from', 'upload', 'post upload'
    ]

    EDITABLE_KEYWORDS = [
        'editable', 'non-editable', 'enabled', 'disabled', 'enable', 'disable'
    ]

    DROPDOWN_KEYWORDS = [
        'dropdown', 'dropdown values', 'reference table', 'selectable'
    ]

    # Conditional keywords
    CONDITIONAL_KEYWORDS = [
        'if', 'then', 'else', 'otherwise', 'when', 'unless'
    ]

    # Document/entity types
    DOCUMENT_TYPES = [
        'pan', 'gstin', 'gst', 'msme', 'aadhaar', 'aadhar', 'bank', 'pincode',
        'pin code', 'cheque', 'electricity', 'cin'
    ]

    # Comparison operators
    COMPARISON_PATTERNS = [
        (r'\bis\s+yes\b', 'yes', ConditionOperator.IN),
        (r'\bis\s+no\b', 'no', ConditionOperator.IN),
        (r'\bvalue\s+is\s+(\w+)', None, ConditionOperator.IN),
        (r'\bselected\s+as\s+([^,\.]+)', None, ConditionOperator.IN),
        (r'\bchosen\s+as\s+([^,\.]+)', None, ConditionOperator.IN),
        (r'\b(?:is|are)\s+([^,\.]+)', None, ConditionOperator.IN),
    ]

    def __init__(self):
        self.keyword_extractor = KeywordExtractor()
        self.entity_extractor = EntityExtractor()
        self.condition_extractor = ConditionExtractor()

    def parse(self, logic_text: str, relationship_type: str = None) -> ParsedLogic:
        """
        Parse logic text into structured ParsedLogic object.

        Args:
            logic_text: Raw logic/rules text from BUD
            relationship_type: Optional relationship type from intra_panel_references

        Returns:
            ParsedLogic object with extracted information
        """
        if not logic_text or not logic_text.strip():
            return ParsedLogic(original_text=logic_text, confidence=0.0)

        logic_lower = logic_text.lower()

        # Extract keywords
        keywords = self.keyword_extractor.extract(logic_lower)

        # Extract field references
        field_refs = self.entity_extractor.extract_field_references(logic_text)

        # Extract document types
        doc_types = self.entity_extractor.extract_document_types(logic_lower)

        # Extract conditions
        conditions = self.condition_extractor.extract_conditions(logic_text)

        # Determine action types
        action_types = self._determine_action_types(logic_lower, keywords)

        # Extract conditional values
        conditional_values = self._extract_conditional_values(logic_text, conditions)

        # Determine flags
        has_if_else = self._has_if_else(logic_lower)
        is_ocr = self._is_ocr(logic_lower)
        is_validation = self._is_validation(logic_lower)
        is_derivation = self._is_derivation(logic_lower)
        is_visibility = self._is_visibility(logic_lower)
        is_mandatory = self._is_mandatory(logic_lower)
        is_editable = self._is_editable(logic_lower)

        # Map relationship type
        rel_type = self._map_relationship_type(relationship_type) if relationship_type else None

        # Calculate confidence
        confidence = self._calculate_confidence(
            keywords, action_types, field_refs, conditions
        )

        return ParsedLogic(
            original_text=logic_text,
            keywords=keywords,
            action_types=action_types,
            field_references=field_refs,
            conditions=conditions,
            relationship_type=rel_type,
            conditional_values=conditional_values,
            has_if_else=has_if_else,
            is_ocr=is_ocr,
            is_validation=is_validation,
            is_derivation=is_derivation,
            is_visibility=is_visibility,
            is_mandatory=is_mandatory,
            is_editable=is_editable,
            document_types=doc_types,
            confidence=confidence
        )

    def _determine_action_types(self, logic_lower: str, keywords: List[str]) -> List[ActionType]:
        """Determine action types from keywords."""
        actions = []

        # Visibility
        if any(kw in logic_lower for kw in ['visible', 'show', 'display']):
            if 'invisible' not in logic_lower or 'not visible' not in logic_lower:
                actions.append(ActionType.MAKE_VISIBLE)
        if any(kw in logic_lower for kw in ['invisible', 'hide', 'hidden']):
            actions.append(ActionType.MAKE_INVISIBLE)

        # Mandatory
        if any(kw in logic_lower for kw in ['mandatory', 'required']):
            if 'non-mandatory' not in logic_lower and 'not mandatory' not in logic_lower:
                actions.append(ActionType.MAKE_MANDATORY)
        if any(kw in logic_lower for kw in ['non-mandatory', 'optional', 'not mandatory']):
            actions.append(ActionType.MAKE_NON_MANDATORY)

        # Editable
        if any(kw in logic_lower for kw in ['non-editable', 'disabled', 'disable']):
            actions.append(ActionType.MAKE_DISABLED)
        if 'editable' in logic_lower and 'non-editable' not in logic_lower:
            actions.append(ActionType.MAKE_ENABLED)

        # Validation
        if 'pan' in logic_lower and any(kw in logic_lower for kw in ['validation', 'validate', 'verify']):
            actions.append(ActionType.VERIFY_PAN)
        if any(kw in logic_lower for kw in ['gst', 'gstin']) and any(kw in logic_lower for kw in ['validation', 'validate', 'verify']):
            actions.append(ActionType.VERIFY_GSTIN)
        if 'bank' in logic_lower and any(kw in logic_lower for kw in ['validation', 'validate', 'verify']):
            actions.append(ActionType.VERIFY_BANK)
        if 'msme' in logic_lower and any(kw in logic_lower for kw in ['validation', 'validate', 'verify']):
            actions.append(ActionType.VERIFY_MSME)
        if any(kw in logic_lower for kw in ['pin code', 'pincode', 'postal code']) and any(kw in logic_lower for kw in ['validation', 'validate', 'verify']):
            actions.append(ActionType.VERIFY_PINCODE)

        # OCR
        if 'pan' in logic_lower and 'ocr' in logic_lower:
            actions.append(ActionType.OCR_PAN)
        if any(kw in logic_lower for kw in ['gst', 'gstin']) and 'ocr' in logic_lower:
            actions.append(ActionType.OCR_GSTIN)
        if any(kw in logic_lower for kw in ['aadhaar', 'aadhar']) and 'ocr' in logic_lower:
            actions.append(ActionType.OCR_AADHAAR)
        if 'msme' in logic_lower and 'ocr' in logic_lower:
            actions.append(ActionType.OCR_MSME)

        # Copy/Clear
        if 'copy' in logic_lower or 'derive' in logic_lower:
            actions.append(ActionType.COPY_TO)
        if 'clear' in logic_lower:
            actions.append(ActionType.CLEAR_FIELD)

        return actions

    def _extract_conditional_values(self, logic_text: str, conditions: List[Condition]) -> List[str]:
        """Extract conditional values from text."""
        values = []

        # From conditions
        for cond in conditions:
            if isinstance(cond.value, list):
                values.extend(cond.value)
            elif cond.value:
                values.append(str(cond.value))

        # Common patterns
        if re.search(r'\bis\s+yes\b', logic_text.lower()):
            values.append('yes')
        if re.search(r'\bis\s+no\b', logic_text.lower()):
            values.append('no')

        return list(set(values))  # Remove duplicates

    def _has_if_else(self, logic_lower: str) -> bool:
        """Check if logic has if/else structure."""
        return ('if' in logic_lower and ('else' in logic_lower or 'otherwise' in logic_lower))

    def _is_ocr(self, logic_lower: str) -> bool:
        """Check if logic involves OCR."""
        return any(kw in logic_lower for kw in self.OCR_KEYWORDS)

    def _is_validation(self, logic_lower: str) -> bool:
        """Check if logic involves validation."""
        return any(kw in logic_lower for kw in self.VALIDATION_KEYWORDS)

    def _is_derivation(self, logic_lower: str) -> bool:
        """Check if logic involves data derivation."""
        return any(kw in logic_lower for kw in self.DERIVATION_KEYWORDS)

    def _is_visibility(self, logic_lower: str) -> bool:
        """Check if logic controls visibility."""
        return any(kw in logic_lower for kw in self.VISIBILITY_KEYWORDS)

    def _is_mandatory(self, logic_lower: str) -> bool:
        """Check if logic controls mandatory status."""
        return any(kw in logic_lower for kw in self.MANDATORY_KEYWORDS)

    def _is_editable(self, logic_lower: str) -> bool:
        """Check if logic controls editability."""
        return any(kw in logic_lower for kw in self.EDITABLE_KEYWORDS)

    def _map_relationship_type(self, relationship_type: str) -> RelationshipType:
        """Map string relationship type to enum."""
        mapping = {
            'visibility_control': RelationshipType.VISIBILITY_CONTROL,
            'mandatory_control': RelationshipType.MANDATORY_CONTROL,
            'value_derivation': RelationshipType.VALUE_DERIVATION,
            'data_dependency': RelationshipType.DATA_DEPENDENCY,
            'validation': RelationshipType.VALIDATION,
            'enable_disable': RelationshipType.ENABLE_DISABLE,
            'conditional': RelationshipType.CONDITIONAL,
            'clear_operation': RelationshipType.CLEAR_OPERATION,
        }
        return mapping.get(relationship_type, RelationshipType.OTHER)

    def _calculate_confidence(
        self,
        keywords: List[str],
        action_types: List[ActionType],
        field_refs: List[str],
        conditions: List[Condition]
    ) -> float:
        """Calculate confidence score for parsed logic."""
        score = 0.0

        # Keywords found
        if keywords:
            score += 0.3

        # Action types identified
        if action_types:
            score += 0.3

        # Field references found
        if field_refs:
            score += 0.2

        # Conditions found
        if conditions:
            score += 0.2

        return min(score, 1.0)


class KeywordExtractor:
    """Extract keywords from logic text."""

    def extract(self, logic_lower: str) -> List[str]:
        """Extract all relevant keywords."""
        keywords = []

        all_keywords = (
            LogicParser.VISIBILITY_KEYWORDS +
            LogicParser.MANDATORY_KEYWORDS +
            LogicParser.VALIDATION_KEYWORDS +
            LogicParser.DERIVATION_KEYWORDS +
            LogicParser.OCR_KEYWORDS +
            LogicParser.EDITABLE_KEYWORDS +
            LogicParser.DROPDOWN_KEYWORDS +
            LogicParser.CONDITIONAL_KEYWORDS
        )

        for keyword in all_keywords:
            if keyword in logic_lower:
                keywords.append(keyword)

        return keywords


class EntityExtractor:
    """Extract entities like field names and document types."""

    def extract_field_references(self, logic_text: str) -> List[str]:
        """Extract field name references from text."""
        field_refs = []

        # Pattern: "field 'Name'" or "field \"Name\""
        patterns = [
            r"field\s+['\"]([^'\"]+)['\"]",
            r"['\"]([^'\"]+)['\"]\s+(?:field|is|value)",
            r"(?:if|when)\s+['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, logic_text, re.IGNORECASE)
            field_refs.extend(matches)

        return list(set(field_refs))  # Remove duplicates

    def extract_document_types(self, logic_lower: str) -> List[str]:
        """Extract document types mentioned in logic."""
        doc_types = []

        for doc_type in LogicParser.DOCUMENT_TYPES:
            if doc_type in logic_lower:
                doc_types.append(doc_type.upper())

        return list(set(doc_types))


class ConditionExtractor:
    """Extract conditional expressions from logic."""

    def extract_conditions(self, logic_text: str) -> List[Condition]:
        """Extract all conditions from logic text."""
        conditions = []

        # Pattern: "if FIELD is VALUE"
        if_pattern = r"if\s+(?:the\s+)?(?:field\s+)?['\"]?([^'\"]+)['\"]?\s+(?:value\s+)?is\s+([a-zA-Z0-9\s,]+)"
        matches = re.findall(if_pattern, logic_text, re.IGNORECASE)

        for field_ref, value in matches:
            field_ref = field_ref.strip()
            value = value.strip().rstrip('.,;')

            # Handle multiple values (e.g., "ZDES, ZDOM, ZRPV")
            if ',' in value:
                values = [v.strip() for v in value.split(',')]
                conditions.append(Condition(
                    field_ref=field_ref,
                    operator=ConditionOperator.IN,
                    value=values
                ))
            else:
                conditions.append(Condition(
                    field_ref=field_ref,
                    operator=ConditionOperator.IN,
                    value=value
                ))

        # Pattern: "selected as VALUE"
        selected_pattern = r"(?:selected|chosen)\s+as\s+['\"]?([^'\",.]+)['\"]?"
        matches = re.findall(selected_pattern, logic_text, re.IGNORECASE)

        for value in matches:
            value = value.strip()
            # Try to find the field this refers to
            # This is a simplification; actual implementation might be more complex
            conditions.append(Condition(
                field_ref="",  # Will be filled in later
                operator=ConditionOperator.IN,
                value=value
            ))

        return conditions
