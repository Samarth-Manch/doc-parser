"""OCR rule builder for document extraction rules."""

from typing import Dict, List, Optional
from .base_builder import BaseRuleBuilder
from ..schema_lookup import RuleSchemaLookup, OCR_SCHEMAS, OCR_VERIFY_CHAINS


class OcrRuleBuilder(BaseRuleBuilder):
    """Builder for OCR rules (PAN_IMAGE, GSTIN_IMAGE, etc.)."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        super().__init__()
        self.schema_lookup = schema_lookup

    def build(
        self,
        source_type: str,
        upload_field_id: int,
        destination_field_ids: List[int],
        post_trigger_ids: List[int] = None
    ) -> Optional[Dict]:
        """
        Build OCR rule.

        Args:
            source_type: OCR source type (e.g., PAN_IMAGE, GSTIN_IMAGE)
            upload_field_id: File upload field ID (source)
            destination_field_ids: Field IDs to populate (destinations)
            post_trigger_ids: Rule IDs to trigger after OCR

        Returns:
            OCR rule dict or None if schema not found
        """
        schema = self.schema_lookup.find_by_action_and_source("OCR", source_type)
        if not schema:
            # Still create rule even without schema
            pass

        rule = self.create_base_rule(
            action_type="OCR",
            source_ids=[upload_field_id],
            destination_ids=destination_field_ids,
            processing_type="SERVER"
        )

        rule["sourceType"] = source_type

        if post_trigger_ids:
            rule["postTriggerRuleIds"] = post_trigger_ids

        return rule

    def build_pan_ocr(
        self,
        upload_field_id: int,
        pan_text_field_id: int,
        verify_rule_id: int = None
    ) -> Dict:
        """
        Build PAN OCR rule.

        Args:
            upload_field_id: Upload PAN field ID
            pan_text_field_id: PAN text field ID
            verify_rule_id: PAN VERIFY rule ID to chain to

        Returns:
            PAN OCR rule dict
        """
        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="PAN_IMAGE",
            upload_field_id=upload_field_id,
            destination_field_ids=[pan_text_field_id],
            post_trigger_ids=post_triggers
        )

    def build_gstin_ocr(
        self,
        upload_field_id: int,
        gstin_text_field_id: int,
        verify_rule_id: int = None
    ) -> Dict:
        """
        Build GSTIN OCR rule.

        Args:
            upload_field_id: Upload GSTIN field ID
            gstin_text_field_id: GSTIN text field ID
            verify_rule_id: GSTIN VERIFY rule ID to chain to

        Returns:
            GSTIN OCR rule dict
        """
        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="GSTIN_IMAGE",
            upload_field_id=upload_field_id,
            destination_field_ids=[gstin_text_field_id],
            post_trigger_ids=post_triggers
        )

    def build_aadhaar_front_ocr(
        self,
        upload_field_id: int,
        destination_field_ids: List[int]
    ) -> Dict:
        """
        Build Aadhaar Front OCR rule.

        NOTE: No VERIFY chain for Aadhaar.

        Args:
            upload_field_id: Upload Aadhaar Front field ID
            destination_field_ids: Destination field IDs

        Returns:
            Aadhaar Front OCR rule dict
        """
        return self.build(
            source_type="AADHAR_IMAGE",
            upload_field_id=upload_field_id,
            destination_field_ids=destination_field_ids,
            post_trigger_ids=[]  # No VERIFY chain
        )

    def build_aadhaar_back_ocr(
        self,
        upload_field_id: int,
        destination_field_ids: List[int]
    ) -> Dict:
        """
        Build Aadhaar Back OCR rule.

        NOTE: No VERIFY chain for Aadhaar.

        Args:
            upload_field_id: Upload Aadhaar Back field ID
            destination_field_ids: Destination field IDs

        Returns:
            Aadhaar Back OCR rule dict
        """
        return self.build(
            source_type="AADHAR_BACK_IMAGE",
            upload_field_id=upload_field_id,
            destination_field_ids=destination_field_ids,
            post_trigger_ids=[]  # No VERIFY chain
        )

    def build_cheque_ocr(
        self,
        upload_field_id: int,
        destination_field_ids: List[int],
        verify_rule_id: int = None
    ) -> Dict:
        """
        Build Cheque OCR rule.

        Args:
            upload_field_id: Cancelled Cheque upload field ID
            destination_field_ids: Bank details field IDs
            verify_rule_id: Bank VERIFY rule ID to chain to

        Returns:
            Cheque OCR rule dict
        """
        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="CHEQUEE",
            upload_field_id=upload_field_id,
            destination_field_ids=destination_field_ids,
            post_trigger_ids=post_triggers
        )

    def build_msme_ocr(
        self,
        upload_field_id: int,
        msme_text_field_id: int,
        verify_rule_id: int = None
    ) -> Dict:
        """
        Build MSME OCR rule.

        Args:
            upload_field_id: Upload MSME field ID
            msme_text_field_id: MSME number field ID
            verify_rule_id: MSME VERIFY rule ID to chain to

        Returns:
            MSME OCR rule dict
        """
        post_triggers = [verify_rule_id] if verify_rule_id else []
        return self.build(
            source_type="MSME",
            upload_field_id=upload_field_id,
            destination_field_ids=[msme_text_field_id],
            post_trigger_ids=post_triggers
        )

    def get_verify_source_type(self, ocr_source_type: str) -> Optional[str]:
        """
        Get the corresponding VERIFY source type for an OCR source type.

        Args:
            ocr_source_type: OCR source type (e.g., PAN_IMAGE)

        Returns:
            VERIFY source type (e.g., PAN_NUMBER) or None
        """
        return OCR_VERIFY_CHAINS.get(ocr_source_type)

    def needs_verify_chain(self, ocr_source_type: str) -> bool:
        """
        Check if an OCR source type needs a VERIFY chain.

        Args:
            ocr_source_type: OCR source type

        Returns:
            True if VERIFY chain is needed
        """
        verify_type = OCR_VERIFY_CHAINS.get(ocr_source_type)
        return verify_type is not None
