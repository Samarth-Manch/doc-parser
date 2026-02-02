"""
Field Matcher Module

Matches field references from logic text to actual field IDs in the schema.
Uses exact matching first, then fuzzy matching with RapidFuzz.
"""

import re
from typing import Dict, List, Optional, Tuple

try:
    from .models import FieldInfo
except ImportError:
    from models import FieldInfo


class FieldMatcher:
    """
    Matches field references from logic text to actual field IDs.

    Uses a two-stage matching approach:
    1. Exact match (O(1) lookup)
    2. Fuzzy match with RapidFuzz if no exact match (80% threshold)
    """

    def __init__(self, fields: List[Dict] = None):
        """
        Initialize the field matcher.

        Args:
            fields: List of field dicts with 'id', 'name', 'variable_name', etc.
        """
        self.fields: List[Dict] = fields or []
        self.by_name: Dict[str, Dict] = {}
        self.by_id: Dict[int, Dict] = {}
        self.by_variable: Dict[str, Dict] = {}
        self.normalized_names: Dict[str, Dict] = {}

        if fields:
            self._build_indexes()

        # Try to import rapidfuzz for fuzzy matching
        try:
            from rapidfuzz import fuzz, process
            self.fuzz = fuzz
            self.process = process
            self.has_rapidfuzz = True
        except ImportError:
            self.has_rapidfuzz = False

    def set_fields(self, fields: List[Dict]):
        """Set or update the field list."""
        self.fields = fields
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes for fast field matching."""
        self.by_name = {}
        self.by_id = {}
        self.by_variable = {}
        self.normalized_names = {}

        for field in self.fields:
            name = field.get('name', '')
            field_id = field.get('id')
            variable = field.get('variable_name', '')

            if name:
                self.by_name[name] = field
                normalized = self._normalize_name(name)
                self.normalized_names[normalized] = field

            if field_id:
                self.by_id[field_id] = field

            if variable:
                self.by_variable[variable] = field

    def _normalize_name(self, name: str) -> str:
        """Normalize a field name for matching."""
        # Remove special characters, convert to lowercase
        normalized = re.sub(r'[^a-z0-9\s]', '', name.lower())
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        return normalized

    def match_field(self, reference: str) -> Optional[Dict]:
        """
        Match a field reference to an actual field.

        Args:
            reference: Field name or partial reference from logic text

        Returns:
            Matching field dict or None
        """
        if not reference:
            return None

        # Stage 1: Exact match
        exact = self._exact_match(reference)
        if exact:
            return exact

        # Stage 2: Fuzzy match
        if self.has_rapidfuzz:
            fuzzy = self._fuzzy_match(reference)
            if fuzzy:
                return fuzzy

        return None

    def _exact_match(self, reference: str) -> Optional[Dict]:
        """Try exact matching against field names."""
        # Try direct name match
        if reference in self.by_name:
            return self.by_name[reference]

        # Try normalized match
        normalized = self._normalize_name(reference)
        if normalized in self.normalized_names:
            return self.normalized_names[normalized]

        # Try variable name match
        if reference in self.by_variable:
            return self.by_variable[reference]

        return None

    def _fuzzy_match(self, reference: str, threshold: int = 80) -> Optional[Dict]:
        """
        Try fuzzy matching with RapidFuzz.

        Args:
            reference: Field reference to match
            threshold: Minimum similarity score (0-100)

        Returns:
            Best matching field if score >= threshold, else None
        """
        if not self.has_rapidfuzz or not self.by_name:
            return None

        # Get list of field names
        names = list(self.by_name.keys())

        # Find best match
        result = self.process.extractOne(
            reference,
            names,
            scorer=self.fuzz.token_sort_ratio
        )

        if result and result[1] >= threshold:
            matched_name = result[0]
            return self.by_name[matched_name]

        return None

    def find_by_id(self, field_id: int) -> Optional[Dict]:
        """Find field by ID."""
        return self.by_id.get(field_id)

    def find_by_name(self, name: str) -> Optional[Dict]:
        """Find field by exact name."""
        return self.by_name.get(name)

    def find_fields_with_pattern(self, pattern: str) -> List[Dict]:
        """
        Find all fields whose names match a pattern.

        Args:
            pattern: Substring or regex pattern

        Returns:
            List of matching fields
        """
        matches = []
        pattern_lower = pattern.lower()

        for name, field in self.by_name.items():
            if pattern_lower in name.lower():
                matches.append(field)

        return matches

    def find_panel_fields(self, panel_name: str) -> List[Dict]:
        """
        Find all fields belonging to a specific panel.

        Args:
            panel_name: Name of the panel

        Returns:
            List of fields in the panel
        """
        matches = []
        for field in self.fields:
            field_panel = field.get('panel_name', '')
            if field_panel and panel_name.lower() in field_panel.lower():
                matches.append(field)
        return matches

    def find_fields_after(self, field_id: int, count: int = 10) -> List[Dict]:
        """
        Find fields that come after a given field (by form order).

        This is useful for "store in next fields" logic.

        Args:
            field_id: ID of the reference field
            count: Maximum number of fields to return

        Returns:
            List of following fields
        """
        ref_field = self.by_id.get(field_id)
        if not ref_field:
            return []

        ref_order = ref_field.get('form_order', 0)

        # Sort fields by form order and filter those after the reference
        following = [
            f for f in self.fields
            if f.get('form_order', 0) > ref_order
        ]

        following.sort(key=lambda f: f.get('form_order', 0))
        return following[:count]

    def get_field_info(self, field: Dict) -> FieldInfo:
        """Convert field dict to FieldInfo object."""
        return FieldInfo(
            id=field.get('id', 0),
            name=field.get('name', ''),
            variable_name=field.get('variable_name', ''),
            field_type=field.get('field_type', field.get('type', '')),
            logic=field.get('logic'),
            rules=field.get('rules'),
            panel_name=field.get('panel_name'),
            is_mandatory=field.get('mandatory', False),
            form_order=field.get('form_order', 0.0)
        )

    def build_field_id_map(self) -> Dict[str, int]:
        """
        Build a mapping of field names to field IDs.

        Returns:
            Dict mapping field name (lowercase) to field ID
        """
        return {
            name.lower(): field.get('id')
            for name, field in self.by_name.items()
            if field.get('id')
        }


class VisibilityGroupBuilder:
    """
    Builds groups of fields controlled by the same source field.

    This is used to consolidate visibility rules - instead of creating
    one rule per destination field, we create one rule with multiple
    destinations.
    """

    def __init__(self, field_matcher: FieldMatcher):
        """
        Initialize the visibility group builder.

        Args:
            field_matcher: FieldMatcher instance for field lookups
        """
        self.field_matcher = field_matcher
        self.groups: Dict[str, Dict] = {}  # source_field -> group info

    def add_destination(
        self,
        source_field_name: str,
        destination_field_name: str,
        conditional_value: str,
        action_type: str
    ):
        """
        Add a destination field to a visibility group.

        Args:
            source_field_name: Name of the controlling field
            destination_field_name: Name of the affected field
            conditional_value: Value that triggers the rule
            action_type: MAKE_VISIBLE, MAKE_INVISIBLE, etc.
        """
        # Create group key
        key = f"{source_field_name}|{action_type}|{conditional_value}"

        if key not in self.groups:
            source_field = self.field_matcher.match_field(source_field_name)
            self.groups[key] = {
                "source_field_name": source_field_name,
                "source_field_id": source_field.get('id') if source_field else None,
                "action_type": action_type,
                "conditional_value": conditional_value,
                "destination_ids": [],
                "destination_names": []
            }

        dest_field = self.field_matcher.match_field(destination_field_name)
        if dest_field and dest_field.get('id'):
            dest_id = dest_field.get('id')
            if dest_id not in self.groups[key]["destination_ids"]:
                self.groups[key]["destination_ids"].append(dest_id)
                self.groups[key]["destination_names"].append(destination_field_name)

    def get_consolidated_groups(self) -> List[Dict]:
        """
        Get all visibility groups ready for rule generation.

        Returns:
            List of group dicts with source_field_id, destination_ids, etc.
        """
        return list(self.groups.values())
