"""
Base rule builder with common functionality.
"""

from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from ..models import GeneratedRule, RuleMatch


class BaseRuleBuilder(ABC):
    """
    Abstract base class for rule builders.

    All rule builders inherit from this class and implement the build method.
    """

    # Default rule properties
    DEFAULT_PROCESSING_TYPE = "CLIENT"
    DEFAULT_CONDITION = "IN"
    DEFAULT_CONDITION_VALUE_TYPE = "TEXT"

    def __init__(self):
        """Initialize the rule builder."""
        self._rule_id_counter = 0

    def _generate_rule_id(self) -> int:
        """Generate a unique rule ID for tracking."""
        self._rule_id_counter += 1
        return self._rule_id_counter

    @abstractmethod
    def build(self, **kwargs) -> GeneratedRule:
        """
        Build a rule with the given parameters.

        Subclasses must implement this method.

        Returns:
            GeneratedRule ready for JSON output
        """
        pass

    def _create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        processing_type: str = DEFAULT_PROCESSING_TYPE
    ) -> GeneratedRule:
        """
        Create a base rule with minimal required fields.

        Args:
            action_type: The action type (MAKE_VISIBLE, VERIFY, etc.)
            source_ids: List of source field IDs
            destination_ids: List of destination field IDs
            processing_type: CLIENT or SERVER

        Returns:
            GeneratedRule with base properties set
        """
        return GeneratedRule(
            action_type=action_type,
            processing_type=processing_type,
            source_ids=source_ids,
            destination_ids=destination_ids,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )

    def _add_condition(
        self,
        rule: GeneratedRule,
        conditional_values: List[str],
        condition: str = DEFAULT_CONDITION,
        condition_value_type: str = DEFAULT_CONDITION_VALUE_TYPE
    ) -> GeneratedRule:
        """
        Add conditional logic to a rule.

        Args:
            rule: The rule to modify
            conditional_values: Values to check against
            condition: IN or NOT_IN
            condition_value_type: TEXT, NUMBER, or EXPR

        Returns:
            Modified GeneratedRule
        """
        rule.conditional_values = conditional_values
        rule.condition = condition
        rule.condition_value_type = condition_value_type
        return rule

    def validate_rule(self, rule: GeneratedRule) -> List[str]:
        """
        Validate a generated rule.

        Args:
            rule: The rule to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not rule.action_type:
            errors.append("Missing action_type")

        if not rule.source_ids:
            errors.append("Missing source_ids")

        if not rule.destination_ids:
            # Some rules (like VERIFY with params) may not need destination_ids
            if rule.action_type not in ["DUMMY_ACTION", "EXECUTE", "COPY_TO_TRANSACTION_ATTR3"]:
                pass  # destination_ids not always required

        if rule.conditional_values and not rule.condition:
            errors.append("Has conditional_values but missing condition")

        return errors


class RuleBuilderFactory:
    """Factory for creating appropriate rule builders."""

    _builders: Dict[str, type] = {}

    @classmethod
    def register(cls, action_type: str, builder_class: type) -> None:
        """Register a builder class for an action type."""
        cls._builders[action_type] = builder_class

    @classmethod
    def get_builder(cls, action_type: str) -> Optional[BaseRuleBuilder]:
        """Get a builder instance for an action type."""
        builder_class = cls._builders.get(action_type)
        if builder_class:
            return builder_class()
        return None

    @classmethod
    def list_registered(cls) -> List[str]:
        """List all registered action types."""
        return list(cls._builders.keys())
