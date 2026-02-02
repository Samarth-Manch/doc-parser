"""
External Dropdown Rule Builder - Build EXT_DROP_DOWN and EXT_VALUE rules.

EXT_DROP_DOWN rules apply when:
- Logic references external tables or Excel files
- Field is DROPDOWN type with external data source
- Cascading dropdowns dependent on parent fields

Common params from reference:
- "COMPANY_CODE"
- "PIDILITE_YES_NO"
- "TYPE_OF_INDUSTRY"
"""

from typing import List, Dict, Optional

from .base_builder import BaseRuleBuilder, get_rule_id
from ..models import GeneratedRule


class ExtDropdownRuleBuilder(BaseRuleBuilder):
    """Build EXT_DROP_DOWN and EXT_VALUE rules."""

    def __init__(self):
        super().__init__()

    def build_ext_dropdown_rule(
        self,
        field_id: int,
        params: str = "",
        searchable: bool = True,
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build EXT_DROP_DOWN rule.

        Args:
            field_id: ID of the dropdown field
            params: External table/lookup name (e.g., "COMPANY_CODE")
            searchable: Whether the dropdown is searchable
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for EXT_DROP_DOWN
        """
        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="EXT_DROP_DOWN",
            source_type="FORM_FILL_DROP_DOWN",
            processing_type="CLIENT",
            source_ids=[field_id],
            destination_ids=[],
            post_trigger_rule_ids=[],
            params=params,
            button="",
            searchable=searchable,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule

    def build_cascading_dropdown_rule(
        self,
        parent_field_id: int,
        child_field_id: int,
        params: str = "",
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build cascading dropdown rule.

        When parent dropdown changes, child dropdown options are filtered.

        Args:
            parent_field_id: ID of the parent/controlling dropdown
            child_field_id: ID of the child/dependent dropdown
            params: Lookup table name
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for cascading dropdown
        """
        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="EXT_DROP_DOWN",
            source_type="FORM_FILL_DROP_DOWN",
            processing_type="CLIENT",
            source_ids=[parent_field_id],
            destination_ids=[child_field_id],
            post_trigger_rule_ids=[],
            params=params,
            button="",
            searchable=True,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule

    def build_ext_value_rule(
        self,
        field_id: int,
        params: str = "",
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build EXT_VALUE rule for external data population.

        Used for non-dropdown fields that get values from external sources.

        Args:
            field_id: ID of the field to populate
            params: External table/lookup name
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for EXT_VALUE
        """
        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="EXT_VALUE",
            source_type="EXTERNAL_DATA_VALUE",
            processing_type="SERVER",
            source_ids=[field_id],
            destination_ids=[],
            post_trigger_rule_ids=[],
            params=params,
            button="",
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule


# Common cascading dropdown patterns
CASCADING_DROPDOWN_PATTERNS = [
    ("Country", "State"),
    ("State", "District"),
    ("State", "City"),
    ("Bank Name", "Branch"),
    ("Account Group", "Account Type"),
    ("Company Code", "Plant"),
    ("Company Code", "Department"),
]


def detect_cascading_relationships(
    fields_with_logic: List[Dict]
) -> List[tuple]:
    """
    Detect parent-child cascading dropdown relationships from field logic.

    Args:
        fields_with_logic: List of fields with their logic text

    Returns:
        List of (parent_field_name, child_field_name) tuples
    """
    import re

    cascades = []

    for field_info in fields_with_logic:
        logic = field_info.get('logic', '') or ''
        field_name = field_info.get('name', '')

        # Pattern: "Parent dropdown field: X"
        match = re.search(
            r"parent\s+dropdown\s+field\s*:\s*['\"]?([^'\"]+)['\"]?",
            logic, re.IGNORECASE
        )
        if match:
            parent_name = match.group(1).strip()
            cascades.append((parent_name, field_name))
            continue

        # Pattern: "Dependent on field X"
        match = re.search(
            r"dependent\s+on\s+(?:field|dropdown)\s*[:\s]+['\"]?([^'\"]+)['\"]?",
            logic, re.IGNORECASE
        )
        if match:
            parent_name = match.group(1).strip()
            cascades.append((parent_name, field_name))
            continue

        # Pattern: "Values based on X selection"
        match = re.search(
            r"values?\s+(?:based|filtered)\s+(?:on|by)\s+(?:the\s+)?['\"]?([^'\"]+)['\"]?\s+selection",
            logic, re.IGNORECASE
        )
        if match:
            parent_name = match.group(1).strip()
            cascades.append((parent_name, field_name))
            continue

    return cascades


def extract_params_from_logic(logic: str) -> str:
    """
    Extract params value from logic text.

    Looks for patterns like:
    - "reference table 1.2"
    - "table: COMPANY_CODE"
    - "from PIDILITE_YES_NO"

    Args:
        logic: Logic text from field

    Returns:
        Params string or empty string
    """
    import re

    if not logic:
        return ""

    # Pattern: explicit table name
    match = re.search(r"table\s*:\s*['\"]?(\w+)['\"]?", logic, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Pattern: "from TABLE_NAME"
    match = re.search(r"from\s+['\"]?([A-Z_]+)['\"]?", logic)
    if match:
        return match.group(1)

    # Pattern: reference table number (generic)
    match = re.search(r"reference\s+table\s+(\d+\.?\d*)", logic, re.IGNORECASE)
    if match:
        # Return a generic identifier based on table number
        table_num = match.group(1).replace('.', '_')
        return f"REF_TABLE_{table_num}"

    return ""
