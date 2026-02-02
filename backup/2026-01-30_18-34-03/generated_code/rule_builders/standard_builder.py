"""
Standard Rule Builder - Builds common rules like MAKE_VISIBLE, MAKE_MANDATORY, etc.
"""

from typing import Dict, List, Optional
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


class StandardRuleBuilder(BaseRuleBuilder):
    """Builds standard rules with actionType (visibility, mandatory, disabled)."""

    def build(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str] = None,
        condition: str = "IN",
        processing_type: str = "CLIENT",
        post_trigger_rule_ids: List[int] = None,
        params: str = None,
    ) -> Dict:
        """
        Build a standard rule.

        Args:
            action_type: Rule action type
            source_ids: Source field IDs (controlling fields)
            destination_ids: Destination field IDs (affected fields)
            conditional_values: Values that trigger the rule
            condition: "IN" or "NOT_IN"
            processing_type: "CLIENT" or "SERVER"
            post_trigger_rule_ids: Rules to trigger after
            params: Optional JSON params

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type=action_type,
            source_ids=source_ids,
            destination_ids=destination_ids,
            processing_type=processing_type,
            conditional_values=conditional_values,
            condition=condition,
            post_trigger_rule_ids=post_trigger_rule_ids,
            params=params,
        )

    def build_visibility_pair(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
    ) -> List[Dict]:
        """
        Build a pair of visibility rules (visible when IN, invisible when NOT_IN).

        Args:
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            conditional_values: Values that trigger visibility

        Returns:
            List of two rule dictionaries
        """
        return [
            self.build(
                action_type="MAKE_VISIBLE",
                source_ids=source_ids,
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="IN",
            ),
            self.build(
                action_type="MAKE_INVISIBLE",
                source_ids=source_ids,
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="NOT_IN",
            ),
        ]

    def build_mandatory_pair(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
    ) -> List[Dict]:
        """
        Build a pair of mandatory rules (mandatory when IN, non-mandatory when NOT_IN).

        Args:
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            conditional_values: Values that trigger mandatory

        Returns:
            List of two rule dictionaries
        """
        return [
            self.build(
                action_type="MAKE_MANDATORY",
                source_ids=source_ids,
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="IN",
            ),
            self.build(
                action_type="MAKE_NON_MANDATORY",
                source_ids=source_ids,
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="NOT_IN",
            ),
        ]

    def build_visibility_and_mandatory_quad(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
    ) -> List[Dict]:
        """
        Build four rules for "visible and mandatory when X, invisible and non-mandatory otherwise".

        Args:
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            conditional_values: Values that trigger visibility and mandatory

        Returns:
            List of four rule dictionaries
        """
        rules = []
        rules.extend(self.build_visibility_pair(source_ids, destination_ids, conditional_values))
        rules.extend(self.build_mandatory_pair(source_ids, destination_ids, conditional_values))
        return rules

    def build_disabled(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str] = None,
        condition: str = "NOT_IN",
    ) -> Dict:
        """
        Build a MAKE_DISABLED rule.

        For always-disabled fields, use conditional_values=["Disable"] with condition="NOT_IN"
        which will always trigger since the field never equals "Disable".

        Args:
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            conditional_values: Values (default: ["Disable"])
            condition: Condition operator (default: "NOT_IN" for always trigger)

        Returns:
            Rule dictionary
        """
        return self.build(
            action_type="MAKE_DISABLED",
            source_ids=source_ids,
            destination_ids=destination_ids,
            conditional_values=conditional_values or ["Disable"],
            condition=condition,
        )

    def build_convert_to_uppercase(
        self,
        source_ids: List[int],
    ) -> Dict:
        """
        Build a CONVERT_TO rule for uppercase.

        Args:
            source_ids: Field IDs to convert

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="CONVERT_TO",
            source_type="UPPER_CASE",
            source_ids=source_ids,
            destination_ids=[],
        )

    def build_copy_txnid(
        self,
        field_id: int,
    ) -> Dict:
        """
        Build a COPY_TXNID_TO_FORM_FILL rule.

        Args:
            field_id: Transaction ID field

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="COPY_TXNID_TO_FORM_FILL",
            source_ids=[field_id],
            destination_ids=[field_id],
            conditional_values=["TXN"],
            condition="NOT_IN",
        )
