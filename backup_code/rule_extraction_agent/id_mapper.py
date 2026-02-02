"""
Destination ID Mapper - Maps BUD field IDs to ordinal-indexed destinationIds arrays.
"""

from typing import Dict, List, Optional
from .schema_lookup import RuleSchemaLookup
from .field_matcher import FieldMatcher


class DestinationIdMapper:
    """Maps BUD field IDs to ordinal-indexed destinationIds arrays."""

    def __init__(self, schema_lookup: RuleSchemaLookup, field_matcher: FieldMatcher):
        """
        Initialize the mapper.

        Args:
            schema_lookup: RuleSchemaLookup instance for schema queries.
            field_matcher: FieldMatcher instance for field resolution.
        """
        self.schema_lookup = schema_lookup
        self.field_matcher = field_matcher

    def map_to_ordinals(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]
    ) -> List[int]:
        """
        Build destinationIds array with -1 for unused ordinals.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json.
            field_mappings: Dict mapping schema field names to BUD field IDs.

        Returns:
            List of field IDs indexed by ordinal position (ordinal 1 → index 0).

        Example:
            schema_id = 360  # Validate PAN (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema = self.schema_lookup.get_schema_by_id(schema_id)
        if not schema:
            return []

        # Get number of destination items
        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        if num_items == 0:
            return []

        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Map field names to their ordinal positions
        name_to_ordinal = {f['name'].lower(): f['ordinal'] for f in dest_fields if 'ordinal' in f}

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            ordinal = name_to_ordinal.get(field_name.lower())
            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 → index 0

        return destination_ids

    def auto_map_destinations(
        self,
        schema_id: int,
        source_field_name: str,
        intra_panel_refs: Optional[Dict] = None
    ) -> List[int]:
        """
        Automatically map destination fields based on intra-panel references.

        Args:
            schema_id: Rule schema ID.
            source_field_name: Name of the source field (e.g., "PAN").
            intra_panel_refs: Intra-panel references JSON.

        Returns:
            List of field IDs indexed by ordinal position.
        """
        # Get schema destination ordinals
        ordinals = self.schema_lookup.get_destination_ordinals(schema_id)
        num_items = self.schema_lookup.get_destination_field_count(schema_id)

        if num_items == 0:
            return []

        # Initialize with -1
        destination_ids = [-1] * num_items

        # If we have intra-panel references, use them
        if intra_panel_refs:
            field_mappings = self._find_mappings_from_refs(
                source_field_name,
                ordinals,
                intra_panel_refs
            )

            for ordinal_name, field_id in field_mappings.items():
                # Find ordinal number for this name
                for ordinal_num, name in ordinals.items():
                    if name.lower() == ordinal_name.lower():
                        destination_ids[ordinal_num - 1] = field_id
                        break

        return destination_ids

    def _find_mappings_from_refs(
        self,
        source_field_name: str,
        ordinals: Dict[int, str],
        intra_panel_refs: Dict
    ) -> Dict[str, int]:
        """Find field ID mappings from intra-panel references."""
        mappings = {}

        source_lower = source_field_name.lower()

        for panel in intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                # Handle different reference structures
                if isinstance(ref, dict):
                    # Check for dependent_field structure
                    dep_field = ref.get('dependent_field', {})
                    if dep_field:
                        dep_name = dep_field.get('field_name', '')
                        refs = ref.get('references', [])

                        for r in refs:
                            ref_field = r.get('referenced_field_name', '')
                            if source_lower in ref_field.lower():
                                # This field depends on our source
                                # Try to match to ordinal names
                                field = self.field_matcher.match_field(dep_name)
                                if field:
                                    for ordinal, ordinal_name in ordinals.items():
                                        if self._fuzzy_match_ordinal(dep_name, ordinal_name):
                                            mappings[ordinal_name] = field.id
                                            break

        return mappings

    def _fuzzy_match_ordinal(self, field_name: str, ordinal_name: str) -> bool:
        """Check if field name matches an ordinal name."""
        field_lower = field_name.lower()
        ordinal_lower = ordinal_name.lower()

        # Direct match
        if ordinal_lower in field_lower or field_lower in ordinal_lower:
            return True

        # Common mappings - extensive mapping for all VERIFY types
        mappings = {
            # PAN mappings
            'pan holder name': ['fullname', 'name'],
            'pan type': ['pan type', 'type'],
            'pan status': ['pan retrieval status', 'status'],
            'aadhaar pan list status': ['aadhaar seeding status'],
            # GSTIN mappings
            'trade name': ['trade name', 'tradename'],
            'legal name': ['legal name', 'legalname', 'longname'],
            'reg date': ['reg date', 'regdate', 'registration date'],
            'city': ['city'],
            'type': ['type'],
            'building number': ['building number', 'building'],
            'flat number': ['flat number', 'flat'],
            'district': ['district code', 'district'],
            'state': ['state code', 'state'],
            'street': ['street'],
            'pincode': ['pincode', 'pin'],
            'locality': ['locality'],
            'landmark': ['landmark'],
            # BANK mappings
            'ifsc code': ['ifsccode', 'ifsc'],
            'account number': ['accountnumber', 'account'],
            'bank name': ['bankname', 'bank'],
            'beneficiary name': ['bank beneficiary name', 'beneficiary'],
            'branch': ['branch'],
            # MSME mappings
            'enterprise name': ['name of enterprise', 'enterprise'],
            'major activity': ['major activity'],
            'social category': ['social category'],
            'date of commencement': ['date of commencement', 'commencement'],
            'msme classification': ['enterprise type', 'classification'],
        }

        for key, variants in mappings.items():
            if key in field_lower:
                if any(v in ordinal_lower for v in variants):
                    return True
            # Also check reverse
            for v in variants:
                if v in field_lower and ordinal_lower in key:
                    return True

        return False

    def create_simple_destination_ids(self, field_ids: List[int]) -> List[int]:
        """Create simple destination IDs list (no ordinal mapping needed)."""
        return field_ids if field_ids else []
