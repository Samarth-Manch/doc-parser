"""
Verify Rule Builder - Build VERIFY rules for validation.

Supports:
- PAN_NUMBER (schema ID 360)
- GSTIN (schema ID 355)
- BANK_ACCOUNT_NUMBER (schema ID 361)
- MSME_UDYAM_REG_NUMBER (schema ID 337)
- CIN_ID (schema ID 349)
- GSTIN_WITH_PAN (cross-validation)

Key insight: VERIFY rules use ordinal-indexed destinationIds arrays.
Use -1 for ordinals that don't have corresponding BUD fields.
"""

from typing import List, Dict, Optional

from .base_builder import BaseRuleBuilder, get_rule_id
from ..models import GeneratedRule
from ..schema_lookup import RuleSchemaLookup


class VerifyRuleBuilder(BaseRuleBuilder):
    """Build VERIFY rules for document validation."""

    # Schema IDs for common VERIFY rules
    SCHEMA_IDS = {
        "PAN_NUMBER": 360,
        "GSTIN": 355,
        "BANK_ACCOUNT_NUMBER": 361,
        "MSME_UDYAM_REG_NUMBER": 337,
        "CIN_ID": 349,
    }

    def __init__(self, schema_lookup: RuleSchemaLookup = None):
        """
        Initialize verify rule builder.

        Args:
            schema_lookup: RuleSchemaLookup instance (created if None)
        """
        super().__init__()
        self.schema_lookup = schema_lookup or RuleSchemaLookup()

    def build_verify_rule(
        self,
        source_type: str,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: List[int] = None,
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build a VERIFY rule with proper destinationIds ordinal mapping.

        Args:
            source_type: Source type (e.g., "PAN_NUMBER", "GSTIN")
            source_field_id: ID of the field being validated
            field_mappings: Dict mapping schema field names to BUD field IDs
                           e.g., {"Fullname": 275535, "Pan type": 275536}
            post_trigger_ids: Rule IDs to trigger after verification
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for VERIFY
        """
        schema_id = self.SCHEMA_IDS.get(source_type)
        if schema_id:
            schema_info = self.schema_lookup.get_schema_info(source_type)
        else:
            schema_info = None

        # Build destinationIds with ordinal mapping
        if schema_id:
            destination_ids = self.schema_lookup.build_destination_ids_array(
                schema_id, field_mappings
            )
        else:
            destination_ids = list(field_mappings.values())

        # Get button text from schema
        button_text = "Verify"
        if schema_info:
            button_text = schema_info.button or "Verify"

        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="VERIFY",
            source_type=source_type,
            processing_type="SERVER",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger_ids or [],
            button=button_text,
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )

        return rule

    def build_pan_verify_rule(
        self,
        pan_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: List[int] = None
    ) -> GeneratedRule:
        """
        Build PAN Validation rule.

        Schema ID 360, 10 destination ordinals:
        1: Panholder title, 2: Firstname, 3: Lastname, 4: Fullname,
        5: Last updated, 6: Pan retrieval status, 7: Fullname without title,
        8: Pan type, 9: Aadhaar seeding status, 10: Middle name

        Args:
            pan_field_id: ID of the PAN text field
            field_mappings: Mapping of schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after

        Returns:
            GeneratedRule for PAN VERIFY
        """
        return self.build_verify_rule(
            source_type="PAN_NUMBER",
            source_field_id=pan_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_gstin_verify_rule(
        self,
        gstin_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: List[int] = None
    ) -> GeneratedRule:
        """
        Build GSTIN Validation rule.

        Schema ID 355, 21 destination ordinals including:
        1: Trade name, 2: Longname, 3: Reg date, 4: City, 5: Type,
        6: Building number, 7: Flat number, 8: District code, etc.

        Args:
            gstin_field_id: ID of the GSTIN text field
            field_mappings: Mapping of schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after

        Returns:
            GeneratedRule for GSTIN VERIFY
        """
        return self.build_verify_rule(
            source_type="GSTIN",
            source_field_id=gstin_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_bank_verify_rule(
        self,
        ifsc_field_id: int,
        account_field_id: int,
        field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> GeneratedRule:
        """
        Build Bank Account Validation rule.

        Schema ID 361, 4 destination ordinals:
        1: Bank Beneficiary Name, 2: Bank Reference,
        3: Verification Status, 4: Message

        Args:
            ifsc_field_id: ID of the IFSC Code field
            account_field_id: ID of the Bank Account Number field
            field_mappings: Mapping of schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after

        Returns:
            GeneratedRule for Bank Account VERIFY
        """
        rule = GeneratedRule(
            id=get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="VERIFY",
            source_type="BANK_ACCOUNT_NUMBER",
            processing_type="SERVER",
            source_ids=[ifsc_field_id, account_field_id],  # Bank requires both!
            destination_ids=list((field_mappings or {}).values()),
            post_trigger_rule_ids=post_trigger_ids or [],
            button="VERIFY",
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule

    def build_msme_verify_rule(
        self,
        msme_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: List[int] = None
    ) -> GeneratedRule:
        """
        Build MSME Validation rule.

        Schema ID 337, 21 destination ordinals including:
        1: Name Of Enterprise, 2: Major Activity, 3: Social Category,
        4: Enterprise, 5: Date Of Commencement, etc.

        Args:
            msme_field_id: ID of the MSME Registration Number field
            field_mappings: Mapping of schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after

        Returns:
            GeneratedRule for MSME VERIFY
        """
        return self.build_verify_rule(
            source_type="MSME_UDYAM_REG_NUMBER",
            source_field_id=msme_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids
        )

    def build_cin_verify_rule(
        self,
        cin_field_id: int,
        field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> GeneratedRule:
        """
        Build CIN Validation rule.

        Schema ID 349, 10 destination ordinals:
        1: Company Name, 2: Model Type, 3: Address, 4: Company Status, etc.

        Args:
            cin_field_id: ID of the CIN field
            field_mappings: Mapping of schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after

        Returns:
            GeneratedRule for CIN VERIFY
        """
        return self.build_verify_rule(
            source_type="CIN_ID",
            source_field_id=cin_field_id,
            field_mappings=field_mappings or {},
            post_trigger_ids=post_trigger_ids
        )

    def build_gstin_with_pan_rule(
        self,
        pan_field_id: int,
        gstin_field_id: int,
        rule_id: int = None
    ) -> GeneratedRule:
        """
        Build GSTIN_WITH_PAN cross-validation rule.

        Verifies that PAN and GSTIN belong to the same entity.

        Args:
            pan_field_id: ID of the PAN field
            gstin_field_id: ID of the GSTIN field
            rule_id: Optional specific rule ID

        Returns:
            GeneratedRule for GSTIN_WITH_PAN cross-validation
        """
        rule = GeneratedRule(
            id=rule_id or get_rule_id(),
            create_user="FIRST_PARTY",
            update_user="FIRST_PARTY",
            action_type="VERIFY",
            source_type="GSTIN_WITH_PAN",
            processing_type="SERVER",
            source_ids=[pan_field_id, gstin_field_id],
            destination_ids=[],
            post_trigger_rule_ids=[],
            params='{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
            on_status_fail="CONTINUE",
            button="",
            searchable=False,
            execute_on_fill=True,
            execute_on_read=False,
            execute_on_esign=False,
            execute_post_esign=False,
            run_post_condition_fail=False,
        )
        return rule

    def build_pin_code_verify_rule(
        self,
        pin_code_field_id: int,
        field_mappings: Dict[str, int] = None,
        post_trigger_ids: List[int] = None
    ) -> GeneratedRule:
        """
        Build PIN Code validation rule.

        Args:
            pin_code_field_id: ID of the PIN code field
            field_mappings: Mapping for city, district, state fields
            post_trigger_ids: Rule IDs to trigger after

        Returns:
            GeneratedRule for PIN_CODE VERIFY
        """
        return self.build_verify_rule(
            source_type="PIN_CODE",
            source_field_id=pin_code_field_id,
            field_mappings=field_mappings or {},
            post_trigger_ids=post_trigger_ids
        )
