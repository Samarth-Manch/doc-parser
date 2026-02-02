"""
OCR Rule Builder - Builds OCR rules for extracting data from images.
"""

from typing import Dict, List, Optional
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


# Source type mappings for OCR
OCR_SOURCE_TYPES = {
    "PAN": "PAN_IMAGE",
    "GSTIN": "GSTIN_IMAGE",
    "AADHAAR_FRONT": "AADHAR_IMAGE",
    "AADHAAR_BACK": "AADHAR_BACK_IMAGE",
    "AADHAAR": "AADHAR_IMAGE",  # Alias
    "CHEQUE": "CHEQUEE",
    "MSME": "MSME",
    "CIN": "CIN",
    "TAN": "TAN",
}


class OcrRuleBuilder(BaseRuleBuilder):
    """Builds OCR rules for document image processing."""

    def __init__(self, schema_lookup=None):
        """
        Initialize with optional schema lookup.

        Args:
            schema_lookup: RuleSchemaLookup instance for schema info
        """
        self.schema_lookup = schema_lookup

    def build(
        self,
        doc_type: str,
        upload_field_id: int,
        destination_ids: List[int],
        post_trigger_rule_ids: List[int] = None,
        conditional_value_id: int = None,
        conditional_values: List[str] = None,
        condition: str = "IN",
        params: str = None,
    ) -> Dict:
        """
        Build an OCR rule.

        Args:
            doc_type: Document type (PAN, GSTIN, AADHAAR_FRONT, AADHAAR_BACK, CHEQUE, etc.)
            upload_field_id: ID of the file upload field (source)
            destination_ids: List of field IDs to populate with OCR results
            post_trigger_rule_ids: Rule IDs to trigger after OCR (e.g., VERIFY rule)
            conditional_value_id: Field ID for conditional value check
            conditional_values: Values that enable this OCR rule
            condition: Condition operator
            params: Optional JSON params string

        Returns:
            Rule dictionary
        """
        source_type = OCR_SOURCE_TYPES.get(doc_type.upper())
        if not source_type:
            raise ValueError(f"Unknown document type for OCR: {doc_type}")

        rule = self._create_base_rule(
            action_type="OCR",
            source_type=source_type,
            source_ids=[upload_field_id],
            destination_ids=destination_ids,
            processing_type="SERVER",
            post_trigger_rule_ids=post_trigger_rule_ids,
            conditional_values=conditional_values,
            condition=condition,
            params=params,
        )

        if conditional_value_id:
            rule["conditionalValueId"] = conditional_value_id

        return rule

    def build_pan_ocr(
        self,
        upload_field_id: int,
        pan_field_id: int,
        verify_rule_id: int = None,
    ) -> Dict:
        """
        Build a PAN OCR rule.

        Args:
            upload_field_id: Upload PAN image field ID
            pan_field_id: PAN text field ID (destination)
            verify_rule_id: PAN VERIFY rule ID to trigger after OCR

        Returns:
            Rule dictionary
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []

        return self.build(
            doc_type="PAN",
            upload_field_id=upload_field_id,
            destination_ids=[pan_field_id],
            post_trigger_rule_ids=post_trigger,
        )

    def build_gstin_ocr(
        self,
        upload_field_id: int,
        gstin_field_id: int,
        verify_rule_id: int = None,
    ) -> Dict:
        """
        Build a GSTIN OCR rule.

        Args:
            upload_field_id: Upload GSTIN image field ID
            gstin_field_id: GSTIN text field ID (destination)
            verify_rule_id: GSTIN VERIFY rule ID to trigger after OCR

        Returns:
            Rule dictionary
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []

        return self.build(
            doc_type="GSTIN",
            upload_field_id=upload_field_id,
            destination_ids=[gstin_field_id],
            post_trigger_rule_ids=post_trigger,
        )

    def build_cheque_ocr(
        self,
        upload_field_id: int,
        ifsc_field_id: int = None,
        account_number_field_id: int = None,
        bank_verify_rule_id: int = None,
    ) -> Dict:
        """
        Build a Cheque OCR rule.

        Cheque OCR extracts:
        - ordinal 1: Account holder name (usually not mapped)
        - ordinal 2: IFSC Code
        - ordinal 3: Bank name (usually not mapped)
        - ordinal 4: Account Number

        Args:
            upload_field_id: Cancelled cheque image field ID
            ifsc_field_id: IFSC code field ID (ordinal 2)
            account_number_field_id: Account number field ID (ordinal 4)
            bank_verify_rule_id: Bank VERIFY rule ID to trigger after OCR

        Returns:
            Rule dictionary
        """
        # Build ordinal-indexed destination array
        destination_ids = [-1, -1, -1, -1]  # 4 ordinals

        if ifsc_field_id:
            destination_ids[1] = ifsc_field_id  # ordinal 2 -> index 1
        if account_number_field_id:
            destination_ids[3] = account_number_field_id  # ordinal 4 -> index 3

        post_trigger = [bank_verify_rule_id] if bank_verify_rule_id else []

        return self.build(
            doc_type="CHEQUE",
            upload_field_id=upload_field_id,
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger,
        )

    def build_aadhaar_front_ocr(
        self,
        upload_field_id: int,
        destination_ids: List[int],
        conditional_value_id: int = None,
        conditional_values: List[str] = None,
        unmask_aadhaar: bool = False,
    ) -> Dict:
        """
        Build an Aadhaar Front OCR rule.

        Args:
            upload_field_id: Aadhaar front image field ID
            destination_ids: Field IDs to populate (name, DOB, etc.)
            conditional_value_id: Field ID for conditional check
            conditional_values: Values that enable this OCR
            unmask_aadhaar: Whether to unmask Aadhaar number

        Returns:
            Rule dictionary
        """
        params = None
        if unmask_aadhaar:
            params = '{"paramMap":{"unMaskAadhaarNumberInImage":"true"}}'
        else:
            params = '{"paramMap":{"unMaskAadhaarNumberInImage":"false"}}'

        return self.build(
            doc_type="AADHAAR_FRONT",
            upload_field_id=upload_field_id,
            destination_ids=destination_ids,
            conditional_value_id=conditional_value_id,
            conditional_values=conditional_values,
            params=params,
        )

    def build_aadhaar_back_ocr(
        self,
        upload_field_id: int,
        destination_ids: List[int],
        conditional_value_id: int = None,
        conditional_values: List[str] = None,
        unmask_aadhaar: bool = False,
    ) -> Dict:
        """
        Build an Aadhaar Back OCR rule.

        Aadhaar Back OCR extracts address fields:
        - ordinal 1: House number (usually not mapped)
        - ordinal 2: Landmark (usually not mapped)
        - ordinal 3: Street
        - ordinal 4: Street 1
        - ordinal 5: Street 2
        - ordinal 6: Street 3
        - ordinal 7: District (usually not mapped)
        - ordinal 8: Postal Code

        Args:
            upload_field_id: Aadhaar back image field ID
            destination_ids: Field IDs to populate (already ordinal-indexed)
            conditional_value_id: Field ID for conditional check
            conditional_values: Values that enable this OCR
            unmask_aadhaar: Whether to unmask Aadhaar number

        Returns:
            Rule dictionary
        """
        params = None
        if not unmask_aadhaar:
            params = '{"paramMap":{"unMaskAadhaarNumberInImage":"false"}}'

        return self.build(
            doc_type="AADHAAR_BACK",
            upload_field_id=upload_field_id,
            destination_ids=destination_ids,
            conditional_value_id=conditional_value_id,
            conditional_values=conditional_values,
            params=params,
        )

    def build_msme_ocr(
        self,
        upload_field_id: int,
        destination_ids: List[int],
        verify_rule_id: int = None,
    ) -> Dict:
        """
        Build an MSME OCR rule.

        Args:
            upload_field_id: MSME certificate image field ID
            destination_ids: Field IDs to populate
            verify_rule_id: MSME VERIFY rule ID to trigger after OCR

        Returns:
            Rule dictionary
        """
        post_trigger = [verify_rule_id] if verify_rule_id else []

        return self.build(
            doc_type="MSME",
            upload_field_id=upload_field_id,
            destination_ids=destination_ids,
            post_trigger_rule_ids=post_trigger,
        )

    def build_cin_ocr(
        self,
        upload_field_id: int,
        cin_field_id: int,
    ) -> Dict:
        """
        Build a CIN OCR rule.

        Args:
            upload_field_id: CIN certificate image field ID
            cin_field_id: CIN text field ID

        Returns:
            Rule dictionary
        """
        return self.build(
            doc_type="CIN",
            upload_field_id=upload_field_id,
            destination_ids=[cin_field_id],
        )
