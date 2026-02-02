"""
Base rule builder class.
"""

from typing import List, Optional
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ..models import RuleSelection, GeneratedRule, FieldInfo
except ImportError:
    from models import RuleSelection, GeneratedRule, FieldInfo


class BaseRuleBuilder:
    """Base class for rule builders."""

    def __init__(self, start_rule_id: int = 100000):
        """
        Initialize rule builder.

        Args:
            start_rule_id: Starting ID for generated rules
        """
        self.current_rule_id = start_rule_id

    def get_next_rule_id(self) -> int:
        """Get next available rule ID."""
        rule_id = self.current_rule_id
        self.current_rule_id += 1
        return rule_id

    def build(self, rule_selection: RuleSelection) -> List[GeneratedRule]:
        """
        Build formFillRules from RuleSelection.

        Args:
            rule_selection: Rule selection to build

        Returns:
            List of GeneratedRule objects
        """
        raise NotImplementedError("Subclasses must implement build()")

    def _get_source_ids(self, source_field: Optional[FieldInfo]) -> List[int]:
        """Get source field IDs."""
        if source_field:
            return [source_field.field_id]
        return []

    def _get_destination_ids(self, destination_fields: List[FieldInfo]) -> List[int]:
        """Get destination field IDs."""
        return [field.field_id for field in destination_fields]
