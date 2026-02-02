"""
Document Rule Builder - Builds DELETE_DOCUMENT, UNDELETE_DOCUMENT, and related rules.

These rules handle:
- Conditional document deletion
- Document restoration
- Document storage operations
"""

from typing import Dict, List, Optional
try:
    from .base_builder import BaseRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder


class DocumentRuleBuilder(BaseRuleBuilder):
    """Builds document operation rules."""

    def build(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "NOT_IN",
    ) -> Dict:
        """
        Build a DELETE_DOCUMENT rule (default implementation).

        Args:
            source_field_id: Controlling field ID
            destination_ids: Document field IDs to delete
            conditional_values: Values that trigger deletion
            condition: Condition operator

        Returns:
            Rule dictionary
        """
        return self.build_delete_document(source_field_id, destination_ids, conditional_values, condition)

    def build_delete_document(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "NOT_IN",
    ) -> Dict:
        """
        Build a DELETE_DOCUMENT rule.

        Args:
            source_field_id: Controlling field ID
            destination_ids: Document field IDs to delete
            conditional_values: Values that trigger deletion
            condition: Condition operator (usually "NOT_IN" to delete when not matching)

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="DELETE_DOCUMENT",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type="CLIENT",
            conditional_values=conditional_values,
            condition=condition,
        )

    def build_undelete_document(
        self,
        source_field_id: int,
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN",
    ) -> Dict:
        """
        Build an UNDELETE_DOCUMENT rule.

        Args:
            source_field_id: Controlling field ID
            destination_ids: Document field IDs to restore
            conditional_values: Values that trigger restoration
            condition: Condition operator (usually "IN" to restore when matching)

        Returns:
            Rule dictionary
        """
        return self._create_base_rule(
            action_type="UNDELETE_DOCUMENT",
            source_ids=[source_field_id],
            destination_ids=destination_ids,
            processing_type="CLIENT",
            conditional_values=conditional_values,
            condition=condition,
        )

    def build_document_visibility_pair(
        self,
        source_field_id: int,
        document_field_ids: List[int],
        conditional_values: List[str],
    ) -> List[Dict]:
        """
        Build a pair of DELETE/UNDELETE rules for conditional document visibility.

        When condition is met: UNDELETE (restore/show document)
        When condition is not met: DELETE (hide/remove document)

        Args:
            source_field_id: Controlling field ID
            document_field_ids: Document field IDs
            conditional_values: Values that show the document

        Returns:
            List of two rule dictionaries
        """
        return [
            self.build_undelete_document(
                source_field_id=source_field_id,
                destination_ids=document_field_ids,
                conditional_values=conditional_values,
                condition="IN",
            ),
            self.build_delete_document(
                source_field_id=source_field_id,
                destination_ids=document_field_ids,
                conditional_values=conditional_values,
                condition="NOT_IN",
            ),
        ]

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
        rule = self._create_base_rule(
            action_type="COPY_TO_DOCUMENT_STORAGE_ID",
            source_ids=[source_field_id],
            destination_ids=[],
            processing_type="CLIENT",
        )

        if conditional_values:
            rule["conditionalValues"] = conditional_values
            rule["condition"] = condition
            rule["conditionValueType"] = "TEXT"

        return rule
