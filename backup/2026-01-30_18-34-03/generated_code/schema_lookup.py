"""
Schema Lookup - Query interface for Rule-Schemas.json.

Provides lookup for 182 pre-defined rules including VERIFY, OCR, etc.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path


# Mapping from document type to source types
DOC_TYPE_TO_VERIFY_SOURCE = {
    "PAN": "PAN_NUMBER",
    "GSTIN": "GSTIN",
    "BANK": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    "CIN": "CIN_ID",
    "TAN": "TAN_NUMBER",
    "FSSAI": "FSSAI",
}

DOC_TYPE_TO_OCR_SOURCE = {
    "PAN": "PAN_IMAGE",
    "GSTIN": "GSTIN_IMAGE",
    "AADHAAR_FRONT": "AADHAR_IMAGE",
    "AADHAAR_BACK": "AADHAR_BACK_IMAGE",
    "CHEQUE": "CHEQUEE",
    "MSME": "MSME",
    "CIN": "CIN",
}

# Common schema IDs for quick lookup
SCHEMA_IDS = {
    # VERIFY rules
    "VERIFY_PAN": 360,
    "VERIFY_GSTIN": 355,
    "VERIFY_BANK": 361,
    "VERIFY_MSME": 337,
    "VERIFY_CIN": 349,
    "VERIFY_TAN": 322,
    "VERIFY_FSSAI": 356,
    "VERIFY_GSTIN_WITH_PAN": 296,

    # OCR rules
    "OCR_PAN": 344,
    "OCR_GSTIN": 347,
    "OCR_AADHAAR_FRONT": 359,
    "OCR_AADHAAR_BACK": 348,
    "OCR_CHEQUE": 269,
    "OCR_MSME": 214,
    "OCR_CIN": 357,
}


class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json (182 pre-defined rules)."""

    def __init__(self, schema_path: str = None):
        """
        Initialize with path to Rule-Schemas.json.

        Args:
            schema_path: Path to Rule-Schemas.json. If None, uses default location.
        """
        if schema_path is None:
            # Try to find in common locations
            possible_paths = [
                Path("/home/samart/project/doc-parser/rules/Rule-Schemas.json"),
                Path("rules/Rule-Schemas.json"),
                Path("../rules/Rule-Schemas.json"),
            ]
            for path in possible_paths:
                if path.exists():
                    schema_path = str(path)
                    break

        if schema_path is None:
            raise FileNotFoundError("Could not find Rule-Schemas.json")

        with open(schema_path, 'r') as f:
            data = json.load(f)

        self.schemas = data.get('content', [])
        self._build_indexes()

    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.by_id: Dict[int, Dict] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source: Dict[str, List[Dict]] = {}
        self.by_name: Dict[str, Dict] = {}

        for schema in self.schemas:
            schema_id = schema.get('id')
            action = schema.get('action')
            source = schema.get('source')
            name = schema.get('name', '')

            if schema_id:
                self.by_id[schema_id] = schema

            if action:
                if action not in self.by_action:
                    self.by_action[action] = []
                self.by_action[action].append(schema)

            if source:
                if source not in self.by_source:
                    self.by_source[source] = []
                self.by_source[source].append(schema)

            if name:
                self.by_name[name.lower()] = schema

    def get_by_id(self, schema_id: int) -> Optional[Dict]:
        """Get rule schema by ID."""
        return self.by_id.get(schema_id)

    def find_by_action_and_source(self, action: str, source: str) -> Optional[Dict]:
        """
        Find rule schema by action type and source type.

        Args:
            action: Action type (e.g., "VERIFY", "OCR")
            source: Source type (e.g., "PAN_NUMBER", "GSTIN_IMAGE")

        Returns:
            Matching schema dict or None
        """
        for schema in self.by_action.get(action, []):
            if schema.get('source') == source:
                return schema
        return None

    def find_verify_schema(self, doc_type: str) -> Optional[Dict]:
        """
        Find VERIFY schema for a document type.

        Args:
            doc_type: Document type (e.g., "PAN", "GSTIN", "BANK")

        Returns:
            Matching VERIFY schema or None
        """
        source = DOC_TYPE_TO_VERIFY_SOURCE.get(doc_type.upper())
        if source:
            return self.find_by_action_and_source("VERIFY", source)
        return None

    def find_ocr_schema(self, doc_type: str) -> Optional[Dict]:
        """
        Find OCR schema for a document type.

        Args:
            doc_type: Document type (e.g., "PAN", "GSTIN", "AADHAAR_FRONT")

        Returns:
            Matching OCR schema or None
        """
        source = DOC_TYPE_TO_OCR_SOURCE.get(doc_type.upper())
        if source:
            return self.find_by_action_and_source("OCR", source)
        return None

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """
        Get mapping of destination field names to ordinal positions.

        Args:
            schema_id: Rule schema ID

        Returns:
            Dict mapping field name (lowercase) to ordinal position
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name'].lower(): f['ordinal'] for f in dest_fields}

    def get_destination_field_count(self, schema_id: int) -> int:
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

    def get_source_field_count(self, schema_id: int) -> int:
        """Get the number of source fields for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return 0
        return schema.get('sourceFields', {}).get('numberOfItems', 0)

    def get_button_text(self, schema_id: int) -> str:
        """Get the button text for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""
        return schema.get('button', '')

    def get_processing_type(self, schema_id: int) -> str:
        """Get the processing type for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return "CLIENT"
        return schema.get('processingType', 'CLIENT')

    def build_llm_context(self, schema_id: int) -> str:
        """
        Build context string for LLM fallback.

        Args:
            schema_id: Rule schema ID

        Returns:
            Formatted string with schema details for LLM context
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema.get('name', 'Unknown')}",
            f"Action: {schema.get('action', 'Unknown')}",
            f"Source: {schema.get('source', 'Unknown')}",
            f"Processing Type: {schema.get('processingType', 'Unknown')}",
            "",
            "Source Fields:"
        ]

        for f in schema.get('sourceFields', {}).get('fields', []):
            lines.append(f"  ordinal {f['ordinal']}: {f['name']} (mandatory: {f.get('mandatory', False)})")

        lines.append("")
        lines.append("Destination Fields:")
        for f in schema.get('destinationFields', {}).get('fields', []):
            lines.append(f"  ordinal {f['ordinal']}: {f['name']}")

        return "\n".join(lines)

    def list_verify_schemas(self) -> List[Dict]:
        """List all VERIFY schemas."""
        return self.by_action.get('VERIFY', [])

    def list_ocr_schemas(self) -> List[Dict]:
        """List all OCR schemas."""
        return self.by_action.get('OCR', [])

    def get_schema_id_for_doc_type(self, doc_type: str, rule_type: str) -> Optional[int]:
        """
        Get schema ID for a document type and rule type.

        Args:
            doc_type: Document type (PAN, GSTIN, BANK, etc.)
            rule_type: Rule type (VERIFY, OCR)

        Returns:
            Schema ID or None
        """
        key = f"{rule_type}_{doc_type}".upper()
        return SCHEMA_IDS.get(key)
