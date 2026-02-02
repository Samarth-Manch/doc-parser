"""
VERIFY Rule Builder

Builds VERIFY rules for PAN, GSTIN, Bank, MSME, CIN validation.
Handles ordinal-indexed destinationIds arrays.
"""

from typing import Dict, List, Optional, Any

try:
    from .base_builder import BaseRuleBuilder
    from ..models import IdGenerator, VERIFY_SCHEMA_IDS
    from ..schema_lookup import RuleSchemaLookup
    from ..id_mapper import DestinationIdMapper
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from rule_builders.base_builder import BaseRuleBuilder
    from models import IdGenerator, VERIFY_SCHEMA_IDS
    from schema_lookup import RuleSchemaLookup
    from id_mapper import DestinationIdMapper


class VerifyRuleBuilder(BaseRuleBuilder):
    """
    Builds VERIFY rules with proper destinationIds ordinal mapping.

    VERIFY rules validate documents (PAN, GSTIN, etc.) against external APIs
    and populate destination fields with the response data.
    """

    def __init__(
        self,
        id_generator: IdGenerator,
        schema_lookup: RuleSchemaLookup,
        id_mapper: DestinationIdMapper
    ):
        """
        Initialize the VERIFY rule builder.

        Args:
            id_generator: IdGenerator for sequential rule IDs
            schema_lookup: RuleSchemaLookup for querying schemas
            id_mapper: DestinationIdMapper for ordinal mapping
        """
        super().__init__(id_generator)
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper

    def build(
        self,
        source_type: str,
        source_field_id: int,
        field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None,
        button: str = "Verify"
    ) -> Dict[str, Any]:
        """
        Build a VERIFY rule with proper destinationIds ordinal mapping.

        Args:
            source_type: VERIFY source type (e.g., "PAN_NUMBER", "GSTIN")
            source_field_id: ID of the field containing the value to verify
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification
            button: Button text (default "Verify")

        Returns:
            Complete VERIFY rule dict
        """
        schema_id = VERIFY_SCHEMA_IDS.get(source_type)

        # Build destinationIds array
        destination_ids = []
        if schema_id and field_mappings:
            destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)
        elif schema_id:
            # Use schema to determine array size, fill with -1
            num_items = self.schema_lookup.get_destination_count(schema_id)
            destination_ids = [-1] * num_items

        rule = self.create_base_rule(
            "VERIFY",
            [source_field_id],
            destination_ids,
            "SERVER"
        )

        rule.update({
            "sourceType": source_type,
            "button": button,
            "postTriggerRuleIds": post_trigger_ids or []
        })

        return rule

    def build_pan_verify(
        self,
        pan_field_id: int,
        pan_holder_name_id: int = None,
        pan_type_id: int = None,
        pan_status_id: int = None,
        aadhaar_status_id: int = None,
        post_trigger_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Build a PAN VERIFY rule with common destination mappings.

        PAN Validation (schema ID 360) has 10 destination ordinals:
        1: Panholder title
        2: Firstname
        3: Lastname
        4: Fullname (Pan Holder Name)
        5: Last updated
        6: Pan retrieval status (PAN Status)
        7: Fullname without title
        8: Pan type
        9: Aadhaar seeding status
        10: Middle name

        Args:
            pan_field_id: ID of the PAN input field
            pan_holder_name_id: ID for Fullname (ordinal 4)
            pan_type_id: ID for Pan type (ordinal 8)
            pan_status_id: ID for Pan retrieval status (ordinal 6)
            aadhaar_status_id: ID for Aadhaar seeding status (ordinal 9)
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            Complete PAN VERIFY rule dict
        """
        # Build destinationIds array (10 elements)
        destination_ids = [-1] * 10

        if pan_holder_name_id:
            destination_ids[3] = pan_holder_name_id  # ordinal 4 -> index 3
        if pan_status_id:
            destination_ids[5] = pan_status_id  # ordinal 6 -> index 5
        if pan_type_id:
            destination_ids[7] = pan_type_id  # ordinal 8 -> index 7
        if aadhaar_status_id:
            destination_ids[8] = aadhaar_status_id  # ordinal 9 -> index 8

        rule = self.create_base_rule(
            "VERIFY",
            [pan_field_id],
            destination_ids,
            "SERVER"
        )

        rule.update({
            "sourceType": "PAN_NUMBER",
            "button": "Verify",
            "postTriggerRuleIds": post_trigger_ids or []
        })

        return rule

    def build_gstin_verify(
        self,
        gstin_field_id: int,
        destination_field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Build a GSTIN VERIFY rule.

        GSTIN Validation (schema ID 355) has 21 destination ordinals including:
        1: Trade name
        2: Longname (Legal Name)
        3: Reg date
        4: City
        5: Type
        6: Building number
        7: Flat number
        8: District code
        9: Pin
        10: State
        ...

        Args:
            gstin_field_id: ID of the GSTIN input field
            destination_field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            Complete GSTIN VERIFY rule dict
        """
        field_mappings = destination_field_mappings or {}
        return self.build("GSTIN", gstin_field_id, field_mappings, post_trigger_ids, "Verify")

    def build_bank_verify(
        self,
        ifsc_field_id: int,
        account_number_field_id: int,
        beneficiary_name_id: int = None,
        verification_status_id: int = None,
        post_trigger_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Build a Bank Account VERIFY rule.

        Bank Validation (schema ID 361) has 4 destination ordinals:
        1: Bank Beneficiary Name
        2: Bank Reference
        3: Verification Status
        4: Message

        Args:
            ifsc_field_id: ID of the IFSC Code field
            account_number_field_id: ID of the Account Number field
            beneficiary_name_id: ID for beneficiary name output
            verification_status_id: ID for verification status output
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            Complete Bank VERIFY rule dict
        """
        # Bank VERIFY uses multiple source fields (IFSC + Account Number)
        destination_ids = [-1] * 4

        if beneficiary_name_id:
            destination_ids[0] = beneficiary_name_id  # ordinal 1
        if verification_status_id:
            destination_ids[2] = verification_status_id  # ordinal 3

        rule = self.create_base_rule(
            "VERIFY",
            [ifsc_field_id, account_number_field_id],
            destination_ids,
            "SERVER"
        )

        rule.update({
            "sourceType": "BANK_ACCOUNT_NUMBER",
            "button": "VERIFY",
            "postTriggerRuleIds": post_trigger_ids or []
        })

        return rule

    def build_msme_verify(
        self,
        msme_field_id: int,
        destination_field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Build a MSME/Udyam VERIFY rule.

        MSME Validation (schema ID 337) has 21 destination ordinals.

        Args:
            msme_field_id: ID of the MSME/Udyam registration number field
            destination_field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            Complete MSME VERIFY rule dict
        """
        field_mappings = destination_field_mappings or {}
        return self.build("MSME_UDYAM_REG_NUMBER", msme_field_id, field_mappings, post_trigger_ids, "")

    def build_gstin_with_pan(
        self,
        pan_field_id: int,
        gstin_field_id: int
    ) -> Dict[str, Any]:
        """
        Build a GSTIN_WITH_PAN cross-validation rule.

        This rule verifies that the PAN in the GSTIN matches the provided PAN.

        Args:
            pan_field_id: ID of the PAN field
            gstin_field_id: ID of the GSTIN field

        Returns:
            GSTIN_WITH_PAN cross-validation rule dict
        """
        rule = self.create_base_rule(
            "VERIFY",
            [pan_field_id, gstin_field_id],
            [],
            "SERVER"
        )

        rule.update({
            "sourceType": "GSTIN_WITH_PAN",
            "params": '{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
            "onStatusFail": "CONTINUE"
        })

        return rule
