"""
OCR rule builder for document OCR extraction rules.

Handles OCR rules for PAN, GSTIN, Aadhaar, Cheque, etc.
"""

from typing import Dict, List, Optional
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule
from ..schema_lookup import RuleSchemaLookup
from ..id_mapper import DestinationIdMapper


class OcrRuleBuilder(BaseRuleBuilder):
    """
    Builder for OCR rules (PAN_IMAGE, GSTIN_IMAGE, AADHAR_IMAGE, etc.).

    OCR rules:
    - Have actionType="OCR"
    - Have sourceType matching the image type (PAN_IMAGE, GSTIN_IMAGE, etc.)
    - Use processingType="SERVER"
    - sourceIds contains the file upload field ID
    - destinationIds contains fields to populate with OCR data
    - Often chain to VERIFY rules via postTriggerRuleIds
    """

    # Source type to schema ID mapping
    OCR_SCHEMAS = {
        "PAN_IMAGE": 344,
        "GSTIN_IMAGE": 347,
        "AADHAR_IMAGE": 359,
        "AADHAR_BACK_IMAGE": 348,
        "CHEQUEE": 269,
        "CIN": 357,
        "MSME": 214,
    }

    def __init__(
        self,
        schema_lookup: RuleSchemaLookup,
        id_mapper: Optional[DestinationIdMapper] = None
    ):
        """
        Initialize the OCR rule builder.

        Args:
            schema_lookup: RuleSchemaLookup instance
            id_mapper: Optional DestinationIdMapper
        """
        super().__init__()
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper or DestinationIdMapper(schema_lookup)

    def build(
        self,
        schema_id: int,
        upload_field_id: int,
        output_field_ids: Optional[List[int]] = None,
        field_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
        params: Optional[str] = None,
    ) -> GeneratedRule:
        """
        Build OCR rule.

        Args:
            schema_id: OCR schema ID (e.g., 344 for PAN OCR)
            upload_field_id: File upload field ID (source)
            output_field_ids: Direct list of destination field IDs
            field_mappings: Alternative: mapping of schema fields to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after OCR (e.g., VERIFY rule)
            params: Optional params JSON string

        Returns:
            GeneratedRule for OCR
        """
        schema_info = self.schema_lookup.get_by_id(schema_id)
        if not schema_info:
            raise ValueError(f"Schema {schema_id} not found")

        # Determine destination_ids
        if output_field_ids:
            destination_ids = output_field_ids
        elif field_mappings:
            destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)
        else:
            # No destinations specified
            destination_ids = []

        rule = GeneratedRule(
            action_type="OCR",
            source_type=schema_info.source,
            processing_type="SERVER",
            source_ids=[upload_field_id],
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger_ids or [],
            button="",
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )

        if params:
            rule.params = params

        return rule

    def build_simple(
        self,
        source_type: str,
        upload_field_id: int,
        output_field_id: int,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build a simple OCR rule with single output field.

        Args:
            source_type: OCR source type (PAN_IMAGE, GSTIN_IMAGE, etc.)
            upload_field_id: File upload field ID
            output_field_id: Single destination field ID
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            GeneratedRule for OCR
        """
        schema_id = self.OCR_SCHEMAS.get(source_type)
        if not schema_id:
            raise ValueError(f"Unknown OCR source type: {source_type}")

        return self.build(
            schema_id=schema_id,
            upload_field_id=upload_field_id,
            output_field_ids=[output_field_id],
            post_trigger_ids=post_trigger_ids,
        )

    def build_pan_ocr(
        self,
        upload_pan_field_id: int,
        pan_field_id: int,
        verify_rule_id: Optional[int] = None,
    ) -> GeneratedRule:
        """
        Build PAN OCR rule (schema ID 344).

        Args:
            upload_pan_field_id: ID of the PAN upload field
            pan_field_id: ID of the PAN text field to populate
            verify_rule_id: ID of the PAN VERIFY rule to chain to

        Returns:
            GeneratedRule for PAN OCR
        """
        post_trigger_ids = [verify_rule_id] if verify_rule_id else []

        return self.build_simple(
            source_type="PAN_IMAGE",
            upload_field_id=upload_pan_field_id,
            output_field_id=pan_field_id,
            post_trigger_ids=post_trigger_ids,
        )

    def build_gstin_ocr(
        self,
        upload_gstin_field_id: int,
        gstin_field_id: int,
        verify_rule_id: Optional[int] = None,
    ) -> GeneratedRule:
        """
        Build GSTIN OCR rule (schema ID 347).

        Args:
            upload_gstin_field_id: ID of the GSTIN image upload field
            gstin_field_id: ID of the GSTIN text field to populate
            verify_rule_id: ID of the GSTIN VERIFY rule to chain to

        Returns:
            GeneratedRule for GSTIN OCR
        """
        post_trigger_ids = [verify_rule_id] if verify_rule_id else []

        return self.build_simple(
            source_type="GSTIN_IMAGE",
            upload_field_id=upload_gstin_field_id,
            output_field_id=gstin_field_id,
            post_trigger_ids=post_trigger_ids,
        )

    def build_aadhaar_front_ocr(
        self,
        upload_aadhaar_field_id: int,
        destination_field_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build Aadhaar Front OCR rule (schema ID 359).

        Schema destination fields (ordinals):
        1: aadharNumberMasked
        2: name
        3: gender
        4: dob
        5: aadharAddress1
        6: aadharAddress2
        7: aadharPin
        8: aadharCity
        9: aadharDist
        10: aadharState
        11: aadharFatherName
        12: aadharFullAddress
        13: newAadhaarstorageId

        Args:
            upload_aadhaar_field_id: ID of the Aadhaar front upload field
            destination_field_mappings: Mapping of schema fields to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            GeneratedRule for Aadhaar Front OCR
        """
        return self.build(
            schema_id=359,
            upload_field_id=upload_aadhaar_field_id,
            field_mappings=destination_field_mappings,
            post_trigger_ids=post_trigger_ids,
        )

    def build_aadhaar_back_ocr(
        self,
        upload_aadhaar_back_field_id: int,
        destination_field_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build Aadhaar Back OCR rule (schema ID 348).

        Schema destination fields (ordinals):
        1: aadharAddress1
        2: aadharAddress2
        3: aadharPin
        4: aadharCity
        5: aadharDist
        6: aadharState
        7: aadharFatherName
        8: aadharFullAddress
        9: newAadhaarstorageId

        Args:
            upload_aadhaar_back_field_id: ID of the Aadhaar back upload field
            destination_field_mappings: Mapping of schema fields to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            GeneratedRule for Aadhaar Back OCR
        """
        return self.build(
            schema_id=348,
            upload_field_id=upload_aadhaar_back_field_id,
            field_mappings=destination_field_mappings,
            post_trigger_ids=post_trigger_ids,
        )

    def build_cheque_ocr(
        self,
        upload_cheque_field_id: int,
        ifsc_field_id: Optional[int] = None,
        account_number_field_id: Optional[int] = None,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build Cheque OCR rule (schema ID 269).

        Schema destination fields (ordinals):
        1: micr
        2: accountNumber
        3: bankName
        4: ifsc
        5: branchName
        6: branchCode
        7: storageId

        Args:
            upload_cheque_field_id: ID of the cancelled cheque upload field
            ifsc_field_id: ID for IFSC destination (ordinal 4)
            account_number_field_id: ID for account number destination (ordinal 2)
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            GeneratedRule for Cheque OCR
        """
        field_mappings = {}
        if ifsc_field_id:
            field_mappings["ifsc"] = ifsc_field_id
        if account_number_field_id:
            field_mappings["accountNumber"] = account_number_field_id

        return self.build(
            schema_id=269,
            upload_field_id=upload_cheque_field_id,
            field_mappings=field_mappings if field_mappings else None,
            post_trigger_ids=post_trigger_ids,
        )

    def build_msme_ocr(
        self,
        upload_msme_field_id: int,
        msme_number_field_id: int,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build MSME OCR rule (schema ID 214).

        Args:
            upload_msme_field_id: ID of the MSME certificate upload field
            msme_number_field_id: ID of the MSME registration number field
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            GeneratedRule for MSME OCR
        """
        return self.build_simple(
            source_type="MSME",
            upload_field_id=upload_msme_field_id,
            output_field_id=msme_number_field_id,
            post_trigger_ids=post_trigger_ids,
        )

    def build_cin_ocr(
        self,
        upload_cin_field_id: int,
        cin_field_id: int,
        post_trigger_ids: Optional[List[int]] = None,
    ) -> GeneratedRule:
        """
        Build CIN OCR rule (schema ID 357).

        Args:
            upload_cin_field_id: ID of the CIN certificate upload field
            cin_field_id: ID of the CIN text field to populate
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            GeneratedRule for CIN OCR
        """
        return self.build_simple(
            source_type="CIN",
            upload_field_id=upload_cin_field_id,
            output_field_id=cin_field_id,
            post_trigger_ids=post_trigger_ids,
        )

    def get_schema_destination_fields(self, source_type: str) -> Dict[str, int]:
        """
        Get destination field names and ordinals for an OCR schema.

        Args:
            source_type: OCR source type (PAN_IMAGE, GSTIN_IMAGE, etc.)

        Returns:
            Dict mapping field name to ordinal position
        """
        schema_id = self.OCR_SCHEMAS.get(source_type)
        if schema_id:
            return self.schema_lookup.get_destination_ordinals(schema_id)
        return {}
