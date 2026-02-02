"""
Field Matcher - Matches field references from logic text to actual field IDs in schema.
"""

import re
from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz, process
from .models import FieldInfo


class FieldMatcher:
    """Matches field references to actual field IDs using fuzzy matching."""

    def __init__(self, threshold: float = 80.0):
        """
        Initialize the field matcher.

        Args:
            threshold: Minimum similarity score (0-100) for fuzzy matching.
        """
        self.threshold = threshold
        self.fields_by_name: Dict[str, FieldInfo] = {}
        self.fields_by_id: Dict[int, FieldInfo] = {}
        self.fields_by_variable: Dict[str, FieldInfo] = {}
        self.field_names: List[str] = []

    def load_fields(self, fields: List[FieldInfo]):
        """Load fields into the matcher."""
        self.fields_by_name = {}
        self.fields_by_id = {}
        self.fields_by_variable = {}

        for field in fields:
            # Index by normalized name
            name_key = self._normalize_name(field.name)
            self.fields_by_name[name_key] = field

            # Also index by original name
            self.fields_by_name[field.name.lower()] = field

            # Index by ID
            self.fields_by_id[field.id] = field

            # Index by variable name
            if field.variable_name:
                self.fields_by_variable[field.variable_name.lower()] = field

        self.field_names = list(self.fields_by_name.keys())

    def load_from_schema(self, schema: Dict):
        """Load fields from a schema JSON."""
        fields = []

        # Extract formFillMetadatas from schema
        doc_types = schema.get('template', {}).get('documentTypes', [])
        for doc_type in doc_types:
            metadatas = doc_type.get('formFillMetadatas', [])
            for meta in metadatas:
                form_tag = meta.get('formTag', {})
                field = FieldInfo(
                    id=meta.get('id', 0),
                    name=form_tag.get('name', ''),
                    variable_name=meta.get('variableName', ''),
                    field_type=form_tag.get('type', ''),
                    is_mandatory=meta.get('mandatory', False),
                    logic=meta.get('logic'),
                    rules_text=meta.get('rules'),
                    form_order=meta.get('formOrder', 0.0)
                )
                fields.append(field)

        self.load_fields(fields)
        return fields

    def _normalize_name(self, name: str) -> str:
        """Normalize field name for matching."""
        # Convert to lowercase
        name = name.lower()

        # Remove common prefixes/suffixes
        name = re.sub(r'^(upload|select|enter|the|please)\s+', '', name)
        name = re.sub(r'\s+(field|number|code|id)$', '', name)

        # Normalize whitespace
        name = ' '.join(name.split())

        return name

    def match_field(self, field_ref: str) -> Optional[FieldInfo]:
        """
        Match a field reference to a field.

        Args:
            field_ref: Field reference from logic text.

        Returns:
            FieldInfo if match found, None otherwise.
        """
        if not field_ref:
            return None

        # Try exact match first
        ref_lower = field_ref.lower()
        if ref_lower in self.fields_by_name:
            return self.fields_by_name[ref_lower]

        # Try normalized match
        ref_normalized = self._normalize_name(field_ref)
        if ref_normalized in self.fields_by_name:
            return self.fields_by_name[ref_normalized]

        # Try variable name match
        if ref_lower in self.fields_by_variable:
            return self.fields_by_variable[ref_lower]

        # Try fuzzy match
        return self._fuzzy_match(field_ref)

    def _fuzzy_match(self, field_ref: str) -> Optional[FieldInfo]:
        """Use fuzzy matching to find the best match."""
        if not self.field_names:
            return None

        ref_normalized = self._normalize_name(field_ref)

        # Use rapidfuzz for efficient fuzzy matching
        result = process.extractOne(
            ref_normalized,
            self.field_names,
            scorer=fuzz.token_sort_ratio
        )

        if result and result[1] >= self.threshold:
            matched_name = result[0]
            return self.fields_by_name.get(matched_name)

        return None

    def match_field_id(self, field_ref: str) -> Optional[int]:
        """Match a field reference and return its ID."""
        field = self.match_field(field_ref)
        return field.id if field else None

    def get_field_by_id(self, field_id: int) -> Optional[FieldInfo]:
        """Get field by ID."""
        return self.fields_by_id.get(field_id)

    def get_field_by_name(self, name: str) -> Optional[FieldInfo]:
        """Get field by exact name."""
        name_lower = name.lower()
        return self.fields_by_name.get(name_lower)

    def find_related_fields(self, field_name: str, relationship: str) -> List[FieldInfo]:
        """
        Find fields related to a given field based on naming patterns.

        For example, "Upload PAN" -> "PAN" for OCR relationships.
        """
        related = []
        name_lower = field_name.lower()

        # Pattern: "Upload X" -> "X" (OCR source -> destination)
        if name_lower.startswith('upload '):
            target = name_lower.replace('upload ', '')
            for field_name_key, field in self.fields_by_name.items():
                if target in field_name_key and field.field_type in ['TEXT', 'DROPDOWN']:
                    related.append(field)

        # Pattern: "X Image" -> "X" (image field -> text field)
        if ' image' in name_lower:
            target = name_lower.replace(' image', '')
            for field_name_key, field in self.fields_by_name.items():
                if target in field_name_key and field.field_type in ['TEXT', 'DROPDOWN']:
                    related.append(field)

        return related

    def find_ocr_destination(self, upload_field_name: str) -> Optional[FieldInfo]:
        """
        Find the destination field for an OCR upload field.

        Examples:
            "Upload PAN" -> "PAN"
            "GSTIN IMAGE" -> "GSTIN"
            "Aadhaar Front copy" -> (Aadhaar related text fields)
        """
        name_lower = upload_field_name.lower()

        # Pattern: "Upload X" -> "X"
        if 'upload' in name_lower:
            target = name_lower.replace('upload ', '').replace('upload', '').strip()

            # Find matching text field
            for field_name_key, field in self.fields_by_name.items():
                if target in field_name_key and field.field_type in ['TEXT', 'DROPDOWN']:
                    # Avoid matching the same field
                    if 'upload' not in field_name_key and 'image' not in field_name_key:
                        return field

        # Pattern: "X IMAGE" or "X Image" -> "X"
        if 'image' in name_lower:
            target = name_lower.replace(' image', '').replace('image', '').strip()

            for field_name_key, field in self.fields_by_name.items():
                if target in field_name_key and field.field_type in ['TEXT', 'DROPDOWN']:
                    if 'image' not in field_name_key:
                        return field

        return None

    def find_verify_destinations(
        self,
        verify_field_name: str,
        intra_panel_refs: Optional[Dict] = None
    ) -> List[FieldInfo]:
        """
        Find destination fields for a VERIFY rule.

        Uses intra-panel references if available, otherwise uses naming patterns.
        """
        destinations = []

        # If we have intra-panel references, use them
        if intra_panel_refs:
            # Look for fields that reference this field as data source
            for panel in intra_panel_refs.get('panel_results', []):
                for ref in panel.get('intra_panel_references', []):
                    # Check different reference structures
                    if isinstance(ref, dict):
                        refs = ref.get('references', [])
                        for r in refs:
                            if r.get('reference_type') == 'data_source':
                                ref_field = r.get('referenced_field_name', '')
                                if verify_field_name.lower() in ref_field.lower():
                                    # This field depends on our verify field
                                    dep_field_name = ref.get('dependent_field', {}).get('field_name')
                                    if dep_field_name:
                                        field = self.match_field(dep_field_name)
                                        if field:
                                            destinations.append(field)

        return destinations

    def get_all_fields(self) -> List[FieldInfo]:
        """Get all loaded fields."""
        return list(self.fields_by_id.values())

    def get_field_ids_by_type(self, field_type: str) -> List[int]:
        """Get all field IDs of a specific type."""
        return [
            field.id for field in self.fields_by_id.values()
            if field.field_type == field_type
        ]
