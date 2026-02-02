"""VERIFY rule builder for validation rules."""

from typing import Dict, List, Optional
from .base_builder import BaseRuleBuilder
from ..schema_lookup import RuleSchemaLookup, VERIFY_SCHEMAS
from ..id_mapper import DestinationIdMapper


class VerifyRuleBuilder(BaseRuleBuilder):
    """Builder for VERIFY rules (PAN, GSTIN, Bank, MSME, CIN validation)."""

    def __init__(self, schema_lookup: RuleSchemaLookup, id_mapper: DestinationIdMapper):
        super().__init__()
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper

    def build(
        self,
        source_type: str,
        source_field_ids: List[int],
        field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """
        Build VERIFY rule with proper destinationIds ordinal mapping.

        Args:
            source_type: VERIFY source type (e.g., PAN_NUMBER, GSTIN)
            source_field_ids: Source field ID(s) - some rules need multiple
            field_mappings: Dict mapping schema destination field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule dict or None if schema not found
        """
        # Find schema
        schema = self.schema_lookup.find_by_action_and_source("VERIFY", source_type)
        if not schema:
            return None

        schema_id = schema.get('id')

        # Check if multi-source rule
        num_source_fields = schema.get('sourceFields', {}).get('numberOfItems', 1)
        if len(source_field_ids) < num_source_fields:
            # Log warning - may cause API error
            pass

        # Build destination IDs using ordinal mapping
        destination_ids = []
        if field_mappings:
            destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)

        # Create rule
        rule = self.create_base_rule(
            action_type="VERIFY",
            source_ids=source_field_ids,
            destination_ids=destination_ids,
            processing_type="SERVER"
        )

        rule["sourceType"] = source_type

        # Add button if schema specifies
        button = schema.get('button', '')
        if button:
            rule["button"] = button
        else:
            rule["button"] = "Verify"

        if post_trigger_ids:
            rule["postTriggerRuleIds"] = post_trigger_ids

        return rule

    def build_pan_verify(
        self,
        pan_field_id: int,
        destination_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """
        Build PAN VERIFY rule.

        Destination ordinals for PAN_NUMBER (Schema 360):
        1: Panholder title    | 6: Pan retrieval status
        2: Firstname          | 7: Fullname without title
        3: Lastname           | 8: Pan type
        4: Fullname           | 9: Aadhaar seeding status
        5: Last updated       | 10: Middle name

        Args:
            pan_field_id: PAN input field ID
            destination_mappings: Map of destination names to field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            PAN VERIFY rule dict
        """
        return self.build(
            source_type="PAN_NUMBER",
            source_field_ids=[pan_field_id],
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_gstin_verify(
        self,
        gstin_field_id: int,
        destination_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """
        Build GSTIN VERIFY rule.

        Args:
            gstin_field_id: GSTIN input field ID
            destination_mappings: Map of destination names to field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            GSTIN VERIFY rule dict
        """
        return self.build(
            source_type="GSTIN",
            source_field_ids=[gstin_field_id],
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_bank_verify(
        self,
        ifsc_field_id: int,
        account_field_id: int,
        destination_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """
        Build BANK_ACCOUNT_NUMBER VERIFY rule.

        NOTE: This rule requires TWO source fields:
        - IFSC Code (ordinal 1)
        - Bank Account Number (ordinal 2)

        Args:
            ifsc_field_id: IFSC Code field ID
            account_field_id: Bank Account Number field ID
            destination_mappings: Map of destination names to field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            Bank VERIFY rule dict
        """
        return self.build(
            source_type="BANK_ACCOUNT_NUMBER",
            source_field_ids=[ifsc_field_id, account_field_id],
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_msme_verify(
        self,
        msme_field_id: int,
        destination_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """Build MSME VERIFY rule."""
        return self.build(
            source_type="MSME_UDYAM_REG_NUMBER",
            source_field_ids=[msme_field_id],
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_cin_verify(
        self,
        cin_field_id: int,
        destination_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """Build CIN VERIFY rule."""
        return self.build(
            source_type="CIN_ID",
            source_field_ids=[cin_field_id],
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_gstin_with_pan(
        self,
        pan_field_id: int,
        gstin_field_id: int,
        error_message: str = "GSTIN and PAN doesn't match."
    ) -> Dict:
        """
        Build GSTIN_WITH_PAN cross-validation rule.

        Args:
            pan_field_id: PAN field ID
            gstin_field_id: GSTIN field ID
            error_message: Error message when validation fails

        Returns:
            GSTIN_WITH_PAN VERIFY rule dict
        """
        rule = self.create_base_rule(
            action_type="VERIFY",
            source_ids=[pan_field_id, gstin_field_id],
            destination_ids=[],
            processing_type="SERVER"
        )

        rule["sourceType"] = "GSTIN_WITH_PAN"
        rule["params"] = f'{{ "paramMap": {{"errorMessage": "{error_message}"}}}}'
        rule["onStatusFail"] = "CONTINUE"

        return rule

    def get_destination_field_names(self, source_type: str) -> List[str]:
        """Get list of destination field names for a VERIFY source type."""
        schema = self.schema_lookup.find_by_action_and_source("VERIFY", source_type)
        if not schema:
            return []

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return [f['name'] for f in dest_fields]

    def get_required_source_fields(self, source_type: str) -> List[Dict]:
        """Get list of required source fields for a VERIFY source type."""
        schema_id = VERIFY_SCHEMAS.get(source_type)
        if not schema_id:
            return []

        return self.schema_lookup.get_mandatory_source_fields(schema_id)
