"""
COPY_TO rule builder.

Generates COPY_TO rules for field value propagation.
"""

from typing import Dict, List, Optional
from ..models import id_generator


class CopyToRuleBuilder:
    """Builds COPY_TO rules for value propagation."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def build(
        self,
        source_ids: List[int],
        destination_ids: List[int],
        source_type: str = "FORM_FILL",
        condition: str = None,
        conditional_values: List[str] = None
    ) -> Dict:
        """
        Build a COPY_TO rule.

        Args:
            source_ids: Source field IDs
            destination_ids: Destination field IDs
            source_type: Source type (default: "FORM_FILL")
            condition: Condition operator (IN, NOT_IN, etc.)
            conditional_values: Conditional values for trigger

        Returns:
            COPY_TO rule dict

        Example from reference:
        {
          "actionType": "COPY_TO",
          "sourceType": "FORM_FILL",
          "processingType": "CLIENT",
          "sourceIds": [275534],
          "destinationIds": [275543],
          "executeOnFill": true
        }
        """
        if not source_ids or not destination_ids:
            return None

        rule = {
            "id": id_generator.next_id('rule'),
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": "COPY_TO",
            "sourceType": source_type,
            "processingType": "CLIENT",
            "sourceIds": source_ids,
            "destinationIds": destination_ids,
            "postTriggerRuleIds": [],
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }

        # Add conditional fields if provided
        if condition and conditional_values:
            rule["condition"] = condition
            rule["conditionalValues"] = conditional_values
            rule["conditionValueType"] = "TEXT"

        if self.verbose:
            print(f"Built COPY_TO rule: {source_ids} -> {destination_ids}")

        return rule

    def build_from_dependency(
        self,
        dependency: Dict,
        field_matcher
    ) -> Optional[Dict]:
        """
        Build COPY_TO rule from dependency reference.

        Args:
            dependency: Dependency dict with source/target info
            field_matcher: FieldMatcher instance

        Returns:
            COPY_TO rule or None
        """
        source_field = dependency.get('source_field', '')
        target_field = dependency.get('target_field', '')

        if not source_field or not target_field:
            return None

        # Match fields to IDs
        source_info = field_matcher.match_field(source_field)
        target_info = field_matcher.match_field(target_field)

        if not source_info or not target_info:
            return None

        return self.build(
            source_ids=[source_info.id],
            destination_ids=[target_info.id]
        )
