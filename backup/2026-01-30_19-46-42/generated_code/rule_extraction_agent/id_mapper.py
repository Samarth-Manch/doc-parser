"""
Destination ID Mapper - Maps BUD field IDs to ordinal-indexed destinationIds arrays.

This module handles the critical ordinal-to-index mapping for VERIFY and OCR rules,
where destinationIds arrays must have -1 for unused ordinal positions.
"""

from typing import Dict, List, Optional
from .schema_lookup import RuleSchemaLookup


class DestinationIdMapper:
    """Maps BUD field IDs to ordinal-indexed destinationIds arrays."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        """
        Initialize the mapper.

        Args:
            schema_lookup: RuleSchemaLookup instance for accessing schemas.
        """
        self.schema_lookup = schema_lookup

    def map_to_ordinals(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]
    ) -> List[int]:
        """
        Build destinationIds array with -1 for unused ordinals.

        The destinationIds array is indexed by ordinal position (ordinal 1 -> index 0).
        Fields that don't have a corresponding BUD field get -1.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            field_mappings: Dict mapping schema field names to BUD field IDs

        Returns:
            List of field IDs indexed by ordinal position

        Example:
            schema_id = 360  # Validate PAN (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema = self.schema_lookup.get_schema_by_id(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Map field names to their ordinal positions
        name_to_ordinal = {f['name']: f['ordinal'] for f in dest_fields}

        # Also create lowercase mapping for fuzzy matching
        name_lower_to_ordinal = {f['name'].lower(): f['ordinal'] for f in dest_fields}

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            # Try exact match first
            ordinal = name_to_ordinal.get(field_name)

            # Try case-insensitive match
            if ordinal is None:
                ordinal = name_lower_to_ordinal.get(field_name.lower())

            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 -> index 0

        return destination_ids

    def map_verify_destinations(
        self,
        source_type: str,
        field_mappings: Dict[str, int]
    ) -> List[int]:
        """
        Map VERIFY rule destinations using source type.

        Args:
            source_type: VERIFY source type (e.g., "PAN_NUMBER", "GSTIN")
            field_mappings: Dict mapping schema field names to BUD field IDs

        Returns:
            List of field IDs indexed by ordinal position
        """
        schema_id = self.schema_lookup.SCHEMA_IDS.get(source_type)
        if not schema_id:
            return []
        return self.map_to_ordinals(schema_id, field_mappings)

    def map_ocr_destinations(
        self,
        source_type: str,
        field_mappings: Dict[str, int]
    ) -> List[int]:
        """
        Map OCR rule destinations using source type.

        Args:
            source_type: OCR source type (e.g., "PAN_IMAGE", "CHEQUEE")
            field_mappings: Dict mapping schema field names to BUD field IDs

        Returns:
            List of field IDs indexed by ordinal position
        """
        schema_id = self.schema_lookup.SCHEMA_IDS.get(source_type)
        if not schema_id:
            return []
        return self.map_to_ordinals(schema_id, field_mappings)

    def get_ordinal_field_names(self, schema_id: int) -> Dict[int, str]:
        """
        Get mapping of ordinal positions to field names for a schema.

        Args:
            schema_id: Schema ID

        Returns:
            Dict mapping ordinal number to field name.
        """
        schema = self.schema_lookup.get_schema_by_id(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['ordinal']: f['name'] for f in dest_fields}

    def suggest_field_mappings(
        self,
        source_type: str,
        available_fields: List[Dict]
    ) -> Dict[str, Optional[int]]:
        """
        Suggest field mappings based on name matching.

        Args:
            source_type: Source type (e.g., "PAN_NUMBER")
            available_fields: List of available BUD fields with 'name' and 'id'

        Returns:
            Dict mapping schema field names to suggested BUD field IDs (or None)
        """
        schema_id = self.schema_lookup.SCHEMA_IDS.get(source_type)
        if not schema_id:
            return {}

        schema = self.schema_lookup.get_schema_by_id(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        suggestions = {}

        # Build mapping of available field names to IDs
        available_by_name_lower = {
            f['name'].lower(): f['id'] for f in available_fields if f.get('name')
        }

        for dest_field in dest_fields:
            dest_name = dest_field['name']
            dest_name_lower = dest_name.lower()

            # Try exact match first
            if dest_name_lower in available_by_name_lower:
                suggestions[dest_name] = available_by_name_lower[dest_name_lower]
            else:
                # Try partial matches
                found = False
                for avail_name_lower, avail_id in available_by_name_lower.items():
                    # Check if schema field name is contained in BUD field name
                    if dest_name_lower in avail_name_lower or avail_name_lower in dest_name_lower:
                        suggestions[dest_name] = avail_id
                        found = True
                        break

                if not found:
                    suggestions[dest_name] = None

        return suggestions


# Predefined ordinal mappings based on reference output
PAN_VERIFY_ORDINALS = {
    # ordinal: field description
    1: "Panholder title",
    2: "Firstname",
    3: "Lastname",
    4: "Fullname",  # -> Pan Holder Name
    5: "Last updated",
    6: "Pan retrieval status",  # -> PAN Status
    7: "Fullname without title",
    8: "Pan type",  # -> PAN Type
    9: "Aadhaar seeding status",  # -> Aadhaar PAN List Status
    10: "Middle name",
}

GSTIN_VERIFY_ORDINALS = {
    1: "Trade name",
    2: "Longname",  # Legal Name
    3: "Reg date",
    4: "City",
    5: "Type",
    6: "Building number",
    7: "Flat number",
    8: "District code",
    9: "Street",
    10: "Pin code",
    11: "State",
}

BANK_VERIFY_ORDINALS = {
    1: "Bank Beneficiary Name",
    2: "Bank Reference",
    3: "Verification Status",
    4: "Message",
}

CHEQUEE_OCR_ORDINALS = {
    1: "bankName",
    2: "ifscCode",
    3: "beneficiaryName",
    4: "accountNumber",
    5: "address",
    6: "micrCode",
    7: "branch",
}

MSME_VERIFY_ORDINALS = {
    1: "Name Of Enterprise",
    2: "Major Activity",
    3: "Social Category",
    4: "Enterprise",
    5: "Date Of Commencement",
    6: "Type",
    7: "Address",
    8: "Category",
    9: "Date",
    10: "Dice Name",
    11: "State",
    12: "Applied State",
    13: "Modified Date",
    14: "Expiry Date",
    15: "Address Line1",
    16: "Building",
    17: "Street",
    18: "Area",
    19: "City",
    20: "Pin",
    21: "District",
}
