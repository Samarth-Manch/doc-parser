"""
VERIFY rule builder for validation rules (PAN, GSTIN, Bank, MSME, CIN).

Handles ordinal-indexed destinationIds arrays as required by verification schemas.
"""

from typing import Dict, List, Optional
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule
from ..schema_lookup import RuleSchemaLookup
from ..id_mapper import DestinationIdMapper


class VerifyRuleBuilder(BaseRuleBuilder):
    """
    Builder for VERIFY rules (PAN, GSTIN, Bank, MSME, CIN validation).

    VERIFY rules:
    - Have actionType="VERIFY"
    - Have sourceType matching the document type (PAN_NUMBER, GSTIN, etc.)
    - Use processingType="SERVER"
    - destinationIds is an ordinal-indexed array with -1 for unmapped ordinals
    - May have postTriggerRuleIds to chain to other rules
    """

    def __init__(
        self,
        schema_lookup: RuleSchemaLookup,
        id_mapper: Optional[DestinationIdMapper] = None
    ):
        """
        Initialize the verify rule builder.

        Args:
            schema_lookup: RuleSchemaLookup instance
            id_mapper: Optional DestinationIdMapper (created if not provided)
        """
        super().__init__()
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper or DestinationIdMapper(schema_lookup)

    def build(
        self,
        schema_id: int,
        source_field_id: int,
        field_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
        additional_source_ids: Optional[List[int]] = None,
        params: Optional[str] = None,
    ) -> GeneratedRule:
        """
        Build VERIFY rule with proper destinationIds ordinal mapping.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            source_field_id: ID of the field to verify (e.g., PAN input field)
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification
            additional_source_ids: Additional source field IDs (e.g., for GSTIN_WITH_PAN)
            params: Optional params JSON string

        Returns:
            GeneratedRule for VERIFY

        Example for PAN Validation (schema_id=360):
            source_field_id = 275534  # PAN input field
            field_mappings = {
                "Fullname": 275535,
                "Pan retrieval status": 275537,
                "Pan type": 275536,
                "Aadhaar seeding status": 275538
            }
        """
        schema_info = self.schema_lookup.get_by_id(schema_id)
        if not schema_info:
            raise ValueError(f"Schema {schema_id} not found")

        # Build destinationIds array with ordinal mapping
        destination_ids = []
        if field_mappings:
            destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)
        elif schema_info.num_destination_items > 0:
            # No mappings provided, use empty array with -1s
            destination_ids = [-1] * schema_info.num_destination_items

        # Build source_ids
        source_ids = [source_field_id]
        if additional_source_ids:
            source_ids.extend(additional_source_ids)

        rule = GeneratedRule(
            action_type=schema_info.action,  # "VERIFY"
            source_type=schema_info.source,  # e.g., "PAN_NUMBER"
            processing_type="SERVER",
            source_ids=source_ids,
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger_ids or [],
            button=schema_info.button or "VERIFY",
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )

        if params:
            rule.params = params

        return rule

    def build_pan_verify(
        self,
        pan_field_id: int,
        pan_holder_name_field_id: Optional[int] = None,
        pan_type_field_id: Optional[int] = None,
        pan_status_field_id: Optional[int] = None,
        aadhaar_seeding_status_id: Optional[int] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build PAN validation rule (schema ID 360).

        Args:
            pan_field_id: ID of the PAN input field
            pan_holder_name_field_id: ID for Fullname destination (ordinal 4)
            pan_type_field_id: ID for Pan type destination (ordinal 8)
            pan_status_field_id: ID for Pan retrieval status (ordinal 6)
            aadhaar_seeding_status_id: ID for Aadhaar seeding status (ordinal 9)
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            GeneratedRule for PAN VERIFY
        """
        field_mappings = {}
        if pan_holder_name_field_id:
            field_mappings["Fullname"] = pan_holder_name_field_id
        if pan_type_field_id:
            field_mappings["Pan type"] = pan_type_field_id
        if pan_status_field_id:
            field_mappings["Pan retrieval status"] = pan_status_field_id
        if aadhaar_seeding_status_id:
            field_mappings["Aadhaar seeding status"] = aadhaar_seeding_status_id

        return self.build(
            schema_id=360,
            source_field_id=pan_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids,
        )

    def build_gstin_verify(
        self,
        gstin_field_id: int,
        destination_field_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build GSTIN validation rule (schema ID 355).

        Args:
            gstin_field_id: ID of the GSTIN input field
            destination_field_mappings: Mapping of GSTIN schema fields to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            GeneratedRule for GSTIN VERIFY
        """
        return self.build(
            schema_id=355,
            source_field_id=gstin_field_id,
            field_mappings=destination_field_mappings,
            post_trigger_ids=post_trigger_ids,
        )

    def build_bank_verify(
        self,
        account_number_field_id: int,
        ifsc_field_id: int,
        beneficiary_name_field_id: Optional[int] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build Bank Account validation rule (schema ID 361).

        Args:
            account_number_field_id: ID of the bank account number field
            ifsc_field_id: ID of the IFSC code field
            beneficiary_name_field_id: ID for beneficiary name destination
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            GeneratedRule for Bank VERIFY
        """
        field_mappings = {}
        if beneficiary_name_field_id:
            field_mappings["Beneficiary Name"] = beneficiary_name_field_id

        return self.build(
            schema_id=361,
            source_field_id=account_number_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids,
            additional_source_ids=[ifsc_field_id],
        )

    def build_msme_verify(
        self,
        msme_reg_number_field_id: int,
        destination_field_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build MSME validation rule (schema ID 337).

        Args:
            msme_reg_number_field_id: ID of the MSME registration number field
            destination_field_mappings: Mapping of MSME schema fields to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            GeneratedRule for MSME VERIFY
        """
        return self.build(
            schema_id=337,
            source_field_id=msme_reg_number_field_id,
            field_mappings=destination_field_mappings,
            post_trigger_ids=post_trigger_ids,
        )

    def build_gstin_with_pan_verify(
        self,
        pan_field_id: int,
        gstin_field_id: int,
        error_message: str = "GSTIN and PAN doesn't match.",
    ) -> GeneratedRule:
        """
        Build GSTIN with PAN cross-validation rule (schema ID 329).

        Args:
            pan_field_id: ID of the PAN field
            gstin_field_id: ID of the GSTIN field
            error_message: Error message to display on mismatch

        Returns:
            GeneratedRule for GSTIN_WITH_PAN VERIFY
        """
        params = f'{{ "paramMap": {{"errorMessage": "{error_message}"}}}}'

        return self.build(
            schema_id=329,
            source_field_id=pan_field_id,
            field_mappings=None,
            post_trigger_ids=[],
            additional_source_ids=[gstin_field_id],
            params=params,
        )

    def get_schema_destination_fields(self, schema_id: int) -> Dict[str, int]:
        """
        Get destination field names and ordinals for a schema.

        Useful for understanding what fields need to be mapped.

        Args:
            schema_id: Rule schema ID

        Returns:
            Dict mapping field name to ordinal position
        """
        return self.schema_lookup.get_destination_ordinals(schema_id)
