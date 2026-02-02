"""
Field matcher module for matching field references to actual field IDs.

Uses exact matching with O(1) lookup and fuzzy matching as fallback.
"""

import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from .models import FieldInfo


@dataclass
class MatchResult:
    """Result of a field matching operation."""
    field_info: Optional[FieldInfo]
    match_score: float
    match_type: str  # "exact", "normalized", "fuzzy"
    original_query: str
    matched_name: Optional[str] = None


class FieldMatcher:
    """
    Matches field references from logic text to actual field IDs in schema.

    Uses multiple matching strategies:
    1. Exact match (O(1) lookup)
    2. Normalized match (lowercase, no spaces)
    3. Fuzzy match using RapidFuzz (80% threshold)
    """

    DEFAULT_FUZZY_THRESHOLD = 80.0  # 80% similarity

    def __init__(self, fields: Optional[List[FieldInfo]] = None):
        """
        Initialize the field matcher.

        Args:
            fields: List of FieldInfo objects to match against
        """
        self.fields: List[FieldInfo] = fields or []
        self._build_indexes()

    def set_fields(self, fields: List[FieldInfo]) -> None:
        """Set or update the fields to match against."""
        self.fields = fields
        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build lookup indexes for fast matching."""
        # Exact name lookup
        self.by_name: Dict[str, FieldInfo] = {}
        # Normalized name lookup (lowercase, no special chars)
        self.by_normalized: Dict[str, FieldInfo] = {}
        # Variable name lookup
        self.by_variable: Dict[str, FieldInfo] = {}
        # ID lookup
        self.by_id: Dict[int, FieldInfo] = {}
        # All names for fuzzy matching
        self.all_names: List[str] = []

        for field in self.fields:
            self.by_name[field.name] = field
            self.by_normalized[self._normalize(field.name)] = field
            self.by_variable[field.variable_name] = field
            self.by_id[field.id] = field
            self.all_names.append(field.name)

    def _normalize(self, name: str) -> str:
        """Normalize field name for comparison."""
        # Lowercase
        name = name.lower()
        # Remove common prefixes/suffixes
        name = re.sub(r'^(please\s+)?(select|choose|enter)\s+', '', name)
        # Remove special characters and extra spaces
        name = re.sub(r'[^\w\s]', '', name)
        name = ' '.join(name.split())
        return name.strip()

    def match(
        self,
        query: str,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD
    ) -> MatchResult:
        """
        Match a field reference to a field.

        Args:
            query: Field name/reference to match
            fuzzy_threshold: Minimum score for fuzzy match (0-100)

        Returns:
            MatchResult with field info and match details
        """
        if not query or not query.strip():
            return MatchResult(
                field_info=None,
                match_score=0.0,
                match_type="none",
                original_query=query
            )

        query = query.strip()

        # Try exact match first
        if query in self.by_name:
            return MatchResult(
                field_info=self.by_name[query],
                match_score=100.0,
                match_type="exact",
                original_query=query,
                matched_name=query
            )

        # Try normalized match
        normalized = self._normalize(query)
        if normalized in self.by_normalized:
            field = self.by_normalized[normalized]
            return MatchResult(
                field_info=field,
                match_score=95.0,
                match_type="normalized",
                original_query=query,
                matched_name=field.name
            )

        # Try variable name match
        if query in self.by_variable:
            field = self.by_variable[query]
            return MatchResult(
                field_info=field,
                match_score=100.0,
                match_type="variable",
                original_query=query,
                matched_name=field.name
            )

        # Try fuzzy match
        fuzzy_result = self._fuzzy_match(query, fuzzy_threshold)
        if fuzzy_result:
            return fuzzy_result

        # No match found
        return MatchResult(
            field_info=None,
            match_score=0.0,
            match_type="none",
            original_query=query
        )

    def _fuzzy_match(
        self,
        query: str,
        threshold: float
    ) -> Optional[MatchResult]:
        """Perform fuzzy matching using RapidFuzz."""
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            return None

        if not self.all_names:
            return None

        # Try token_sort_ratio for better handling of word order variations
        result = process.extractOne(
            query,
            self.all_names,
            scorer=fuzz.token_sort_ratio
        )

        if result and result[1] >= threshold:
            matched_name = result[0]
            score = result[1]
            field = self.by_name.get(matched_name)
            if field:
                return MatchResult(
                    field_info=field,
                    match_score=score,
                    match_type="fuzzy",
                    original_query=query,
                    matched_name=matched_name
                )

        return None

    def match_multiple(
        self,
        queries: List[str],
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD
    ) -> Dict[str, MatchResult]:
        """
        Match multiple field references.

        Args:
            queries: List of field names/references
            fuzzy_threshold: Minimum score for fuzzy match

        Returns:
            Dict mapping query to MatchResult
        """
        results = {}
        for query in queries:
            results[query] = self.match(query, fuzzy_threshold)
        return results

    def find_by_id(self, field_id: int) -> Optional[FieldInfo]:
        """Find field by ID."""
        return self.by_id.get(field_id)

    def find_by_variable(self, variable_name: str) -> Optional[FieldInfo]:
        """Find field by variable name."""
        return self.by_variable.get(variable_name)

    def get_all_fields(self) -> List[FieldInfo]:
        """Get all fields."""
        return self.fields

    def get_fields_in_panel(self, panel_name: str) -> List[FieldInfo]:
        """Get all fields in a specific panel."""
        return [f for f in self.fields if f.panel_name == panel_name]

    def get_nearby_fields(
        self,
        field_id: int,
        count: int = 10
    ) -> List[FieldInfo]:
        """
        Get fields near a given field (by form order).

        Useful for finding potential destination fields for rules.

        Args:
            field_id: Target field ID
            count: Number of nearby fields to return

        Returns:
            List of nearby FieldInfo objects
        """
        target = self.by_id.get(field_id)
        if not target:
            return []

        # Sort by form order
        sorted_fields = sorted(self.fields, key=lambda f: f.form_order)

        # Find target position
        target_idx = None
        for i, f in enumerate(sorted_fields):
            if f.id == field_id:
                target_idx = i
                break

        if target_idx is None:
            return []

        # Get surrounding fields
        start = max(0, target_idx - count // 2)
        end = min(len(sorted_fields), target_idx + count // 2 + 1)

        return sorted_fields[start:end]

    def search_by_pattern(self, pattern: str) -> List[FieldInfo]:
        """
        Search fields by regex pattern.

        Args:
            pattern: Regex pattern to match field names

        Returns:
            List of matching FieldInfo objects
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return []

        return [f for f in self.fields if regex.search(f.name)]


