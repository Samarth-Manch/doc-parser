"""
Copy Rule Builder - Builds COPY_TO and related data transfer rules.

These rules handle:
- Copying values between fields
- Auto-populating fields from system values
- Document storage operations
"""

from typing import Dict, List, Optional
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


class CopyRuleBuilder(BaseRuleBuilder):
    """Builds COPY_TO and related data transfer rules."""

    def build(
        self,
        source_field_id: int,
        destination_ids: List[int],
        source_type: str = "FORM_FILL_METADATA",
        conditional_values: List[str] = None,
        condition: str = None,
    ) -> Dict:
        """
        Build a COPY_TO rule (default implementation).

        Args:
            source_field_id: Source field ID
            destination_ids: Destination field IDs
            source_type: Source type
            conditional_values: Values that trigger the copy
            condition: Condition operator

        Returns:
            Rule dictionary
        """
        return self.build_copy_to(source_field_id, destination_ids, source_type, conditional_values, condition)

    def build_copy_to(
        self,
        source_field_id: int,
        destination_ids: List[int],
        source_type: str = "FORM_FILL_METADATA",
        conditional_values: List[str] = None,
        condition: str = None,
    ) -> Dict:
        """
        Build a COPY_TO rule for copying values between fields.

        Args:
            source_field_id: Source field ID
            destination_ids: List of destination field IDs
            source_type: Source type (FORM_FILL_METADATA, CREATED_BY, etc.)
            conditional_values: Values that trigger the copy
            condition: Condition operator

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="COPY_TO",
            source_type=source_type,
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type="CLIENT",
            conditional_values=conditional_values,
            condition=condition,
        )

    def build_copy_created_by(
        self,
        field_id: int,
        destination_ids: List[int] = None,
    ) -> Dict:
        """
        Build a COPY_TO rule for copying created by information.

        Args:
            field_id: The field to copy to
            destination_ids: Additional destination fields

        Returns:
            Rule dictionary
        """
        dests = destination_ids or []
        if field_id not in dests:
            dests.insert(0, field_id)

        return self._create_base_rule(
            action_type="COPY_TO",
            source_type="CREATED_BY",
            source_ids=[field_id],
            destination_ids=dests,
            processing_type="CLIENT",
        )

    def build_copy_txnid(
        self,
        field_id: int,
    ) -> Dict:
        """
        Build a COPY_TXNID_TO_FORM_FILL rule for transaction ID.

        Args:
            field_id: Transaction ID field

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="COPY_TXNID_TO_FORM_FILL",
            source_ids=[field_id],
            destination_ids=[field_id],
            processing_type="CLIENT",
            conditional_values=["TXN"],
            condition="NOT_IN",
        )

    def build_copy_to_document_storage(
        self,
        source_field_id: int,
        conditional_values: List[str] = None,
        condition: str = "IN",
    ) -> Dict:
        """
        Build a COPY_TO_DOCUMENT_STORAGE_ID rule.

        Args:
            source_field_id: Source file field ID
            conditional_values: Values that trigger the copy
            condition: Condition operator

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="COPY_TO_DOCUMENT_STORAGE_ID",
            source_ids=[source_field_id],
            destination_ids=[],
            processing_type="CLIENT",
            conditional_values=conditional_values,
            condition=condition,
        )

    def build_concat(
        self,
        source_ids: List[int],
        destination_id: int,
        params: str = None,
    ) -> Dict:
        """
        Build a CONCAT rule for concatenating field values.

        Args:
            source_ids: Source field IDs to concatenate
            destination_id: Destination field ID
            params: Optional params for separator/format

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="CONCAT",
            source_ids=source_ids,
            destination_ids=[destination_id],
            processing_type="CLIENT",
            params=params,
        )

    def build_set_date(
        self,
        field_id: int,
        date_type: str = "CURRENT_DATE",
    ) -> Dict:
        """
        Build a SET_DATE rule for auto-filling date fields.

        Args:
            field_id: Date field ID
            date_type: Type of date to set (CURRENT_DATE, etc.)

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="SET_DATE",
            source_type=date_type,
            source_ids=[field_id],
            destination_ids=[field_id],
            processing_type="CLIENT",
        )
