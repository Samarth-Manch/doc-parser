"""
Rule Schema Lookup - Query interface for Rule-Schemas.json.

Provides access to the 182 pre-defined rule schemas for:
- OCR rules (PAN_IMAGE, GSTIN_IMAGE, CHEQUEE, etc.)
- VERIFY rules (PAN_NUMBER, GSTIN, BANK_ACCOUNT_NUMBER, etc.)
- Other rule types

Key functionality:
- Find schemas by action type and source type
- Get destination field ordinal mappings
- Build destinationIds arrays with -1 for unmapped positions
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from .models import RuleSchema, RuleSchemaDestField, RuleSchemaSourceField


class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json (182 pre-defined rules)."""

    # Key schema IDs for common rule types
    SCHEMA_IDS = {
        # OCR Rules
        "PAN_IMAGE": 344,
        "GSTIN_IMAGE": 347,
        "CHEQUEE": 269,
        "MSME": 214,
        "CIN": 357,
        "AADHAR_IMAGE": 359,
        "AADHAR_BACK_IMAGE": 348,

        # VERIFY Rules
        "PAN_NUMBER": 360,
        "GSTIN": 355,
        "BANK_ACCOUNT_NUMBER": 361,
        "MSME_UDYAM_REG_NUMBER": 337,
        "CIN_ID": 349,
    }

    def __init__(self, path: str = None):
        """
        Initialize schema lookup.

        Args:
            path: Path to Rule-Schemas.json. If None, uses default location.
        """
        if path is None:
            # Try multiple locations
            possible_paths = [
                Path(__file__).parent.parent.parent.parent.parent / "rules" / "Rule-Schemas.json",
                Path("/home/samart/project/doc-parser/rules/Rule-Schemas.json"),
            ]
            for p in possible_paths:
                if p.exists():
                    path = str(p)
                    break
            if path is None:
                raise FileNotFoundError("Rule-Schemas.json not found")

        with open(path, 'r') as f:
            data = json.load(f)

        self.schemas: List[Dict] = data.get('content', [])
        self._build_indexes()

    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.by_id: Dict[int, Dict] = {}
        self.by_source: Dict[str, List[Dict]] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source_and_action: Dict[Tuple[str, str], Dict] = {}

        for schema in self.schemas:
            schema_id = schema.get('id')
            source = schema.get('source', '')
            action = schema.get('action', '')

            self.by_id[schema_id] = schema

            if source not in self.by_source:
                self.by_source[source] = []
            self.by_source[source].append(schema)

            if action not in self.by_action:
                self.by_action[action] = []
            self.by_action[action].append(schema)

            # Index by (source, action) tuple
            key = (source, action)
            if key not in self.by_source_and_action:
                self.by_source_and_action[key] = schema

    def get_schema_by_id(self, schema_id: int) -> Optional[Dict]:
        """Get schema by ID."""
        return self.by_id.get(schema_id)

    def find_by_source(self, source: str) -> List[Dict]:
        """Find all schemas with given source type."""
        return self.by_source.get(source, [])

    def find_by_action(self, action: str) -> List[Dict]:
        """Find all schemas with given action type."""
        return self.by_action.get(action, [])

    def find_by_source_and_action(self, source: str, action: str) -> Optional[Dict]:
        """
        Find schema by source type and action type.

        Args:
            source: Source type (e.g., "PAN_NUMBER", "PAN_IMAGE")
            action: Action type (e.g., "VERIFY", "OCR")

        Returns:
            Schema dict or None if not found
        """
        return self.by_source_and_action.get((source, action))

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """
        Get mapping of destination field names to ordinal positions.

        Args:
            schema_id: Rule schema ID

        Returns:
            Dict mapping field name -> ordinal (1-indexed)
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name']: f['ordinal'] for f in dest_fields}

    def get_num_destination_fields(self, schema_id: int) -> int:
        """Get the number of destination fields for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return 0
        return schema.get('destinationFields', {}).get('numberOfItems', 0)

    def get_source_field_requirements(self, schema_id: int) -> List[Dict]:
        """Get source field requirements (mandatory, etc.)."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return []
        return schema.get('sourceFields', {}).get('fields', [])

    def get_button_text(self, schema_id: int) -> str:
        """Get the button text for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""
        return schema.get('button', '')

    def build_destination_ids_array(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]
    ) -> List[int]:
        """
        Build destinationIds array with -1 for unused ordinals.

        Args:
            schema_id: Rule schema ID (e.g., 360 for PAN Validation)
            field_mappings: Dict mapping schema field names to BUD field IDs
                           e.g., {"Fullname": 275535, "Pan type": 275536}

        Returns:
            List of field IDs indexed by ordinal position (ordinal 1 -> index 0)
            Unmatched ordinals will have -1

        Example:
            schema_id = 360  # PAN Validation (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Build name -> ordinal mapping (case-insensitive)
        name_to_ordinal = {}
        for f in dest_fields:
            name_to_ordinal[f['name'].lower()] = f['ordinal']

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            ordinal = name_to_ordinal.get(field_name.lower())
            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 -> index 0

        return destination_ids

    def get_schema_info(self, source_type: str) -> Optional[RuleSchema]:
        """
        Get RuleSchema object for a source type.

        Args:
            source_type: Source type (e.g., "PAN_NUMBER", "PAN_IMAGE")

        Returns:
            RuleSchema object or None
        """
        schemas = self.find_by_source(source_type)
        if not schemas:
            return None

        # Prefer SERVER processing type for VERIFY/OCR
        schema = schemas[0]
        for s in schemas:
            if s.get('processingType') == 'SERVER':
                schema = s
                break

        dest_fields = []
        for f in schema.get('destinationFields', {}).get('fields', []):
            dest_fields.append(RuleSchemaDestField(
                name=f['name'],
                ordinal=f['ordinal'],
                mandatory=f.get('mandatory', False)
            ))

        src_fields = []
        for f in schema.get('sourceFields', {}).get('fields', []):
            src_fields.append(RuleSchemaSourceField(
                name=f['name'],
                ordinal=f['ordinal'],
                mandatory=f.get('mandatory', False)
            ))

        return RuleSchema(
            id=schema['id'],
            name=schema['name'],
            source=schema['source'],
            action=schema['action'],
            processing_type=schema.get('processingType', 'SERVER'),
            destination_fields=dest_fields,
            source_fields=src_fields,
            button=schema.get('button', ''),
            num_destination_fields=schema.get('destinationFields', {}).get('numberOfItems', 0)
        )

    def build_llm_context(self, source_type: str) -> str:
        """
        Build context string for LLM fallback.

        Args:
            source_type: Source type to get schema for

        Returns:
            Formatted context string for LLM
        """
        schema_info = self.get_schema_info(source_type)
        if not schema_info:
            return f"No schema found for source type: {source_type}"

        lines = [
            f"Rule Schema ID: {schema_info.id}",
            f"Name: {schema_info.name}",
            f"Action: {schema_info.action}",
            f"Source: {schema_info.source}",
            f"Processing Type: {schema_info.processing_type}",
            "",
        ]

        if schema_info.source_fields:
            lines.append("Source Fields:")
            for f in schema_info.source_fields:
                lines.append(f"  ordinal {f.ordinal}: {f.name} (mandatory: {f.mandatory})")
            lines.append("")

        if schema_info.destination_fields:
            lines.append(f"Destination Fields ({schema_info.num_destination_fields}):")
            for f in schema_info.destination_fields:
                lines.append(f"  ordinal {f.ordinal}: {f.name}")

        if schema_info.button:
            lines.append("")
            lines.append(f"Button: {schema_info.button}")

        return "\n".join(lines)


# OCR -> VERIFY chain mappings
OCR_VERIFY_CHAINS = {
    # OCR sourceType -> VERIFY sourceType
    "PAN_IMAGE": "PAN_NUMBER",
    "GSTIN_IMAGE": "GSTIN",
    "CHEQUEE": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    "CIN": "CIN_ID",
    "AADHAR_IMAGE": None,      # Aadhaar Front - no VERIFY chain
    "AADHAR_BACK_IMAGE": None, # Aadhaar Back - no VERIFY chain
}


def get_verify_source_for_ocr(ocr_source_type: str) -> Optional[str]:
    """Get the VERIFY source type that chains from an OCR source type."""
    return OCR_VERIFY_CHAINS.get(ocr_source_type)
