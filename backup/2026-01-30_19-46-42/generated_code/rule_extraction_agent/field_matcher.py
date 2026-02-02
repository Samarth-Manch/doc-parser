"""
Field Matcher - Match field references from logic text to actual field IDs.

Uses exact matching first, then fuzzy matching for flexible name matching.
"""

import re
from typing import Dict, List, Optional, Tuple
from .models import FieldInfo

# Try to import rapidfuzz for fuzzy matching
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class FieldMatcher:
    """Match field references to actual field IDs."""

    def __init__(self, fields: Optional[List[FieldInfo]] = None, fuzzy_threshold: float = 80.0):
        """
        Initialize the field matcher.

        Args:
            fields: List of FieldInfo objects to match against.
            fuzzy_threshold: Minimum fuzzy match score (0-100).
        """
        self.fields = fields or []
        self.fuzzy_threshold = fuzzy_threshold

        # Build indexes
        self._by_name: Dict[str, FieldInfo] = {}
        self._by_name_lower: Dict[str, FieldInfo] = {}
        self._by_variable: Dict[str, FieldInfo] = {}
        self._by_id: Dict[int, FieldInfo] = {}

        if fields:
            self._build_indexes(fields)

    def _build_indexes(self, fields: List[FieldInfo]):
        """Build lookup indexes."""
        for field in fields:
            self._by_name[field.name] = field
            self._by_name_lower[field.name.lower()] = field
            self._by_id[field.id] = field
            if field.variable_name:
                self._by_variable[field.variable_name] = field
                # Also index without underscores
                clean_var = field.variable_name.strip("_")
                self._by_variable[clean_var] = field

    def set_fields(self, fields: List[FieldInfo]):
        """Set fields to match against."""
        self.fields = fields
        self._by_name = {}
        self._by_name_lower = {}
        self._by_variable = {}
        self._by_id = {}
        self._build_indexes(fields)

    def match_field(self, field_ref: str) -> Optional[FieldInfo]:
        """
        Match a field reference to an actual field.

        Args:
            field_ref: Field reference from logic text.

        Returns:
            FieldInfo or None if not found.
        """
        if not field_ref:
            return None

        # 1. Try exact match
        if field_ref in self._by_name:
            return self._by_name[field_ref]

        # 2. Try case-insensitive match
        field_lower = field_ref.lower()
        if field_lower in self._by_name_lower:
            return self._by_name_lower[field_lower]

        # 3. Try variable name match
        if field_ref in self._by_variable:
            return self._by_variable[field_ref]

        # 4. Try normalized match (remove spaces, special chars)
        normalized = self._normalize_name(field_ref)
        for name, field in self._by_name_lower.items():
            if self._normalize_name(name) == normalized:
                return field

        # 5. Try partial match (field_ref contained in name)
        for name, field in self._by_name_lower.items():
            if field_lower in name or name in field_lower:
                return field

        # 6. Try fuzzy matching if available
        if RAPIDFUZZ_AVAILABLE and self.fields:
            result = self._fuzzy_match(field_ref)
            if result:
                return result

        return None

    def match_field_id(self, field_ref: str) -> Optional[int]:
        """
        Match a field reference and return the ID.

        Args:
            field_ref: Field reference from logic text.

        Returns:
            Field ID or None if not found.
        """
        field = self.match_field(field_ref)
        return field.id if field else None

    def _normalize_name(self, name: str) -> str:
        """Normalize field name for matching."""
        # Remove special characters, convert to lowercase
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def _fuzzy_match(self, field_ref: str) -> Optional[FieldInfo]:
        """Try fuzzy matching using rapidfuzz."""
        if not RAPIDFUZZ_AVAILABLE or not self.fields:
            return None

        field_names = [f.name for f in self.fields]
        results = process.extract(
            field_ref,
            field_names,
            scorer=fuzz.token_sort_ratio,
            limit=1
        )

        if results and results[0][1] >= self.fuzzy_threshold:
            matched_name = results[0][0]
            return self._by_name.get(matched_name)

        return None

    def get_field_by_id(self, field_id: int) -> Optional[FieldInfo]:
        """Get field by ID."""
        return self._by_id.get(field_id)

    def find_fields_by_logic_pattern(self, pattern: str) -> List[FieldInfo]:
        """
        Find fields whose logic matches a pattern.

        Args:
            pattern: Regex pattern to match in field logic.

        Returns:
            List of matching FieldInfo objects.
        """
        matches = []
        for field in self.fields:
            if field.logic and re.search(pattern, field.logic, re.IGNORECASE):
                matches.append(field)
        return matches

    def find_verify_destination_fields(self, verify_source_type: str) -> List[FieldInfo]:
        """
        Find fields that are destinations of a VERIFY rule.

        These fields have logic like "Data will come from X validation".

        Args:
            verify_source_type: Type of verification (e.g., "PAN", "GSTIN")

        Returns:
            List of destination fields.
        """
        pattern = rf"data\s+will\s+come\s+from\s+{verify_source_type}\s+validation"
        return self.find_fields_by_logic_pattern(pattern)

    def find_ocr_destination_field(self, ocr_field_name: str) -> Optional[FieldInfo]:
        """
        Find the destination field for an OCR rule.

        OCR fields are typically named "Upload X" and populate field "X".

        Args:
            ocr_field_name: Name of the OCR upload field.

        Returns:
            Destination field or None.
        """
        # Pattern: "Upload X" -> "X"
        match = re.match(r"upload\s+(.+)", ocr_field_name, re.IGNORECASE)
        if match:
            target_name = match.group(1).strip()
            return self.match_field(target_name)
        return None

    def find_fields_controlled_by(self, source_field_name: str) -> List[Tuple[FieldInfo, str, str]]:
        """
        Find fields whose visibility/mandatory is controlled by a source field.

        Args:
            source_field_name: Name of the controlling field.

        Returns:
            List of tuples: (field, conditional_value, action_type)
        """
        results = []
        source_lower = source_field_name.lower()

        for field in self.fields:
            if not field.logic:
                continue

            logic_lower = field.logic.lower()

            # Check if this field references the source
            if source_lower not in logic_lower:
                continue

            # Extract conditional value and action
            match = re.search(
                rf"field\s+['\"]?{re.escape(source_field_name)}['\"]?\s+(?:value|values?)\s+(?:is|are)\s+([^\s,]+)\s+then\s+(visible|mandatory)",
                logic_lower
            )
            if match:
                value = match.group(1).strip("'\"")
                action = f"MAKE_{match.group(2).upper()}"
                results.append((field, value, action))

        return results

    def build_visibility_groups(self) -> Dict[str, List[Dict]]:
        """
        Build groups of fields controlled by the same source field.

        Returns:
            Dict mapping source_field_name to list of destination info dicts.
        """
        groups: Dict[str, List[Dict]] = {}

        for field in self.fields:
            if not field.logic:
                continue

            # Pattern: "if the field 'X' value is Y then visible"
            matches = re.finditer(
                r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value|values?)\s+(?:is|are)\s+([^\s,]+)\s+then\s+(visible|mandatory)",
                field.logic,
                re.IGNORECASE
            )

            for match in matches:
                source_field = match.group(1)
                value = match.group(2).strip("'\"")
                action = match.group(3)

                if source_field not in groups:
                    groups[source_field] = []

                groups[source_field].append({
                    "field_name": field.name,
                    "field_id": field.id,
                    "conditional_value": value,
                    "action_type": f"MAKE_{action.upper()}",
                })

        return groups


