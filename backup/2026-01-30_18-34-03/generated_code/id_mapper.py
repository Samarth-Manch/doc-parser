"""
Destination ID Mapper - Maps BUD field IDs to ordinal-indexed destinationIds arrays.

For VERIFY and OCR rules, destinationIds must be arrays where:
- Index 0 corresponds to ordinal 1
- Index N corresponds to ordinal N+1
- -1 is used for ordinals without corresponding BUD fields
"""

from typing import Dict, List, Optional
try:
    from .schema_lookup import RuleSchemaLookup
except ImportError:
    from schema_lookup import RuleSchemaLookup


class DestinationIdMapper:
    """Maps BUD field IDs to ordinal-indexed destinationIds arrays."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        """
        Initialize with a RuleSchemaLookup instance.

        Args:
            schema_lookup: Instance of RuleSchemaLookup for accessing schema info
        """
        self.schema_lookup = schema_lookup

    def map_to_ordinals(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]
    ) -> List[int]:
        """
        Build destinationIds array with -1 for unused ordinals.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            field_mappings: Dict mapping schema field names to BUD field IDs
                           Keys are schema field names (case-insensitive)
                           Values are BUD field IDs

        Returns:
            List of field IDs indexed by ordinal position (ordinal 1 -> index 0)
            Uses -1 for ordinals without corresponding BUD fields

        Example:
            schema_id = 360  # Validate PAN (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema = self.schema_lookup.get_by_id(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        if num_items == 0:
            return []

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Build name-to-ordinal mapping (case-insensitive)
        name_to_ordinal = {f['name'].lower(): f['ordinal'] for f in dest_fields}

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            ordinal = name_to_ordinal.get(field_name.lower())
            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 -> index 0

        return destination_ids

    def map_with_fuzzy_matching(
        self,
        schema_id: int,
        bud_fields: Dict[str, int],
        threshold: float = 0.8
    ) -> List[int]:
        """
        Build destinationIds array using fuzzy matching for field names.

        Args:
            schema_id: Rule schema ID
            bud_fields: Dict mapping BUD field names to field IDs
            threshold: Minimum similarity score (0-1) for matching

        Returns:
            List of field IDs indexed by ordinal position
        """
        try:
            from rapidfuzz import fuzz
        except ImportError:
            # Fall back to exact matching if rapidfuzz not available
            return self.map_to_ordinals(schema_id, bud_fields)

        schema = self.schema_lookup.get_by_id(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        if num_items == 0:
            return []

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # For each schema destination field, find best matching BUD field
        for dest_field in dest_fields:
            schema_name = dest_field['name'].lower()
            ordinal = dest_field['ordinal']

            best_match = None
            best_score = 0

            for bud_name, bud_id in bud_fields.items():
                # Calculate similarity score
                score = fuzz.token_sort_ratio(schema_name, bud_name.lower()) / 100.0

                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = bud_id

            if best_match is not None and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = best_match

        return destination_ids

    def get_ordinal_field_mapping(self, schema_id: int) -> Dict[int, str]:
        """
        Get mapping of ordinal positions to schema field names.

        Args:
            schema_id: Rule schema ID

        Returns:
            Dict mapping ordinal (1-based) to field name
        """
        schema = self.schema_lookup.get_by_id(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['ordinal']: f['name'] for f in dest_fields}

    def validate_mapping(
        self,
        schema_id: int,
        destination_ids: List[int]
    ) -> Dict:
        """
        Validate a destinationIds array against the schema.

        Args:
            schema_id: Rule schema ID
            destination_ids: Array of destination field IDs

        Returns:
            Dict with validation results:
            - valid: bool
            - expected_length: int
            - actual_length: int
            - mapped_count: int (fields with IDs != -1)
            - unmapped_ordinals: List[int] (ordinals with -1)
        """
        schema = self.schema_lookup.get_by_id(schema_id)
        if not schema:
            return {
                "valid": False,
                "error": f"Schema {schema_id} not found"
            }

        expected_length = schema.get('destinationFields', {}).get('numberOfItems', 0)
        actual_length = len(destination_ids)
        mapped_count = sum(1 for id_ in destination_ids if id_ != -1)
        unmapped_ordinals = [i + 1 for i, id_ in enumerate(destination_ids) if id_ == -1]

        return {
            "valid": actual_length == expected_length,
            "expected_length": expected_length,
            "actual_length": actual_length,
            "mapped_count": mapped_count,
            "unmapped_ordinals": unmapped_ordinals,
        }
