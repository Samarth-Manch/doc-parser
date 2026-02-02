"""
Schema lookup module for querying Rule-Schemas.json.

Provides fast access to pre-defined rule schemas for OCR, verification, etc.
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json (182 pre-defined rules)."""

    # Key schema IDs
    SCHEMA_IDS = {
        # VERIFY rules
        "PAN_NUMBER": 360,
        "GSTIN": 355,
        "BANK_ACCOUNT_NUMBER": 361,
        "MSME_UDYAM_REG_NUMBER": 337,
        "CIN_ID": 349,
        "TAN_NUMBER": 322,
        "FSSAI": 356,

        # OCR rules
        "PAN_IMAGE": 344,
        "GSTIN_IMAGE": 347,
        "AADHAR_IMAGE": 359,
        "AADHAR_BACK_IMAGE": 348,
        "CHEQUEE": 269,
        "MSME": 214,
    }

    # OCR to VERIFY chain mapping
    OCR_VERIFY_CHAINS = {
        "PAN_IMAGE": "PAN_NUMBER",
        "GSTIN_IMAGE": "GSTIN",
        "CHEQUEE": "BANK_ACCOUNT_NUMBER",
        "MSME": "MSME_UDYAM_REG_NUMBER",
        "CIN": "CIN_ID",
        "AADHAR_IMAGE": None,  # No VERIFY chain
        "AADHAR_BACK_IMAGE": None,  # No VERIFY chain
    }

    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize the schema lookup.

        Args:
            schema_path: Path to Rule-Schemas.json, or None to use default.
        """
        if schema_path is None:
            # Try default paths
            possible_paths = [
                Path(__file__).parent.parent.parent.parent / "rules" / "Rule-Schemas.json",
                Path("/home/samart/project/doc-parser/rules/Rule-Schemas.json"),
            ]
            for path in possible_paths:
                if path.exists():
                    schema_path = str(path)
                    break

        self.schemas: List[Dict] = []
        self.by_id: Dict[int, Dict] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source: Dict[str, Dict] = {}

        if schema_path and Path(schema_path).exists():
            self._load_schemas(schema_path)

    def _load_schemas(self, path: str):
        """Load schemas from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        # Rule-Schemas.json is a paginated response with 'content' array
        self.schemas = data.get('content', [])
        self._build_indexes()

    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.by_id = {s['id']: s for s in self.schemas}

        for s in self.schemas:
            action = s.get('action')
            source = s.get('source')

            if action:
                if action not in self.by_action:
                    self.by_action[action] = []
                self.by_action[action].append(s)

            if source:
                self.by_source[source] = s

    def find_by_action_and_source(self, action: str, source: str) -> Optional[Dict]:
        """
        Find rule schema by action type and source type.

        Args:
            action: Action type (e.g., "VERIFY", "OCR")
            source: Source type (e.g., "PAN_NUMBER", "GSTIN_IMAGE")

        Returns:
            Schema dict or None if not found.
        """
        for schema in self.by_action.get(action, []):
            if schema.get('source') == source:
                return schema
        return None

    def find_by_source(self, source: str) -> Optional[Dict]:
        """
        Find schema by source type.

        Args:
            source: Source type (e.g., "PAN_NUMBER")

        Returns:
            Schema dict or None.
        """
        return self.by_source.get(source)

    def get_schema_by_id(self, schema_id: int) -> Optional[Dict]:
        """Get schema by ID."""
        return self.by_id.get(schema_id)

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """
        Get mapping of destination field names to ordinal positions.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json

        Returns:
            Dict mapping field name to ordinal position.
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name']: f['ordinal'] for f in dest_fields}

    def get_destination_field_count(self, schema_id: int) -> int:
        """Get the number of destination fields for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return 0
        return schema.get('destinationFields', {}).get('numberOfItems', 0)

    def get_source_field_requirements(self, schema_id: int) -> List[Dict]:
        """
        Get source field requirements (mandatory, etc.).

        Args:
            schema_id: Schema ID

        Returns:
            List of source field definitions.
        """
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

    def get_processing_type(self, schema_id: int) -> str:
        """Get the processing type for a schema."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return "CLIENT"
        return schema.get('processingType', 'CLIENT')

    def get_verify_chain_target(self, ocr_source: str) -> Optional[str]:
        """
        Get the VERIFY source type that should be chained to an OCR rule.

        Args:
            ocr_source: OCR source type (e.g., "PAN_IMAGE")

        Returns:
            VERIFY source type (e.g., "PAN_NUMBER") or None.
        """
        return self.OCR_VERIFY_CHAINS.get(ocr_source)

    def build_llm_context(self, schema_id: int) -> str:
        """
        Build context string for LLM fallback.

        Args:
            schema_id: Schema ID to build context for.

        Returns:
            Formatted string with schema details.
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema.get('name', 'N/A')}",
            f"Action: {schema.get('action', 'N/A')}",
            f"Source: {schema.get('source', 'N/A')}",
            f"Processing Type: {schema.get('processingType', 'N/A')}",
            "",
            "Source Fields:",
        ]

        for f in schema.get('sourceFields', {}).get('fields', []):
            lines.append(
                f"  ordinal {f['ordinal']}: {f['name']} (mandatory: {f.get('mandatory', False)})"
            )

        lines.append("")
        lines.append("Destination Fields:")
        for f in schema.get('destinationFields', {}).get('fields', []):
            lines.append(f"  ordinal {f['ordinal']}: {f['name']}")

        if schema.get('button'):
            lines.append("")
            lines.append(f"Button: {schema['button']}")

        return "\n".join(lines)

    def detect_verify_type(self, logic_text: str) -> Optional[Tuple[str, int]]:
        """
        Detect VERIFY type from logic text.

        Args:
            logic_text: Logic statement from BUD

        Returns:
            Tuple of (source_type, schema_id) or None.
        """
        if not logic_text:
            return None

        logic_lower = logic_text.lower()

        # Skip destination fields ("Data will come from X validation")
        if re.search(r"data\s+will\s+come\s+from", logic_lower):
            return None

        # Check for verification keywords
        if not re.search(r"(perform|validate|verify|validation|verification)", logic_lower):
            return None

        # Detect document type
        patterns = {
            r"bank\s*(account)?.*validation|validate.*bank|verify.*bank|bank.*verification|ifsc.*validat": ("BANK_ACCOUNT_NUMBER", 361),
            r"msme|udyam.*validation|validate.*msme|verify.*msme": ("MSME_UDYAM_REG_NUMBER", 337),
            r"pan\s*validation|validate\s*pan|verify\s*pan|perform\s*pan": ("PAN_NUMBER", 360),
            r"gstin?\s*validation|validate\s*gstin?|verify\s*gstin?|perform\s*gstin?": ("GSTIN", 355),
            r"cin\s*validation|validate\s*cin|verify\s*cin": ("CIN_ID", 349),
            r"tan\s*validation|validate\s*tan|verify\s*tan": ("TAN_NUMBER", 322),
            r"fssai\s*validation|validate\s*fssai|verify\s*fssai": ("FSSAI", 356),
        }

        for pattern, (source_type, schema_id) in patterns.items():
            if re.search(pattern, logic_lower):
                return (source_type, schema_id)

        return None

    def detect_ocr_type(self, field_name: str, logic_text: str) -> Optional[Tuple[str, int]]:
        """
        Detect OCR type from field name and logic.

        Args:
            field_name: Name of the field
            logic_text: Logic statement

        Returns:
            Tuple of (source_type, schema_id) or None.
        """
        combined = f"{field_name} {logic_text}".lower()

        # Must have OCR keywords OR be a file upload
        if not re.search(r"ocr|extract|scan|upload|file|image", combined):
            return None

        patterns = {
            r"upload\s*pan|pan\s*(?:image|upload|file)|pan.*ocr": ("PAN_IMAGE", 344),
            r"upload\s*gstin|gstin\s*(?:image|upload|file)|gstin.*ocr": ("GSTIN_IMAGE", 347),
            r"aadhaar?\s*front|front\s*aadhaar?": ("AADHAR_IMAGE", 359),
            r"aadhaar?\s*back|back\s*aadhaar?": ("AADHAR_BACK_IMAGE", 348),
            r"cheque|cancelled\s*cheque": ("CHEQUEE", 269),
            r"cin\s*(?:image|upload|file)|upload\s*cin": ("CIN", None),
            r"msme\s*(?:image|upload|file)|upload\s*msme|udyam\s*(?:image|upload)": ("MSME", 214),
        }

        for pattern, (source_type, schema_id) in patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                return (source_type, schema_id)

        return None

    def get_verify_destination_fields(self, source_type: str) -> Dict[str, int]:
        """
        Get destination field ordinals for a VERIFY rule.

        Args:
            source_type: VERIFY source type (e.g., "PAN_NUMBER")

        Returns:
            Dict mapping field name to ordinal position.
        """
        schema_id = self.SCHEMA_IDS.get(source_type)
        if not schema_id:
            return {}
        return self.get_destination_ordinals(schema_id)

    def get_ocr_destination_fields(self, source_type: str) -> Dict[str, int]:
        """
        Get destination field ordinals for an OCR rule.

        Args:
            source_type: OCR source type (e.g., "PAN_IMAGE")

        Returns:
            Dict mapping field name to ordinal position.
        """
        schema_id = self.SCHEMA_IDS.get(source_type)
        if not schema_id:
            return {}
        return self.get_destination_ordinals(schema_id)
