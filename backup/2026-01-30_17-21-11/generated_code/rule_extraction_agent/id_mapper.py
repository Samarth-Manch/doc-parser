"""
ID Mapper module for ordinal-to-index conversion.

Maps BUD field IDs to ordinal-indexed destinationIds arrays as required by
formFillRules for VERIFY and OCR rules.
"""

from typing import Dict, List, Optional, Tuple
from .schema_lookup import RuleSchemaLookup, RuleSchemaInfo


class DestinationIdMapper:
    """
    Maps BUD field IDs to ordinal-indexed destinationIds arrays.

    VERIFY and OCR rules require destinationIds arrays where each index
    corresponds to an ordinal position from the Rule-Schema. Fields not
    mapped in the BUD should have -1 at their ordinal position.

    Example for PAN Validation (schema ID 360, 10 destination ordinals):
        BUD only has mappings for ordinals 4, 6, 8, 9
        Result: [-1, -1, -1, 275535, -1, 275537, -1, 275536, 275538, -1]
    """

    def __init__(self, schema_lookup: RuleSchemaLookup):
        """
        Initialize the mapper.

        Args:
            schema_lookup: RuleSchemaLookup instance for accessing schema info.
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

        Returns:
            List of field IDs indexed by ordinal position (ordinal 1 -> index 0)

        Example:
            schema_id = 360  # Validate PAN (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema_info = self.schema_lookup.get_by_id(schema_id)
        if not schema_info:
            return []

        num_items = schema_info.num_destination_items
        if num_items == 0:
            return []

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Get ordinal map from schema
        ordinal_map = schema_info.get_destination_ordinal_map()

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            ordinal = ordinal_map.get(field_name)
            if ordinal and 1 <= ordinal <= num_items:
                # ordinal 1 -> index 0, ordinal N -> index N-1
                destination_ids[ordinal - 1] = field_id

        return destination_ids

    def map_with_fuzzy_matching(
        self,
        schema_id: int,
        bud_fields: Dict[str, int],
        threshold: float = 0.8
    ) -> Tuple[List[int], Dict[str, str]]:
        """
        Build destinationIds with fuzzy field name matching.

        Args:
            schema_id: Rule schema ID
            bud_fields: Dict mapping BUD field names to field IDs
            threshold: Fuzzy matching threshold (0-1)

        Returns:
            Tuple of (destinationIds list, matched field names dict)
        """
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            # Fall back to exact matching if rapidfuzz not available
            return self._map_exact(schema_id, bud_fields)

        schema_info = self.schema_lookup.get_by_id(schema_id)
        if not schema_info:
            return [], {}

        num_items = schema_info.num_destination_items
        if num_items == 0:
            return [], {}

        destination_ids = [-1] * num_items
        matched_fields = {}

        # Get destination field names and ordinals
        ordinal_map = schema_info.get_destination_ordinal_map()
        bud_field_names = list(bud_fields.keys())

        for schema_field_name, ordinal in ordinal_map.items():
            if not bud_field_names:
                break

            # Try exact match first
            if schema_field_name in bud_fields:
                field_id = bud_fields[schema_field_name]
                destination_ids[ordinal - 1] = field_id
                matched_fields[schema_field_name] = schema_field_name
                continue

            # Try fuzzy match
            result = process.extractOne(
                schema_field_name,
                bud_field_names,
                scorer=fuzz.token_sort_ratio
            )

            if result and result[1] >= threshold * 100:
                matched_bud_name = result[0]
                field_id = bud_fields[matched_bud_name]
                destination_ids[ordinal - 1] = field_id
                matched_fields[schema_field_name] = matched_bud_name

        return destination_ids, matched_fields

    def _map_exact(
        self,
        schema_id: int,
        bud_fields: Dict[str, int]
    ) -> Tuple[List[int], Dict[str, str]]:
        """Fallback to exact matching when fuzzy matching unavailable."""
        schema_info = self.schema_lookup.get_by_id(schema_id)
        if not schema_info:
            return [], {}

        num_items = schema_info.num_destination_items
        destination_ids = [-1] * num_items
        matched_fields = {}

        ordinal_map = schema_info.get_destination_ordinal_map()

        # Normalize BUD field names for matching
        normalized_bud = {
            self._normalize_name(k): (k, v)
            for k, v in bud_fields.items()
        }

        for schema_field_name, ordinal in ordinal_map.items():
            norm_schema = self._normalize_name(schema_field_name)

            if norm_schema in normalized_bud:
                orig_name, field_id = normalized_bud[norm_schema]
                destination_ids[ordinal - 1] = field_id
                matched_fields[schema_field_name] = orig_name

        return destination_ids, matched_fields

    def _normalize_name(self, name: str) -> str:
        """Normalize field name for comparison."""
        return name.lower().replace(" ", "").replace("_", "").replace("-", "")

    def get_schema_field_info(self, schema_id: int) -> Dict[str, Dict]:
        """
        Get detailed information about schema destination fields.

        Args:
            schema_id: Rule schema ID

        Returns:
            Dict with field names as keys, containing ordinal and other info
        """
        schema_info = self.schema_lookup.get_by_id(schema_id)
        if not schema_info:
            return {}

        result = {}
        for field in schema_info.destination_fields:
            result[field['name']] = {
                'ordinal': field['ordinal'],
                'mandatory': field.get('mandatory', False),
                'unlimited': field.get('unlimited', False),
            }
        return result

    def validate_mapping(
        self,
        schema_id: int,
        destination_ids: List[int]
    ) -> List[str]:
        """
        Validate a destinationIds mapping.

        Args:
            schema_id: Rule schema ID
            destination_ids: The destinationIds array to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        schema_info = self.schema_lookup.get_by_id(schema_id)

        if not schema_info:
            errors.append(f"Schema {schema_id} not found")
            return errors

        expected_length = schema_info.num_destination_items
        actual_length = len(destination_ids)

        if actual_length != expected_length:
            errors.append(
                f"destinationIds length mismatch: expected {expected_length}, got {actual_length}"
            )

        # Check for mandatory fields
        ordinal_map = schema_info.get_destination_ordinal_map()
        for field in schema_info.destination_fields:
            if field.get('mandatory', False):
                ordinal = field['ordinal']
                if ordinal <= len(destination_ids) and destination_ids[ordinal - 1] == -1:
                    errors.append(
                        f"Mandatory field '{field['name']}' (ordinal {ordinal}) is not mapped"
                    )

        return errors


class SourceIdMapper:
    """Helper for mapping source field IDs."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        self.schema_lookup = schema_lookup

    def get_source_requirements(self, schema_id: int) -> List[Dict]:
        """Get source field requirements for a schema."""
        return self.schema_lookup.get_source_field_requirements(schema_id)

    def build_source_ids(
        self,
        schema_id: int,
        primary_field_id: int,
        additional_fields: Optional[Dict[str, int]] = None
    ) -> List[int]:
        """
        Build sourceIds array for a rule.

        Args:
            schema_id: Rule schema ID
            primary_field_id: Primary source field ID
            additional_fields: Optional additional source fields

        Returns:
            List of source field IDs
        """
        source_ids = [primary_field_id]

        if additional_fields:
            schema_info = self.schema_lookup.get_by_id(schema_id)
            if schema_info:
                # Match additional fields to source field ordinals
                source_fields = schema_info.source_fields
                for sf in source_fields[1:]:  # Skip first (primary)
                    field_name = sf['name']
                    if field_name in additional_fields:
                        source_ids.append(additional_fields[field_name])

        return source_ids
