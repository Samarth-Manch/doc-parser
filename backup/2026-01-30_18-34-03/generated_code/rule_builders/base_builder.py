"""
Base Rule Builder - Abstract base class for rule builders.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseRuleBuilder(ABC):
    """Abstract base class for all rule builders."""

    # Counter for generating temporary rule IDs
    _rule_id_counter = 100000

    @classmethod
    def _next_rule_id(cls) -> int:
        """Generate a new temporary rule ID."""
        cls._rule_id_counter += 1
        return cls._rule_id_counter

    @abstractmethod
    def build(self, **kwargs) -> Dict:
        """
        Build a rule dictionary.

        Returns:
            Dict representing a formFillRule
        """
        pass

    def _create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        processing_type: str = "CLIENT",
        source_type: Optional[str] = None,
        conditional_values: List[str] = None,
        condition: str = "IN",
        post_trigger_rule_ids: List[int] = None,
        button: str = "",
        params: Optional[str] = None,
        execute_on_fill: bool = True,
        execute_on_read: bool = False,
    ) -> Dict:
        """
        Create a base rule dictionary with common fields.

        Args:
            action_type: Rule action type (e.g., "MAKE_VISIBLE", "VERIFY")
            source_ids: List of source field IDs
            destination_ids: List of destination field IDs
            processing_type: "CLIENT" or "SERVER"
            source_type: Source type for VERIFY/OCR rules
            conditional_values: List of values that trigger the rule
            condition: Condition operator ("IN", "NOT_IN")
            post_trigger_rule_ids: Rule IDs to trigger after this rule
            button: Button text (for VERIFY rules)
            params: JSON params string
            execute_on_fill: Whether to execute when form is filled
            execute_on_read: Whether to execute when form is read

        Returns:
            Dict representing a formFillRule
        """
        rule = {
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": action_type,
            "processingType": processing_type,
            "sourceIds": source_ids,
            "destinationIds": destination_ids,
            "postTriggerRuleIds": post_trigger_rule_ids or [],
            "button": button,
            "searchable": False,
            "executeOnFill": execute_on_fill,
            "executeOnRead": execute_on_read,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False,
        }

        if source_type:
            rule["sourceType"] = source_type

        if conditional_values:
            rule["conditionalValues"] = conditional_values
            rule["condition"] = condition
            rule["conditionValueType"] = "TEXT"

        if params:
            rule["params"] = params

        return rule
