"""
Base Rule Builder - Common functionality for all rule builders.
"""

from typing import List, Dict, Any, Optional
from ..models import GeneratedRule


class RuleIdGenerator:
    """Generate unique rule IDs."""

    def __init__(self, start_id: int = 200000):
        """
        Initialize ID generator.

        Args:
            start_id: Starting ID for generated rules
        """
        self._next_id = start_id

    def next_id(self) -> int:
        """Get next available ID."""
        rule_id = self._next_id
        self._next_id += 1
        return rule_id

    def reset(self, start_id: int = 200000):
        """Reset the ID counter."""
        self._next_id = start_id


# Global rule ID generator
_id_generator = RuleIdGenerator()


def get_rule_id() -> int:
    """Get the next available rule ID."""
    return _id_generator.next_id()


def reset_rule_ids(start_id: int = 200000):
    """Reset the rule ID counter."""
    _id_generator.reset(start_id)


class BaseRuleBuilder:
    """Base class for rule builders."""

    def __init__(self):
        pass

    def create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int] = None,
        processing_type: str = "CLIENT",
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Create a base rule with all required fields.

        Args:
            action_type: Rule action type (e.g., "MAKE_VISIBLE")
            source_ids: List of source field IDs
            destination_ids: List of destination field IDs
            processing_type: "CLIENT" or "SERVER"
            rule_id: Optional specific rule ID (auto-generated if None)

        Returns:
            GeneratedRule with base fields filled
        """
        return GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
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
            run_post_condition_fail=False,
        )

    def create_conditional_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN",
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Create a conditional rule (visibility, mandatory, etc.).

        Args:
            action_type: Rule action type (e.g., "MAKE_VISIBLE")
            source_ids: List of source field IDs (controlling fields)
            destination_ids: List of destination field IDs (affected fields)
            conditional_values: Values that trigger the rule
            condition: "IN" or "NOT_IN"
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule with conditional fields
        """
        rule = self.create_base_rule(
            action_type=action_type,
            source_ids=source_ids,
            destination_ids=destination_ids,
            processing_type="CLIENT",
            rule_id=rule_id
        )
        rule.conditional_values = conditional_values
        rule.condition = condition
        rule.condition_value_type = "TEXT"
        return rule

    def create_disabled_rule(
        self,
        source_id: int,
        destination_ids: List[int],
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Create a MAKE_DISABLED rule.

        Uses the RuleCheck pattern: condition "NOT_IN" with value "Disable"
        so the rule always triggers.

        Args:
            source_id: Source field ID (typically RuleCheck field)
            destination_ids: Field IDs to disable
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for MAKE_DISABLED
        """
        rule = self.create_conditional_rule(
            action_type="MAKE_DISABLED",
            source_ids=[source_id],
            destination_ids=destination_ids,
            conditional_values=["Disable"],
            condition="NOT_IN",
            rule_id=rule_id
        )
        return rule

    def create_convert_to_rule(
        self,
        source_id: int,
        conversion_type: str = "UPPER_CASE",
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Create a CONVERT_TO rule (e.g., uppercase).

        Args:
            source_id: Field ID to convert
            conversion_type: "UPPER_CASE" or "LOWER_CASE"
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for CONVERT_TO
        """
        rule = self.create_base_rule(
            action_type="CONVERT_TO",
            source_ids=[source_id],
            destination_ids=[],
            processing_type="CLIENT",
            rule_id=rule_id
        )
        rule.source_type = conversion_type
        return rule

    def create_copy_to_rule(
        self,
        source_id: int,
        destination_ids: List[int],
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Create a COPY_TO rule.

        Args:
            source_id: Source field ID
            destination_ids: Destination field IDs
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for COPY_TO
        """
        return self.create_base_rule(
            action_type="COPY_TO",
            source_ids=[source_id],
            destination_ids=destination_ids,
            processing_type="CLIENT",
            rule_id=rule_id
        )

    def rules_to_dict_list(self, rules: List[GeneratedRule]) -> List[Dict[str, Any]]:
        """Convert list of GeneratedRule to list of dicts."""
        return [rule.to_dict() for rule in rules]
