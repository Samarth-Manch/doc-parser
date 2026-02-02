"""
Verify Rule Builder - Build VERIFY rules for validation (PAN, GSTIN, Bank, MSME, etc.).

CRITICAL: VERIFY rules use ordinal-indexed destinationIds arrays.
"""

from typing import List, Dict, Optional
from .base_builder import BaseRuleBuilder, RuleIdGenerator
from ..models import GeneratedRule
from ..schema_lookup import RuleSchemaLookup
from ..id_mapper import DestinationIdMapper


class VerifyRuleBuilder(BaseRuleBuilder):
    """Build VERIFY rules for validation."""

    def __init__(
        self,
        id_generator: Optional[RuleIdGenerator] = None,
        schema_lookup: Optional[RuleSchemaLookup] = None
    ):
        super().__init__(id_generator)
        self.schema_lookup = schema_lookup or RuleSchemaLookup()
        self.id_mapper = DestinationIdMapper(self.schema_lookup)

    def build_pan_verify(
        self,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build PAN verification rule.

        Args:
            source_field_id: PAN input field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
                Example: {"Fullname": 275535, "Pan type": 275536}
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule for PAN.
        """
        return self._build_verify_rule(
            source_type="PAN_NUMBER",
            schema_id=360,
            source_field_id=source_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids,
            button="VERIFY"
        )

    def build_gstin_verify(
        self,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build GSTIN verification rule.

        Args:
            source_field_id: GSTIN input field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule for GSTIN.
        """
        return self._build_verify_rule(
            source_type="GSTIN",
            schema_id=355,
            source_field_id=source_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids,
            button="Verify"
        )

    def build_bank_verify(
        self,
        ifsc_field_id: int,
        account_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build Bank Account verification rule.

        Bank verification uses TWO source fields: IFSC Code and Account Number.

        Args:
            ifsc_field_id: IFSC Code field ID
            account_field_id: Bank Account Number field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule for Bank Account.
        """
        destination_ids = self.id_mapper.map_to_ordinals(361, field_mappings)

        rule = self.create_base_rule(
            action_type="VERIFY",
            source_ids=[ifsc_field_id, account_field_id],
            destination_ids=destination_ids,
            processing_type="SERVER"
        )
        rule.source_type = "BANK_ACCOUNT_NUMBER"
        rule.button = "VERIFY"
        rule.post_trigger_rule_ids = post_trigger_ids or []
        return rule

    def build_msme_verify(
        self,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build MSME/Udyam verification rule.

        Args:
            source_field_id: MSME Registration Number field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule for MSME.
        """
        return self._build_verify_rule(
            source_type="MSME_UDYAM_REG_NUMBER",
            schema_id=337,
            source_field_id=source_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids,
            button="Verify"
        )

    def build_cin_verify(
        self,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build CIN verification rule.

        Args:
            source_field_id: CIN input field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule for CIN.
        """
        return self._build_verify_rule(
            source_type="CIN_ID",
            schema_id=349,
            source_field_id=source_field_id,
            field_mappings=field_mappings,
            post_trigger_ids=post_trigger_ids,
            button="Verify"
        )

    def build_gstin_with_pan(
        self,
        pan_field_id: int,
        gstin_field_id: int
    ) -> GeneratedRule:
        """
        Build GSTIN with PAN cross-validation rule.

        This rule verifies that the PAN characters 3-12 in GSTIN match the PAN.

        Args:
            pan_field_id: PAN field ID
            gstin_field_id: GSTIN field ID

        Returns:
            Cross-validation VERIFY rule.
        """
        rule = self.create_base_rule(
            action_type="VERIFY",
            source_ids=[pan_field_id, gstin_field_id],
            destination_ids=[],
            processing_type="SERVER"
        )
        rule.source_type = "GSTIN_WITH_PAN"
        rule.params = '{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}'
        rule.on_status_fail = "CONTINUE"
        return rule

    def _build_verify_rule(
        self,
        source_type: str,
        schema_id: int,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None,
        button: str = "Verify"
    ) -> GeneratedRule:
        """
        Build a generic VERIFY rule.

        Args:
            source_type: Verification source type (e.g., "PAN_NUMBER")
            schema_id: Schema ID from Rule-Schemas.json
            source_field_id: Source field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification
            button: Button text

        Returns:
            VERIFY rule.
        """
        destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)

        rule = self.create_base_rule(
            action_type="VERIFY",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type="SERVER"
        )
        rule.source_type = source_type
        rule.button = button
        rule.post_trigger_rule_ids = post_trigger_ids or []
        return rule

    def build_verify_from_type(
        self,
        verify_type: str,
        source_field_id: int,
        field_mappings: Dict[str, int],
        post_trigger_ids: Optional[List[int]] = None
    ) -> Optional[GeneratedRule]:
        """
        Build a VERIFY rule based on the verification type.

        Args:
            verify_type: Type of verification ("PAN", "GSTIN", "BANK", "MSME", "CIN")
            source_field_id: Source field ID
            field_mappings: Dict mapping schema field names to BUD field IDs
            post_trigger_ids: Rule IDs to trigger after verification

        Returns:
            VERIFY rule or None if type not recognized.
        """
        type_to_builder = {
            "PAN": (self.build_pan_verify, {"source_field_id": source_field_id}),
            "GSTIN": (self.build_gstin_verify, {"source_field_id": source_field_id}),
            "MSME": (self.build_msme_verify, {"source_field_id": source_field_id}),
            "CIN": (self.build_cin_verify, {"source_field_id": source_field_id}),
        }

        if verify_type.upper() in type_to_builder:
            builder, kwargs = type_to_builder[verify_type.upper()]
            return builder(
                **kwargs,
                field_mappings=field_mappings,
                post_trigger_ids=post_trigger_ids
            )

        return None
