"""
Standard Rule Builder

Builds standard rules including:
- MAKE_DISABLED
- EXT_DROP_DOWN
- EXT_VALUE
- CONVERT_TO
- COPY_TO
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


class StandardRuleBuilder(BaseRuleBuilder):
    """
    Builds standard rules for common action types.

    Handles:
    - MAKE_DISABLED: Disable field editing
    - EXT_DROP_DOWN: External/cascading dropdowns
    - EXT_VALUE: External data values
    - CONVERT_TO: Text transformations (uppercase, lowercase)
    - COPY_TO: Copy data between fields
    """

    def __init__(self, id_generator: IdGenerator):
        """
        Initialize the standard rule builder.

        Args:
            id_generator: IdGenerator for sequential rule IDs
        """
        super().__init__(id_generator)

    def build_make_disabled(
        self,
        source_field_id: int,
        destination_ids: List[int],
        use_rule_check: bool = True
    ) -> Dict[str, Any]:
        """
        Build a MAKE_DISABLED rule.

        Reference uses a RuleCheck control field with conditional value "Disable"
        and condition NOT_IN (always triggers).

        Args:
            source_field_id: ID of the controlling field (RuleCheck or self)
            destination_ids: IDs of fields to disable
            use_rule_check: If True, uses standard RuleCheck pattern

        Returns:
            MAKE_DISABLED rule dict
        """
        rule = self.create_conditional_rule(
            "MAKE_DISABLED",
            [source_field_id],
            destination_ids,
            ["Disable"],
            "NOT_IN"  # NOT_IN with value "Disable" = always triggers
        )
        return rule

    def build_ext_dropdown(
        self,
        source_field_id: int,
        params: str = "",
        searchable: bool = True
    ) -> Dict[str, Any]:
        """
        Build an EXT_DROP_DOWN rule.

        Used for external/cascading dropdowns that get options from
        external data sources.

        Args:
            source_field_id: ID of the dropdown field
            params: External table/lookup name (e.g., "COMPANY_CODE")
            searchable: Whether the dropdown is searchable

        Returns:
            EXT_DROP_DOWN rule dict
        """
        rule = self.create_base_rule(
            "EXT_DROP_DOWN",
            [source_field_id],
            [],
            "CLIENT"
        )

        rule.update({
            "sourceType": "FORM_FILL_DROP_DOWN",
            "params": params,
            "searchable": searchable
        })

        return rule

    def build_ext_value(
        self,
        source_field_id: int,
        params: str = ""
    ) -> Dict[str, Any]:
        """
        Build an EXT_VALUE rule.

        Used for fields that get values from external data sources.

        Args:
            source_field_id: ID of the field
            params: External table/lookup name

        Returns:
            EXT_VALUE rule dict
        """
        rule = self.create_base_rule(
            "EXT_VALUE",
            [source_field_id],
            [],
            "CLIENT"
        )

        rule.update({
            "sourceType": "EXTERNAL_DATA_VALUE",
            "params": params
        })

        return rule

    def build_convert_to_uppercase(
        self,
        field_id: int
    ) -> Dict[str, Any]:
        """
        Build a CONVERT_TO UPPER_CASE rule.

        Args:
            field_id: ID of the field to convert

        Returns:
            CONVERT_TO rule dict
        """
        rule = self.create_base_rule(
            "CONVERT_TO",
            [field_id],
            [field_id],
            "CLIENT"
        )

        rule["sourceType"] = "UPPER_CASE"

        return rule

    def build_convert_to_lowercase(
        self,
        field_id: int
    ) -> Dict[str, Any]:
        """
        Build a CONVERT_TO LOWER_CASE rule.

        Args:
            field_id: ID of the field to convert

        Returns:
            CONVERT_TO rule dict
        """
        rule = self.create_base_rule(
            "CONVERT_TO",
            [field_id],
            [field_id],
            "CLIENT"
        )

        rule["sourceType"] = "LOWER_CASE"

        return rule

    def build_copy_to(
        self,
        source_field_id: int,
        destination_ids: List[int],
        source_type: str = "FORM_FILL_METADATA"
    ) -> Dict[str, Any]:
        """
        Build a COPY_TO rule.

        Args:
            source_field_id: ID of the source field
            destination_ids: IDs of destination fields
            source_type: Source type (e.g., "FORM_FILL_METADATA", "CREATED_BY")

        Returns:
            COPY_TO rule dict
        """
        rule = self.create_base_rule(
            "COPY_TO",
            [source_field_id],
            destination_ids,
            "SERVER"
        )

        rule["sourceType"] = source_type

        return rule

    def build_copy_created_by(
        self,
        source_field_id: int,
        destination_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Build a COPY_TO rule for copying created-by user details.

        Args:
            source_field_id: ID of the source field
            destination_ids: IDs of destination fields (name, email, mobile)

        Returns:
            COPY_TO rule dict
        """
        return self.build_copy_to(source_field_id, destination_ids, "CREATED_BY")

    def build_set_date(
        self,
        field_id: int,
        date_format: str = "dd-MM-yyyy hh:mm:ss a"
    ) -> Dict[str, Any]:
        """
        Build a SET_DATE rule.

        Args:
            field_id: ID of the date field
            date_format: Date format string

        Returns:
            SET_DATE rule dict
        """
        rule = self.create_base_rule(
            "SET_DATE",
            [field_id],
            [field_id],
            "SERVER"
        )

        rule["params"] = date_format

        return rule

    def build_copy_txnid(
        self,
        field_id: int
    ) -> Dict[str, Any]:
        """
        Build a COPY_TXNID_TO_FORM_FILL rule.

        Used to populate a field with the transaction ID.

        Args:
            field_id: ID of the field to populate

        Returns:
            COPY_TXNID_TO_FORM_FILL rule dict
        """
        rule = self.create_conditional_rule(
            "COPY_TXNID_TO_FORM_FILL",
            [field_id],
            [field_id],
            ["TXN"],
            "NOT_IN"
        )

        return rule

    def build_copy_to_transaction_attr(
        self,
        source_field_id: int,
        attr_number: int
    ) -> Dict[str, Any]:
        """
        Build a COPY_TO_TRANSACTION_ATTRn rule.

        Args:
            source_field_id: ID of the source field
            attr_number: Attribute number (1-8)

        Returns:
            COPY_TO_TRANSACTION_ATTRn rule dict
        """
        action_type = f"COPY_TO_TRANSACTION_ATTR{attr_number}"

        rule = self.create_base_rule(
            action_type,
            [source_field_id],
            [],
            "SERVER"
        )

        rule["sourceType"] = "FORM_FILL_METADATA"

        return rule
