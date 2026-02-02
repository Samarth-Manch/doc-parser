"""
Base Rule Builder

Provides common functionality for all rule builders.
"""

from typing import List, Optional, Dict, Any

try:
    from ..models import IdGenerator, GeneratedRule
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import IdGenerator, GeneratedRule


class BaseRuleBuilder:
    """
    Base class for all rule builders.

    Provides common functionality for creating rules with sequential IDs
    and all required fields.
    """

    def __init__(self, id_generator: IdGenerator = None):
        """
        Initialize the base builder.

        Args:
            id_generator: IdGenerator instance for sequential rule IDs
        """
        self.id_generator = id_generator or IdGenerator()

    def create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int] = None,
        processing_type: str = "CLIENT"
    ) -> Dict[str, Any]:
        """
        Create a base rule with all required fields and sequential ID.

        Args:
            action_type: Rule action type
            source_ids: Source field ID(s)
            destination_ids: Destination field ID(s)
            processing_type: "CLIENT" or "SERVER"

        Returns:
            Rule dict with all required fields
        """
        return {
            "id": self.id_generator.next_id('rule'),
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": action_type,
            "processingType": processing_type,
            "sourceIds": source_ids,
            "destinationIds": destination_ids or [],
            "postTriggerRuleIds": [],
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }

    def create_conditional_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict[str, Any]:
        """
        Create a conditional rule (e.g., MAKE_VISIBLE with condition).

        Args:
            action_type: Rule action type
            source_ids: Source field ID(s)
            destination_ids: Destination field ID(s)
            conditional_values: Values to match
            condition: "IN" or "NOT_IN"

        Returns:
            Rule dict with conditional fields
        """
        rule = self.create_base_rule(action_type, source_ids, destination_ids)
        rule.update({
            "conditionalValues": conditional_values,
            "condition": condition,
            "conditionValueType": "TEXT"
        })
        return rule

    def add_post_trigger(self, rule: Dict, post_trigger_id: int):
        """Add a post-trigger rule ID to a rule."""
        if "postTriggerRuleIds" not in rule:
            rule["postTriggerRuleIds"] = []
        if post_trigger_id not in rule["postTriggerRuleIds"]:
            rule["postTriggerRuleIds"].append(post_trigger_id)

    def to_generated_rule(self, rule_dict: Dict) -> GeneratedRule:
        """Convert a rule dict to a GeneratedRule object."""
        return GeneratedRule(
            id=rule_dict.get("id", 0),
            action_type=rule_dict.get("actionType", ""),
            source_ids=rule_dict.get("sourceIds", []),
            destination_ids=rule_dict.get("destinationIds", []),
            processing_type=rule_dict.get("processingType", "CLIENT"),
            source_type=rule_dict.get("sourceType"),
            conditional_values=rule_dict.get("conditionalValues", []),
            condition=rule_dict.get("condition"),
            condition_value_type=rule_dict.get("conditionValueType"),
            post_trigger_rule_ids=rule_dict.get("postTriggerRuleIds", []),
            params=rule_dict.get("params"),
            button=rule_dict.get("button", ""),
            searchable=rule_dict.get("searchable", False),
            execute_on_fill=rule_dict.get("executeOnFill", True),
            execute_on_read=rule_dict.get("executeOnRead", False),
            execute_on_esign=rule_dict.get("executeOnEsign", False),
            execute_post_esign=rule_dict.get("executePostEsign", False),
            run_post_condition_fail=rule_dict.get("runPostConditionFail", False),
            on_status_fail=rule_dict.get("onStatusFail")
        )
