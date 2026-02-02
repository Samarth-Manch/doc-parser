"""Base rule builder with common functionality."""

from typing import Dict, List, Optional
from ..models import GeneratedRule, id_generator


class BaseRuleBuilder:
    """Base class for rule builders."""

    def __init__(self):
        self.id_generator = id_generator

    def create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int] = None,
        processing_type: str = "CLIENT"
    ) -> Dict:
        """
        Create base rule with all required fields and sequential ID.

        Args:
            action_type: Rule action type (e.g., MAKE_VISIBLE, VERIFY)
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            processing_type: CLIENT or SERVER

        Returns:
            Dict with base rule structure
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
            "runPostConditionFail": False,
        }

    def create_conditional_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict:
        """
        Create conditional visibility/mandatory rule.

        Args:
            action_type: MAKE_VISIBLE, MAKE_INVISIBLE, MAKE_MANDATORY, etc.
            source_ids: Controlling field IDs
            destination_ids: Controlled field IDs
            conditional_values: Values that trigger the rule
            condition: IN or NOT_IN

        Returns:
            Dict with conditional rule structure
        """
        rule = self.create_base_rule(action_type, source_ids, destination_ids)
        rule.update({
            "conditionalValues": conditional_values,
            "condition": condition,
            "conditionValueType": "TEXT",
        })
        return rule

    def create_disabled_rule(
        self,
        source_id: int,
        destination_ids: List[int]
    ) -> Dict:
        """
        Create MAKE_DISABLED rule.

        Uses a control field with NOT_IN condition to always disable.

        Args:
            source_id: Control field ID (or rule check field)
            destination_ids: Fields to disable

        Returns:
            Dict with disabled rule structure
        """
        rule = self.create_base_rule(
            "MAKE_DISABLED",
            [source_id],
            destination_ids
        )
        rule.update({
            "conditionalValues": ["Disable"],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
        })
        return rule

    def set_post_trigger_rules(self, rule: Dict, trigger_ids: List[int]):
        """Set postTriggerRuleIds on a rule."""
        rule["postTriggerRuleIds"] = trigger_ids

    def to_generated_rule(self, rule_dict: Dict) -> GeneratedRule:
        """Convert dict to GeneratedRule object."""
        return GeneratedRule(
            id=rule_dict.get("id", 0),
            action_type=rule_dict.get("actionType", ""),
            processing_type=rule_dict.get("processingType", "CLIENT"),
            source_type=rule_dict.get("sourceType"),
            source_ids=rule_dict.get("sourceIds", []),
            destination_ids=rule_dict.get("destinationIds", []),
            conditional_values=rule_dict.get("conditionalValues", []),
            condition=rule_dict.get("condition", ""),
            condition_value_type=rule_dict.get("conditionValueType", "TEXT"),
            post_trigger_rule_ids=rule_dict.get("postTriggerRuleIds", []),
            button=rule_dict.get("button", ""),
            params=rule_dict.get("params", ""),
            searchable=rule_dict.get("searchable", False),
            execute_on_fill=rule_dict.get("executeOnFill", True),
            execute_on_read=rule_dict.get("executeOnRead", False),
            execute_on_esign=rule_dict.get("executeOnEsign", False),
            execute_post_esign=rule_dict.get("executePostEsign", False),
            run_post_condition_fail=rule_dict.get("runPostConditionFail", False),
        )
