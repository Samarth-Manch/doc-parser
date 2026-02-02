"""
Visibility Rule Builder

Builds visibility rules (MAKE_VISIBLE, MAKE_INVISIBLE) and mandatory rules
(MAKE_MANDATORY, MAKE_NON_MANDATORY).

IMPORTANT: Visibility rules are placed on the SOURCE/CONTROLLING field,
NOT on each destination field. Multiple destinations are consolidated
into a single rule with multiple destinationIds.
"""

from typing import Dict, List, Optional, Any

try:
    from .base_builder import BaseRuleBuilder
    from ..models import IdGenerator
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from rule_builders.base_builder import BaseRuleBuilder
    from models import IdGenerator


class VisibilityRuleBuilder(BaseRuleBuilder):
    """
    Builds visibility and mandatory rules.

    Key insight: When logic says "if field X is Y then Z is visible",
    the rule is placed on field X (source) with Z in destinationIds.

    For if/else patterns, generates BOTH rules:
    - Positive case: MAKE_VISIBLE with condition IN
    - Negative case: MAKE_INVISIBLE with condition NOT_IN
    """

    def __init__(self, id_generator: IdGenerator):
        """
        Initialize the visibility rule builder.

        Args:
            id_generator: IdGenerator for sequential rule IDs
        """
        super().__init__(id_generator)

    def build_visibility_pair(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Build a visibility pair (MAKE_VISIBLE + MAKE_INVISIBLE).

        For "if X is Y then visible otherwise invisible" logic,
        generates two rules:
        1. MAKE_VISIBLE when condition is IN
        2. MAKE_INVISIBLE when condition is NOT_IN

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to show/hide
            conditional_values: Values that trigger visibility

        Returns:
            List of two rule dicts (MAKE_VISIBLE, MAKE_INVISIBLE)
        """
        visible_rule = self.create_conditional_rule(
            "MAKE_VISIBLE",
            [source_field_id],
            destination_ids,
            conditional_values,
            "IN"
        )

        invisible_rule = self.create_conditional_rule(
            "MAKE_INVISIBLE",
            [source_field_id],
            destination_ids,
            conditional_values,
            "NOT_IN"
        )

        return [visible_rule, invisible_rule]

    def build_mandatory_pair(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Build a mandatory pair (MAKE_MANDATORY + MAKE_NON_MANDATORY).

        For "if X is Y then mandatory otherwise non-mandatory" logic,
        generates two rules:
        1. MAKE_MANDATORY when condition is IN
        2. MAKE_NON_MANDATORY when condition is NOT_IN

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to make mandatory/optional
            conditional_values: Values that trigger mandatory status

        Returns:
            List of two rule dicts (MAKE_MANDATORY, MAKE_NON_MANDATORY)
        """
        mandatory_rule = self.create_conditional_rule(
            "MAKE_MANDATORY",
            [source_field_id],
            destination_ids,
            conditional_values,
            "IN"
        )

        non_mandatory_rule = self.create_conditional_rule(
            "MAKE_NON_MANDATORY",
            [source_field_id],
            destination_ids,
            conditional_values,
            "NOT_IN"
        )

        return [mandatory_rule, non_mandatory_rule]

    def build_visibility_and_mandatory_quad(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Build visibility AND mandatory rules (4 rules total).

        For "if X is Y then visible and mandatory otherwise invisible and non-mandatory",
        generates four rules:
        1. MAKE_VISIBLE with IN condition
        2. MAKE_MANDATORY with IN condition
        3. MAKE_INVISIBLE with NOT_IN condition
        4. MAKE_NON_MANDATORY with NOT_IN condition

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields affected
            conditional_values: Values that trigger the rules

        Returns:
            List of four rule dicts
        """
        rules = []
        rules.extend(self.build_visibility_pair(source_field_id, destination_ids, conditional_values))
        rules.extend(self.build_mandatory_pair(source_field_id, destination_ids, conditional_values))
        return rules

    def build_make_visible(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict[str, Any]:
        """
        Build a single MAKE_VISIBLE rule.

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to show
            conditional_values: Values that trigger visibility
            condition: "IN" or "NOT_IN"

        Returns:
            MAKE_VISIBLE rule dict
        """
        return self.create_conditional_rule(
            "MAKE_VISIBLE",
            [source_field_id],
            destination_ids,
            conditional_values,
            condition
        )

    def build_make_invisible(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict[str, Any]:
        """
        Build a single MAKE_INVISIBLE rule.

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to hide
            conditional_values: Values that trigger invisibility
            condition: "IN" or "NOT_IN"

        Returns:
            MAKE_INVISIBLE rule dict
        """
        return self.create_conditional_rule(
            "MAKE_INVISIBLE",
            [source_field_id],
            destination_ids,
            conditional_values,
            condition
        )

    def build_make_mandatory(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict[str, Any]:
        """
        Build a single MAKE_MANDATORY rule.

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to make mandatory
            conditional_values: Values that trigger mandatory status
            condition: "IN" or "NOT_IN"

        Returns:
            MAKE_MANDATORY rule dict
        """
        return self.create_conditional_rule(
            "MAKE_MANDATORY",
            [source_field_id],
            destination_ids,
            conditional_values,
            condition
        )

    def build_make_non_mandatory(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict[str, Any]:
        """
        Build a single MAKE_NON_MANDATORY rule.

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to make optional
            conditional_values: Values that trigger optional status
            condition: "IN" or "NOT_IN"

        Returns:
            MAKE_NON_MANDATORY rule dict
        """
        return self.create_conditional_rule(
            "MAKE_NON_MANDATORY",
            [source_field_id],
            destination_ids,
            conditional_values,
            condition
        )

    def build_session_based_visibility(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        party_type: str = "FIRST_PARTY"
    ) -> Dict[str, Any]:
        """
        Build a SESSION_BASED_MAKE_VISIBLE rule.

        Used when visibility depends on session/party type.

        Args:
            source_field_id: ID of the source field
            destination_ids: IDs of fields to show
            conditional_values: Values that trigger visibility
            party_type: "FIRST_PARTY" or "SECOND_PARTY"

        Returns:
            SESSION_BASED_MAKE_VISIBLE rule dict
        """
        rule = self.create_conditional_rule(
            "SESSION_BASED_MAKE_VISIBLE",
            [source_field_id],
            destination_ids,
            conditional_values,
            "NOT_IN"
        )
        rule["params"] = party_type
        return rule
