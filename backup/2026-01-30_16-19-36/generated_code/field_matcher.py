"""
Field matcher using fuzzy string matching to map field references to field IDs.
"""

from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process

try:
    from .models import FieldInfo
except ImportError:
    from models import FieldInfo


class FieldMatcher:
    """Match field references from logic text to actual field IDs in schema."""

    def __init__(self, schema: Dict):
        """
        Initialize field matcher with schema.

        Args:
            schema: Full schema JSON from vendor_creation_schema.json
        """
        self.schema = schema
        self.field_index = self._build_field_index()

    def _build_field_index(self) -> Dict[str, FieldInfo]:
        """Build index of all fields for fast lookup."""
        index = {}

        # Navigate schema structure
        template = self.schema.get('template', {})
        doc_types = template.get('documentTypes', [])

        for doc_type in doc_types:
            metadata_list = doc_type.get('formFillMetadatas', [])

            for metadata in metadata_list:
                form_tag = metadata.get('formTag', {})
                field_name = form_tag.get('name', '')
                field_type = form_tag.get('type', '')
                field_id = metadata.get('id')
                variable_name = metadata.get('variableName', '')

                if field_name and field_id:
                    field_info = FieldInfo(
                        field_id=field_id,
                        field_name=field_name,
                        variable_name=variable_name,
                        field_type=field_type
                    )

                    # Index by field name (lowercase)
                    index[field_name.lower()] = field_info

                    # Also index by variable name
                    if variable_name:
                        index[variable_name.lower()] = field_info

        return index

    def match_field(
        self,
        field_reference: str,
        threshold: int = 80
    ) -> Optional[FieldInfo]:
        """
        Match a field reference to a field in the schema.

        Args:
            field_reference: Field name or reference from logic text
            threshold: Minimum similarity score (0-100)

        Returns:
            FieldInfo if match found, None otherwise
        """
        if not field_reference:
            return None

        field_ref_lower = field_reference.lower().strip()

        # Exact match first
        if field_ref_lower in self.field_index:
            return self.field_index[field_ref_lower]

        # Fuzzy match
        field_names = list(self.field_index.keys())
        result = process.extractOne(
            field_ref_lower,
            field_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold
        )

        if result:
            matched_name, score, _ = result
            return self.field_index[matched_name]

        return None

    def match_multiple_fields(
        self,
        field_references: List[str],
        threshold: int = 80
    ) -> List[FieldInfo]:
        """
        Match multiple field references.

        Args:
            field_references: List of field names/references
            threshold: Minimum similarity score

        Returns:
            List of matched FieldInfo objects
        """
        matched_fields = []

        for field_ref in field_references:
            field_info = self.match_field(field_ref, threshold)
            if field_info and field_info not in matched_fields:
                matched_fields.append(field_info)

        return matched_fields

    def get_field_by_id(self, field_id: int) -> Optional[FieldInfo]:
        """Get field info by field ID."""
        for field_info in self.field_index.values():
            if field_info.field_id == field_id:
                return field_info
        return None

    def get_all_fields(self) -> List[FieldInfo]:
        """Get all fields in the schema."""
        # Remove duplicates
        seen_ids = set()
        unique_fields = []

        for field_info in self.field_index.values():
            if field_info.field_id not in seen_ids:
                seen_ids.add(field_info.field_id)
                unique_fields.append(field_info)

        return unique_fields

    def search_fields(self, query: str, limit: int = 10) -> List[Tuple[FieldInfo, float]]:
        """
        Search for fields matching query.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of (FieldInfo, score) tuples
        """
        query_lower = query.lower().strip()
        field_names = list(self.field_index.keys())

        results = process.extract(
            query_lower,
            field_names,
            scorer=fuzz.token_sort_ratio,
            limit=limit
        )

        matched = []
        for name, score, _ in results:
            field_info = self.field_index[name]
            matched.append((field_info, score))

        return matched
