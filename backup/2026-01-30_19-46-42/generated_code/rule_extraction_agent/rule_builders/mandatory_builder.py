"""
Mandatory Rule Builder - Build MAKE_MANDATORY and MAKE_NON_MANDATORY rules.
"""

from typing import List, Dict, Optional
from .base_builder import BaseRuleBuilder, RuleIdGenerator
from ..models import GeneratedRule


class MandatoryRuleBuilder(BaseRuleBuilder):
    """Build mandatory rules (MAKE_MANDATORY, MAKE_NON_MANDATORY)."""

    def __init__(self, id_generator: Optional[RuleIdGenerator] = None):
        super().__init__(id_generator)

    def build_mandatory_pair(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        include_non_mandatory: bool = True
    ) -> List[GeneratedRule]:
        """
        Build a mandatory rule pair (mandatory + non-mandatory).

        For "if X is Y then mandatory otherwise non-mandatory", generates:
        1. MAKE_MANDATORY with condition IN
        2. MAKE_NON_MANDATORY with condition NOT_IN

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to make mandatory/non-mandatory
            conditional_values: Values that trigger mandatory
            include_non_mandatory: Whether to include the MAKE_NON_MANDATORY rule

        Returns:
            List of mandatory rules.
        """
        rules = []

        # MAKE_MANDATORY rule
        mandatory_rule = self.create_conditional_rule(
            action_type="MAKE_MANDATORY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        )
        rules.append(mandatory_rule)

        # MAKE_NON_MANDATORY rule (opposite condition)
        if include_non_mandatory:
            non_mandatory_rule = self.create_conditional_rule(
                action_type="MAKE_NON_MANDATORY",
                source_ids=[source_field_id],
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="NOT_IN"
            )
            rules.append(non_mandatory_rule)

        return rules

    def build_visibility_mandatory_quad(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> List[GeneratedRule]:
        """
        Build the full set of visibility + mandatory rules.

        For "if X is Y then visible and mandatory otherwise invisible and non-mandatory":
        1. MAKE_VISIBLE with condition IN
        2. MAKE_MANDATORY with condition IN
        3. MAKE_INVISIBLE with condition NOT_IN
        4. MAKE_NON_MANDATORY with condition NOT_IN

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of affected fields
            conditional_values: Values that trigger visible+mandatory

        Returns:
            List of 4 rules.
        """
        rules = []

        # MAKE_VISIBLE
        rules.append(self.create_conditional_rule(
            action_type="MAKE_VISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        ))

        # MAKE_MANDATORY
        rules.append(self.create_conditional_rule(
            action_type="MAKE_MANDATORY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        ))

        # MAKE_INVISIBLE
        rules.append(self.create_conditional_rule(
            action_type="MAKE_INVISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="NOT_IN"
        ))

        # MAKE_NON_MANDATORY
        rules.append(self.create_conditional_rule(
            action_type="MAKE_NON_MANDATORY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="NOT_IN"
        ))

        return rules

    def build_session_based_mandatory(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        party_type: str = "FIRST_PARTY"
    ) -> GeneratedRule:
        """
        Build a session-based mandatory rule.

        Args:
            source_field_id: ID of the controlling field
            destination_ids: IDs of fields to make mandatory
            conditional_values: Values to match
            party_type: "FIRST_PARTY" or "SECOND_PARTY"

        Returns:
            Session-based mandatory rule.
        """
        rule = self.create_conditional_rule(
            action_type="SESSION_BASED_MAKE_MANDATORY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="NOT_IN"
        )
        rule.params = party_type
        return rule
