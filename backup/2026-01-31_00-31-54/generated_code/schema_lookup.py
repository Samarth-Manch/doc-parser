"""
Rule Schema Lookup Module

Provides query interface for Rule-Schemas.json containing 182 pre-defined rules.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path


class RuleSchemaLookup:
    """
    Query interface for Rule-Schemas.json (182 pre-defined rules).

    The Rule-Schemas.json file is a paginated response with 'content' array
    containing all pre-defined rules with their sourceFields and destinationFields.
    """

    def __init__(self, path: str = None):
        """
        Initialize the schema lookup.

        Args:
            path: Path to Rule-Schemas.json file
        """
        if path is None:
            # Default path relative to project root
            path = Path(__file__).parent.parent.parent.parent / "rules" / "Rule-Schemas.json"

        self.path = Path(path)
        self.schemas: List[Dict] = []
        self.by_id: Dict[int, Dict] = {}
        self.by_action: Dict[str, List[Dict]] = {}
        self.by_source: Dict[str, List[Dict]] = {}

        self._load_schemas()
        self._build_indexes()

    def _load_schemas(self):
        """Load schemas from JSON file."""
        if not self.path.exists():
            print(f"Warning: Rule-Schemas.json not found at {self.path}")
            return

        with open(self.path, 'r') as f:
            data = json.load(f)

        # The file has a 'content' array containing all rules
        self.schemas = data.get('content', [])

    def _build_indexes(self):
        """Build fast lookup indexes."""
        for schema in self.schemas:
            # Index by ID
            schema_id = schema.get('id')
            if schema_id:
                self.by_id[schema_id] = schema

            # Index by action
            action = schema.get('action')
            if action:
                if action not in self.by_action:
                    self.by_action[action] = []
                self.by_action[action].append(schema)

            # Index by source
            source = schema.get('source')
            if source:
                if source not in self.by_source:
                    self.by_source[source] = []
                self.by_source[source].append(schema)

    def find_by_action_and_source(self, action: str, source: str) -> Optional[Dict]:
        """
        Find rule schema by action type and source type.

        Args:
            action: Action type (e.g., "VERIFY", "OCR")
            source: Source type (e.g., "PAN_NUMBER", "PAN_IMAGE")

        Returns:
            Matching schema or None
        """
        for schema in self.by_action.get(action, []):
            if schema.get('source') == source:
                return schema
        return None

    def get_schema_by_id(self, schema_id: int) -> Optional[Dict]:
        """Get schema by ID."""
        return self.by_id.get(schema_id)

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """
        Get mapping of destination field names to ordinal positions.

        Args:
            schema_id: Rule schema ID

        Returns:
            Dict mapping field name to ordinal (1-based)
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}

        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name']: f['ordinal'] for f in dest_fields}

    def get_destination_count(self, schema_id: int) -> int:
        """
        Get the number of destination fields for a schema.

        Args:
            schema_id: Rule schema ID

        Returns:
            Number of destination fields (numberOfItems)
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return 0

        return schema.get('destinationFields', {}).get('numberOfItems', 0)

    def get_source_field_requirements(self, schema_id: int) -> List[Dict]:
        """
        Get source field requirements (mandatory, etc.).

        Args:
            schema_id: Rule schema ID

        Returns:
            List of source field specifications
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return []
        return schema.get('sourceFields', {}).get('fields', [])

    def build_llm_context(self, schema_id: int) -> str:
        """
        Build context string for LLM fallback.

        Args:
            schema_id: Rule schema ID

        Returns:
            Formatted context string with schema details
        """
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema.get('name', 'Unknown')}",
            f"Action: {schema.get('action', 'Unknown')}",
            f"Source: {schema.get('source', 'Unknown')}",
            "",
            "Source Fields:"
        ]

        for f in schema.get('sourceFields', {}).get('fields', []):
            lines.append(f"  ordinal {f.get('ordinal', '?')}: {f.get('name', '?')} (mandatory: {f.get('mandatory', False)})")

        lines.append("")
        lines.append("Destination Fields:")
        for f in schema.get('destinationFields', {}).get('fields', []):
            lines.append(f"  ordinal {f.get('ordinal', '?')}: {f.get('name', '?')}")

        return "\n".join(lines)

    def find_candidates(self, logic_text: str, action_types: List[str]) -> List[Dict]:
        """
        Find candidate schemas based on logic text and possible action types.

        Args:
            logic_text: The logic statement being analyzed
            action_types: List of possible action types

        Returns:
            List of potentially matching schemas
        """
        candidates = []
        for action in action_types:
            if action in self.by_action:
                candidates.extend(self.by_action[action])
        return candidates


