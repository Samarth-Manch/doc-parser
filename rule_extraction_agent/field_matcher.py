"""Field matching using fuzzy string matching."""

import re
from typing import Dict, List, Optional, Tuple
from .models import FieldInfo


class FieldMatcher:
    """Match field references from logic text to actual field IDs in schema."""

    def __init__(self, fields: List[Dict] = None):
        self.fields: List[FieldInfo] = []
        self.by_name: Dict[str, FieldInfo] = {}
        self.by_id: Dict[int, FieldInfo] = {}
        self.by_variable: Dict[str, FieldInfo] = {}

        if fields:
            self.load_fields(fields)

    def load_fields(self, fields: List[Dict]):
        """Load fields from schema JSON."""
        self.fields = []
        self.by_name = {}
        self.by_id = {}
        self.by_variable = {}

        for field_data in fields:
            form_tag = field_data.get('formTag', {})

            field_info = FieldInfo(
                id=field_data.get('id', 0),
                name=form_tag.get('name', ''),
                variable_name=field_data.get('variableName', ''),
                field_type=form_tag.get('type', 'TEXT'),
                editable=field_data.get('editable', True),
                mandatory=field_data.get('mandatory', False),
                visible=field_data.get('visible', True),
            )

            self.fields.append(field_info)

            # Index by normalized name
            normalized_name = self._normalize(field_info.name)
            self.by_name[normalized_name] = field_info

            # Index by ID
            self.by_id[field_info.id] = field_info

            # Index by variable name
            if field_info.variable_name:
                self.by_variable[field_info.variable_name.lower()] = field_info

    def _normalize(self, text: str) -> str:
        """Normalize text for matching."""
        if not text:
            return ""
        # Lowercase and remove special characters
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text

    def find_by_name(self, name: str) -> Optional[FieldInfo]:
        """Find field by exact normalized name."""
        normalized = self._normalize(name)
        return self.by_name.get(normalized)

    def find_by_id(self, field_id: int) -> Optional[FieldInfo]:
        """Find field by ID."""
        return self.by_id.get(field_id)

    def find_by_variable(self, variable_name: str) -> Optional[FieldInfo]:
        """Find field by variable name."""
        return self.by_variable.get(variable_name.lower())

    def match_field(self, query: str, threshold: float = 0.6) -> Optional[FieldInfo]:
        """
        Match a field reference to actual field using fuzzy matching.

        Args:
            query: Field name to search for
            threshold: Minimum similarity score (0-1)

        Returns:
            Best matching FieldInfo or None
        """
        # Try exact match first
        exact = self.find_by_name(query)
        if exact:
            return exact

        # Try fuzzy matching
        best_match = None
        best_score = threshold

        query_normalized = self._normalize(query)
        query_tokens = set(query_normalized.split())

        for field in self.fields:
            field_normalized = self._normalize(field.name)
            field_tokens = set(field_normalized.split())

            # Token-based similarity
            score = self._token_similarity(query_tokens, field_tokens)

            if score > best_score:
                best_score = score
                best_match = field

        return best_match

    def _token_similarity(self, tokens1: set, tokens2: set) -> float:
        """Calculate token-based similarity."""
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def find_field_by_pattern(self, pattern: str) -> List[FieldInfo]:
        """Find fields matching a regex pattern."""
        matches = []
        regex = re.compile(pattern, re.IGNORECASE)

        for field in self.fields:
            if regex.search(field.name):
                matches.append(field)

        return matches

    def find_fields_by_type(self, field_type: str) -> List[FieldInfo]:
        """Find all fields of a given type."""
        return [f for f in self.fields if f.field_type == field_type]

    def find_related_fields(self, base_name: str) -> List[FieldInfo]:
        """
        Find fields related to a base name.

        Example: "Upload PAN" -> finds "PAN", "PAN Type", "PAN Status", etc.
        """
        # Extract the key term from base name
        # Remove common prefixes like "Upload", "Get", "Validate"
        key_terms = re.sub(r'^(upload|get|validate|verify)\s+', '', base_name, flags=re.I)
        key_terms = self._normalize(key_terms)

        related = []
        for field in self.fields:
            field_normalized = self._normalize(field.name)

            # Check if key terms appear in field name
            if key_terms in field_normalized or field_normalized in key_terms:
                related.append(field)

        return related

    def find_ocr_target(self, upload_field: FieldInfo) -> Optional[FieldInfo]:
        """
        Find the target field for an OCR upload field.

        Example: "Upload PAN" -> "PAN"
        """
        # Pattern: "Upload X" -> find field "X"
        match = re.match(r'^upload\s+(.+)$', upload_field.name, re.I)
        if match:
            target_name = match.group(1).strip()

            # Try exact match
            target = self.match_field(target_name, threshold=0.7)
            if target and target.field_type in ['TEXT', 'DROPDOWN']:
                return target

            # Try finding by pattern
            pattern = re.escape(target_name).replace(r'\ ', r'\s*')
            matches = self.find_field_by_pattern(f'^{pattern}$')
            for m in matches:
                if m.field_type in ['TEXT', 'DROPDOWN'] and m.id != upload_field.id:
                    return m

        return None

    def find_verify_destinations(
        self,
        source_field: FieldInfo,
        schema_dest_names: List[str]
    ) -> Dict[str, int]:
        """
        Find destination fields for a VERIFY rule based on schema field names.

        Args:
            source_field: The source field being verified
            schema_dest_names: List of destination field names from schema

        Returns:
            Dict mapping schema field names to BUD field IDs
        """
        mappings = {}

        # Get base name from source field
        base_name = source_field.name.lower()

        for schema_name in schema_dest_names:
            schema_lower = schema_name.lower()

            # Try different matching strategies
            candidates = []

            # Strategy 1: Direct match with schema name
            direct = self.match_field(schema_name, threshold=0.6)
            if direct:
                candidates.append((direct, 0.9))

            # Strategy 2: Prefix with source field name
            combined = f"{base_name} {schema_lower}"
            combined_match = self.match_field(combined, threshold=0.6)
            if combined_match:
                candidates.append((combined_match, 0.8))

            # Strategy 3: Look for fields containing both base name and schema term
            for field in self.fields:
                field_lower = field.name.lower()
                if base_name in field_lower and any(
                    term in field_lower for term in schema_lower.split()
                ):
                    candidates.append((field, 0.7))

            # Select best candidate
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                mappings[schema_name] = candidates[0][0].id

        return mappings

    def get_all_fields(self) -> List[FieldInfo]:
        """Get all loaded fields."""
        return self.fields

    def get_panel_fields(self, panel_name: str) -> List[FieldInfo]:
        """Get all fields in a specific panel."""
        return [f for f in self.fields if f.panel_name == panel_name]
