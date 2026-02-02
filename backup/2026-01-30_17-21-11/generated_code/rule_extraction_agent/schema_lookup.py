"""
Schema lookup module for Rule-Schemas.json queries.

Provides fast lookup indexes for finding rule schemas by action type, source type,
and building LLM context strings for complex rules.
"""

import json
import os
from typing import Dict, List, Optional, Any
from .models import RuleSchemaInfo


class RuleSchemaLookup:
    """
    Query interface for Rule-Schemas.json (182 pre-defined rules).

    Provides fast lookup by:
    - Schema ID
    - Action type (VERIFY, OCR, etc.)
    - Source type (PAN_NUMBER, GSTIN_IMAGE, etc.)
    """

    # Known source type mappings for common document types
    DOCUMENT_TYPE_TO_SOURCE = {
        # VERIFY sources
        "PAN": "PAN_NUMBER",
        "GSTIN": "GSTIN",
        "GST": "GSTIN",
        "BANK": "BANK_ACCOUNT_NUMBER",
        "BANK_ACCOUNT": "BANK_ACCOUNT_NUMBER",
        "MSME": "MSME_UDYAM_REG_NUMBER",
        "UDYAM": "MSME_UDYAM_REG_NUMBER",
        "CIN": "CIN_ID",
        "TAN": "TAN_NUMBER",
        "FSSAI": "FSSAI",
        "GSTIN_WITH_PAN": "GSTIN_WITH_PAN",

        # OCR sources
        "PAN_IMAGE": "PAN_IMAGE",
        "GSTIN_IMAGE": "GSTIN_IMAGE",
        "AADHAAR_FRONT": "AADHAR_IMAGE",
        "AADHAAR_BACK": "AADHAR_BACK_IMAGE",
        "AADHAR": "AADHAR_IMAGE",
        "CHEQUE": "CHEQUEE",
        "CANCELLED_CHEQUE": "CHEQUEE",
        "CIN_IMAGE": "CIN",
        "MSME_IMAGE": "MSME",
    }

    # Known schema IDs for common operations
    KNOWN_SCHEMAS = {
        # VERIFY
        ("VERIFY", "PAN_NUMBER"): 360,
        ("VERIFY", "GSTIN"): 355,
        ("VERIFY", "BANK_ACCOUNT_NUMBER"): 361,
        ("VERIFY", "MSME_UDYAM_REG_NUMBER"): 337,
        ("VERIFY", "CIN_ID"): 349,
        ("VERIFY", "TAN_NUMBER"): 322,
        ("VERIFY", "FSSAI"): 356,
        ("VERIFY", "GSTIN_WITH_PAN"): 329,
        ("VERIFY", "PINCODE"): 333,

        # OCR
        ("OCR", "PAN_IMAGE"): 344,
        ("OCR", "GSTIN_IMAGE"): 347,
        ("OCR", "AADHAR_IMAGE"): 359,
        ("OCR", "AADHAR_BACK_IMAGE"): 348,
        ("OCR", "CHEQUEE"): 269,
        ("OCR", "CIN"): 357,
        ("OCR", "MSME"): 214,
    }

    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize the schema lookup.

        Args:
            schema_path: Path to Rule-Schemas.json. If None, uses default path.
        """
        if schema_path is None:
            # Try to find in standard locations
            possible_paths = [
                "/home/samart/project/doc-parser/rules/Rule-Schemas.json",
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "rules", "Rule-Schemas.json"),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    schema_path = path
                    break

        if schema_path is None or not os.path.exists(schema_path):
            raise FileNotFoundError(f"Rule-Schemas.json not found. Tried: {possible_paths}")

        self.schema_path = schema_path
        self._load_schemas()
        self._build_indexes()

    def _load_schemas(self) -> None:
        """Load schemas from JSON file."""
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.raw_schemas = data.get('content', [])

    def _build_indexes(self) -> None:
        """Build fast lookup indexes."""
        self.by_id: Dict[int, Dict] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source: Dict[str, Dict] = {}
        self.by_action_source: Dict[tuple, Dict] = {}

        for schema in self.raw_schemas:
            schema_id = schema.get('id')
            action = schema.get('action')
            source = schema.get('source')

            # Index by ID
            self.by_id[schema_id] = schema

            # Index by action
            if action not in self.by_action:
                self.by_action[action] = []
            self.by_action[action].append(schema)

            # Index by source
            if source:
                self.by_source[source] = schema

            # Index by (action, source) tuple
            if action and source:
                self.by_action_source[(action, source)] = schema

    def get_by_id(self, schema_id: int) -> Optional[RuleSchemaInfo]:
        """Get schema by ID."""
        schema = self.by_id.get(schema_id)
        if schema:
            return self._to_schema_info(schema)
        return None

    def find_by_action_and_source(self, action: str, source: str) -> Optional[RuleSchemaInfo]:
        """
        Find rule schema by action type and source type.

        Args:
            action: Action type (VERIFY, OCR, etc.)
            source: Source type (PAN_NUMBER, GSTIN_IMAGE, etc.)

        Returns:
            RuleSchemaInfo if found, None otherwise.
        """
        schema = self.by_action_source.get((action, source))
        if schema:
            return self._to_schema_info(schema)
        return None

    def find_by_document_type(self, doc_type: str, action: str = "VERIFY") -> Optional[RuleSchemaInfo]:
        """
        Find schema by document type name (e.g., "PAN", "GSTIN").

        Args:
            doc_type: Human-readable document type
            action: Expected action type (default: VERIFY)

        Returns:
            RuleSchemaInfo if found, None otherwise.
        """
        # Normalize document type
        doc_type_upper = doc_type.upper().replace(" ", "_")

        # Try direct mapping
        source = self.DOCUMENT_TYPE_TO_SOURCE.get(doc_type_upper)
        if source:
            return self.find_by_action_and_source(action, source)

        # Try known schema lookup
        for (act, src), schema_id in self.KNOWN_SCHEMAS.items():
            if act == action and doc_type_upper in src:
                return self.get_by_id(schema_id)

        return None

    def get_schemas_by_action(self, action: str) -> List[RuleSchemaInfo]:
        """Get all schemas with a given action type."""
        schemas = self.by_action.get(action, [])
        return [self._to_schema_info(s) for s in schemas]

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """
        Get mapping of destination field names to ordinal positions.

        Args:
            schema_id: Schema ID

        Returns:
            Dict mapping field name to ordinal (1-based)
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}
        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name']: f['ordinal'] for f in dest_fields}

    def get_source_field_requirements(self, schema_id: int) -> List[Dict]:
        """Get source field requirements (mandatory, etc.)."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return []
        return schema.get('sourceFields', {}).get('fields', [])

    def get_num_destination_items(self, schema_id: int) -> int:
        """Get number of destination items for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return 0
        return schema.get('destinationFields', {}).get('numberOfItems', 0)

    def build_llm_context(self, schema_id: int) -> str:
        """
        Build context string for LLM fallback.

        Args:
            schema_id: Schema ID

        Returns:
            Formatted context string for LLM prompt
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema.get('name', 'Unknown')}",
            f"Action: {schema.get('action')}",
            f"Source: {schema.get('source')}",
            f"Processing Type: {schema.get('processingType', 'SERVER')}",
            "",
            "Source Fields (input):"
        ]

        source_fields = schema.get('sourceFields', {}).get('fields', [])
        for f in source_fields:
            lines.append(f"  ordinal {f['ordinal']}: {f['name']} (mandatory: {f.get('mandatory', False)})")

        lines.append("")
        lines.append("Destination Fields (output - for mapping):")
        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        for f in dest_fields:
            lines.append(f"  ordinal {f['ordinal']}: {f['name']}")

        return "\n".join(lines)

    def find_candidates(self, logic_text: str, possible_actions: List[str]) -> List[RuleSchemaInfo]:
        """
        Find candidate schemas based on logic text and possible action types.

        Args:
            logic_text: The raw logic text
            possible_actions: List of possible action types

        Returns:
            List of candidate RuleSchemaInfo objects
        """
        candidates = []
        logic_lower = logic_text.lower()

        # Check for document type keywords
        doc_keywords = [
            ("pan", "PAN_NUMBER", "PAN_IMAGE"),
            ("gstin", "GSTIN", "GSTIN_IMAGE"),
            ("gst", "GSTIN", "GSTIN_IMAGE"),
            ("bank", "BANK_ACCOUNT_NUMBER", None),
            ("msme", "MSME_UDYAM_REG_NUMBER", "MSME"),
            ("udyam", "MSME_UDYAM_REG_NUMBER", "MSME"),
            ("cin", "CIN_ID", "CIN"),
            ("aadhaar", "AADHAR_IMAGE", "AADHAR_BACK_IMAGE"),
            ("aadhar", "AADHAR_IMAGE", "AADHAR_BACK_IMAGE"),
            ("cheque", "CHEQUEE", None),
            ("tan", "TAN_NUMBER", None),
            ("fssai", "FSSAI", None),
        ]

        for keyword, verify_source, ocr_source in doc_keywords:
            if keyword in logic_lower:
                if "VERIFY" in possible_actions and verify_source:
                    schema = self.find_by_action_and_source("VERIFY", verify_source)
                    if schema:
                        candidates.append(schema)
                if "OCR" in possible_actions and ocr_source:
                    schema = self.find_by_action_and_source("OCR", ocr_source)
                    if schema:
                        candidates.append(schema)

        return candidates

    def _to_schema_info(self, schema: Dict) -> RuleSchemaInfo:
        """Convert raw schema dict to RuleSchemaInfo."""
        source_fields = schema.get('sourceFields', {}).get('fields', [])
        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        num_dest = schema.get('destinationFields', {}).get('numberOfItems', 0)

        return RuleSchemaInfo(
            id=schema.get('id'),
            name=schema.get('name', ''),
            source=schema.get('source', ''),
            action=schema.get('action', ''),
            processing_type=schema.get('processingType', 'SERVER'),
            source_fields=source_fields,
            destination_fields=dest_fields,
            num_destination_items=num_dest,
            button=schema.get('button', ''),
            params=schema.get('params'),
        )

    def get_all_sources(self) -> List[str]:
        """Get list of all source types."""
        return list(self.by_source.keys())

    def get_all_actions(self) -> List[str]:
        """Get list of all action types."""
        return list(self.by_action.keys())