class PanelFieldMatcher(FieldMatcher):
    """
    Field matcher with panel-aware matching.

    Prioritizes fields within the same panel when matching.
    """

    def __init__(
        self,
        fields: Optional[List[FieldInfo]] = None,
        current_panel: Optional[str] = None
    ):
        super().__init__(fields)
        self.current_panel = current_panel

    def set_current_panel(self, panel_name: str) -> None:
        """Set the current panel context."""
        self.current_panel = panel_name

    def match(
        self,
        query: str,
        fuzzy_threshold: float = FieldMatcher.DEFAULT_FUZZY_THRESHOLD,
        prefer_same_panel: bool = True
    ) -> MatchResult:
        """
        Match with panel preference.

        Args:
            query: Field name/reference to match
            fuzzy_threshold: Minimum score for fuzzy match
            prefer_same_panel: If True, prefer fields in current panel

        Returns:
            MatchResult with field info
        """
        # First try standard match
        result = super().match(query, fuzzy_threshold)

        if not prefer_same_panel or not self.current_panel:
            return result

        if result.field_info:
            # Check if matched field is in same panel
            if result.field_info.panel_name == self.current_panel:
                return result

            # Try to find a same-panel match
            panel_fields = self.get_fields_in_panel(self.current_panel)
            panel_matcher = FieldMatcher(panel_fields)
            panel_result = panel_matcher.match(query, fuzzy_threshold)

            if panel_result.field_info and panel_result.match_score >= fuzzy_threshold:
                return panel_result

        return result

    def find_controlling_field(
        self,
        field_ref: str,
        target_field_id: int
    ) -> Optional[FieldInfo]:
        """
        Find the controlling field for a rule.

        Searches for a field that likely controls the target field.

        Args:
            field_ref: Field reference from logic text
            target_field_id: ID of the field being controlled

        Returns:
            FieldInfo of the controlling field, or None
        """
        # First try direct match
        result = self.match(field_ref)
        if result.field_info:
            return result.field_info

        # Try finding in nearby fields
        nearby = self.get_nearby_fields(target_field_id, 20)
        if nearby:
            local_matcher = FieldMatcher(nearby)
            result = local_matcher.match(field_ref)
            if result.field_info:
                return result.field_info

        return None


def fields_from_schema(schema: Dict) -> List[FieldInfo]:
    """
    Extract FieldInfo objects from a schema JSON.

    Args:
        schema: Schema dict with documentTypes and formFillMetadatas

    Returns:
        List of FieldInfo objects
    """
    fields = []

    # Navigate to formFillMetadatas
    doc_types = schema.get('template', {}).get('documentTypes', [])
    if not doc_types:
        doc_types = schema.get('documentTypes', [])

    current_panel = None

    for doc_type in doc_types:
        for meta in doc_type.get('formFillMetadatas', []):
            form_tag = meta.get('formTag', {})
            field_type = form_tag.get('type', 'UNKNOWN')

            # Track current panel
            if field_type == 'PANEL':
                current_panel = form_tag.get('name')
                continue

            field_info = FieldInfo(
                id=meta.get('id'),
                name=form_tag.get('name', ''),
                variable_name=meta.get('variableName', ''),
                field_type=field_type,
                panel_name=current_panel,
                mandatory=meta.get('mandatory', False),
                editable=meta.get('editable', True),
                visible=meta.get('visible', True),
                form_order=meta.get('formOrder', 0.0),
            )
            fields.append(field_info)

    return fields
