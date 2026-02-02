"""
OCR Rule Builder - Builds OCR rules for document extraction.
"""

from typing import List, Optional
from .base_builder import BaseRuleBuilder
from ..models import GeneratedRule, IdGenerator
from ..schema_lookup import RuleSchemaLookup


class OcrRuleBuilder(BaseRuleBuilder):
    """Builds OCR rules (PAN_IMAGE, GSTIN_IMAGE, etc.)."""

    def __init__(self, id_generator: IdGenerator, schema_lookup: RuleSchemaLookup):
        """
        Initialize the builder.

        Args:
            id_generator: IdGenerator instance.
            schema_lookup: RuleSchemaLookup for schema queries.
        """
        super().__init__(id_generator)
        self.schema_lookup = schema_lookup

    def build(
        self,
        source_type: str,
        upload_field_id: int,
        output_field_id: int,
        post_trigger_ids: Optional[List[int]] = None
    ) -> GeneratedRule:
        """
        Build OCR rule.

        Args:
            source_type: OCR source type (e.g., "PAN_IMAGE", "GSTIN_IMAGE").
            upload_field_id: File upload field ID (source).
            output_field_id: Text field ID to populate (destination).
            post_trigger_ids: Rule IDs to trigger after OCR (e.g., VERIFY rule).

        Returns:
            GeneratedRule for OCR.
        """
        rule = self.create_base_rule(
            "OCR",
            [upload_field_id],
            [output_field_id],
            "SERVER"
        )

        rule.source_type = source_type
        rule.post_trigger_rule_ids = post_trigger_ids or []

        return rule

    def build_pan_ocr(
        self,
        upload_field_id: int,
        pan_field_id: int,
        verify_rule_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Build PAN OCR rule.

        Args:
            upload_field_id: Upload PAN field ID.
            pan_field_id: PAN text field ID.
            verify_rule_id: PAN VERIFY rule ID to trigger after.

        Returns:
            GeneratedRule for PAN OCR.
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="PAN_IMAGE",
            upload_field_id=upload_field_id,
            output_field_id=pan_field_id,
            post_trigger_ids=post_trigger
        )

    def build_gstin_ocr(
        self,
        upload_field_id: int,
        gstin_field_id: int,
        verify_rule_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Build GSTIN OCR rule.

        Args:
            upload_field_id: GSTIN IMAGE field ID.
            gstin_field_id: GSTIN text field ID.
            verify_rule_id: GSTIN VERIFY rule ID to trigger after.

        Returns:
            GeneratedRule for GSTIN OCR.
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="GSTIN_IMAGE",
            upload_field_id=upload_field_id,
            output_field_id=gstin_field_id,
            post_trigger_ids=post_trigger
        )

    def build_cheque_ocr(
        self,
        upload_field_id: int,
        output_field_id: int,
        verify_rule_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Build Cheque OCR rule.

        Args:
            upload_field_id: Cancelled Cheque Image field ID.
            output_field_id: IFSC or Account Number field ID.
            verify_rule_id: Bank VERIFY rule ID to trigger after.

        Returns:
            GeneratedRule for Cheque OCR.
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="CHEQUEE",
            upload_field_id=upload_field_id,
            output_field_id=output_field_id,
            post_trigger_ids=post_trigger
        )

    def build_aadhaar_front_ocr(
        self,
        upload_field_id: int,
        output_field_id: int
    ) -> GeneratedRule:
        """
        Build Aadhaar Front OCR rule.

        Args:
            upload_field_id: Aadhaar Front copy field ID.
            output_field_id: Output field ID.

        Returns:
            GeneratedRule for Aadhaar Front OCR.
        """
        return self.build(
            source_type="AADHAR_IMAGE",
            upload_field_id=upload_field_id,
            output_field_id=output_field_id,
            post_trigger_ids=None
        )

    def build_aadhaar_back_ocr(
        self,
        upload_field_id: int,
        output_field_id: int
    ) -> GeneratedRule:
        """
        Build Aadhaar Back OCR rule.

        Args:
            upload_field_id: Aadhaar Back Image field ID.
            output_field_id: Output field ID.

        Returns:
            GeneratedRule for Aadhaar Back OCR.
        """
        return self.build(
            source_type="AADHAR_BACK_IMAGE",
            upload_field_id=upload_field_id,
            output_field_id=output_field_id,
            post_trigger_ids=None
        )

    def build_msme_ocr(
        self,
        upload_field_id: int,
        msme_field_id: int,
        verify_rule_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Build MSME OCR rule.

        Args:
            upload_field_id: MSME Image field ID.
            msme_field_id: MSME Registration Number field ID.
            verify_rule_id: MSME VERIFY rule ID to trigger after.

        Returns:
            GeneratedRule for MSME OCR.
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="MSME",
            upload_field_id=upload_field_id,
            output_field_id=msme_field_id,
            post_trigger_ids=post_trigger
        )

    def build_cin_ocr(
        self,
        upload_field_id: int,
        cin_field_id: int,
        verify_rule_id: Optional[int] = None
    ) -> GeneratedRule:
        """
        Build CIN OCR rule.

        Args:
            upload_field_id: CIN Image field ID.
            cin_field_id: CIN text field ID.
            verify_rule_id: CIN VERIFY rule ID to trigger after.

        Returns:
            GeneratedRule for CIN OCR.
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="CIN",
            upload_field_id=upload_field_id,
            output_field_id=cin_field_id,
            post_trigger_ids=post_trigger
        )
