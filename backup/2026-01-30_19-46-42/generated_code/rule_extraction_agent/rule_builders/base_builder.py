"""
Base Rule Builder - Common functionality for all rule builders.
"""

from typing import List, Dict, Optional
from ..models import GeneratedRule


class RuleIdGenerator:
    """Generate unique rule IDs."""

    def __init__(self, start_id: int = 200000):
        """
        Initialize with a starting ID.

        Args:
            start_id: Starting ID for rule generation.
        """
        self.current_id = start_id

    def next_id(self) -> int:
        """Get the next rule ID."""
        rule_id = self.current_id
        self.current_id += 1
        return rule_id

    def reset(self, start_id: int = 200000):
        """Reset the ID counter."""
        self.current_id = start_id


class BaseRuleBuilder:
    """Base class for rule builders."""

    def __init__(self, id_generator: Optional[RuleIdGenerator] = None):
        """
        Initialize the builder.

        Args:
            id_generator: RuleIdGenerator instance for generating rule IDs.
        """
        self.id_generator = id_generator or RuleIdGenerator()

    def create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: Optional[List[int]] = None,
        processing_type: str = "CLIENT"
    ) -> GeneratedRule:
        """
        Create a base rule with all required fields.

        Args:
            action_type: Rule action type (e.g., "MAKE_VISIBLE")
            source_ids: Source field ID(s)
            destination_ids: Destination field ID(s)
            processing_type: "CLIENT" or "SERVER"

        Returns:
            GeneratedRule with all required fields.
        """
        return GeneratedRule(
            id=self.id_generator.next_id(),
            action_type=action_type,
            processing_type=processing_type,
            source_ids=source_ids,
            destination_ids=destination_ids or [],
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
        condition: str = "IN"
    ) -> GeneratedRule:
        """
        Create a conditional rule (visibility, mandatory, etc.).

        Args:
            action_type: Rule action type
            source_ids: Source field ID(s)
            destination_ids: Destination field ID(s)
            conditional_values: Values to match
            condition: "IN" or "NOT_IN"

        Returns:
            GeneratedRule with conditional fields.
        """
        rule = self.create_base_rule(action_type, source_ids, destination_ids)
        rule.conditional_values = conditional_values
        rule.condition = condition
        rule.condition_value_type = "TEXT"
        return rule

    def to_dict(self, rule: GeneratedRule) -> Dict:
        """Convert a rule to a dictionary."""
        return rule.to_dict()

    def to_dict_list(self, rules: List[GeneratedRule]) -> List[Dict]:
        """Convert a list of rules to dictionaries."""
        return [rule.to_dict() for rule in rules]
