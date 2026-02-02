"""
External Data Value Rule Builder - Builds EXT_DROP_DOWN and EXT_VALUE rules.

These rules handle:
- Dropdown values from external reference tables
- Cascading/filtered dropdowns based on parent field selection
- External data lookups
"""

from typing import Dict, List, Optional
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


class EdvRuleBuilder(BaseRuleBuilder):
    """Builds EXT_DROP_DOWN and EXT_VALUE rules for external data."""

    def build(
        self,
        field_id: int,
        params: str,
        source_ids: List[int] = None,
        source_type: str = "FORM_FILL_DROP_DOWN",
    ) -> Dict:
        """
        Build an EXT_DROP_DOWN rule (default implementation).

        Args:
            field_id: The dropdown field ID
            params: The lookup parameter name
            source_ids: Source field IDs
            source_type: Source type

        Returns:
            Rule dictionary
        """
        return self.build_ext_dropdown(field_id, params, source_ids, source_type)

    def build_ext_dropdown(
        self,
        field_id: int,
        params: str,
        source_ids: List[int] = None,
        source_type: str = "FORM_FILL_DROP_DOWN",
    ) -> Dict:
        """
        Build an EXT_DROP_DOWN rule for a dropdown field.

        Args:
            field_id: The dropdown field ID
            params: The lookup parameter name (e.g., "COMPANY_CODE", "PIDILITE_YES_NO")
            source_ids: Source field IDs (usually the field itself or parent dropdown)
            source_type: Source type (default: "FORM_FILL_DROP_DOWN")

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="EXT_DROP_DOWN",
            source_type=source_type,
            source_ids=source_ids or [field_id],
            destination_ids=[],
            processing_type="SERVER",
            params=params,
        )

    def build_cascading_dropdown(
        self,
        field_id: int,
        parent_field_id: int,
        params: str,
    ) -> Dict:
        """
        Build a cascading dropdown rule where this field's values depend on parent.

        Args:
            field_id: The dependent dropdown field ID
            parent_field_id: The parent dropdown field ID
            params: The lookup parameter name

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="EXT_DROP_DOWN",
            source_type="FORM_FILL_DROP_DOWN",
            source_ids=[parent_field_id],
            destination_ids=[field_id],
            processing_type="SERVER",
            params=params,
        )

    def build_ext_value(
        self,
        source_field_id: int,
        destination_ids: List[int],
        params: str,
        source_type: str = "EXTERNAL_DATA_VALUE",
        conditional_value_id: int = None,
        conditional_values: List[str] = None,
    ) -> Dict:
        """
        Build an EXT_VALUE rule for external data lookup.

        Args:
            source_field_id: The source field ID
            destination_ids: List of destination field IDs
            params: The lookup parameter name or JSON params
            source_type: Source type (default: "EXTERNAL_DATA_VALUE")
            conditional_value_id: Field ID for conditional check
            conditional_values: Values that enable this lookup

        Returns:
            Rule dictionary
        """
        rule = self._create_base_rule(
            action_type="EXT_VALUE",
            source_type=source_type,
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type="SERVER",
            params=params,
        )

        if conditional_value_id:
            rule["conditionalValueId"] = conditional_value_id
        if conditional_values:
            rule["conditionalValues"] = conditional_values
            rule["condition"] = "IN"
            rule["conditionValueType"] = "TEXT"

        return rule

    def build_validation_lookup(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        params: str,
    ) -> Dict:
        """
        Build a VALIDATION rule for external data lookup and validation.

        Args:
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            params: JSON params with lookup configuration

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="VALIDATION",
            source_type="EXTERNAL_DATA_VALUE",
            source_ids=source_ids,
            destination_ids=destination_ids,
            processing_type="SERVER",
            params=params,
        )


# Common dropdown lookup parameters
COMMON_DROPDOWN_PARAMS = {
    "yes_no": "PIDILITE_YES_NO",
    "company_code": "COMPANY_CODE",
    "country": "COUNTRY",
    "state": "STATE",
    "city": "CITY",
    "currency": "CURRENCY",
}
