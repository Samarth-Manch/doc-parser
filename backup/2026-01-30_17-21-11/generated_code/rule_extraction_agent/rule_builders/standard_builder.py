"""
Standard rule builder for visibility, mandatory, and disable rules.

Handles:
- MAKE_VISIBLE / MAKE_INVISIBLE
- MAKE_MANDATORY / MAKE_NON_MANDATORY
- MAKE_DISABLED / MAKE_ENABLED
- SESSION_BASED variants
"""

from typing import List, Optional, Tuple
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule, ParsedLogic, Condition


class StandardRuleBuilder(BaseRuleBuilder):
    """
    Builder for standard visibility, mandatory, and editability rules.

    These rules typically have:
    - sourceIds: The controlling field(s)
    - destinationIds: The field(s) being controlled
    - conditionalValues: Values that trigger the rule
    - condition: IN or NOT_IN
    """

    # Map of action types to their inverse
    INVERSE_ACTIONS = {
        "MAKE_VISIBLE": "MAKE_INVISIBLE",
        "MAKE_INVISIBLE": "MAKE_VISIBLE",
        "MAKE_MANDATORY": "MAKE_NON_MANDATORY",
        "MAKE_NON_MANDATORY": "MAKE_MANDATORY",
        "MAKE_DISABLED": "MAKE_ENABLED",
        "MAKE_ENABLED": "MAKE_DISABLED",
    }

    def build(
        self,
        action_type: str,
        source_field_id: int,
        destination_field_id: int,
        conditional_values: Optional[List[str]] = None,
        condition: str = "IN",
        session_based: bool = False,
        party_type: Optional[str] = None,
    ) -> GeneratedRule:
        """
        Build a standard visibility/mandatory/disable rule.

        Args:
            action_type: MAKE_VISIBLE, MAKE_MANDATORY, etc.
            source_field_id: ID of the controlling field
            destination_field_id: ID of the field being controlled
            conditional_values: Values that trigger the rule
            condition: IN or NOT_IN
            session_based: If True, use SESSION_BASED variant
            party_type: FIRST_PARTY or SECOND_PARTY (for session-based)

        Returns:
            GeneratedRule
        """
        # Handle session-based variants
        if session_based:
            if not action_type.startswith("SESSION_BASED_"):
                action_type = f"SESSION_BASED_{action_type}"

        rule = self._create_base_rule(
            action_type=action_type,
            source_ids=[source_field_id],
            destination_ids=[destination_field_id],
            processing_type="CLIENT"
        )

        if conditional_values:
            self._add_condition(rule, conditional_values, condition)

        # Add params for session-based rules
        if session_based and party_type:
            rule.params = party_type

        return rule

    def build_conditional_pair(
        self,
        positive_action: str,
        source_field_id: int,
        destination_field_id: int,
        conditional_values: List[str],
    ) -> Tuple[GeneratedRule, GeneratedRule]:
        """
        Build a pair of rules for if/else conditional logic.

        For "if X is Y then visible otherwise invisible", generates:
        1. MAKE_VISIBLE with condition IN
        2. MAKE_INVISIBLE with condition NOT_IN

        Args:
            positive_action: Action for when condition is true
            source_field_id: Controlling field ID
            destination_field_id: Controlled field ID
            conditional_values: Values for the condition

        Returns:
            Tuple of (positive_rule, negative_rule)
        """
        # Build positive rule (condition IN)
        positive_rule = self.build(
            action_type=positive_action,
            source_field_id=source_field_id,
            destination_field_id=destination_field_id,
            conditional_values=conditional_values,
            condition="IN"
        )

        # Build negative rule (condition NOT_IN)
        negative_action = self.INVERSE_ACTIONS.get(positive_action)
        if not negative_action:
            negative_action = positive_action  # Fallback

        negative_rule = self.build(
            action_type=negative_action,
            source_field_id=source_field_id,
            destination_field_id=destination_field_id,
            conditional_values=conditional_values,
            condition="NOT_IN"
        )

        return positive_rule, negative_rule

    def build_visibility_mandatory_set(
        self,
        source_field_id: int,
        destination_field_id: int,
        conditional_values: List[str],
        visible_when_true: bool = True,
        mandatory_when_true: bool = True,
    ) -> List[GeneratedRule]:
        """
        Build a complete set of visibility and mandatory rules.

        For "if X then visible and mandatory otherwise invisible and non-mandatory",
        generates 4 rules.

        Args:
            source_field_id: Controlling field ID
            destination_field_id: Controlled field ID
            conditional_values: Values for the condition
            visible_when_true: If True, make visible when condition true
            mandatory_when_true: If True, make mandatory when condition true

        Returns:
            List of 4 GeneratedRule objects
        """
        rules = []

        # Visibility rules
        if visible_when_true:
            vis_pos, vis_neg = self.build_conditional_pair(
                "MAKE_VISIBLE",
                source_field_id,
                destination_field_id,
                conditional_values
            )
        else:
            vis_pos, vis_neg = self.build_conditional_pair(
                "MAKE_INVISIBLE",
                source_field_id,
                destination_field_id,
                conditional_values
            )
        rules.extend([vis_pos, vis_neg])

        # Mandatory rules
        if mandatory_when_true:
            mand_pos, mand_neg = self.build_conditional_pair(
                "MAKE_MANDATORY",
                source_field_id,
                destination_field_id,
                conditional_values
            )
        else:
            mand_pos, mand_neg = self.build_conditional_pair(
                "MAKE_NON_MANDATORY",
                source_field_id,
                destination_field_id,
                conditional_values
            )
        rules.extend([mand_pos, mand_neg])

        return rules

    def build_disable_rule(
        self,
        source_field_id: int,
        destination_field_id: int,
        always_disabled: bool = True,
        conditional_values: Optional[List[str]] = None,
    ) -> GeneratedRule:
        """
        Build a MAKE_DISABLED rule.

        Args:
            source_field_id: Controlling field ID (often same as destination for always rules)
            destination_field_id: Field to disable
            always_disabled: If True, use NOT_IN with non-matching value to always trigger
            conditional_values: Values for conditional disabling

        Returns:
            GeneratedRule for MAKE_DISABLED
        """
        rule = self.build(
            action_type="MAKE_DISABLED",
            source_field_id=source_field_id,
            destination_field_id=destination_field_id,
            conditional_values=conditional_values or ["Disable"],
            condition="NOT_IN" if always_disabled else "IN"
        )
        return rule

    def build_from_parsed_logic(
        self,
        parsed_logic: ParsedLogic,
        source_field_id: int,
        destination_field_id: int,
    ) -> List[GeneratedRule]:
        """
        Build rules from parsed logic.

        Args:
            parsed_logic: Parsed logic from LogicParser
            source_field_id: Controlling field ID
            destination_field_id: Controlled field ID

        Returns:
            List of GeneratedRule objects
        """
        rules = []

        # Get conditional values from parsed logic
        conditional_values = []
        for condition in parsed_logic.conditions:
            if condition.value:
                conditional_values.append(condition.value)

        # Default to 'yes' if no values found but is conditional
        if not conditional_values and parsed_logic.is_conditional:
            conditional_values = ["yes"]

        # Check for visibility + mandatory combination
        has_visible = any(a in ["MAKE_VISIBLE", "MAKE_INVISIBLE"] for a in parsed_logic.action_types)
        has_mandatory = any(a in ["MAKE_MANDATORY", "MAKE_NON_MANDATORY"] for a in parsed_logic.action_types)

        if has_visible and has_mandatory and parsed_logic.has_else_branch:
            # Full visibility + mandatory set
            visible_positive = "MAKE_VISIBLE" in parsed_logic.action_types
            mandatory_positive = "MAKE_MANDATORY" in parsed_logic.action_types
            rules = self.build_visibility_mandatory_set(
                source_field_id,
                destination_field_id,
                conditional_values,
                visible_when_true=visible_positive,
                mandatory_when_true=mandatory_positive
            )
        else:
            # Build individual rules
            for action_type in parsed_logic.action_types:
                if action_type in self.INVERSE_ACTIONS and parsed_logic.has_else_branch:
                    # Conditional pair
                    pos, neg = self.build_conditional_pair(
                        action_type,
                        source_field_id,
                        destination_field_id,
                        conditional_values
                    )
                    rules.extend([pos, neg])
                elif action_type.startswith("MAKE_"):
                    # Single rule
                    rule = self.build(
                        action_type=action_type,
                        source_field_id=source_field_id,
                        destination_field_id=destination_field_id,
                        conditional_values=conditional_values,
                        condition="IN" if conditional_values else None
                    )
                    rules.append(rule)

        return rules
