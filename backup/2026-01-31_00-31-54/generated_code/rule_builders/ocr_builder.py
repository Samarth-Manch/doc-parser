"""
OCR Rule Builder

Builds OCR rules for document text extraction (PAN, GSTIN, Cheque, Aadhaar, etc.).
Handles OCR -> VERIFY rule chaining via postTriggerRuleIds.
"""

from typing import Dict, List, Optional, Any

try:
    from .base_builder import BaseRuleBuilder
    from ..models import IdGenerator, OCR_SCHEMA_IDS, OCR_TO_VERIFY_MAPPING
    from ..schema_lookup import RuleSchemaLookup
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from rule_builders.base_builder import BaseRuleBuilder
    from models import IdGenerator, OCR_SCHEMA_IDS, OCR_TO_VERIFY_MAPPING
    from schema_lookup import RuleSchemaLookup


class OcrRuleBuilder(BaseRuleBuilder):
    """
    Builds OCR rules for document text extraction.

    OCR rules extract text from uploaded document images and populate
    text fields with the extracted values.

    CRITICAL: OCR rules MUST have postTriggerRuleIds linking to VERIFY rules
    when the extracted value needs validation.
    """

    def __init__(
        self,
        id_generator: IdGenerator,
        schema_lookup: RuleSchemaLookup = None
    ):
        """
        Initialize the OCR rule builder.

        Args:
            id_generator: IdGenerator for sequential rule IDs
            schema_lookup: RuleSchemaLookup for querying schemas
        """
        super().__init__(id_generator)
        self.schema_lookup = schema_lookup

    def build(
        self,
        source_type: str,
        upload_field_id: int,
        output_field_id: int,
        post_trigger_ids: List[int] = None,
        additional_destination_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Build an OCR rule.

        Args:
            source_type: OCR source type (e.g., "PAN_IMAGE", "GSTIN_IMAGE")
            upload_field_id: ID of the file upload field (source)
            output_field_id: ID of the text field to populate (primary destination)
            post_trigger_ids: Rule IDs to trigger after OCR (e.g., VERIFY rule)
            additional_destination_ids: Additional destination field IDs

        Returns:
            Complete OCR rule dict
        """
        destination_ids = [output_field_id]
        if additional_destination_ids:
            destination_ids.extend(additional_destination_ids)

        rule = self.create_base_rule(
            "OCR",
            [upload_field_id],
            destination_ids,
            "SERVER"
        )

        rule.update({
            "sourceType": source_type,
            "postTriggerRuleIds": post_trigger_ids or []
        })

        return rule

    def build_pan_ocr(
        self,
        upload_field_id: int,
        pan_field_id: int,
        verify_rule_id: int = None
    ) -> Dict[str, Any]:
        """
        Build a PAN OCR rule.

        PAN OCR (schema ID 344) extracts:
        - panNo (ordinal 1) -> PAN field
        - name (ordinal 2)
        - fatherName (ordinal 3)
        - dob (ordinal 4)

        Args:
            upload_field_id: ID of the Upload PAN field
            pan_field_id: ID of the PAN text field
            verify_rule_id: ID of the PAN VERIFY rule to trigger

        Returns:
            PAN OCR rule dict
        """
        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build("PAN_IMAGE", upload_field_id, pan_field_id, post_triggers)

    def build_gstin_ocr(
        self,
        upload_field_id: int,
        gstin_field_id: int,
        verify_rule_id: int = None
    ) -> Dict[str, Any]:
        """
        Build a GSTIN OCR rule.

        GSTIN OCR (schema ID 347) extracts registration number and other fields.

        Args:
            upload_field_id: ID of the GSTIN IMAGE field
            gstin_field_id: ID of the GSTIN text field
            verify_rule_id: ID of the GSTIN VERIFY rule to trigger

        Returns:
            GSTIN OCR rule dict
        """
        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build("GSTIN_IMAGE", upload_field_id, gstin_field_id, post_triggers)

    def build_cheque_ocr(
        self,
        upload_field_id: int,
        destination_ids: List[int] = None,
        verify_rule_id: int = None
    ) -> Dict[str, Any]:
        """
        Build a Cheque OCR rule.

        Cheque OCR (schema ID 269) extracts:
        - bankName (ordinal 1)
        - ifscCode (ordinal 2)
        - beneficiaryName (ordinal 3)
        - accountNumber (ordinal 4)
        - address (ordinal 5)
        - micrCode (ordinal 6)
        - branch (ordinal 7)

        Args:
            upload_field_id: ID of the Cancelled Cheque Image field
            destination_ids: List of destination field IDs in ordinal order
            verify_rule_id: ID of the Bank VERIFY rule to trigger

        Returns:
            Cheque OCR rule dict
        """
        # If no destination_ids provided, use empty list with ordinal placeholders
        if not destination_ids:
            destination_ids = [-1] * 7

        rule = self.create_base_rule(
            "OCR",
            [upload_field_id],
            destination_ids,
            "SERVER"
        )

        rule.update({
            "sourceType": "CHEQUEE",
            "postTriggerRuleIds": [verify_rule_id] if verify_rule_id else []
        })

        return rule

    def build_aadhaar_back_ocr(
        self,
        upload_field_id: int,
        destination_ids: List[int] = None,
        conditional_value_id: int = None,
        conditional_values: List[str] = None
    ) -> Dict[str, Any]:
        """
        Build an Aadhaar Back OCR rule.

        Aadhaar Back OCR (schema ID 348) extracts address details:
        - aadharAddress1 (ordinal 1)
        - aadharAddress2 (ordinal 2)
        - aadharPin (ordinal 3)
        - aadharCity (ordinal 4)
        - aadharDist (ordinal 5)
        - aadharState (ordinal 6)
        - aadharFatherName (ordinal 7)
        - aadharCountry (ordinal 8)
        - aadharCoords (ordinal 9)

        Args:
            upload_field_id: ID of the Aadhaar Back Image field
            destination_ids: List of destination field IDs in ordinal order
            conditional_value_id: ID of the field controlling this rule's execution
            conditional_values: Values that trigger this rule

        Returns:
            Aadhaar Back OCR rule dict
        """
        if not destination_ids:
            destination_ids = [-1] * 9

        rule = self.create_base_rule(
            "OCR",
            [upload_field_id],
            destination_ids,
            "SERVER"
        )

        rule["sourceType"] = "AADHAR_BACK_IMAGE"

        # Add conditional execution if specified
        if conditional_value_id and conditional_values:
            rule["conditionalValueId"] = conditional_value_id
            rule["conditionalValues"] = conditional_values

        return rule

    def build_msme_ocr(
        self,
        upload_field_id: int,
        msme_field_id: int,
        additional_destination_ids: List[int] = None,
        verify_rule_id: int = None
    ) -> Dict[str, Any]:
        """
        Build a MSME OCR rule.

        MSME OCR (schema ID 214) extracts:
        - regNumber (ordinal 1)
        - name (ordinal 2)
        - type (ordinal 3)
        - address (ordinal 4)
        - category (ordinal 5)
        - dateOfIncorporation (ordinal 6)

        Args:
            upload_field_id: ID of the MSME Image field
            msme_field_id: ID of the MSME registration number field
            additional_destination_ids: Additional destination field IDs
            verify_rule_id: ID of the MSME VERIFY rule to trigger

        Returns:
            MSME OCR rule dict
        """
        destination_ids = [msme_field_id]
        if additional_destination_ids:
            destination_ids.extend(additional_destination_ids)

        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build("MSME", upload_field_id, msme_field_id, post_triggers, additional_destination_ids)

    def should_chain_to_verify(self, source_type: str) -> bool:
        """
        Check if this OCR type should chain to a VERIFY rule.

        Args:
            source_type: OCR source type

        Returns:
            True if should chain to VERIFY
        """
        verify_type = OCR_TO_VERIFY_MAPPING.get(source_type)
        return verify_type is not None

    def get_verify_source_type(self, ocr_source_type: str) -> Optional[str]:
        """
        Get the corresponding VERIFY source type for an OCR source type.

        Args:
            ocr_source_type: OCR source type

        Returns:
            VERIFY source type or None
        """
        return OCR_TO_VERIFY_MAPPING.get(ocr_source_type)
