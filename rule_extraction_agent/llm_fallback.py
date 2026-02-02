"""LLM fallback handler for complex logic extraction."""

import os
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class LLMExtractionResult:
    """Result from LLM extraction."""
    rules: List[Dict]
    confidence: float
    raw_response: str
    error: Optional[str] = None


class LLMFallback:
    """Handle complex/ambiguous logic using OpenAI."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialize OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package is required for LLM fallback")
        return self._client

    def extract_rules(
        self,
        logic_text: str,
        field_info: Dict,
        schema_context: str = "",
        all_fields: List[Dict] = None
    ) -> LLMExtractionResult:
        """
        Extract rules using LLM when pattern matching fails.

        Args:
            logic_text: Natural language logic statement
            field_info: Current field metadata
            schema_context: Context from Rule-Schemas.json
            all_fields: All fields for reference

        Returns:
            LLMExtractionResult with extracted rules
        """
        if not self.api_key:
            return LLMExtractionResult(
                rules=[],
                confidence=0.0,
                raw_response="",
                error="No OpenAI API key configured"
            )

        # Build prompt
        prompt = self._build_prompt(logic_text, field_info, schema_context, all_fields)

        try:
            client = self._get_client()

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            raw_response = response.choices[0].message.content

            # Parse response
            rules = self._parse_response(raw_response)

            return LLMExtractionResult(
                rules=rules,
                confidence=0.85 if rules else 0.0,
                raw_response=raw_response
            )

        except Exception as e:
            return LLMExtractionResult(
                rules=[],
                confidence=0.0,
                raw_response="",
                error=str(e)
            )

    def _get_system_prompt(self) -> str:
        """Get system prompt for LLM."""
        return """You are a rule extraction expert. Given a natural language logic statement from a business document, extract the corresponding form fill rules.

Return rules in JSON format with these properties:
- actionType: MAKE_VISIBLE, MAKE_INVISIBLE, MAKE_MANDATORY, MAKE_NON_MANDATORY, MAKE_DISABLED, VERIFY, OCR, etc.
- sourceType: For VERIFY/OCR rules (e.g., PAN_NUMBER, GSTIN_IMAGE)
- conditionalValues: Values that trigger the rule (for conditional rules)
- condition: IN or NOT_IN

Return a JSON array of rule objects. If no rules can be extracted, return an empty array.

Example input: "if the field 'GST option' is Yes then visible and mandatory otherwise invisible"

Example output:
```json
[
  {"actionType": "MAKE_VISIBLE", "conditionalValues": ["Yes"], "condition": "IN"},
  {"actionType": "MAKE_INVISIBLE", "conditionalValues": ["Yes"], "condition": "NOT_IN"},
  {"actionType": "MAKE_MANDATORY", "conditionalValues": ["Yes"], "condition": "IN"},
  {"actionType": "MAKE_NON_MANDATORY", "conditionalValues": ["Yes"], "condition": "NOT_IN"}
]
```"""

    def _build_prompt(
        self,
        logic_text: str,
        field_info: Dict,
        schema_context: str,
        all_fields: List[Dict]
    ) -> str:
        """Build prompt for LLM."""
        field_name = field_info.get('formTag', {}).get('name', 'Unknown')
        field_type = field_info.get('formTag', {}).get('type', 'TEXT')

        prompt_parts = [
            f"Field Name: {field_name}",
            f"Field Type: {field_type}",
            f"Logic Statement: {logic_text}",
        ]

        if schema_context:
            prompt_parts.append(f"\nRelevant Rule Schema:\n{schema_context}")

        if all_fields:
            # Include nearby fields for context
            field_names = [f.get('formTag', {}).get('name', '') for f in all_fields[:20]]
            prompt_parts.append(f"\nAvailable Fields: {', '.join(field_names)}")

        prompt_parts.append("\nExtract the form fill rules from this logic statement.")

        return "\n".join(prompt_parts)

    def _parse_response(self, response: str) -> List[Dict]:
        """Parse LLM response to extract rules."""
        # Try to find JSON in response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find array directly
            json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response)
            if json_match:
                json_str = json_match.group(0)
            else:
                return []

        try:
            rules = json.loads(json_str)
            if isinstance(rules, list):
                return rules
            return []
        except json.JSONDecodeError:
            return []


class RuleValidator:
    """Validate generated rules against schema."""

    def __init__(self, schema_lookup):
        self.schema_lookup = schema_lookup

    def validate_rule(self, rule: Dict) -> List[str]:
        """
        Validate a rule and return list of issues.

        Args:
            rule: Rule dict to validate

        Returns:
            List of validation issue strings
        """
        issues = []

        # Required fields
        required = ['actionType', 'sourceIds', 'destinationIds']
        for field in required:
            if field not in rule:
                issues.append(f"Missing required field: {field}")

        # Validate action type
        action_type = rule.get('actionType', '')
        valid_actions = [
            'MAKE_VISIBLE', 'MAKE_INVISIBLE', 'MAKE_MANDATORY', 'MAKE_NON_MANDATORY',
            'MAKE_DISABLED', 'MAKE_ENABLED', 'VERIFY', 'OCR', 'COPY_TO', 'CLEAR_FIELD',
            'EXT_DROP_DOWN', 'EXT_VALUE', 'VALIDATION', 'CONVERT_TO'
        ]
        if action_type and action_type not in valid_actions:
            issues.append(f"Invalid actionType: {action_type}")

        # Validate VERIFY rules
        if action_type == 'VERIFY':
            source_type = rule.get('sourceType', '')
            if not source_type:
                issues.append("VERIFY rule missing sourceType")

            # Check for multi-source rules
            schema = self.schema_lookup.find_by_action_and_source('VERIFY', source_type)
            if schema:
                required_sources = schema.get('sourceFields', {}).get('numberOfItems', 1)
                actual_sources = len(rule.get('sourceIds', []))
                if actual_sources < required_sources:
                    issues.append(
                        f"VERIFY rule requires {required_sources} source fields, "
                        f"but only {actual_sources} provided"
                    )

        # Validate OCR rules
        if action_type == 'OCR':
            if not rule.get('sourceType'):
                issues.append("OCR rule missing sourceType")
            if not rule.get('destinationIds'):
                issues.append("OCR rule missing destinationIds")

        # Validate conditional rules
        conditional_actions = ['MAKE_VISIBLE', 'MAKE_INVISIBLE', 'MAKE_MANDATORY', 'MAKE_NON_MANDATORY']
        if action_type in conditional_actions:
            if 'conditionalValues' not in rule or not rule['conditionalValues']:
                # Could be a warning, not always required
                pass

        return issues

    def validate_rules(self, rules: List[Dict]) -> Dict[str, List[str]]:
        """
        Validate all rules and return issues grouped by rule ID.

        Args:
            rules: List of rule dicts

        Returns:
            Dict mapping rule ID to list of issues
        """
        all_issues = {}

        for rule in rules:
            rule_id = rule.get('id', 'unknown')
            issues = self.validate_rule(rule)
            if issues:
                all_issues[str(rule_id)] = issues

        return all_issues
