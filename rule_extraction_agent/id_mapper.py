"""Maps BUD field IDs to ordinal-indexed destinationIds arrays."""

from typing import Dict, List, Optional
from .schema_lookup import RuleSchemaLookup


class DestinationIdMapper:
    """Maps BUD field IDs to ordinal-indexed destinationIds arrays."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        self.schema_lookup = schema_lookup

    def map_to_ordinals(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]  # schema_field_name → field_id
    ) -> List[int]:
        """
        Build destinationIds array with -1 for unused ordinals.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            field_mappings: Dict mapping schema field names to BUD field IDs

        Returns:
            List of field IDs indexed by ordinal position (ordinal 1 → index 0)

        Example:
            schema_id = 360  # Validate PAN (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema = self.schema_lookup.find_by_id(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        if num_items == 0:
            return []

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Map field names to their ordinal positions
        name_to_ordinal = {f['name'].lower(): f['ordinal'] for f in dest_fields}

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            # Try exact match first
            ordinal = name_to_ordinal.get(field_name.lower())

            # Try fuzzy match if no exact match
            if ordinal is None:
                # Find the BEST match, not just the first match
                best_match = self._find_best_match(field_name.lower(), name_to_ordinal)
                if best_match:
                    ordinal = best_match

            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 → index 0

        return destination_ids

    def _find_best_match(self, field_name: str, name_to_ordinal: Dict[str, int]) -> Optional[int]:
        """Find the best matching ordinal for a field name."""
        candidates = []

        for schema_name, ord_pos in name_to_ordinal.items():
            if self._fuzzy_match(field_name, schema_name):
                # Calculate a match score
                score = self._match_score(field_name, schema_name)
                candidates.append((ord_pos, score))

        if not candidates:
            return None

        # Return the ordinal with the highest score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _match_score(self, text1: str, text2: str) -> float:
        """Calculate a match score between two strings (higher is better)."""
        # Exact match
        if text1 == text2:
            return 1.0

        text1_norm = text1.replace('_', ' ').replace('-', ' ')
        text2_norm = text2.replace('_', ' ').replace('-', ' ')

        # Check containment
        if text1_norm == text2_norm:
            return 0.99
        if text1_norm in text2_norm:
            return 0.9 + len(text1_norm) / (len(text2_norm) * 10)
        if text2_norm in text1_norm:
            return 0.9 + len(text2_norm) / (len(text1_norm) * 10)

        # Token overlap
        tokens1 = set(text1_norm.split())
        tokens2 = set(text2_norm.split())

        if not tokens1 or not tokens2:
            return 0.0

        # Jaccard similarity
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = intersection / union if union > 0 else 0

        # Boost for more specific matches (longer common tokens)
        common_tokens = tokens1 & tokens2
        specificity_boost = 0
        for token in common_tokens:
            if len(token) > 4:  # Longer words are more specific
                specificity_boost += 0.05 * len(token)

        # Check semantic equivalences and boost score
        semantic_boost = self._semantic_match_score(text1_norm, text2_norm)

        return jaccard + specificity_boost + semantic_boost

    def _semantic_match_score(self, text1: str, text2: str) -> float:
        """Score based on semantic equivalences."""
        # Specific semantic mappings with high confidence
        high_confidence_pairs = [
            ('pan holder name', 'fullname'),
            ('holder name', 'fullname'),
            ('pan status', 'pan retrieval status'),
            ('aadhaar pan list status', 'aadhaar seeding status'),
            ('trade name', 'trade name'),
            ('legal name', 'longname'),
            ('beneficiary name', 'beneficiary name'),
            ('bank name', 'bankname'),
        ]

        for pair1, pair2 in high_confidence_pairs:
            if (pair1 in text1 and pair2 in text2) or (pair2 in text1 and pair1 in text2):
                return 0.5  # High boost for known semantic matches

        return 0.0

    def map_source_fields(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]  # schema_field_name → field_id
    ) -> List[int]:
        """
        Build sourceIds array for multi-source VERIFY rules.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            field_mappings: Dict mapping schema field names to BUD field IDs

        Returns:
            List of field IDs in ordinal order

        Example:
            schema_id = 361  # Bank Account Validation (2 source fields)
            field_mappings = {"IFSC Code": 87, "Bank Account Number": 88}
            Returns: [87, 88]
        """
        schema = self.schema_lookup.find_by_id(schema_id)
        if not schema:
            return []

        source_fields = schema.get('sourceFields', {}).get('fields', [])
        num_items = schema.get('sourceFields', {}).get('numberOfItems', 1)

        if num_items <= 1:
            # Single source field - just return the first mapped ID
            for field_id in field_mappings.values():
                return [field_id]
            return []

        # Multi-source field - map by ordinal
        source_ids = [-1] * num_items
        name_to_ordinal = {f['name'].lower(): f['ordinal'] for f in source_fields}

        for field_name, field_id in field_mappings.items():
            ordinal = name_to_ordinal.get(field_name.lower())

            if ordinal is None:
                for schema_name, ord_pos in name_to_ordinal.items():
                    if self._fuzzy_match(field_name.lower(), schema_name):
                        ordinal = ord_pos
                        break

            if ordinal and 1 <= ordinal <= num_items:
                source_ids[ordinal - 1] = field_id

        # Remove trailing -1s
        while source_ids and source_ids[-1] == -1:
            source_ids.pop()

        return source_ids

    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.6) -> bool:
        """
        Fuzzy match using multiple strategies.

        Handles cases like:
        - "Pan Holder Name" matches "Fullname"
        - "PAN Type" matches "Pan type"
        - "PAN Status" matches "Pan retrieval status"
        - "Aadhaar PAN List Status" matches "Aadhaar seeding status"
        """
        text1_lower = text1.lower().strip()
        text2_lower = text2.lower().strip()

        # Exact match
        if text1_lower == text2_lower:
            return True

        # Normalize texts
        text1_norm = text1_lower.replace('_', ' ').replace('-', ' ')
        text2_norm = text2_lower.replace('_', ' ').replace('-', ' ')

        # Check if one contains the other (for cases like "PAN Type" vs "Pan type")
        if text1_norm in text2_norm or text2_norm in text1_norm:
            return True

        # Token-based matching
        tokens1 = set(text1_norm.split())
        tokens2 = set(text2_norm.split())

        if not tokens1 or not tokens2:
            return False

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = intersection / union if union > 0 else 0

        if jaccard >= threshold:
            return True

        # Check for common words (at least one significant word matches)
        common_words = {'name', 'type', 'status', 'number', 'date', 'code'}
        sig_tokens1 = tokens1 - {'the', 'a', 'an', 'of', 'for', 'and', 'or'}
        sig_tokens2 = tokens2 - {'the', 'a', 'an', 'of', 'for', 'and', 'or'}

        if sig_tokens1 & sig_tokens2:
            # At least one significant word matches
            common_sig = sig_tokens1 & sig_tokens2
            if any(w in common_words for w in common_sig) or len(common_sig) >= 2:
                return True

        # Semantic equivalences mapping
        equivalences = {
            'fullname': ['holder name', 'full name', 'name', 'pan holder'],
            'firstname': ['first name', 'first'],
            'lastname': ['last name', 'surname'],
            'pan type': ['type', 'pan type'],
            'pan retrieval status': ['pan status', 'status', 'retrieval status'],
            'aadhaar seeding status': ['aadhaar status', 'aadhaar pan', 'seeding status', 'pan list status'],
            'trade name': ['trade', 'business name'],
            'legal name': ['legal', 'registered name', 'longname'],
            'reg date': ['registration date', 'date of registration'],
            'beneficiary name': ['account holder', 'account name', 'holder name'],
            'bank name': ['bank', 'name of bank'],
            'ifsc code': ['ifsc', 'bank code'],
            'account number': ['account', 'bank account', 'account no'],
        }

        for canonical, synonyms in equivalences.items():
            # Check if text1 matches any synonym and text2 matches canonical (or vice versa)
            canonical_matches_1 = canonical in text1_norm
            canonical_matches_2 = canonical in text2_norm
            synonym_matches_1 = any(syn in text1_norm for syn in synonyms)
            synonym_matches_2 = any(syn in text2_norm for syn in synonyms)

            if (canonical_matches_1 and synonym_matches_2) or (canonical_matches_2 and synonym_matches_1):
                return True

            # Also check if both texts match synonyms of the same canonical term
            if synonym_matches_1 and synonym_matches_2:
                return True

        return False

    def get_required_source_count(self, schema_id: int) -> int:
        """Get number of required source fields for a schema."""
        return self.schema_lookup.get_source_field_count(schema_id)

    def get_required_destination_count(self, schema_id: int) -> int:
        """Get number of destination fields for a schema."""
        return self.schema_lookup.get_destination_field_count(schema_id)
