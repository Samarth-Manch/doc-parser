"""
Visibility Rule Builder - Build MAKE_VISIBLE, MAKE_INVISIBLE,
MAKE_MANDATORY, MAKE_NON_MANDATORY, and MAKE_DISABLED rules.

Key insight: Visibility rules go on the CONTROLLING field, not the destinations.
For logic like:
  "if the field 'GST option' is yes then visible otherwise invisible"

Generate rules on the GST option field with multiple destination IDs,
NOT individual rules on each destination field.
"""

from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .base_builder import BaseRuleBuilder, get_rule_id
from ..models import GeneratedRule, ParsedCondition


class VisibilityRuleBuilder(BaseRuleBuilder):
    """Build visibility and mandatory rules."""

    def __init__(self):
        super().__init__()

    def build_visibility_rules(
        self,
        source_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        include_invisible: bool = True
    ) -> List[GeneratedRule]:
        """
        Build MAKE_VISIBLE and optionally MAKE_INVISIBLE rules.

        For "if X is Y then visible otherwise invisible" patterns,
        generates paired rules:
        - MAKE_VISIBLE with condition IN [Y]
        - MAKE_INVISIBLE with condition NOT_IN [Y]

        Args:
            source_id: Controlling field ID
            destination_ids: Field IDs to show/hide
            conditional_values: Values that make fields visible
            include_invisible: Whether to also generate MAKE_INVISIBLE rule

        Returns:
            List of GeneratedRule objects
        """
        rules = []

        # MAKE_VISIBLE rule
        rules.append(self.create_conditional_rule(
            action_type="MAKE_VISIBLE",
            source_ids=[source_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        ))

        # MAKE_INVISIBLE rule (paired)
        if include_invisible:
            rules.append(self.create_conditional_rule(
                action_type="MAKE_INVISIBLE",
                source_ids=[source_id],
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="NOT_IN"
            ))

        return rules

    def build_mandatory_rules(
        self,
        source_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        include_non_mandatory: bool = True
    ) -> List[GeneratedRule]:
        """
        Build MAKE_MANDATORY and optionally MAKE_NON_MANDATORY rules.

        Args:
            source_id: Controlling field ID
            destination_ids: Field IDs to make mandatory/optional
            conditional_values: Values that make fields mandatory
            include_non_mandatory: Whether to also generate MAKE_NON_MANDATORY rule

        Returns:
            List of GeneratedRule objects
        """
        rules = []

        # MAKE_MANDATORY rule
        rules.append(self.create_conditional_rule(
            action_type="MAKE_MANDATORY",
            source_ids=[source_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        ))

        # MAKE_NON_MANDATORY rule (paired)
        if include_non_mandatory:
            rules.append(self.create_conditional_rule(
                action_type="MAKE_NON_MANDATORY",
                source_ids=[source_id],
                destination_ids=destination_ids,
                conditional_values=conditional_values,
                condition="NOT_IN"
            ))

        return rules

    def build_full_visibility_mandatory_rules(
        self,
        source_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> List[GeneratedRule]:
        """
        Build full set of visibility and mandatory rules.

        For "if X is Y then visible and mandatory otherwise invisible and non-mandatory"
        generates 4 rules:
        1. MAKE_VISIBLE (IN)
        2. MAKE_MANDATORY (IN)
        3. MAKE_INVISIBLE (NOT_IN)
        4. MAKE_NON_MANDATORY (NOT_IN)

        Args:
            source_id: Controlling field ID
            destination_ids: Field IDs affected
            conditional_values: Values that trigger visibility/mandatory

        Returns:
            List of 4 GeneratedRule objects
        """
        rules = []
        rules.extend(self.build_visibility_rules(
            source_id, destination_ids, conditional_values, include_invisible=True
        ))
        rules.extend(self.build_mandatory_rules(
            source_id, destination_ids, conditional_values, include_non_mandatory=True
        ))
        return rules

    def build_disabled_rule_consolidated(
        self,
        rulecheck_field_id: int,
        destination_ids: List[int]
    ) -> GeneratedRule:
        """
        Build a consolidated MAKE_DISABLED rule with multiple destinations.

        Uses the RuleCheck pattern from reference:
        - sourceIds: [rulecheck_field_id]
        - conditionalValues: ["Disable"]
        - condition: "NOT_IN" (always triggers)

        Args:
            rulecheck_field_id: ID of the RuleCheck control field
            destination_ids: All field IDs to disable

        Returns:
            Single GeneratedRule with all destinations
        """
        return self.create_disabled_rule(
            source_id=rulecheck_field_id,
            destination_ids=destination_ids
        )

    def build_session_based_visibility_rule(
        self,
        source_id: int,
        destination_ids: List[int],
        party_type: str = "FIRST_PARTY"
    ) -> GeneratedRule:
        """
        Build SESSION_BASED_MAKE_VISIBLE rule.

        Used when visibility differs between first party and second party.

        Args:
            source_id: Controlling field ID
            destination_ids: Field IDs to show/hide
            party_type: "FIRST_PARTY" or "SECOND_PARTY"

        Returns:
            GeneratedRule for session-based visibility
        """
        rule = self.create_conditional_rule(
            action_type="SESSION_BASED_MAKE_VISIBLE",
            source_ids=[source_id],
            destination_ids=destination_ids,
            conditional_values=["Invisible"],
            condition="NOT_IN"
        )
        rule.params = party_type
        return rule


class VisibilityGroupCollector:
    """
    Collect and group visibility rules by controlling field.

    Parses field logic to identify which fields control visibility of others,
    then groups all destinations under the controlling field's rules.
    """

    def __init__(self):
        # controlling_field_name -> {conditional_value -> [destination_field_ids]}
        self.groups: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))

        # Track what actions each group needs
        # controlling_field_name -> set of actions (MAKE_VISIBLE, MAKE_MANDATORY, etc.)
        self.actions: Dict[str, set] = defaultdict(set)

    def add_visibility_reference(
        self,
        controlling_field_name: str,
        destination_field_id: int,
        conditional_values: List[str],
        is_mandatory: bool = False
    ):
        """
        Add a visibility reference.

        Args:
            controlling_field_name: Name of the field that controls visibility
            destination_field_id: ID of the field being controlled
            conditional_values: Values that trigger visibility
            is_mandatory: Whether this also affects mandatory status
        """
        for value in conditional_values:
            self.groups[controlling_field_name][value].append(destination_field_id)

        self.actions[controlling_field_name].add("MAKE_VISIBLE")
        self.actions[controlling_field_name].add("MAKE_INVISIBLE")

        if is_mandatory:
            self.actions[controlling_field_name].add("MAKE_MANDATORY")
            self.actions[controlling_field_name].add("MAKE_NON_MANDATORY")

    def get_grouped_rules(
        self,
        field_name_to_id: Dict[str, int]
    ) -> List[GeneratedRule]:
        """
        Generate consolidated visibility rules.

        Args:
            field_name_to_id: Mapping of field names to IDs

        Returns:
            List of consolidated GeneratedRule objects
        """
        builder = VisibilityRuleBuilder()
        rules = []

        for controlling_name, value_groups in self.groups.items():
            controlling_id = field_name_to_id.get(controlling_name)
            if not controlling_id:
                continue

            actions = self.actions[controlling_name]

            for conditional_value, destination_ids in value_groups.items():
                # Remove duplicates
                unique_dest_ids = list(set(destination_ids))

                if "MAKE_VISIBLE" in actions:
                    rules.append(builder.create_conditional_rule(
                        action_type="MAKE_VISIBLE",
                        source_ids=[controlling_id],
                        destination_ids=unique_dest_ids,
                        conditional_values=[conditional_value],
                        condition="IN"
                    ))

                if "MAKE_INVISIBLE" in actions:
                    rules.append(builder.create_conditional_rule(
                        action_type="MAKE_INVISIBLE",
                        source_ids=[controlling_id],
                        destination_ids=unique_dest_ids,
                        conditional_values=[conditional_value],
                        condition="NOT_IN"
                    ))

                if "MAKE_MANDATORY" in actions:
                    rules.append(builder.create_conditional_rule(
                        action_type="MAKE_MANDATORY",
                        source_ids=[controlling_id],
                        destination_ids=unique_dest_ids,
                        conditional_values=[conditional_value],
                        condition="IN"
                    ))

                if "MAKE_NON_MANDATORY" in actions:
                    rules.append(builder.create_conditional_rule(
                        action_type="MAKE_NON_MANDATORY",
                        source_ids=[controlling_id],
                        destination_ids=unique_dest_ids,
                        conditional_values=[conditional_value],
                        condition="NOT_IN"
                    ))

        return rules
