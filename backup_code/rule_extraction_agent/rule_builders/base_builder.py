"""
Base Rule Builder - Foundation for all rule builders.
"""

from typing import List, Optional, Dict, Any
from ..models import GeneratedRule, IdGenerator


class BaseRuleBuilder:
    """Base class for rule builders."""

    def __init__(self, id_generator: IdGenerator):
        """
        Initialize the builder.

        Args:
            id_generator: IdGenerator instance for generating sequential IDs.
        """
        self.id_generator = id_generator

    def create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: Optional[List[int]] = None,
        processing_type: str = "CLIENT"
    ) -> GeneratedRule:
        """
        Create base rule with all required fields.

        Args:
            action_type: Rule action type (e.g., "MAKE_VISIBLE", "VERIFY").
            source_ids: List of source field IDs.
            destination_ids: List of destination field IDs.
            processing_type: "CLIENT" or "SERVER".

        Returns:
            GeneratedRule with base fields populated.
        """
        return GeneratedRule(
            id=self.id_generator.next_id('rule'),
            action_type=action_type,
            processing_type=processing_type,
            source_ids=source_ids,
            destination_ids=destination_ids or [],
            post_trigger_rule_ids=[],
            button="",
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False
        )

    def create_conditional_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> GeneratedRule:
        """
        Create conditional visibility/mandatory rule.

        Args:
            action_type: Rule action type.
            source_ids: Source field IDs (controlling fields).
            destination_ids: Destination field IDs (controlled fields).
            conditional_values: Values that trigger the rule.
            condition: "IN" or "NOT_IN".

        Returns:
            GeneratedRule with conditional fields populated.
        """
        rule = self.create_base_rule(action_type, source_ids, destination_ids)
        rule.conditional_values = conditional_values
        rule.condition = condition
        rule.condition_value_type = "TEXT"
        return rule

    def create_disabled_rule(
        self,
        source_id: int,
        destination_id: int,
        control_field_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Create MAKE_DISABLED rule for non-editable fields.

        Args:
            source_id: Source field ID (typically a RuleCheck control field).
            destination_id: Destination field ID to disable.
            control_field_id: Optional control field for conditional disable.

        Returns:
            GeneratedRule for MAKE_DISABLED.
        """
        rule = self.create_base_rule(
            "MAKE_DISABLED",
            [control_field_id or source_id],
            [destination_id]
        )
        rule.conditional_values = ["Disable"]
        rule.condition = "NOT_IN"  # Always triggers
        rule.condition_value_type = "TEXT"
        return rule
