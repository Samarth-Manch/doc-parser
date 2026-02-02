"""
Visibility Rule Builder - Builds visibility and mandatory control rules.
"""

from typing import List, Dict, Any, Optional
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule, IdGenerator, VisibilityGroup


class VisibilityRuleBuilder(BaseRuleBuilder):
    """Builds visibility control rules with consolidated destinations."""

    def __init__(self, id_generator: IdGenerator):
        super().__init__(id_generator)

    def build_visibility_group_rules(
        self,
        controlling_field_id: int,
        visibility_group: VisibilityGroup
    ) -> List[GeneratedRule]:
        """
        Build all visibility rules for a visibility group.

        CRITICAL: Visibility rules are placed on the CONTROLLING field,
        with multiple destinations in destinationIds array.

        Args:
            controlling_field_id: ID of the field that controls visibility.
            visibility_group: Group of fields controlled by this field.

        Returns:
            List of GeneratedRules for visibility control.
        """
        rules = []

        # Group destinations by conditional value
        by_value: Dict[str, List[Dict]] = {}

        for dest in visibility_group.destination_fields:
            values = dest.get('conditional_values', [])
            action = dest.get('action', 'MAKE_VISIBLE')

            for value in values:
                key = f"{action}:{value}"
                if key not in by_value:
                    by_value[key] = []
                by_value[key].append(dest)

        # Create one rule per unique (action, value) combination
        for key, destinations in by_value.items():
            action, value = key.split(':', 1)

            dest_ids = [d.get('field_id') for d in destinations if d.get('field_id')]

            if dest_ids:
                rule = self.create_conditional_rule(
                    action_type=action,
                    source_ids=[controlling_field_id],
                    destination_ids=dest_ids,
                    conditional_values=[value],
                    condition="IN"
                )
                rules.append(rule)

        return rules

    def build_visibility_pair(
        self,
        controlling_field_id: int,
        destination_ids: List[int],
        show_values: List[str],
        hide_values: Optional[List[str]] = None
    ) -> List[GeneratedRule]:
        """
        Build visibility rule pair (show and hide).

        Args:
            controlling_field_id: ID of the controlling field.
            destination_ids: IDs of fields to show/hide.
            show_values: Values that make fields visible.
            hide_values: Values that make fields invisible (optional).

        Returns:
            List containing MAKE_VISIBLE and optionally MAKE_INVISIBLE rules.
        """
        rules = []

        # MAKE_VISIBLE rule
        visible_rule = self.create_conditional_rule(
            "MAKE_VISIBLE",
            [controlling_field_id],
            destination_ids,
            show_values,
            "IN"
        )
        rules.append(visible_rule)

        # MAKE_INVISIBLE rule (for opposite values or NOT_IN)
        if hide_values:
            invisible_rule = self.create_conditional_rule(
                "MAKE_INVISIBLE",
                [controlling_field_id],
                destination_ids,
                hide_values,
                "IN"
            )
            rules.append(invisible_rule)
        else:
            # Use NOT_IN for the same values
            invisible_rule = self.create_conditional_rule(
                "MAKE_INVISIBLE",
                [controlling_field_id],
                destination_ids,
                show_values,
                "NOT_IN"
            )
            rules.append(invisible_rule)

        return rules

    def build_mandatory_pair(
        self,
        controlling_field_id: int,
        destination_ids: List[int],
        mandatory_values: List[str],
        non_mandatory_values: Optional[List[str]] = None
    ) -> List[GeneratedRule]:
        """
        Build mandatory rule pair.

        Args:
            controlling_field_id: ID of the controlling field.
            destination_ids: IDs of fields to make mandatory/optional.
            mandatory_values: Values that make fields mandatory.
            non_mandatory_values: Values that make fields optional (optional).

        Returns:
            List containing MAKE_MANDATORY and MAKE_NON_MANDATORY rules.
        """
        rules = []

        # MAKE_MANDATORY rule
        mandatory_rule = self.create_conditional_rule(
            "MAKE_MANDATORY",
            [controlling_field_id],
            destination_ids,
            mandatory_values,
            "IN"
        )
        rules.append(mandatory_rule)

        # MAKE_NON_MANDATORY rule
        if non_mandatory_values:
            non_mandatory_rule = self.create_conditional_rule(
                "MAKE_NON_MANDATORY",
                [controlling_field_id],
                destination_ids,
                non_mandatory_values,
                "IN"
            )
            rules.append(non_mandatory_rule)
        else:
            non_mandatory_rule = self.create_conditional_rule(
                "MAKE_NON_MANDATORY",
                [controlling_field_id],
                destination_ids,
                mandatory_values,
                "NOT_IN"
            )
            rules.append(non_mandatory_rule)

        return rules

    def build_visibility_and_mandatory_pair(
        self,
        controlling_field_id: int,
        destination_ids: List[int],
        trigger_values: List[str],
        opposite_values: Optional[List[str]] = None
    ) -> List[GeneratedRule]:
        """
        Build combined visibility and mandatory rules.

        This is for common patterns like:
        "if X is Yes then visible and mandatory, otherwise invisible and non-mandatory"

        Args:
            controlling_field_id: ID of the controlling field.
            destination_ids: IDs of controlled fields.
            trigger_values: Values that trigger visible+mandatory.
            opposite_values: Values that trigger invisible+non-mandatory.

        Returns:
            List of 4 rules: MAKE_VISIBLE, MAKE_MANDATORY, MAKE_INVISIBLE, MAKE_NON_MANDATORY.
        """
        rules = []

        # Visible and mandatory for trigger values
        rules.append(self.create_conditional_rule(
            "MAKE_VISIBLE",
            [controlling_field_id],
            destination_ids,
            trigger_values,
            "IN"
        ))

        rules.append(self.create_conditional_rule(
            "MAKE_MANDATORY",
            [controlling_field_id],
            destination_ids,
            trigger_values,
            "IN"
        ))

        # Invisible and non-mandatory for opposite values
        if opposite_values:
            rules.append(self.create_conditional_rule(
                "MAKE_INVISIBLE",
                [controlling_field_id],
                destination_ids,
                opposite_values,
                "IN"
            ))

            rules.append(self.create_conditional_rule(
                "MAKE_NON_MANDATORY",
                [controlling_field_id],
                destination_ids,
                opposite_values,
                "IN"
            ))
        else:
            rules.append(self.create_conditional_rule(
                "MAKE_INVISIBLE",
                [controlling_field_id],
                destination_ids,
                trigger_values,
                "NOT_IN"
            ))

            rules.append(self.create_conditional_rule(
                "MAKE_NON_MANDATORY",
                [controlling_field_id],
                destination_ids,
                trigger_values,
                "NOT_IN"
            ))

        return rules
