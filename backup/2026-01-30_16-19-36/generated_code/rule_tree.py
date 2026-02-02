"""
Rule selection tree for deterministic rule generation from parsed logic.
"""

from typing import List, Optional

try:
    from .models import (
        ParsedLogic, RuleSelection, FieldInfo, ActionType,
        ConditionOperator, RelationshipType
    )
except ImportError:
    from models import (
        ParsedLogic, RuleSelection, FieldInfo, ActionType,
        ConditionOperator, RelationshipType
    )


class RuleTree:
    """Decision tree for selecting rules based on parsed logic."""

    def __init__(self):
        """Initialize rule tree."""
        pass

    def select_rules(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """
        Select rules to generate based on parsed logic.

        Args:
            parsed_logic: Parsed logic information
            source_field: Source field (controlling field)
            target_fields: Target fields (controlled fields)

        Returns:
            List of RuleSelection objects
        """
        rules = []

        # Route based on relationship type
        if parsed_logic.relationship_type == RelationshipType.VISIBILITY_CONTROL:
            rules.extend(self._handle_visibility_control(parsed_logic, source_field, target_fields))
        elif parsed_logic.relationship_type == RelationshipType.MANDATORY_CONTROL:
            rules.extend(self._handle_mandatory_control(parsed_logic, source_field, target_fields))
        elif parsed_logic.relationship_type == RelationshipType.VALIDATION:
            rules.extend(self._handle_validation(parsed_logic, source_field, target_fields))
        elif parsed_logic.relationship_type == RelationshipType.VALUE_DERIVATION:
            rules.extend(self._handle_value_derivation(parsed_logic, source_field, target_fields))
        elif parsed_logic.relationship_type == RelationshipType.DATA_DEPENDENCY:
            rules.extend(self._handle_data_dependency(parsed_logic, source_field, target_fields))
        elif parsed_logic.relationship_type == RelationshipType.ENABLE_DISABLE:
            rules.extend(self._handle_enable_disable(parsed_logic, source_field, target_fields))
        else:
            # Fallback: analyze action types directly
            rules.extend(self._handle_generic(parsed_logic, source_field, target_fields))

        return rules

    def _handle_visibility_control(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Handle visibility control rules."""
        rules = []

        # Determine conditional values
        conditional_values = parsed_logic.conditional_values or ['yes']

        # If has if/else, generate rules for both conditions
        if parsed_logic.has_if_else:
            # MAKE_VISIBLE when condition is true
            if any(a == ActionType.MAKE_VISIBLE for a in parsed_logic.action_types):
                rules.append(RuleSelection(
                    action_type=ActionType.MAKE_VISIBLE,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=conditional_values,
                    condition_operator=ConditionOperator.IN,
                    confidence=parsed_logic.confidence
                ))

            # MAKE_INVISIBLE when condition is false
            if any(a == ActionType.MAKE_INVISIBLE for a in parsed_logic.action_types):
                rules.append(RuleSelection(
                    action_type=ActionType.MAKE_INVISIBLE,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=conditional_values,
                    condition_operator=ConditionOperator.NOT_IN,
                    confidence=parsed_logic.confidence
                ))
        else:
            # Single condition
            for action_type in parsed_logic.action_types:
                if action_type in [ActionType.MAKE_VISIBLE, ActionType.MAKE_INVISIBLE]:
                    operator = ConditionOperator.IN if action_type == ActionType.MAKE_VISIBLE else ConditionOperator.NOT_IN
                    rules.append(RuleSelection(
                        action_type=action_type,
                        source_field=source_field,
                        destination_fields=target_fields,
                        conditional_values=conditional_values,
                        condition_operator=operator,
                        confidence=parsed_logic.confidence
                    ))

        return rules

    def _handle_mandatory_control(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Handle mandatory control rules."""
        rules = []

        conditional_values = parsed_logic.conditional_values or ['yes']

        if parsed_logic.has_if_else:
            # MAKE_MANDATORY when condition is true
            if any(a == ActionType.MAKE_MANDATORY for a in parsed_logic.action_types):
                rules.append(RuleSelection(
                    action_type=ActionType.MAKE_MANDATORY,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=conditional_values,
                    condition_operator=ConditionOperator.IN,
                    confidence=parsed_logic.confidence
                ))

            # MAKE_NON_MANDATORY when condition is false
            if any(a == ActionType.MAKE_NON_MANDATORY for a in parsed_logic.action_types):
                rules.append(RuleSelection(
                    action_type=ActionType.MAKE_NON_MANDATORY,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=conditional_values,
                    condition_operator=ConditionOperator.NOT_IN,
                    confidence=parsed_logic.confidence
                ))
        else:
            for action_type in parsed_logic.action_types:
                if action_type in [ActionType.MAKE_MANDATORY, ActionType.MAKE_NON_MANDATORY]:
                    operator = ConditionOperator.IN if action_type == ActionType.MAKE_MANDATORY else ConditionOperator.NOT_IN
                    rules.append(RuleSelection(
                        action_type=action_type,
                        source_field=source_field,
                        destination_fields=target_fields,
                        conditional_values=conditional_values,
                        condition_operator=operator,
                        confidence=parsed_logic.confidence
                    ))

        return rules

    def _handle_validation(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Handle validation rules."""
        rules = []

        # Validation rules are typically server-side
        for action_type in parsed_logic.action_types:
            if action_type in [
                ActionType.VERIFY_PAN,
                ActionType.VERIFY_GSTIN,
                ActionType.VERIFY_BANK,
                ActionType.VERIFY_MSME,
                ActionType.VERIFY_PINCODE
            ]:
                rules.append(RuleSelection(
                    action_type=action_type,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=[],
                    condition_operator=ConditionOperator.IN,
                    processing_type="SERVER",
                    confidence=parsed_logic.confidence
                ))

        # If validation makes field non-editable
        if ActionType.MAKE_DISABLED in parsed_logic.action_types:
            rules.append(RuleSelection(
                action_type=ActionType.MAKE_DISABLED,
                source_field=None,  # Self-reference
                destination_fields=target_fields,
                conditional_values=[],
                condition_operator=ConditionOperator.IN,
                confidence=parsed_logic.confidence
            ))

        return rules

    def _handle_value_derivation(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Handle value derivation rules."""
        rules = []

        # Value derivation typically uses COPY_TO
        if ActionType.COPY_TO in parsed_logic.action_types or parsed_logic.is_derivation:
            rules.append(RuleSelection(
                action_type=ActionType.COPY_TO,
                source_field=source_field,
                destination_fields=target_fields,
                conditional_values=parsed_logic.conditional_values,
                condition_operator=ConditionOperator.IN,
                confidence=parsed_logic.confidence
            ))

        # Derived fields are often non-editable
        if ActionType.MAKE_DISABLED in parsed_logic.action_types or 'non-editable' in parsed_logic.original_text.lower():
            rules.append(RuleSelection(
                action_type=ActionType.MAKE_DISABLED,
                source_field=None,
                destination_fields=target_fields,
                conditional_values=[],
                condition_operator=ConditionOperator.IN,
                confidence=parsed_logic.confidence
            ))

        return rules

    def _handle_data_dependency(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Handle data dependency rules (like dropdown values from reference tables)."""
        rules = []

        # Data dependency often involves validation or derivation
        for action_type in parsed_logic.action_types:
            if action_type in [
                ActionType.VERIFY_PAN,
                ActionType.VERIFY_GSTIN,
                ActionType.VERIFY_MSME,
                ActionType.VERIFY_PINCODE,
                ActionType.COPY_TO
            ]:
                rules.append(RuleSelection(
                    action_type=action_type,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=parsed_logic.conditional_values,
                    condition_operator=ConditionOperator.IN,
                    processing_type="SERVER" if "VERIFY" in action_type.value else "CLIENT",
                    confidence=parsed_logic.confidence
                ))

        # Make non-editable if specified
        if 'non-editable' in parsed_logic.original_text.lower():
            rules.append(RuleSelection(
                action_type=ActionType.MAKE_DISABLED,
                source_field=None,
                destination_fields=target_fields,
                conditional_values=[],
                condition_operator=ConditionOperator.IN,
                confidence=parsed_logic.confidence
            ))

        return rules

    def _handle_enable_disable(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Handle enable/disable rules."""
        rules = []

        for action_type in parsed_logic.action_types:
            if action_type in [ActionType.MAKE_ENABLED, ActionType.MAKE_DISABLED]:
                rules.append(RuleSelection(
                    action_type=action_type,
                    source_field=source_field,
                    destination_fields=target_fields,
                    conditional_values=parsed_logic.conditional_values,
                    condition_operator=ConditionOperator.IN,
                    confidence=parsed_logic.confidence
                ))

        return rules

    def _handle_generic(
        self,
        parsed_logic: ParsedLogic,
        source_field: Optional[FieldInfo],
        target_fields: List[FieldInfo]
    ) -> List[RuleSelection]:
        """Generic handler based on action types."""
        rules = []

        for action_type in parsed_logic.action_types:
            # Determine processing type
            processing_type = "SERVER" if "VERIFY" in action_type.value or "OCR" in action_type.value else "CLIENT"

            # Determine conditional values
            conditional_values = parsed_logic.conditional_values if source_field else []

            rules.append(RuleSelection(
                action_type=action_type,
                source_field=source_field,
                destination_fields=target_fields,
                conditional_values=conditional_values,
                condition_operator=ConditionOperator.IN,
                processing_type=processing_type,
                confidence=parsed_logic.confidence
            ))

        return rules
