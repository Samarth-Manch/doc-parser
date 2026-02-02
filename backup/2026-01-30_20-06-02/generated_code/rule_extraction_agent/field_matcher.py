"""
Field Matcher - Match field references to actual field IDs.

Uses exact matching first, then falls back to fuzzy matching
with RapidFuzz library (80% threshold).
"""

import re
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher

from .models import FieldInfo


class FieldMatcher:
    """Match field name references to actual field IDs in schema."""

    # Similarity threshold for fuzzy matching (0.0 to 1.0)
    FUZZY_THRESHOLD = 0.80

    def __init__(self, fields: List[FieldInfo] = None):
        """
        Initialize field matcher.

        Args:
            fields: List of FieldInfo objects from schema
        """
        self.fields: List[FieldInfo] = fields or []
        self._exact_index: Dict[str, FieldInfo] = {}
        self._normalized_index: Dict[str, FieldInfo] = {}

        if fields:
            self._build_indexes()

    def set_fields(self, fields: List[FieldInfo]):
        """Set the field list and rebuild indexes."""
        self.fields = fields
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes for fast exact matching."""
        self._exact_index.clear()
        self._normalized_index.clear()

        for field in self.fields:
            # Exact name index
            self._exact_index[field.name] = field

            # Normalized name index (lowercase, no special chars)
            normalized = self._normalize_name(field.name)
            self._normalized_index[normalized] = field

            # Also index by variable name
            if field.variable_name:
                self._exact_index[field.variable_name] = field
                self._normalized_index[self._normalize_name(field.variable_name)] = field

    def _normalize_name(self, name: str) -> str:
        """Normalize field name for matching."""
        if not name:
            return ""
        # Lowercase, remove special chars, collapse spaces
        normalized = name.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def match_field(self, field_reference: str) -> Optional[FieldInfo]:
        """
        Find a field by name reference.

        Tries exact match first, then normalized match, then fuzzy match.

        Args:
            field_reference: Field name or reference from logic text

        Returns:
            FieldInfo if match found, None otherwise
        """
        if not field_reference:
            return None

        # 1. Try exact match
        if field_reference in self._exact_index:
            return self._exact_index[field_reference]

        # 2. Try normalized match
        normalized = self._normalize_name(field_reference)
        if normalized in self._normalized_index:
            return self._normalized_index[normalized]

        # 3. Try fuzzy match
        return self._fuzzy_match(field_reference)

    def match_field_id(self, field_reference: str) -> Optional[int]:
        """
        Find field ID by name reference.

        Args:
            field_reference: Field name or reference from logic text

        Returns:
            Field ID if match found, None otherwise
        """
        field = self.match_field(field_reference)
        return field.id if field else None

    def _fuzzy_match(self, field_reference: str) -> Optional[FieldInfo]:
        """
        Fuzzy match field reference to field names.

        Uses SequenceMatcher for similarity calculation.
        Falls back to token-based matching for partial matches.

        Args:
            field_reference: Field name to match

        Returns:
            FieldInfo if match found above threshold, None otherwise
        """
        if not field_reference:
            return None

        normalized_ref = self._normalize_name(field_reference)
        best_match: Optional[FieldInfo] = None
        best_score = 0.0

        for field in self.fields:
            # Compare with normalized field name
            normalized_name = self._normalize_name(field.name)

            # Calculate similarity
            score = self._calculate_similarity(normalized_ref, normalized_name)

            if score > best_score:
                best_score = score
                best_match = field

        # Return if above threshold
        if best_score >= self.FUZZY_THRESHOLD:
            return best_match

        # Try token-based matching as fallback
        return self._token_match(field_reference)

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1, s2).ratio()

    def _token_match(self, field_reference: str) -> Optional[FieldInfo]:
        """
        Token-based matching for partial field references.

        E.g., "GST option" matches "Please select GST option"

        Args:
            field_reference: Field name to match

        Returns:
            FieldInfo if token match found, None otherwise
        """
        ref_tokens = set(self._normalize_name(field_reference).split())
        if not ref_tokens:
            return None

        best_match: Optional[FieldInfo] = None
        best_overlap = 0

        for field in self.fields:
            name_tokens = set(self._normalize_name(field.name).split())

            # Calculate token overlap
            overlap = len(ref_tokens & name_tokens)

            # Require at least 2 tokens to match or all tokens if reference is short
            min_required = min(2, len(ref_tokens))
            if overlap >= min_required and overlap > best_overlap:
                best_overlap = overlap
                best_match = field

        return best_match

    def find_fields_by_partial_name(self, partial_name: str) -> List[FieldInfo]:
        """
        Find all fields containing the partial name.

        Args:
            partial_name: Partial field name to search

        Returns:
            List of matching FieldInfo objects
        """
        if not partial_name:
            return []

        normalized_partial = self._normalize_name(partial_name)
        matches = []

        for field in self.fields:
            normalized_name = self._normalize_name(field.name)
            if normalized_partial in normalized_name:
                matches.append(field)

        return matches

    def find_fields_by_type(self, field_type: str) -> List[FieldInfo]:
        """
        Find all fields of a specific type.

        Args:
            field_type: Field type to search (e.g., "FILE", "TEXT")

        Returns:
            List of matching FieldInfo objects
        """
        return [f for f in self.fields if f.field_type.upper() == field_type.upper()]

    def find_nearby_fields(
        self,
        field_id: int,
        count: int = 10,
        direction: str = "both"
    ) -> List[FieldInfo]:
        """
        Find fields near a given field by form order.

        Useful for finding destination fields for OCR/VERIFY rules.

        Args:
            field_id: ID of the reference field
            count: Number of nearby fields to return
            direction: "before", "after", or "both"

        Returns:
            List of nearby FieldInfo objects
        """
        # Find the reference field
        ref_field = None
        for field in self.fields:
            if field.id == field_id:
                ref_field = field
                break

        if not ref_field:
            return []

        # Sort by form order
        sorted_fields = sorted(self.fields, key=lambda f: f.form_order)

        # Find index of reference field
        ref_idx = -1
        for i, field in enumerate(sorted_fields):
            if field.id == field_id:
                ref_idx = i
                break

        if ref_idx == -1:
            return []

        # Get nearby fields
        result = []
        if direction in ["before", "both"]:
            start = max(0, ref_idx - count // 2)
            result.extend(sorted_fields[start:ref_idx])

        if direction in ["after", "both"]:
            end = min(len(sorted_fields), ref_idx + 1 + count // 2)
            result.extend(sorted_fields[ref_idx + 1:end])

        return result

    def find_fields_in_panel(self, panel_name: str) -> List[FieldInfo]:
        """
        Find all fields in a specific panel.

        Args:
            panel_name: Name of the panel

        Returns:
            List of FieldInfo objects in the panel
        """
        normalized_panel = self._normalize_name(panel_name)
        return [
            f for f in self.fields
            if self._normalize_name(f.panel_name) == normalized_panel
        ]

    def get_field_by_id(self, field_id: int) -> Optional[FieldInfo]:
        """Get field by ID."""
        for field in self.fields:
            if field.id == field_id:
                return field
        return None

    def match_destination_fields(
        self,
        schema_field_names: List[str],
        source_field_id: int
    ) -> Dict[str, int]:
        """
        Match schema destination field names to BUD field IDs.

        Uses nearby fields and fuzzy matching.

        Args:
            schema_field_names: List of field names from Rule-Schemas.json
            source_field_id: ID of the source field (for nearby context)

        Returns:
            Dict mapping schema field name -> BUD field ID
        """
        mappings = {}

        # Get nearby fields for context
        nearby = self.find_nearby_fields(source_field_id, count=30, direction="after")

        for schema_name in schema_field_names:
            # First try exact/fuzzy match in nearby fields
            for field in nearby:
                similarity = self._calculate_similarity(
                    self._normalize_name(schema_name),
                    self._normalize_name(field.name)
                )
                if similarity >= 0.7:
                    mappings[schema_name] = field.id
                    break

            # If not found, try global match
            if schema_name not in mappings:
                match = self.match_field(schema_name)
                if match:
                    mappings[schema_name] = match.id

        return mappings


def build_field_index_from_schema(schema_data: Dict) -> List[FieldInfo]:
    """
    Build list of FieldInfo from schema JSON.

    Args:
        schema_data: Schema JSON data with formFillMetadatas

    Returns:
        List of FieldInfo objects
    """
    fields = []

    doc_types = schema_data.get('template', {}).get('documentTypes', [])
    for doc_type in doc_types:
        metadatas = doc_type.get('formFillMetadatas', [])
        for meta in metadatas:
            form_tag = meta.get('formTag', {})
            field_info = FieldInfo(
                id=meta.get('id', 0),
                name=form_tag.get('name', ''),
                variable_name=meta.get('variableName', ''),
                field_type=form_tag.get('type', 'TEXT'),
                is_mandatory=meta.get('mandatory', False),
                form_order=meta.get('formOrder', 0.0),
            )
            fields.append(field_info)

    return fields


def build_field_index_from_parsed(parsed_fields: List) -> List[FieldInfo]:
    """
    Build list of FieldInfo from parsed BUD document fields.

    Args:
        parsed_fields: List of FieldDefinition objects from doc_parser

    Returns:
        List of FieldInfo objects
    """
    fields = []

    for i, field in enumerate(parsed_fields):
        # Generate a pseudo-ID based on index if not available
        field_id = getattr(field, 'id', i + 1000)

        # Generate variable name if not available
        var_name = getattr(field, 'variable_name', '')
        if not var_name:
            # Generate from name: "PAN Number" -> "__pan_number__"
            var_name = f"__{field.name.lower().replace(' ', '_')}__"

        field_info = FieldInfo(
            id=field_id,
            name=field.name,
            variable_name=var_name,
            field_type=field.field_type.value if hasattr(field.field_type, 'value') else str(field.field_type),
            is_mandatory=field.is_mandatory,
            logic=getattr(field, 'logic', ''),
            rules=getattr(field, 'rules', ''),
            panel_name=getattr(field, 'section', ''),
            form_order=float(i),
        )
        fields.append(field_info)

    return fields
