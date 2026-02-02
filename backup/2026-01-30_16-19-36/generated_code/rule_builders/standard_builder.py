"""
Standard rule builder for actionType-based rules.
"""

from typing import List
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from .base_builder import BaseRuleBuilder
    from ..models import RuleSelection, GeneratedRule
except (ImportError, ValueError):
    # Import from current package directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from rule_builders.base_builder import BaseRuleBuilder
    from models import RuleSelection, GeneratedRule


class StandardRuleBuilder(BaseRuleBuilder):
    """Builder for standard formFillRules with actionType."""

    def build(self, rule_selection: RuleSelection) -> List[GeneratedRule]:
        """
        Build standard formFillRule.

        Args:
            rule_selection: Rule selection to build

        Returns:
            List containing single GeneratedRule
        """
        source_ids = self._get_source_ids(rule_selection.source_field)
        destination_ids = self._get_destination_ids(rule_selection.destination_fields)

        # For rules without source (self-reference), use destination as source
        if not source_ids and destination_ids:
            source_ids = destination_ids

        rule = GeneratedRule(
            rule_id=self.get_next_rule_id(),
            action_type=rule_selection.action_type.value,
            processing_type=rule_selection.processing_type,
            source_ids=source_ids,
            destination_ids=destination_ids,
            conditional_values=rule_selection.conditional_values,
            condition=rule_selection.condition_operator.value,
            condition_value_type="TEXT",
            execute_on_fill=rule_selection.execute_on_fill,
            execute_on_read=rule_selection.execute_on_read,
            execute_on_esign=rule_selection.execute_on_esign
        )

        return [rule]
