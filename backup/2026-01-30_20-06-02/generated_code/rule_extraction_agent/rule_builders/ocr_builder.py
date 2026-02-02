"""
OCR Rule Builder - Build OCR rules for document extraction.

Supports:
- PAN_IMAGE (schema ID 344) - 4 destination ordinals
- GSTIN_IMAGE (schema ID 347) - 11 destination ordinals
- CHEQUEE (schema ID 269) - 7 destination ordinals
- AADHAR_IMAGE (schema ID 359) - 13 destination ordinals
- AADHAR_BACK_IMAGE (schema ID 348) - 9 destination ordinals
- MSME (schema ID 214) - 6 destination ordinals
- CIN (schema ID 357) - 7 destination ordinals

Key insight: OCR rules should have postTriggerRuleIds linking to VERIFY rules
to create the OCR -> VERIFY chain.
"""

from typing import List, Dict, Optional

from .base_builder import BaseRuleBuilder, get_rule_id
from ..models import GeneratedRule
from ..schema_lookup import RuleSchemaLookup, get_verify_source_for_ocr


class OcrRuleBuilder(BaseRuleBuilder):
    """Build OCR rules for document extraction."""

    # Schema IDs for OCR rules
    SCHEMA_IDS = {
        "PAN_IMAGE": 344,
        "GSTIN_IMAGE": 347,
        "CHEQUEE": 269,
        "AADHAR_IMAGE": 359,
        "AADHAR_BACK_IMAGE": 348,
        "MSME": 214,
        "CIN": 357,
    }

    def __init__(self, schema_lookup: RuleSchemaLookup = None):
        """
        Initialize OCR rule builder.

        Args:
            schema_lookup: RuleSchemaLookup instance (created if None)
        """
        super().__init__()
        self.schema_lookup = schema_lookup or RuleSchemaLookup()

    def build_ocr_rule(
        self,
        source_type: str,
        upload_field_id: int,
        output_field_id: int,
        post_trigger_ids: List[int] = None,
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build basic OCR rule.

        Args:
            source_type: OCR source type (e.g., "PAN_IMAGE")
            upload_field_id: ID of the file upload field
            output_field_id: ID of the text field to populate
            post_trigger_ids: Rule IDs to trigger after OCR (typically VERIFY)
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for OCR
        """
        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="OCR",
            source_type=source_type,
            processing_type="SERVER",
            source_ids=[upload_field_id],
            destination_ids=[output_field_id],
            post_trigger_rule_ids=post_trigger_ids or [],
            button="",
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule

    def build_ocr_rule_with_ordinals(
        self,
        source_type: str,
        upload_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: List[int] = None,
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build OCR rule with ordinal-indexed destinationIds.

        Args:
            source_type: OCR source type
            upload_field_id: ID of the file upload field
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after OCR
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for OCR with ordinal mapping
        """
        schema_id = self.SCHEMA_IDS.get(source_type)
        if schema_id:
            destination_ids = self.schema_lookup.build_destination_ids_array(
                schema_id, field_mappings
            )
        else:
            destination_ids = list(field_mappings.values())

        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="OCR",
            source_type=source_type,
            processing_type="SERVER",
            source_ids=[upload_field_id],
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger_ids or [],
            button="",
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule

    def build_pan_ocr_rule(
        self,
        upload_field_id: int,
        pan_field_id: int,
        verify_rule_id: int = None
    ) -> GeneratedRule:
        """
        Build PAN OCR rule.

        Schema ID 344, 4 destination ordinals:
        1: panNo, 2: name, 3: fatherName, 4: dob

        For simple case, only panNo (ordinal 1) is mapped to the PAN field.

        Args:
            upload_field_id: ID of the Upload PAN field
            pan_field_id: ID of the PAN text field
            verify_rule_id: ID of the PAN VERIFY rule to chain to

        Returns:
            GeneratedRule for PAN OCR
        """
        return self.build_ocr_rule(
            source_type="PAN_IMAGE",
            upload_field_id=upload_field_id,
            output_field_id=pan_field_id,
            post_trigger_ids=[verify_rule_id] if verify_rule_id else []
        )

    def build_gstin_ocr_rule(
        self,
        upload_field_id: int,
        gstin_field_id: int,
        verify_rule_id: int = None
    ) -> GeneratedRule:
        """
        Build GSTIN OCR rule.

        Schema ID 347, 11 destination ordinals.
        For simple case, only regNumber (ordinal 1) is mapped to GSTIN field.

        Args:
            upload_field_id: ID of the GSTIN IMAGE upload field
            gstin_field_id: ID of the GSTIN text field
            verify_rule_id: ID of the GSTIN VERIFY rule to chain to

        Returns:
            GeneratedRule for GSTIN OCR
        """
        return self.build_ocr_rule(
            source_type="GSTIN_IMAGE",
            upload_field_id=upload_field_id,
            output_field_id=gstin_field_id,
            post_trigger_ids=[verify_rule_id] if verify_rule_id else []
        )

    def build_cheque_ocr_rule(
        self,
        upload_field_id: int,
        field_mappings: Dict[str, int],
        verify_rule_id: int = None
    ) -> GeneratedRule:
        """
        Build Cheque OCR rule.

        Schema ID 269, 7 destination ordinals:
        1: bankName, 2: ifscCode, 3: beneficiaryName, 4: accountNumber,
        5: address, 6: chequeNo, 7: type

        Args:
            upload_field_id: ID of the Cancelled Cheque upload field
            field_mappings: Mapping of schema field names to BUD field IDs
                           e.g., {"ifscCode": 275560, "accountNumber": 275561}
            verify_rule_id: ID of the Bank VERIFY rule to chain to

        Returns:
            GeneratedRule for Cheque OCR
        """
        return self.build_ocr_rule_with_ordinals(
            source_type="CHEQUEE",
            upload_field_id=upload_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=[verify_rule_id] if verify_rule_id else []
        )

    def build_aadhaar_back_ocr_rule(
        self,
        upload_field_id: int,
        field_mappings: Dict[str, int],
        conditional_value_id: int = None,
        conditional_values: List[str] = None
    ) -> GeneratedRule:
        """
        Build Aadhaar Back OCR rule.

        Schema ID 348, 9 destination ordinals:
        1: aadharAddress1, 2: aadharAddress2, 3: aadharPin, 4: aadharCity,
        5: aadharDist, 6: aadharState, 7: aadharFatherName, 8: aadharFullAddress,
        9: newAadhaarstorageId

        Args:
            upload_field_id: ID of the Aadhaar Back upload field
            field_mappings: Mapping of schema field names to BUD field IDs
            conditional_value_id: Field ID for conditional execution
            conditional_values: Values that trigger OCR

        Returns:
            GeneratedRule for Aadhaar Back OCR
        """
        rule = self.build_ocr_rule_with_ordinals(
            source_type="AADHAR_BACK_IMAGE",
            upload_field_id=upload_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=[]
        )

        # Add conditional execution if specified
        if conditional_value_id and conditional_values:
            # This is a special case - we need to add conditionalValueId
            # which is different from sourceIds
            pass  # Would need to extend GeneratedRule model

        return rule

    def build_msme_ocr_rule(
        self,
        upload_field_id: int,
        field_mappings: Dict[str, int],
        verify_rule_id: int = None
    ) -> GeneratedRule:
        """
        Build MSME OCR rule.

        Schema ID 214, 6 destination ordinals:
        1: regNumber, 2: name, 3: type, 4: address, 5: category, 6: date

        Args:
            upload_field_id: ID of the MSME Image upload field
            field_mappings: Mapping of schema field names to BUD field IDs
            verify_rule_id: ID of the MSME VERIFY rule to chain to

        Returns:
            GeneratedRule for MSME OCR
        """
        return self.build_ocr_rule_with_ordinals(
            source_type="MSME",
            upload_field_id=upload_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=[verify_rule_id] if verify_rule_id else []
        )

    def build_cin_ocr_rule(
        self,
        upload_field_id: int,
        cin_field_id: int,
        verify_rule_id: int = None
    ) -> GeneratedRule:
        """
        Build CIN OCR rule.

        Schema ID 357, 7 destination ordinals:
        1: cinNumber, 2: companyName, 3: panNumber, 4: address,
        5: pinCode, 6: city, 7: state

        Args:
            upload_field_id: ID of the CIN upload field
            cin_field_id: ID of the CIN text field
            verify_rule_id: ID of the CIN VERIFY rule to chain to

        Returns:
            GeneratedRule for CIN OCR
        """
        return self.build_ocr_rule(
            source_type="CIN",
            upload_field_id=upload_field_id,
            output_field_id=cin_field_id,
            post_trigger_ids=[verify_rule_id] if verify_rule_id else []
        )


def link_ocr_to_verify_rules(
    ocr_rules: List[GeneratedRule],
    verify_rules: List[GeneratedRule]
) -> None:
    """
    Link OCR rules to corresponding VERIFY rules via postTriggerRuleIds.

    This is CRITICAL for rule chaining.

    Args:
        ocr_rules: List of OCR rules
        verify_rules: List of VERIFY rules

    Side effects:
        Modifies ocr_rules to add postTriggerRuleIds
    """
    # Build index of VERIFY rules by source field ID
    verify_by_source = {}
    for rule in verify_rules:
        for source_id in rule.source_ids:
            verify_by_source[source_id] = rule

    # Link each OCR rule to its corresponding VERIFY rule
    for ocr_rule in ocr_rules:
        if not ocr_rule.destination_ids:
            continue

        # OCR destination is the field that gets populated
        # This field should be the source for VERIFY
        for dest_id in ocr_rule.destination_ids:
            if dest_id == -1:
                continue
            if dest_id in verify_by_source:
                verify_rule = verify_by_source[dest_id]
                if verify_rule.id not in ocr_rule.post_trigger_rule_ids:
                    ocr_rule.post_trigger_rule_ids.append(verify_rule.id)
                break
