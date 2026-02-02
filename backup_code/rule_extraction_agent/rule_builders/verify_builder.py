"""
VERIFY Rule Builder - Builds VERIFY rules (PAN, GSTIN, Bank, MSME, CIN validation).
"""

from typing import List, Optional, Dict
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule, IdGenerator
from ..schema_lookup import RuleSchemaLookup
from ..id_mapper import DestinationIdMapper


class VerifyRuleBuilder(BaseRuleBuilder):
    """Builds VERIFY rules with proper destinationIds ordinal mapping."""

    def __init__(
        self,
        id_generator: IdGenerator,
        schema_lookup: RuleSchemaLookup,
        id_mapper: DestinationIdMapper
    ):
        """
        Initialize the builder.

        Args:
            id_generator: IdGenerator instance.
            schema_lookup: RuleSchemaLookup for schema queries.
            id_mapper: DestinationIdMapper for ordinal mapping.
        """
        super().__init__(id_generator)
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper

    def build(
        self,
        source_type: str,
        source_field_id: int,
        field_mappings: Optional[Dict[str, int]] = None,
        destination_ids: Optional[List[int]] = None,
        post_trigger_ids: Optional[List[int]] = None,
        button: str = "Verify"
    ) -> GeneratedRule:
        """
        Build VERIFY rule with proper destinationIds ordinal mapping.

        Args:
            source_type: Verification source type (e.g., "PAN_NUMBER", "GSTIN").
            source_field_id: Source field ID being verified.
            field_mappings: Dict mapping schema field names to BUD field IDs.
            destination_ids: Pre-computed destination IDs (optional).
            post_trigger_ids: Rule IDs to trigger after this rule.
            button: Button text (default: "Verify").

        Returns:
            GeneratedRule for VERIFY.

        Example:
            source_type = "PAN_NUMBER"
            source_field_id = 275534
            field_mappings = {
                "Fullname": 275535,
                "Pan retrieval status": 275537,
                "Pan type": 275536,
                "Aadhaar seeding status": 275538
            }
        """
        rule = self.create_base_rule(
            "VERIFY",
            [source_field_id],
            [],
            "SERVER"
        )

        rule.source_type = source_type
        rule.button = button
        rule.post_trigger_rule_ids = post_trigger_ids or []

        # Get destination IDs
        if destination_ids:
            rule.destination_ids = destination_ids
        elif field_mappings:
            schema_id = self.schema_lookup.get_schema_id_for_source(source_type)
            if schema_id:
                rule.destination_ids = self.id_mapper.map_to_ordinals(
                    schema_id,
                    field_mappings
                )

        return rule

    def build_pan_verify(
        self,
        pan_field_id: int,
        holder_name_id: Optional[int] = None,
        pan_type_id: Optional[int] = None,
        pan_status_id: Optional[int] = None,
        aadhaar_status_id: Optional[int] = None,
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build PAN VERIFY rule.

        Args:
            pan_field_id: PAN field ID.
            holder_name_id: Pan Holder Name field ID.
            pan_type_id: PAN Type field ID.
            pan_status_id: PAN Status field ID.
            aadhaar_status_id: Aadhaar PAN List Status field ID.
            post_trigger_ids: Rules to trigger after.

        Returns:
            GeneratedRule for PAN validation.
        """
        field_mappings = {}

        if holder_name_id:
            field_mappings['Fullname'] = holder_name_id
        if pan_type_id:
            field_mappings['Pan type'] = pan_type_id
        if pan_status_id:
            field_mappings['Pan retrieval status'] = pan_status_id
        if aadhaar_status_id:
            field_mappings['Aadhaar seeding status'] = aadhaar_status_id

        return self.build(
            source_type="PAN_NUMBER",
            source_field_id=pan_field_id,
            field_mappings=field_mappings if field_mappings else None,
            post_trigger_ids=post_trigger_ids,
            button="VERIFY"
        )

    def build_gstin_verify(
        self,
        gstin_field_id: int,
        destination_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build GSTIN VERIFY rule.

        Args:
            gstin_field_id: GSTIN field ID.
            destination_mappings: Dict mapping destination field names to IDs.
            post_trigger_ids: Rules to trigger after.

        Returns:
            GeneratedRule for GSTIN validation.
        """
        return self.build(
            source_type="GSTIN",
            source_field_id=gstin_field_id,
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids,
            button="Verify"
        )

    def build_bank_verify(
        self,
        account_field_id: int,
        ifsc_field_id: Optional[int] = None,
        bank_name_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build Bank Account VERIFY rule.

        Args:
            account_field_id: Bank Account Number field ID.
            ifsc_field_id: IFSC Code field ID.
            bank_name_id: Bank Name field ID.
            branch_id: Branch field ID.
            post_trigger_ids: Rules to trigger after.

        Returns:
            GeneratedRule for bank validation.
        """
        field_mappings = {}

        if ifsc_field_id:
            field_mappings['ifscCode'] = ifsc_field_id
        if bank_name_id:
            field_mappings['bankName'] = bank_name_id
        if branch_id:
            field_mappings['branch'] = branch_id

        return self.build(
            source_type="BANK_ACCOUNT_NUMBER",
            source_field_id=account_field_id,
            field_mappings=field_mappings if field_mappings else None,
            post_trigger_ids=post_trigger_ids,
            button="Verify"
        )

    def build_msme_verify(
        self,
        msme_field_id: int,
        destination_mappings: Optional[Dict[str, int]] = None,
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build MSME VERIFY rule.

        Args:
            msme_field_id: MSME Registration Number field ID.
            destination_mappings: Dict mapping destination field names to IDs.
            post_trigger_ids: Rules to trigger after.

        Returns:
            GeneratedRule for MSME validation.
        """
        return self.build(
            source_type="MSME_UDYAM_REG_NUMBER",
            source_field_id=msme_field_id,
            field_mappings=destination_mappings,
            post_trigger_ids=post_trigger_ids,
            button="Verify"
        )

    def build_gstin_with_pan(
        self,
        pan_field_id: int,
        gstin_field_id: int
    ) -> GeneratedRule:
        """
        Build GSTIN_WITH_PAN cross-validation rule.

        Args:
            pan_field_id: PAN field ID.
            gstin_field_id: GSTIN field ID.

        Returns:
            GeneratedRule for cross-validation.
        """
        rule = self.create_base_rule(
            "VERIFY",
            [pan_field_id, gstin_field_id],
            [],
            "SERVER"
        )

        rule.source_type = "GSTIN_WITH_PAN"
        rule.params = '{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}'
        rule.on_status_fail = "CONTINUE"
        rule.button = ""

        return rule