class FieldNameSimilarity:
    """Calculate similarity between field names for mapping."""

    # Synonyms and abbreviations
    SYNONYMS = {
        "fullname": ["full name", "name", "holder name", "pan holder name"],
        "pan type": ["pantype", "type"],
        "pan status": ["panstatus", "retrieval status", "pan retrieval status"],
        "aadhaar": ["aadhar", "aadhaar pan", "aadhaar seeding"],
        "legal name": ["longname", "legal", "legalname"],
        "trade name": ["tradename", "trade"],
        "reg date": ["regdate", "registration date"],
        "ifsc": ["ifsc code", "ifsccode"],
        "account number": ["accountnumber", "bank account number"],
        "beneficiary": ["beneficiary name", "bank beneficiary name"],
    }

    @classmethod
    def are_similar(cls, name1: str, name2: str, threshold: float = 0.7) -> bool:
        """
        Check if two field names are similar.

        Args:
            name1: First field name.
            name2: Second field name.
            threshold: Similarity threshold (0-1).

        Returns:
            True if names are considered similar.
        """
        n1_lower = name1.lower().strip()
        n2_lower = name2.lower().strip()

        # Exact match
        if n1_lower == n2_lower:
            return True

        # Check synonyms
        for key, synonyms in cls.SYNONYMS.items():
            all_variants = [key] + synonyms
            if n1_lower in all_variants and n2_lower in all_variants:
                return True

        # Substring match
        if n1_lower in n2_lower or n2_lower in n1_lower:
            return True

        # Use rapidfuzz if available
        if RAPIDFUZZ_AVAILABLE:
            score = fuzz.token_sort_ratio(n1_lower, n2_lower)
            return score >= (threshold * 100)

        return False

    @classmethod
    def find_best_match(cls, target: str, candidates: List[str]) -> Optional[str]:
        """
        Find the best matching field name from candidates.

        Args:
            target: Target field name to match.
            candidates: List of candidate field names.

        Returns:
            Best matching candidate or None.
        """
        target_lower = target.lower().strip()

        # Try exact match first
        for candidate in candidates:
            if candidate.lower().strip() == target_lower:
                return candidate

        # Try synonyms
        for candidate in candidates:
            if cls.are_similar(target, candidate):
                return candidate

        # Use fuzzy matching if available
        if RAPIDFUZZ_AVAILABLE and candidates:
            results = process.extract(
                target,
                candidates,
                scorer=fuzz.token_sort_ratio,
                limit=1
            )
            if results and results[0][1] >= 70:
                return results[0][0]

        return None
