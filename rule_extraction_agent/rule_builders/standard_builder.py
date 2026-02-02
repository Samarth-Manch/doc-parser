"""Standard rule builder for common rule types."""

from typing import Dict, List, Optional
from .base_builder import BaseRuleBuilder


class StandardRuleBuilder(BaseRuleBuilder):
    """Builder for standard visibility/mandatory/disabled rules."""

    def build_visibility_rules(
        self,
        source_field_id: int,
        visible_destinations: List[int],
        invisible_destinations: List[int],
        conditional_values: List[str]
    ) -> List[Dict]:
        """
        Build visibility rules for a controlling field.

        Args:
            source_field_id: Controlling field ID
            visible_destinations: Field IDs to make visible when condition matches
            invisible_destinations: Field IDs to make invisible when condition matches
            conditional_values: Values that trigger visibility

        Returns:
            List of visibility rule dicts
        """
        rules = []

        # MAKE_VISIBLE when condition IN
        if visible_destinations:
            rules.append(self.create_conditional_rule(
                action_type="MAKE_VISIBLE",
                source_ids=[source_field_id],
                destination_ids=visible_destinations,
                conditional_values=conditional_values,
                condition="IN"
            ))

        # MAKE_INVISIBLE when condition NOT_IN
        if invisible_destinations:
            rules.append(self.create_conditional_rule(
                action_type="MAKE_INVISIBLE",
                source_ids=[source_field_id],
                destination_ids=invisible_destinations,
                conditional_values=conditional_values,
                condition="NOT_IN"
            ))

        return rules

    def build_mandatory_rules(
        self,
        source_field_id: int,
        mandatory_destinations: List[int],
        non_mandatory_destinations: List[int],
        conditional_values: List[str]
    ) -> List[Dict]:
        """
        Build mandatory rules for a controlling field.

        Args:
            source_field_id: Controlling field ID
            mandatory_destinations: Field IDs to make mandatory when condition matches
            non_mandatory_destinations: Field IDs to make non-mandatory
            conditional_values: Values that trigger mandatory

        Returns:
            List of mandatory rule dicts
        """
        rules = []

        # MAKE_MANDATORY when condition IN
        if mandatory_destinations:
            rules.append(self.create_conditional_rule(
                action_type="MAKE_MANDATORY",
                source_ids=[source_field_id],
                destination_ids=mandatory_destinations,
                conditional_values=conditional_values,
                condition="IN"
            ))

        # MAKE_NON_MANDATORY when condition NOT_IN
        if non_mandatory_destinations:
            rules.append(self.create_conditional_rule(
                action_type="MAKE_NON_MANDATORY",
                source_ids=[source_field_id],
                destination_ids=non_mandatory_destinations,
                conditional_values=conditional_values,
                condition="NOT_IN"
            ))

        return rules

    def build_visibility_and_mandatory(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> List[Dict]:
        """
        Build combined visibility and mandatory rules.

        When condition matches: visible AND mandatory
        When condition doesn't match: invisible AND non-mandatory

        Args:
            source_field_id: Controlling field ID
            destination_ids: Field IDs to control
            conditional_values: Values that trigger the rules

        Returns:
            List of 4 rules (visible, invisible, mandatory, non-mandatory)
        """
        rules = []

        # MAKE_VISIBLE when IN
        rules.append(self.create_conditional_rule(
            action_type="MAKE_VISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        ))

        # MAKE_INVISIBLE when NOT_IN
        rules.append(self.create_conditional_rule(
            action_type="MAKE_INVISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="NOT_IN"
        ))

        # MAKE_MANDATORY when IN
        rules.append(self.create_conditional_rule(
            action_type="MAKE_MANDATORY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        ))

        # MAKE_NON_MANDATORY when NOT_IN
        rules.append(self.create_conditional_rule(
            action_type="MAKE_NON_MANDATORY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="NOT_IN"
        ))

        return rules

    def build_disabled_rules(
        self,
        control_field_id: int,
        destination_ids: List[int]
    ) -> List[Dict]:
        """
        Build MAKE_DISABLED rules.

        Args:
            control_field_id: Control field ID (usually RuleCheck field)
            destination_ids: Field IDs to disable

        Returns:
            List with single disabled rule
        """
        return [self.create_disabled_rule(control_field_id, destination_ids)]

    def build_convert_to_rule(
        self,
        field_id: int,
        convert_type: str = "UPPER_CASE"
    ) -> Dict:
        """
        Build CONVERT_TO rule.

        Args:
            field_id: Field to convert
            convert_type: Conversion type (UPPER_CASE, LOWER_CASE, etc.)

        Returns:
            CONVERT_TO rule dict
        """
        rule = self.create_base_rule(
            action_type="CONVERT_TO",
            source_ids=[field_id],
            destination_ids=[]
        )
        rule["sourceType"] = convert_type
        return rule

    def build_clear_field_rule(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> Dict:
        """
        Build CLEAR_FIELD rule.

        Args:
            source_field_id: Triggering field ID
            destination_ids: Fields to clear
            conditional_values: Values that trigger clearing

        Returns:
            CLEAR_FIELD rule dict
        """
        rule = self.create_conditional_rule(
            action_type="CLEAR_FIELD",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition="IN"
        )
        return rule

    def build_copy_to_rule(
        self,
        source_field_id: int,
        destination_field_id: int
    ) -> Dict:
        """
        Build COPY_TO rule.

        Args:
            source_field_id: Source field ID
            destination_field_id: Destination field ID

        Returns:
            COPY_TO rule dict
        """
        return self.create_base_rule(
            action_type="COPY_TO",
            source_ids=[source_field_id],
            destination_ids=[destination_field_id]
        )
