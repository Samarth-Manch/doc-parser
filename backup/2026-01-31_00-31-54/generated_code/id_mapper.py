"""
Destination ID Mapper Module

Maps BUD field IDs to ordinal-indexed destinationIds arrays for VERIFY and OCR rules.
"""

from typing import Dict, List, Optional

try:
    from .schema_lookup import RuleSchemaLookup, get_destination_mappings_for_source
except ImportError:
    from schema_lookup import RuleSchemaLookup, get_destination_mappings_for_source


class DestinationIdMapper:
    """
    Maps BUD field IDs to ordinal-indexed destinationIds arrays.

    For VERIFY and OCR rules, destination fields are mapped by ordinal position.
    Fields that don't have a corresponding BUD field use -1 as placeholder.

    Example:
        schema_id = 360  # Validate PAN (10 destination fields)
        field_mappings = {"Fullname": 275535, "Pan type": 275536}
        Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
    """

    def __init__(self, schema_lookup: RuleSchemaLookup):
        """
        Initialize the mapper.

        Args:
            schema_lookup: RuleSchemaLookup instance for querying schemas
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
        """
        schema = self.schema_lookup.get_schema_by_id(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Map field names to their ordinal positions
        name_to_ordinal = {f['name'].lower(): f['ordinal'] for f in dest_fields}

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            # Try exact match first
            ordinal = name_to_ordinal.get(field_name.lower())

            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 -> index 0

        return destination_ids

    def auto_map_destinations(
        self,
        source_type: str,
        schema_id: int,
        available_fields: Dict[str, int],
        field_order: List[str] = None
    ) -> List[int]:
        """
        Automatically map destination fields based on field name patterns.

        Args:
            source_type: The source type (e.g., "PAN_NUMBER", "GSTIN")
            schema_id: Rule schema ID
            available_fields: Dict mapping field names to field IDs
            field_order: Optional list of field names in order (for "next fields" logic)

        Returns:
            List of field IDs indexed by ordinal position
        """
        # Get the mapping patterns for this source type
        mappings = get_destination_mappings_for_source(source_type)

        # Get schema destination field info
        schema = self.schema_lookup.get_schema_by_id(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Initialize with -1
        destination_ids = [-1] * num_items

        # Build a normalized lookup of available fields
        normalized_fields = {}
        for name, field_id in available_fields.items():
            normalized = name.lower().strip()
            normalized_fields[normalized] = field_id

        # Try to match each schema destination field to an available field
        for dest_field in dest_fields:
            schema_field_name = dest_field.get('name', '')
            ordinal = dest_field.get('ordinal', 0)

            if ordinal < 1 or ordinal > num_items:
                continue

            # Get possible BUD field patterns for this schema field
            patterns = mappings.get(schema_field_name, [schema_field_name.lower()])

            # Try each pattern
            matched_id = None
            for pattern in patterns:
                pattern_lower = pattern.lower()

                # Try exact match
                if pattern_lower in normalized_fields:
                    matched_id = normalized_fields[pattern_lower]
                    break

                # Try partial match (pattern contained in field name)
                for field_name, field_id in normalized_fields.items():
                    if pattern_lower in field_name or field_name in pattern_lower:
                        matched_id = field_id
                        break

                if matched_id:
                    break

            if matched_id:
                destination_ids[ordinal - 1] = matched_id

        return destination_ids

    def map_verify_destinations_from_context(
        self,
        source_type: str,
        schema_id: int,
        source_field_id: int,
        all_fields: List[Dict],
        panel_fields: List[Dict] = None
    ) -> List[int]:
        """
        Map VERIFY destinations based on field context and "next fields" logic.

        This method looks for fields that have logic like "Data will come from X validation"
        and maps them to the appropriate ordinal positions.

        Args:
            source_type: The VERIFY source type
            schema_id: Rule schema ID
            source_field_id: ID of the field triggering the VERIFY
            all_fields: List of all fields in the schema
            panel_fields: Optional list of fields in the same panel

        Returns:
            List of destination field IDs
        """
        fields_to_search = panel_fields if panel_fields else all_fields
        field_mappings = {}

        # Get destination field patterns
        mappings = get_destination_mappings_for_source(source_type)

        # Get schema ordinals
        ordinals = self.schema_lookup.get_destination_ordinals(schema_id)

        # Find fields that reference this validation
        source_name_patterns = {
            "PAN_NUMBER": ["pan validation", "pan verify"],
            "GSTIN": ["gstin validation", "gstin verification", "gst validation"],
            "BANK_ACCOUNT_NUMBER": ["bank validation", "bank verification", "bank account validation"],
            "MSME_UDYAM_REG_NUMBER": ["msme validation", "udyam validation"],
        }

        patterns = source_name_patterns.get(source_type, [])

        for field in fields_to_search:
            field_logic = (field.get('logic', '') or '').lower()
            field_name = field.get('name', '')
            field_id = field.get('id')

            # Check if this field receives data from the validation
            is_destination = any(
                f"data will come from {p}" in field_logic or
                f"data from {p}" in field_logic or
                f"populated from {p}" in field_logic
                for p in patterns
            )

            if is_destination and field_id:
                # Try to match to a schema field
                for schema_field, bud_patterns in mappings.items():
                    for pattern in bud_patterns:
                        if pattern.lower() in field_name.lower():
                            field_mappings[schema_field] = field_id
                            break

        return self.map_to_ordinals(schema_id, field_mappings)
