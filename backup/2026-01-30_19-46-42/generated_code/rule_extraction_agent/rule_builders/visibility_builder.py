"""
Visibility Rule Builder - Build MAKE_VISIBLE and MAKE_INVISIBLE rules.

CRITICAL: Visibility rules are placed on the SOURCE/CONTROLLING field,
NOT on each destination field individually!
"""

from typing import List, Dict, Optional, Tuple
from .base_builder import BaseRuleBuilder, RuleIdGenerator
from ..models import GeneratedRule


class VisibilityRuleBuilder(BaseRuleBuilder):
    """Build visibility rules (MAKE_VISIBLE, MAKE_INVISIBLE)."""

    def __init__(self, id_generator: Optional[RuleIdGenerator] = None):
        super().__init__(id_generator)

    def build_visibility_pair(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        include_invisible: bool = True
    ) -> List[GeneratedRule]:
        """
        Build a visibility rule pair (visible + invisible).

        For "if X is Y then visible otherwise invisible", generates:
        1. MAKE_VISIBLE with condition IN
        2. MAKE_INVISIBLE with condition NOT_IN

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to show/hide
            conditional_values: Values that trigger visibility
            include_invisible: Whether to include the MAKE_INVISIBLE rule

        Returns:
            List of visibility rules.
        """
        rules = []

        # MAKE_VISIBLE rule
        visible_rule = self.create_conditional_rule(
            action_type="MAKE_VISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        )
        rules.append(visible_rule)

        # MAKE_INVISIBLE rule (opposite condition)
        if include_invisible:
            invisible_rule = self.create_conditional_rule(
                action_type="MAKE_INVISIBLE",
                source_ids=[source_field_id],
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="NOT_IN"
            )
            rules.append(invisible_rule)

        return rules

    def build_multi_value_visibility(
        self,
        source_field_id: int,
        destination_ids: List[int],
        visible_values: List[str],
        invisible_values: Optional[List[str]] = None
    ) -> List[GeneratedRule]:
        """
        Build visibility rules for multiple conditional values.

        Example: GST option can be "GST Registered", "SEZ", "Compounding", "GST Non-Registered"
        - Visible for: "GST Registered", "SEZ", "Compounding"
        - Invisible for: "GST Non-Registered"

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to show/hide
            visible_values: Values that make fields visible
            invisible_values: Values that make fields invisible (optional)

        Returns:
            List of visibility rules.
        """
        rules = []

        # MAKE_VISIBLE for each value that shows the fields
        for value in visible_values:
            visible_rule = self.create_conditional_rule(
                action_type="MAKE_VISIBLE",
                source_ids=[source_field_id],
                destination_ids=destination_ids,
                conditional_values=[value],
                condition="IN"
            )
            rules.append(visible_rule)

        # MAKE_INVISIBLE for values that hide the fields
        if invisible_values:
            for value in invisible_values:
                invisible_rule = self.create_conditional_rule(
                    action_type="MAKE_INVISIBLE",
                    source_ids=[source_field_id],
                    destination_ids=destination_ids,
                    conditional_values=[value],
                    condition="IN"
                )
                rules.append(invisible_rule)

        return rules

    def build_from_visibility_group(
        self,
        source_field_id: int,
        group: List[Dict]
    ) -> List[GeneratedRule]:
        """
        Build visibility rules from a visibility group.

        A visibility group contains multiple destination fields controlled
        by the same source field with possibly different conditions.

        Args:
            source_field_id: ID of the controlling field
            group: List of dicts with {field_id, conditional_value, action_type}

        Returns:
            List of visibility rules.
        """
        rules = []

        # Group by conditional value
        by_value: Dict[str, List[int]] = {}
        for item in group:
            value = item.get("conditional_value")
            field_id = item.get("field_id")
            if value and field_id:
                if value not in by_value:
                    by_value[value] = []
                by_value[value].append(field_id)

        # Create rules for each value
        for value, destination_ids in by_value.items():
            # MAKE_VISIBLE
            visible_rule = self.create_conditional_rule(
                action_type="MAKE_VISIBLE",
                source_ids=[source_field_id],
                destination_ids=destination_ids,
                conditional_values=[value],
                condition="IN"
            )
            rules.append(visible_rule)

            # MAKE_INVISIBLE (opposite)
            invisible_rule = self.create_conditional_rule(
                action_type="MAKE_INVISIBLE",
                source_ids=[source_field_id],
                destination_ids=destination_ids,
                conditional_values=[value],
                condition="NOT_IN"
            )
            rules.append(invisible_rule)

        return rules

    def build_session_based_visibility(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        party_type: str = "FIRST_PARTY"
    ) -> GeneratedRule:
        """
        Build a session-based visibility rule.

        These rules behave differently based on which party is viewing.

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to show/hide
            conditional_values: Values to match
            party_type: "FIRST_PARTY" or "SECOND_PARTY"

        Returns:
            Session-based visibility rule.
        """
        rule = self.create_conditional_rule(
            action_type="SESSION_BASED_MAKE_VISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="NOT_IN"
        )
        rule.params = party_type
        return rule
