"""
LLM fallback module for complex rule extraction.

Uses OpenAI API to handle complex logic statements that can't be
deterministically matched with pattern-based approaches.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from ..models import RuleMatch, GeneratedRule, FieldInfo
from ..schema_lookup import RuleSchemaLookup

logger = logging.getLogger(__name__)


class LLMFallback:
    """
    LLM-based rule extraction for complex logic.

    Used when deterministic pattern matching has low confidence (< 0.7).
    Provides Rule-Schemas.json context to guide the LLM.
    """

    def __init__(
        self,
        schema_lookup: Optional[RuleSchemaLookup] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize LLM fallback.

        Args:
            schema_lookup: RuleSchemaLookup for schema context
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            model: Model to use (default: gpt-4o-mini)
        """
        self.schema_lookup = schema_lookup
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI package not installed. LLM fallback will not work.")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                return None
        return self._client

    def match(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        schema_context: Optional[str] = None,
        available_fields: Optional[List[FieldInfo]] = None,
    ) -> Optional[RuleMatch]:
        """
        Use LLM to extract rule from complex logic.

        Args:
            logic_text: The raw logic text
            field_info: Information about the current field
            schema_context: Pre-built schema context string
            available_fields: List of available BUD fields for mapping

        Returns:
            RuleMatch if extraction successful, None otherwise
        """
        client = self._get_client()
        if not client:
            return None

        prompt = self._build_prompt(logic_text, field_info, schema_context, available_fields)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000,
            )

            result_text = response.choices[0].message.content
            return self._parse_response(result_text)

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

    def extract_field_mappings(
        self,
        logic_text: str,
        schema_id: int,
        available_fields: List[FieldInfo],
    ) -> Optional[Dict[str, int]]:
        """
        Use LLM to extract field mappings for VERIFY/OCR rules.

        Args:
            logic_text: The raw logic text
            schema_id: Rule schema ID
            available_fields: List of available BUD fields

        Returns:
            Dict mapping schema field names to BUD field IDs
        """
        client = self._get_client()
        if not client or not self.schema_lookup:
            return None

        # Build context with schema info
        schema_context = self.schema_lookup.build_llm_context(schema_id)

        # Build field list
        field_list = "\n".join([
            f"- {f.name} (ID: {f.id}, Type: {f.field_type})"
            for f in available_fields[:30]  # Limit to avoid token limits
        ])

        prompt = f"""## Logic Statement
{logic_text}

## Rule Schema Context
{schema_context}

## Available BUD Fields
{field_list}

## Task
Based on the logic text and available fields, determine which BUD fields
should map to which destination ordinals in the schema.

Return a JSON object with field_mappings:
```json
{{
  "field_mappings": {{
    "SchemaFieldName": BUD_field_id,
    ...
  }}
}}
```

Use -1 if no appropriate BUD field exists for a schema field.
Only map fields that are clearly related based on names and logic.
"""

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at mapping form fields based on business logic."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
            )

            result_text = response.choices[0].message.content
            return self._parse_field_mappings(result_text)

        except Exception as e:
            logger.error(f"LLM field mapping failed: {e}")
            return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for rule extraction."""
        return """You are an expert at extracting form fill rules from business logic descriptions.
Your task is to identify the rule type and provide structured output.

Rule types include:
- MAKE_VISIBLE / MAKE_INVISIBLE: Control field visibility
- MAKE_MANDATORY / MAKE_NON_MANDATORY: Control whether field is required
- MAKE_DISABLED / MAKE_ENABLED: Control field editability
- VERIFY: Validation rules (PAN, GSTIN, Bank, etc.)
- OCR: Extract data from images
- EXT_DROP_DOWN / EXT_VALUE: External data/dropdown rules
- COPY_TO: Copy data between fields

Always return valid JSON with the following structure:
{
  "action_type": "THE_ACTION_TYPE",
  "source_type": "optional_source_type_for_VERIFY_OCR",
  "confidence": 0.0 to 1.0,
  "is_conditional": true/false,
  "conditional_values": ["value1"],
  "requires_else_rule": true/false
}
"""

    def _build_prompt(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        schema_context: Optional[str],
        available_fields: Optional[List[FieldInfo]],
    ) -> str:
        """Build prompt for LLM."""
        prompt_parts = [
            "## Logic Statement",
            logic_text,
            "",
            "## Current Field",
            f"Name: {field_info.get('name', 'Unknown')}",
            f"Type: {field_info.get('field_type', 'Unknown')}",
            f"ID: {field_info.get('id', 'Unknown')}",
        ]

        if schema_context:
            prompt_parts.extend([
                "",
                "## Relevant Rule Schema",
                schema_context,
            ])

        if available_fields:
            prompt_parts.extend([
                "",
                "## Available Fields (for reference)",
            ])
            for f in available_fields[:20]:
                prompt_parts.append(f"- {f.name} (ID: {f.id})")

        prompt_parts.extend([
            "",
            "## Task",
            "Extract the rule type and details from the logic statement.",
            "Return JSON with action_type, source_type (if applicable), confidence, and conditions.",
        ])

        return "\n".join(prompt_parts)

    def _parse_response(self, response_text: str) -> Optional[RuleMatch]:
        """Parse LLM response into RuleMatch."""
        try:
            # Extract JSON from response
            json_match = None
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_match = response_text[start:end].strip()
            elif "{" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_match = response_text[start:end]

            if not json_match:
                return None

            data = json.loads(json_match)

            return RuleMatch(
                action_type=data.get("action_type", ""),
                source_type=data.get("source_type"),
                confidence=data.get("confidence", 0.7),
                matched_pattern="llm_extraction",
                requires_llm=False,  # Already used LLM
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None

    def _parse_field_mappings(self, response_text: str) -> Optional[Dict[str, int]]:
        """Parse LLM response into field mappings."""
        try:
            # Extract JSON from response
            json_match = None
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_match = response_text[start:end].strip()
            elif "{" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_match = response_text[start:end]

            if not json_match:
                return None

            data = json.loads(json_match)
            return data.get("field_mappings", {})

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse field mappings: {e}")
            return None


class MockLLMFallback(LLMFallback):
    """
    Mock LLM fallback for testing without API calls.

    Returns reasonable defaults based on keywords in logic text.
    """

    def __init__(self, schema_lookup: Optional[RuleSchemaLookup] = None):
        super().__init__(schema_lookup, api_key="mock")

    def _get_client(self):
        """Return mock client."""
        return self  # Use self as mock client

    def match(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        schema_context: Optional[str] = None,
        available_fields: Optional[List[FieldInfo]] = None,
    ) -> Optional[RuleMatch]:
        """Mock match based on keywords."""
        text_lower = logic_text.lower()

        # Simple keyword-based matching
        if "visible" in text_lower:
            return RuleMatch(
                action_type="MAKE_VISIBLE",
                confidence=0.75,
                matched_pattern="mock_visible",
            )
        elif "mandatory" in text_lower:
            return RuleMatch(
                action_type="MAKE_MANDATORY",
                confidence=0.75,
                matched_pattern="mock_mandatory",
            )
        elif "validation" in text_lower or "verify" in text_lower:
            return RuleMatch(
                action_type="VERIFY",
                confidence=0.75,
                matched_pattern="mock_verify",
            )
        elif "ocr" in text_lower:
            return RuleMatch(
                action_type="OCR",
                confidence=0.75,
                matched_pattern="mock_ocr",
            )

        return None
