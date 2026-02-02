"""
Standard Rule Builder - Builds standard action-type rules.
"""

from typing import List, Optional
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule, IdGenerator


class StandardRuleBuilder(BaseRuleBuilder):
    """Builds standard action-type rules (MAKE_VISIBLE, MAKE_MANDATORY, etc.)."""

    def __init__(self, id_generator: IdGenerator):
        super().__init__(id_generator)

    def build_visibility_rule(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        make_visible: bool = True
    ) -> GeneratedRule:
        """
        Build visibility rule (MAKE_VISIBLE or MAKE_INVISIBLE).

        Args:
            source_ids: Controlling field IDs.
            destination_ids: Fields to show/hide.
            conditional_values: Values that trigger the rule.
            make_visible: True for MAKE_VISIBLE, False for MAKE_INVISIBLE.

        Returns:
            GeneratedRule for visibility control.
        """
        action = "MAKE_VISIBLE" if make_visible else "MAKE_INVISIBLE"
        return self.create_conditional_rule(
            action,
            source_ids,
            destination_ids,
            conditional_values,
            "IN"
        )

    def build_mandatory_rule(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        make_mandatory: bool = True
    ) -> GeneratedRule:
        """
        Build mandatory rule (MAKE_MANDATORY or MAKE_NON_MANDATORY).

        Args:
            source_ids: Controlling field IDs.
            destination_ids: Fields to make mandatory/optional.
            conditional_values: Values that trigger the rule.
            make_mandatory: True for MAKE_MANDATORY, False for MAKE_NON_MANDATORY.

        Returns:
            GeneratedRule for mandatory control.
        """
        action = "MAKE_MANDATORY" if make_mandatory else "MAKE_NON_MANDATORY"
        return self.create_conditional_rule(
            action,
            source_ids,
            destination_ids,
            conditional_values,
            "IN"
        )

    def build_enabled_rule(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        make_enabled: bool = True
    ) -> GeneratedRule:
        """
        Build enabled/disabled rule.

        Args:
            source_ids: Controlling field IDs.
            destination_ids: Fields to enable/disable.
            conditional_values: Values that trigger the rule.
            make_enabled: True for MAKE_ENABLED, False for MAKE_DISABLED.

        Returns:
            GeneratedRule for editability control.
        """
        action = "MAKE_ENABLED" if make_enabled else "MAKE_DISABLED"
        return self.create_conditional_rule(
            action,
            source_ids,
            destination_ids,
            conditional_values,
            "IN"
        )

    def build_ext_dropdown_rule(
        self,
        field_id: int,
        params: str = "",
        parent_field_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Build EXT_DROP_DOWN rule for external/cascading dropdowns.

        Args:
            field_id: The dropdown field ID.
            params: Parameters for the dropdown (e.g., "COMPANY_CODE").
            parent_field_id: Parent field ID for cascading dropdowns.

        Returns:
            GeneratedRule for external dropdown.
        """
        if parent_field_id:
            # Cascading dropdown
            rule = self.create_base_rule(
                "EXT_DROP_DOWN",
                [parent_field_id],
                [field_id],
                "SERVER"
            )
        else:
            # Simple external dropdown
            rule = self.create_base_rule(
                "EXT_DROP_DOWN",
                [field_id],
                [],
                "SERVER"
            )

        rule.source_type = "FORM_FILL_DROP_DOWN"
        rule.params = params
        rule.searchable = True
        return rule

    def build_ext_value_rule(
        self,
        field_id: int,
        params: str = ""
    ) -> GeneratedRule:
        """
        Build EXT_VALUE rule for external data values.

        Args:
            field_id: The field ID to populate.
            params: Parameters for the value lookup.

        Returns:
            GeneratedRule for external value.
        """
        rule = self.create_base_rule(
            "EXT_VALUE",
            [field_id],
            [],
            "SERVER"
        )
        rule.source_type = "EXTERNAL_DATA_VALUE"
        rule.params = params
        return rule

    def build_convert_to_rule(
        self,
        field_id: int,
        conversion_type: str = "UPPER_CASE"
    ) -> GeneratedRule:
        """
        Build CONVERT_TO rule for text conversion.

        Args:
            field_id: Field to convert.
            conversion_type: Type of conversion (e.g., "UPPER_CASE").

        Returns:
            GeneratedRule for text conversion.
        """
        rule = self.create_base_rule(
            "CONVERT_TO",
            [field_id],
            [],
            "CLIENT"
        )
        rule.source_type = conversion_type
        return rule

    def build_copy_to_rule(
        self,
        source_field_id: int,
        destination_field_ids: List[int]
    ) -> GeneratedRule:
        """
        Build COPY_TO rule for copying values between fields.

        Args:
            source_field_id: Source field to copy from.
            destination_field_ids: Destination fields to copy to.

        Returns:
            GeneratedRule for value copying.
        """
        return self.create_base_rule(
            "COPY_TO",
            [source_field_id],
            destination_field_ids,
            "CLIENT"
        )

    def build_clear_field_rule(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str]
    ) -> GeneratedRule:
        """
        Build CLEAR_FIELD rule.

        Args:
            source_ids: Triggering field IDs.
            destination_ids: Fields to clear.
            conditional_values: Values that trigger the clear.

        Returns:
            GeneratedRule for clearing fields.
        """
        return self.create_conditional_rule(
            "CLEAR_FIELD",
            source_ids,
            destination_ids,
            conditional_values,
            "IN"
        )
