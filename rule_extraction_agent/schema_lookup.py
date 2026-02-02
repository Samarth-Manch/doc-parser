"""Query interface for Rule-Schemas.json."""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path


class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json (182 pre-defined rules)."""

    def __init__(self, path: str = None):
        if path is None:
            # Default to rules/Rule-Schemas.json relative to project root
            path = Path(__file__).parent.parent / "rules" / "Rule-Schemas.json"

        with open(path, 'r') as f:
            data = json.load(f)

        self.schemas = data.get('content', [])
        self._build_indexes()

    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.by_id: Dict[int, Dict] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source: Dict[str, Dict] = {}
        self.by_action_source: Dict[str, Dict] = {}

        for schema in self.schemas:
            schema_id = schema.get('id')
            action = schema.get('action')
            source = schema.get('source')

            if schema_id:
                self.by_id[schema_id] = schema

            if action:
                if action not in self.by_action:
                    self.by_action[action] = []
                self.by_action[action].append(schema)

            if source:
                self.by_source[source] = schema

            if action and source:
                key = f"{action}:{source}"
                # Prefer schemas with more destination fields or SERVER processing
                existing = self.by_action_source.get(key)
                if existing:
                    # Compare: prefer SERVER over CLIENT, prefer more destination fields
                    existing_dest_count = existing.get('destinationFields', {}).get('numberOfItems', 0)
                    new_dest_count = schema.get('destinationFields', {}).get('numberOfItems', 0)
                    existing_is_server = existing.get('processingType') == 'SERVER'
                    new_is_server = schema.get('processingType') == 'SERVER'

                    # Replace if new is better
                    if (new_is_server and not existing_is_server) or \
                       (new_dest_count > existing_dest_count and new_is_server == existing_is_server):
                        self.by_action_source[key] = schema
                else:
                    self.by_action_source[key] = schema

    def find_by_id(self, schema_id: int) -> Optional[Dict]:
        """Find schema by ID."""
        return self.by_id.get(schema_id)

    def find_by_action(self, action: str) -> List[Dict]:
        """Find all schemas with given action type."""
        return self.by_action.get(action, [])

    def find_by_source(self, source: str) -> Optional[Dict]:
        """Find schema by source type."""
        return self.by_source.get(source)

    def find_by_action_and_source(self, action: str, source: str) -> Optional[Dict]:
        """Find rule schema by action type and source type."""
        key = f"{action}:{source}"
        if key in self.by_action_source:
            return self.by_action_source[key]

        # Fallback: search through schemas
        for schema in self.by_action.get(action, []):
            if schema.get('source') == source:
                return schema
        return None

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """Get mapping of destination field names to ordinal positions."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name']: f['ordinal'] for f in dest_fields}

    def get_destination_field_count(self, schema_id: int) -> int:
        """Get number of destination fields for a schema."""
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

    def get_source_field_count(self, schema_id: int) -> int:
        """Get number of required source fields."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return 1
        return schema.get('sourceFields', {}).get('numberOfItems', 1)

    def get_mandatory_source_fields(self, schema_id: int) -> List[Dict]:
        """Get mandatory source field names for a schema."""
        fields = self.get_source_field_requirements(schema_id)
        return [f for f in fields if f.get('mandatory', False)]

    def build_llm_context(self, schema_id: int) -> str:
        """Build context string for LLM fallback."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema.get('name', 'Unknown')}",
            f"Action: {schema.get('action')}",
            f"Source: {schema.get('source')}",
            f"Processing Type: {schema.get('processingType', 'CLIENT')}",
            ""
        ]

        # Source fields
        source_fields = schema.get('sourceFields', {}).get('fields', [])
        if source_fields:
            lines.append("Source Fields:")
            for f in source_fields:
                mandatory = f.get('mandatory', False)
                lines.append(f"  ordinal {f['ordinal']}: {f['name']} (mandatory: {mandatory})")
            lines.append("")

        # Destination fields
        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        if dest_fields:
            lines.append("Destination Fields:")
            for f in dest_fields:
                lines.append(f"  ordinal {f['ordinal']}: {f['name']}")
            lines.append("")

        # Button
        if schema.get('button'):
            lines.append(f"Button: {schema['button']}")

        return "\n".join(lines)

    def find_candidates(self, logic_text: str, possible_actions: List[str]) -> List[Dict]:
        """Find candidate schemas based on logic text and possible actions."""
        candidates = []
        logic_lower = logic_text.lower()

        for action in possible_actions:
            schemas = self.find_by_action(action)
            for schema in schemas:
                source = schema.get('source', '').lower()
                name = schema.get('name', '').lower()

                # Simple relevance check
                if source and source.replace('_', ' ') in logic_lower:
                    candidates.append(schema)
                elif name and any(word in logic_lower for word in name.split()):
                    candidates.append(schema)

        return candidates

    def get_all_verify_sources(self) -> List[str]:
        """Get all VERIFY source types."""
        verify_schemas = self.find_by_action('VERIFY')
        return [s.get('source') for s in verify_schemas if s.get('source')]

    def get_all_ocr_sources(self) -> List[str]:
        """Get all OCR source types."""
        ocr_schemas = self.find_by_action('OCR')
        return [s.get('source') for s in ocr_schemas if s.get('source')]


# Common schema lookups
VERIFY_SCHEMAS = {
    "PAN_NUMBER": 360,
    "GSTIN": 355,
    "BANK_ACCOUNT_NUMBER": 361,
    "MSME_UDYAM_REG_NUMBER": 337,
    "CIN_ID": 349,
    "TAN_NUMBER": 322,
    "FSSAI": 356,
}

OCR_SCHEMAS = {
    "PAN_IMAGE": 344,
    "GSTIN_IMAGE": 347,
    "AADHAR_IMAGE": 359,
    "AADHAR_BACK_IMAGE": 348,
    "CHEQUEE": 269,
    "MSME": 214,
}

# OCR to VERIFY chain mappings
OCR_VERIFY_CHAINS = {
    "PAN_IMAGE": "PAN_NUMBER",
    "GSTIN_IMAGE": "GSTIN",
    "CHEQUEE": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    "CIN": "CIN_ID",
    # Aadhaar OCR types don't have VERIFY chains
    "AADHAR_IMAGE": None,
    "AADHAR_BACK_IMAGE": None,
}