# Pre-defined destination field mappings for common VERIFY rules
# These map schema field names to typical BUD field name patterns

PAN_VERIFY_DESTINATION_MAPPINGS = {
    # Schema field name -> list of possible BUD field name patterns
    "Panholder title": ["pan holder title", "title"],
    "Firstname": ["first name", "firstname"],
    "Lastname": ["last name", "lastname"],
    "Fullname": ["pan holder name", "name as per pan", "full name", "fullname"],
    "Last updated": ["last updated"],
    "Pan retrieval status": ["pan status", "pan retrieval status", "status"],
    "Fullname without title": ["name without title"],
    "Pan type": ["pan type", "type"],
    "Aadhaar seeding status": ["aadhaar pan list status", "aadhaar seeding status", "aadhaar status"],
    "Middle name": ["middle name", "middlename"]
}

GSTIN_VERIFY_DESTINATION_MAPPINGS = {
    "Trade name": ["trade name", "tradename"],
    "Longname": ["legal name", "longname", "legal name as per gst"],
    "Reg date": ["reg date", "registration date", "gst registration date"],
    "City": ["city"],
    "Type": ["type", "gst type"],
    "Building number": ["building number", "building no", "building"],
    "Flat number": ["flat number", "flat no"],
    "District code": ["district", "district code"],
    "Pin": ["pin code", "pincode", "postal code"],
    "State": ["state", "state name"],
    "Street": ["street", "street name"],
}

BANK_VERIFY_DESTINATION_MAPPINGS = {
    "Bank Beneficiary Name": ["beneficiary name", "bank beneficiary name", "account holder name"],
    "Bank Reference": ["bank reference", "reference"],
    "Verification Status": ["verification status", "bank verification status"],
    "Message": ["message", "verification message"]
}

CHEQUE_OCR_DESTINATION_MAPPINGS = {
    "bankName": ["bank name", "bankname"],
    "ifscCode": ["ifsc code", "ifsc", "ifsccode"],
    "beneficiaryName": ["beneficiary name", "account holder name"],
    "accountNumber": ["account number", "bank account number", "accountnumber"],
    "address": ["bank address", "branch address"],
    "micrCode": ["micr code", "micr"],
    "branch": ["branch", "bank branch"]
}

AADHAAR_BACK_OCR_DESTINATION_MAPPINGS = {
    "aadharAddress1": ["street", "address 1", "address line 1"],
    "aadharAddress2": ["street 1", "address 2", "address line 2"],
    "aadharPin": ["postal code", "pin code", "pincode"],
    "aadharCity": ["city"],
    "aadharDist": ["district"],
    "aadharState": ["state"],
    "aadharFatherName": ["father name", "fathers name"],
    "aadharCountry": ["country"],
    "aadharCoords": ["coordinates"]
}


def get_destination_mappings_for_source(source_type: str) -> Dict[str, List[str]]:
    """
    Get the destination field mappings for a given source type.

    Args:
        source_type: The source type (e.g., "PAN_NUMBER", "GSTIN")

    Returns:
        Dict mapping schema field names to possible BUD field patterns
    """
    mappings = {
        "PAN_NUMBER": PAN_VERIFY_DESTINATION_MAPPINGS,
        "GSTIN": GSTIN_VERIFY_DESTINATION_MAPPINGS,
        "BANK_ACCOUNT_NUMBER": BANK_VERIFY_DESTINATION_MAPPINGS,
        "CHEQUEE": CHEQUE_OCR_DESTINATION_MAPPINGS,
        "AADHAR_BACK_IMAGE": AADHAAR_BACK_OCR_DESTINATION_MAPPINGS,
    }
    return mappings.get(source_type, {})
