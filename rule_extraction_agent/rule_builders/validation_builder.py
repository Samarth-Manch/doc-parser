"""
VALIDATION rule builder.

Generates VALIDATION rules with EXTERNAL_DATA_VALUE source type.
"""

from typing import Dict, List, Optional
from ..models import id_generator


class ValidationRuleBuilder:
    """Builds VALIDATION rules for field validation."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def build(
        self,
        source_ids: List[int],
        destination_ids: List[int] = None,
        params: str = None,
        post_trigger_rule_ids: List[int] = None
    ) -> Dict:
        """
        Build a VALIDATION rule.

        Args:
            source_ids: Source field IDs to validate
            destination_ids: Destination field IDs to populate after validation
            params: EDV table name or validation params
            post_trigger_rule_ids: Rules to trigger after validation

        Returns:
            VALIDATION rule dict

        Example from reference:
        {
          "actionType": "VALIDATION",
          "sourceType": "EXTERNAL_DATA_VALUE",
          "processingType": "SERVER",
          "sourceIds": [275506],
          "destinationIds": [276399, 276400, 276383, 275629],
          "postTriggerRuleIds": [120145, 120479],
          "params": "COMPANY_CODE",
          "executeOnFill": true
        }
        """
        if not source_ids:
            return None

        rule = {
            "id": id_generator.next_id('rule'),
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": "VALIDATION",
            "sourceType": "EXTERNAL_DATA_VALUE",
            "processingType": "SERVER",
            "sourceIds": source_ids,
            "destinationIds": destination_ids or [],
            "postTriggerRuleIds": post_trigger_rule_ids or [],
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }

        # Add params if provided (EDV table name)
        if params:
            rule["params"] = params

        if self.verbose:
            print(f"Built VALIDATION rule for sourceIds={source_ids}, params={params}")

        return rule

    def build_from_edv_mapping(
        self,
        field_id: int,
        edv_mapping: Dict,
        all_fields: List[Dict]
    ) -> Optional[Dict]:
        """
        Build VALIDATION rule from EDV mapping data.

        Args:
            field_id: Field ID to validate
            edv_mapping: EDV mapping dict with table info
            all_fields: All fields for destination matching

        Returns:
            VALIDATION rule or None
        """
        edv_table = edv_mapping.get('edv_table_name')
        if not edv_table:
            return None

        # Check if this is a validation-type EDV mapping
        # (not all EDV mappings need VALIDATION rules, some are just EXT_DROP_DOWN)
        mapping_type = edv_mapping.get('mapping_type', 'validation')
        if mapping_type != 'validation':
            return None

        # Get destination fields from mapping
        dest_fields = edv_mapping.get('destination_fields', [])
        dest_ids = []

        # Match destination fields to IDs
        for dest_name in dest_fields:
            for field in all_fields:
                if field.get('formTag', {}).get('name', '').lower() == dest_name.lower():
                    dest_ids.append(field.get('id'))
                    break

        return self.build(
            source_ids=[field_id],
            destination_ids=dest_ids,
            params=edv_table
        )
