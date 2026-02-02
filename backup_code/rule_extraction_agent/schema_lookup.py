"""
Schema Lookup - Query interface for Rule-Schemas.json (182 pre-defined rules).
"""

import json
from typing import Dict, List, Optional, Any


class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json."""

    # Known schema IDs for common rules
    KNOWN_SCHEMAS = {
        'PAN_NUMBER': 360,
        'GSTIN': 355,
        'BANK_ACCOUNT_NUMBER': 361,
        'MSME_UDYAM_REG_NUMBER': 337,
        'CIN_ID': 349,
        'TAN_NUMBER': 322,
        'FSSAI': 356,
        'PAN_IMAGE': 344,
        'GSTIN_IMAGE': 347,
        'AADHAR_BACK_IMAGE': 348,
        'AADHAR_IMAGE': 359,
        'CHEQUEE': 269,
        'MSME': 214,
    }

    # OCR -> VERIFY chain mappings
    OCR_VERIFY_CHAINS = {
        'PAN_IMAGE': 'PAN_NUMBER',
        'GSTIN_IMAGE': 'GSTIN',
        'CHEQUEE': 'BANK_ACCOUNT_NUMBER',
        'MSME': 'MSME_UDYAM_REG_NUMBER',
        'CIN': 'CIN_ID',
        'AADHAR_IMAGE': None,  # No direct VERIFY
        'AADHAR_BACK_IMAGE': None,
    }

    # Destination ordinal mappings for VERIFY rules
    VERIFY_ORDINAL_MAPPINGS = {
        'PAN_NUMBER': {
            1: 'Panholder title',
            2: 'Firstname',
            3: 'Lastname',
            4: 'Fullname',
            5: 'Last updated',
            6: 'Pan retrieval status',
            7: 'Fullname without title',
            8: 'Pan type',
            9: 'Aadhaar seeding status',
            10: 'Middle name',
        },
        'CHEQUEE': {
            1: 'bankName',
            2: 'ifscCode',
            3: 'beneficiaryName',
            4: 'accountNumber',
            5: 'address',
            6: 'micrCode',
            7: 'branch',
        },
        'AADHAR_BACK_IMAGE': {
            1: 'aadharAddress1',
            2: 'aadharAddress2',
            3: 'aadharPin',
            4: 'aadharCity',
            5: 'aadharDist',
            6: 'aadharState',
            7: 'aadharFatherName',
            8: 'aadharCountry',
            9: 'aadharCoords',
        },
    }

    def __init__(self, path: str = "rules/Rule-Schemas.json"):
        """Initialize with path to Rule-Schemas.json."""
        self.path = path
        self.schemas: List[Dict] = []
        self.by_id: Dict[int, Dict] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source: Dict[str, Dict] = {}

        try:
            self._load_schemas()
        except FileNotFoundError:
            print(f"Warning: Rule-Schemas.json not found at {path}")

    def _load_schemas(self):
        """Load and index schemas from JSON file."""
        with open(self.path, 'r') as f:
            data = json.load(f)

        self.schemas = data.get('content', [])
        self._build_indexes()

    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.by_id = {}
        self.by_action = {}
        self.by_source = {}

        for schema in self.schemas:
            schema_id = schema.get('id')
            action = schema.get('action', '')
            source = schema.get('source', '')

            # Index by ID
            if schema_id:
                self.by_id[schema_id] = schema

            # Index by action
            if action:
                if action not in self.by_action:
                    self.by_action[action] = []
                self.by_action[action].append(schema)

            # Index by source
            if source:
                self.by_source[source] = schema

    def get_schema_by_id(self, schema_id: int) -> Optional[Dict]:
        """Get schema by ID."""
        return self.by_id.get(schema_id)

    def find_by_action_and_source(self, action: str, source: str) -> Optional[Dict]:
        """Find rule schema by action type and source type."""
        for schema in self.by_action.get(action, []):
            if schema.get('source') == source:
                return schema
        return None

    def find_by_source(self, source: str) -> Optional[Dict]:
        """Find schema by source type."""
        return self.by_source.get(source)

    def get_schema_id_for_source(self, source: str) -> Optional[int]:
        """Get schema ID for a given source type."""
        # Check known mappings first
        if source in self.KNOWN_SCHEMAS:
            return self.KNOWN_SCHEMAS[source]

        # Fall back to lookup
        schema = self.by_source.get(source)
        return schema.get('id') if schema else None

    def get_destination_ordinals(self, schema_id: int) -> Dict[int, str]:
        """Get mapping of ordinal positions to destination field names."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {})
        fields = dest_fields.get('fields', [])

        return {f['ordinal']: f['name'] for f in fields if 'ordinal' in f}

    def get_destination_field_count(self, schema_id: int) -> int:
        """Get the number of destination fields for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return 0

        dest_fields = schema.get('destinationFields', {})
        return dest_fields.get('numberOfItems', 0)

    def get_source_field_requirements(self, schema_id: int) -> List[Dict]:
        """Get source field requirements (mandatory, etc.)."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return []

        source_fields = schema.get('sourceFields', {})
        return source_fields.get('fields', [])

    def get_verify_source_for_ocr(self, ocr_source: str) -> Optional[str]:
        """Get the VERIFY source type that corresponds to an OCR source type."""
        return self.OCR_VERIFY_CHAINS.get(ocr_source)

    def build_llm_context(self, schema_id: int) -> str:
        """Build context string for LLM fallback."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema.get('name', 'Unknown')}",
            f"Action: {schema.get('action', 'N/A')}",
            f"Source: {schema.get('source', 'N/A')}",
            "",
            "Source Fields:"
        ]

        source_fields = schema.get('sourceFields', {}).get('fields', [])
        for f in source_fields:
            mandatory = f.get('mandatory', False)
            lines.append(f"  ordinal {f.get('ordinal', '?')}: {f.get('name', 'Unknown')} (mandatory: {mandatory})")

        lines.append("")
        lines.append("Destination Fields:")
        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        for f in dest_fields:
            lines.append(f"  ordinal {f.get('ordinal', '?')}: {f.get('name', 'Unknown')}")

        return "\n".join(lines)

    def find_candidates(self, logic_text: str, possible_actions: List[str]) -> List[Dict]:
        """Find candidate schemas based on logic text and possible actions."""
        candidates = []
        logic_lower = logic_text.lower()

        # Check for specific document types
        doc_keywords = {
            'pan': ['PAN_NUMBER', 'PAN_IMAGE'],
            'gstin': ['GSTIN', 'GSTIN_IMAGE'],
            'gst': ['GSTIN', 'GSTIN_IMAGE'],
            'aadhaar': ['AADHAR_IMAGE', 'AADHAR_BACK_IMAGE'],
            'aadhar': ['AADHAR_IMAGE', 'AADHAR_BACK_IMAGE'],
            'bank': ['BANK_ACCOUNT_NUMBER', 'CHEQUEE'],
            'cheque': ['CHEQUEE', 'BANK_ACCOUNT_NUMBER'],
            'msme': ['MSME_UDYAM_REG_NUMBER', 'MSME'],
            'udyam': ['MSME_UDYAM_REG_NUMBER', 'MSME'],
            'cin': ['CIN_ID', 'CIN'],
            'tan': ['TAN_NUMBER'],
            'fssai': ['FSSAI'],
        }

        for keyword, sources in doc_keywords.items():
            if keyword in logic_lower:
                for source in sources:
                    schema = self.by_source.get(source)
                    if schema and schema not in candidates:
                        candidates.append(schema)

        # Also check by action type
        for action in possible_actions:
            for schema in self.by_action.get(action, []):
                if schema not in candidates:
                    candidates.append(schema)

        return candidates[:10]  # Limit to first 10

    def get_all_ocr_sources(self) -> List[str]:
        """Get all OCR source types."""
        return [source for source, chain in self.OCR_VERIFY_CHAINS.items() if chain is not None]

    def get_all_verify_sources(self) -> List[str]:
        """Get all VERIFY source types."""
        verify_schemas = self.by_action.get('VERIFY', [])
        return [s.get('source') for s in verify_schemas if s.get('source')]
