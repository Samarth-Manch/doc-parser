"""
VERIFY Rule Builder - Builds verification rules (PAN, GSTIN, Bank, MSME, CIN, etc.).
"""

from typing import Dict, List, Optional
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


# Source type mappings for verification
VERIFY_SOURCE_TYPES = {
    "PAN": "PAN_NUMBER",
    "GSTIN": "GSTIN",
    "BANK": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    "CIN": "CIN_ID",
    "TAN": "TAN_NUMBER",
    "FSSAI": "FSSAI",
    "GSTIN_WITH_PAN": "GSTIN_WITH_PAN",
}


class VerifyRuleBuilder(BaseRuleBuilder):
    """Builds VERIFY rules for document validation."""

    def __init__(self, schema_lookup=None, id_mapper=None):
        """
        Initialize with optional schema lookup and ID mapper.

        Args:
            schema_lookup: RuleSchemaLookup instance for schema info
            id_mapper: DestinationIdMapper for ordinal mapping
        """
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper

    def build(
        self,
        doc_type: str,
        source_field_id: int,
        destination_ids: List[int],
        post_trigger_rule_ids: List[int] = None,
        button: str = "VERIFY",
        params: str = None,
    ) -> Dict:
        """
        Build a VERIFY rule.

        Args:
            doc_type: Document type (PAN, GSTIN, BANK, MSME, CIN, TAN)
            source_field_id: ID of the field containing the value to verify
            destination_ids: List of field IDs to populate with verification results
                            Should be ordinal-indexed array with -1 for unused ordinals
            post_trigger_rule_ids: Rule IDs to trigger after verification
            button: Button text (default: "VERIFY")
            params: Optional JSON params string

        Returns:
            Rule dictionary
        """
        source_type = VERIFY_SOURCE_TYPES.get(doc_type.upper())
        if not source_type:
            raise ValueError(f"Unknown document type for VERIFY: {doc_type}")

        return self._create_base_rule(
            action_type="VERIFY",
            source_type=source_type,
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type="SERVER",
            post_trigger_rule_ids=post_trigger_rule_ids,
            button=button,
            params=params,
        )

    def build_with_schema(
        self,
        schema_id: int,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_rule_ids: List[int] = None,
    ) -> Dict:
        """
        Build a VERIFY rule using schema info for destination ordinal mapping.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            source_field_id: ID of the field containing the value to verify
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_rule_ids: Rule IDs to trigger after verification

        Returns:
            Rule dictionary
        """
        if not self.schema_lookup or not self.id_mapper:
            raise ValueError("schema_lookup and id_mapper required for build_with_schema")

        schema = self.schema_lookup.get_by_id(schema_id)
        if not schema:
            raise ValueError(f"Schema {schema_id} not found")

        # Map field names to ordinal positions
        destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)

        return self._create_base_rule(
            action_type="VERIFY",
            source_type=schema.get("source"),
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type=schema.get("processingType", "SERVER"),
            post_trigger_rule_ids=post_trigger_rule_ids,
            button=schema.get("button", "Verify"),
        )

    def build_pan_verify(
        self,
        pan_field_id: int,
        pan_holder_name_id: int = None,
        pan_status_id: int = None,
        pan_type_id: int = None,
        aadhaar_status_id: int = None,
        post_trigger_rule_ids: List[int] = None,
    ) -> Dict:
        """
        Build a PAN VERIFY rule with common field mappings.

        PAN Verify schema has 10 destination ordinals:
        1: Panholder title
        2: Firstname
        3: Lastname
        4: Fullname <- typically "Pan Holder Name"
        5: Last updated
        6: Pan retrieval status <- typically "PAN Status"
        7: Fullname without title
        8: Pan type <- typically "PAN Type"
        9: Aadhaar seeding status <- typically "Aadhaar PAN List Status"
        10: Middle name

        Args:
            pan_field_id: PAN input field ID
            pan_holder_name_id: Field ID for Pan Holder Name (ordinal 4)
            pan_status_id: Field ID for PAN Status (ordinal 6)
            pan_type_id: Field ID for PAN Type (ordinal 8)
            aadhaar_status_id: Field ID for Aadhaar seeding status (ordinal 9)
            post_trigger_rule_ids: Rule IDs to trigger after

        Returns:
            Rule dictionary
        """
        # Build destination_ids array (10 elements for 10 ordinals)
        destination_ids = [-1] * 9  # PAN verify has 9-10 destination fields

        if pan_holder_name_id:
            destination_ids[3] = pan_holder_name_id  # ordinal 4 -> index 3
        if pan_status_id:
            destination_ids[5] = pan_status_id  # ordinal 6 -> index 5
        if pan_type_id:
            destination_ids[7] = pan_type_id  # ordinal 8 -> index 7
        if aadhaar_status_id:
            destination_ids[8] = aadhaar_status_id  # ordinal 9 -> index 8

        return self.build(
            doc_type="PAN",
            source_field_id=pan_field_id,
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger_rule_ids,
            button="VERIFY",
        )

    def build_gstin_verify(
        self,
        gstin_field_id: int,
        destination_field_ids: Dict[str, int] = None,
        post_trigger_rule_ids: List[int] = None,
    ) -> Dict:
        """
        Build a GSTIN VERIFY rule.

        GSTIN Verify schema has 21 destination ordinals including:
        1: Trade name
        2: Longname (Legal name)
        3: Reg date
        4: City
        5: Type
        6: Building number
        7: Flat number
        8: District code
        9: State code
        10: Street
        11: Pincode
        ...

        Args:
            gstin_field_id: GSTIN input field ID
            destination_field_ids: Dict mapping common names to field IDs
            post_trigger_rule_ids: Rule IDs to trigger after

        Returns:
            Rule dictionary
        """
        # GSTIN has 21 destination ordinals
        destination_ids = [-1] * 11  # Using common 11 fields

        if destination_field_ids:
            # Map common field names to ordinal positions
            ordinal_mapping = {
                "trade_name": 0,      # ordinal 1
                "legal_name": 1,      # ordinal 2
                "reg_date": 2,        # ordinal 3
                "city": 3,            # ordinal 4
                "type": 4,            # ordinal 5
                "building_number": 5, # ordinal 6
                "district": 7,        # ordinal 8
                "state": 8,           # ordinal 9
                "street": 9,          # ordinal 10
                "pincode": 10,        # ordinal 11
            }

            for name, idx in ordinal_mapping.items():
                if name in destination_field_ids:
                    destination_ids[idx] = destination_field_ids[name]

        return self.build(
            doc_type="GSTIN",
            source_field_id=gstin_field_id,
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger_rule_ids,
            button="Verify",
        )

    def build_bank_verify(
        self,
        ifsc_field_id: int,
        account_number_field_id: int,
        beneficiary_name_id: int = None,
        post_trigger_rule_ids: List[int] = None,
    ) -> Dict:
        """
        Build a Bank Account VERIFY rule.

        Args:
            ifsc_field_id: IFSC code field ID
            account_number_field_id: Bank account number field ID
            beneficiary_name_id: Field ID to populate with beneficiary name
            post_trigger_rule_ids: Rule IDs to trigger after

        Returns:
            Rule dictionary
        """
        destination_ids = []
        if beneficiary_name_id:
            destination_ids = [beneficiary_name_id]

        return self._create_base_rule(
            action_type="VERIFY",
            source_type="BANK_ACCOUNT_NUMBER",
            source_ids=[account_number_field_id, ifsc_field_id],
            destination_ids=destination_ids,
            processing_type="SERVER",
            post_trigger_rule_ids=post_trigger_rule_ids,
            button="VERIFY",
        )

    def build_gstin_with_pan(
        self,
        pan_field_id: int,
        gstin_field_id: int,
        error_message: str = "GSTIN and PAN doesn't match.",
    ) -> Dict:
        """
        Build a GSTIN_WITH_PAN validation rule.

        This rule validates that GSTIN and PAN match.

        Args:
            pan_field_id: PAN field ID
            gstin_field_id: GSTIN field ID
            error_message: Error message if validation fails

        Returns:
            Rule dictionary
        """
        params = f'{{ "paramMap": {{"errorMessage": "{error_message}"}}}}'

        rule = self._create_base_rule(
            action_type="VERIFY",
            source_type="GSTIN_WITH_PAN",
            source_ids=[pan_field_id, gstin_field_id],
            destination_ids=[],
            processing_type="SERVER",
            params=params,
        )

        rule["onStatusFail"] = "CONTINUE"

        return rule
