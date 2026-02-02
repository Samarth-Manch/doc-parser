"""
Field Matcher - Match field references from logic text to actual field IDs.

Uses exact matching first, then fuzzy matching as fallback.
"""

import re
from typing import Dict, List, Optional, Tuple
try:
    from .models import FieldInfo
except ImportError:
    from models import FieldInfo


class FieldMatcher:
    """Matches field references to field IDs using exact and fuzzy matching."""

    def __init__(self, fields: List[Dict] = None, threshold: float = 0.8):
        """
        Initialize the field matcher.

        Args:
            fields: List of field dictionaries with 'id', 'name', 'variable_name', etc.
            threshold: Minimum similarity score (0-1) for fuzzy matching
        """
        self.threshold = threshold
        self.fields: List[Dict] = []
        self.by_name: Dict[str, Dict] = {}
        self.by_variable: Dict[str, Dict] = {}
        self.by_id: Dict[int, Dict] = {}

        if fields:
            self.load_fields(fields)

    def load_fields(self, fields: List[Dict]):
        """
        Load fields and build lookup indexes.

        Args:
            fields: List of field dictionaries
        """
        self.fields = fields
        self.by_name = {}
        self.by_variable = {}
        self.by_id = {}

        for field in fields:
            field_id = field.get('id')
            name = field.get('name', '')
            variable = field.get('variable_name', field.get('variableName', ''))

            if field_id:
                self.by_id[field_id] = field

            if name:
                # Store both original and normalized versions
                self.by_name[name.lower()] = field
                normalized = self._normalize_name(name)
                if normalized != name.lower():
                    self.by_name[normalized] = field

            if variable:
                self.by_variable[variable.lower()] = field

    def _normalize_name(self, name: str) -> str:
        """Normalize a field name for matching."""
        # Remove special characters, convert to lowercase
        normalized = re.sub(r'[^\w\s]', '', name.lower())
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def match_exact(self, field_ref: str) -> Optional[Dict]:
        """
        Try exact match for a field reference.

        Args:
            field_ref: Field name or variable name to match

        Returns:
            Matching field dict or None
        """
        ref_lower = field_ref.lower()

        # Try exact name match
        if ref_lower in self.by_name:
            return self.by_name[ref_lower]

        # Try normalized name match
        normalized = self._normalize_name(field_ref)
        if normalized in self.by_name:
            return self.by_name[normalized]

        # Try variable name match
        if ref_lower in self.by_variable:
            return self.by_variable[ref_lower]

        return None

    def match_fuzzy(self, field_ref: str) -> Optional[Tuple[Dict, float]]:
        """
        Try fuzzy match for a field reference.

        Args:
            field_ref: Field name to match

        Returns:
            Tuple of (matching field dict, score) or None
        """
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return None

        ref_lower = field_ref.lower()
        best_match = None
        best_score = 0

        for field in self.fields:
            name = field.get('name', '').lower()
            if not name:
                continue

            # Calculate similarity using token_sort_ratio for better partial matching
            score = fuzz.token_sort_ratio(ref_lower, name) / 100.0

            if score > best_score and score >= self.threshold:
                best_score = score
                best_match = field

        if best_match:
            return (best_match, best_score)
        return None

    def match(self, field_ref: str) -> Optional[Dict]:
        """
        Match a field reference using exact match first, then fuzzy.

        Args:
            field_ref: Field name or variable name to match

        Returns:
            Matching field dict or None
        """
        # Try exact match first
        result = self.match_exact(field_ref)
        if result:
            return result

        # Fall back to fuzzy match
        fuzzy_result = self.match_fuzzy(field_ref)
        if fuzzy_result:
            return fuzzy_result[0]

        return None

    def get_field_id(self, field_ref: str) -> Optional[int]:
        """
        Get field ID for a field reference.

        Args:
            field_ref: Field name or variable name

        Returns:
            Field ID or None
        """
        field = self.match(field_ref)
        if field:
            return field.get('id')
        return None

    def get_field_by_id(self, field_id: int) -> Optional[Dict]:
        """Get field by ID."""
        return self.by_id.get(field_id)

    def get_field_by_name(self, name: str) -> Optional[Dict]:
        """Get field by exact name (case-insensitive)."""
        return self.by_name.get(name.lower())

    def find_fields_by_pattern(self, pattern: str) -> List[Dict]:
        """
        Find all fields matching a regex pattern.

        Args:
            pattern: Regex pattern to match against field names

        Returns:
            List of matching field dicts
        """
        regex = re.compile(pattern, re.IGNORECASE)
        return [f for f in self.fields if regex.search(f.get('name', ''))]

    def find_fields_by_type(self, field_type: str) -> List[Dict]:
        """
        Find all fields of a specific type.

        Args:
            field_type: Field type (e.g., "FILE", "TEXT", "DROPDOWN")

        Returns:
            List of matching field dicts
        """
        field_type_upper = field_type.upper()
        return [
            f for f in self.fields
            if f.get('field_type', f.get('formTag', {}).get('type', '')).upper() == field_type_upper
        ]

    def find_fields_in_section(self, section_name: str) -> List[Dict]:
        """
        Find all fields in a specific section/panel.

        Args:
            section_name: Section or panel name

        Returns:
            List of matching field dicts
        """
        section_lower = section_name.lower()
        return [
            f for f in self.fields
            if f.get('section', '').lower() == section_lower
        ]

    def find_nearby_fields(self, field_id: int, count: int = 10) -> List[Dict]:
        """
        Find fields near a given field (by form order).

        Args:
            field_id: Reference field ID
            count: Number of fields to return (before and after)

        Returns:
            List of nearby field dicts
        """
        ref_field = self.by_id.get(field_id)
        if not ref_field:
            return []

        ref_order = ref_field.get('formOrder', ref_field.get('form_order', 0))

        # Sort fields by form order
        sorted_fields = sorted(
            self.fields,
            key=lambda f: f.get('formOrder', f.get('form_order', 0))
        )

        # Find index of reference field
        ref_index = None
        for i, f in enumerate(sorted_fields):
            if f.get('id') == field_id:
                ref_index = i
                break

        if ref_index is None:
            return []

        # Return fields before and after
        start = max(0, ref_index - count // 2)
        end = min(len(sorted_fields), ref_index + count // 2 + 1)

        return sorted_fields[start:end]

    def build_name_to_id_map(self) -> Dict[str, int]:
        """Build a mapping from field names to IDs."""
        return {
            f.get('name', ''): f.get('id')
            for f in self.fields
            if f.get('name') and f.get('id')
        }

    def get_all_field_names(self) -> List[str]:
        """Get list of all field names."""
        return [f.get('name', '') for f in self.fields if f.get('name')]
