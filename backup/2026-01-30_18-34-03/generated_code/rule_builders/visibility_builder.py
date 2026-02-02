"""
Visibility Rule Builder - Builds visibility and mandatory rules from intra-panel references.
"""

from typing import Dict, List, Optional, Tuple
from collections import defaultdict
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


class VisibilityRuleBuilder(BaseRuleBuilder):
    """
    Builds visibility and mandatory rules from field logic.

    CRITICAL: Visibility rules go on the SOURCE/CONTROLLING field, not the destinations.
    When multiple fields say "if field 'X' is Y then visible", we create ONE rule on field X
    with ALL affected fields in destinationIds.
    """

    def __init__(self, field_matcher=None):
        """
        Initialize with optional field matcher.

        Args:
            field_matcher: FieldMatcher instance for resolving field names to IDs
        """
        self.field_matcher = field_matcher

    def build(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN",
    ) -> Dict:
        """
        Build a visibility/mandatory rule.

        Args:
            action_type: MAKE_VISIBLE, MAKE_INVISIBLE, MAKE_MANDATORY, MAKE_NON_MANDATORY
            source_ids: Controlling field IDs
            destination_ids: Affected field IDs
            conditional_values: Values that trigger the rule
            condition: IN or NOT_IN

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type=action_type,
            source_ids=source_ids,
            destination_ids=destination_ids,
            conditional_values=conditional_values,
            condition=condition,
        )

    def build_visibility_rules_from_group(
        self,
        source_field_id: int,
        destination_field_ids: List[int],
        conditional_value: str,
        include_mandatory: bool = False,
    ) -> List[Dict]:
        """
        Build visibility rules for a group of fields controlled by one source.

        Args:
            source_field_id: ID of the controlling field
            destination_field_ids: IDs of fields to show/hide
            conditional_value: Value that triggers visibility
            include_mandatory: Whether to also generate mandatory rules

        Returns:
            List of rule dictionaries
        """
        rules = []

        # MAKE_VISIBLE when value matches
        rules.append(self.build(
            action_type="MAKE_VISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_field_ids,
            conditional_values=[conditional_value],
            condition="IN",
        ))

        # MAKE_INVISIBLE when value doesn't match
        rules.append(self.build(
            action_type="MAKE_INVISIBLE",
            source_ids=[source_field_id],
            destination_ids=destination_field_ids,
            conditional_values=[conditional_value],
            condition="NOT_IN",
        ))

        if include_mandatory:
            # MAKE_MANDATORY when value matches
            rules.append(self.build(
                action_type="MAKE_MANDATORY",
                source_ids=[source_field_id],
                destination_ids=destination_field_ids,
                conditional_values=[conditional_value],
                condition="IN",
            ))

            # MAKE_NON_MANDATORY when value doesn't match
            rules.append(self.build(
                action_type="MAKE_NON_MANDATORY",
                source_ids=[source_field_id],
                destination_ids=destination_field_ids,
                conditional_values=[conditional_value],
                condition="NOT_IN",
            ))

        return rules

    def build_from_intra_panel_references(
        self,
        references: List[Dict],
        field_name_to_id: Dict[str, int],
    ) -> Dict[int, List[Dict]]:
        """
        Build visibility rules from intra-panel references.

        This groups all destinations by their controlling field and generates
        efficient rules with multiple destinations.

        Args:
            references: List of intra-panel reference dicts
            field_name_to_id: Mapping from field names to IDs

        Returns:
            Dict mapping source field ID to list of rules
        """
        # Group by controlling field and conditional value
        groups = defaultdict(lambda: defaultdict(list))

        for ref in references:
            ref_type = ref.get('reference_type', '')
            if 'visibility' not in ref_type.lower() and 'mandatory' not in ref_type.lower():
                continue

            # Extract controlling field
            controlling_field = None
            dependent_field = None
            conditional_value = None
            include_mandatory = 'mandatory' in ref_type.lower()

            # Handle different reference formats
            if 'controlling_field' in ref:
                controlling_field = ref['controlling_field'].get('field_name')
            elif 'referenced_field' in ref:
                if isinstance(ref['referenced_field'], dict):
                    controlling_field = ref['referenced_field'].get('field_name')
                else:
                    controlling_field = ref.get('referenced_field')
            elif 'depends_on' in ref:
                controlling_field = ref['depends_on'].get('field_name')

            if 'dependent_field' in ref:
                if isinstance(ref['dependent_field'], dict):
                    dependent_field = ref['dependent_field'].get('field_name')
                else:
                    dependent_field = ref.get('dependent_field')
            elif 'source_field' in ref:
                dependent_field = ref.get('source_field')

            # Extract conditional value
            if 'condition' in ref:
                condition = ref['condition']
                if isinstance(condition, dict):
                    conditional_value = condition.get('when_value') or condition.get('value')
            if not conditional_value:
                # Try to extract from logic description
                logic = ref.get('logic_description', '') or ref.get('original_logic', '')
                if logic:
                    import re
                    match = re.search(r"(?:is|=)\s*['\"]?([^'\"]+?)['\"]?\s+then", logic, re.IGNORECASE)
                    if match:
                        conditional_value = match.group(1).strip()
                    elif 'YES' in logic.upper():
                        conditional_value = 'YES'
                    elif 'Yes' in logic:
                        conditional_value = 'Yes'

            if controlling_field and dependent_field and conditional_value:
                source_id = field_name_to_id.get(controlling_field)
                dest_id = field_name_to_id.get(dependent_field)

                if source_id and dest_id:
                    key = (conditional_value, include_mandatory)
                    groups[source_id][key].append(dest_id)

        # Build rules from groups
        result = defaultdict(list)

        for source_id, value_groups in groups.items():
            for (conditional_value, include_mandatory), dest_ids in value_groups.items():
                rules = self.build_visibility_rules_from_group(
                    source_field_id=source_id,
                    destination_field_ids=list(set(dest_ids)),
                    conditional_value=conditional_value,
                    include_mandatory=include_mandatory,
                )
                result[source_id].extend(rules)

        return dict(result)

    def analyze_logic_for_visibility(
        self,
        logic_text: str,
    ) -> Optional[Dict]:
        """
        Analyze logic text to extract visibility information.

        Args:
            logic_text: Logic text from field definition

        Returns:
            Dict with visibility info or None if not a visibility pattern
        """
        import re

        if not logic_text:
            return None

        # Pattern: "if the field 'X' values is Y then visible"
        pattern = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:values?\s+is|is)\s+['\"]?([^'\"]+?)['\"]?\s+then\s+(visible|invisible|mandatory)"

        match = re.search(pattern, logic_text, re.IGNORECASE)
        if not match:
            return None

        controlling_field = match.group(1).strip()
        conditional_value = match.group(2).strip()
        action = match.group(3).lower()

        # Determine flags
        is_visible = action == "visible"
        is_mandatory = "mandatory" in logic_text.lower() and "non-mandatory" not in logic_text.lower()

        # Check for "and mandatory" pattern
        if re.search(r"visible\s+and\s+mandatory", logic_text, re.IGNORECASE):
            is_mandatory = True

        # Check for "otherwise" patterns
        has_otherwise_invisible = bool(re.search(r"otherwise\s+invisible", logic_text, re.IGNORECASE))
        has_otherwise_non_mandatory = bool(re.search(r"otherwise\s+(?:non-mandatory|non\s+mandatory)", logic_text, re.IGNORECASE))

        return {
            "controlling_field": controlling_field,
            "conditional_value": conditional_value,
            "is_visible_when_true": is_visible,
            "is_mandatory_when_true": is_mandatory,
            "has_otherwise_invisible": has_otherwise_invisible,
            "has_otherwise_non_mandatory": has_otherwise_non_mandatory,
        }
