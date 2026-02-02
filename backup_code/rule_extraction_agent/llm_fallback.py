"""
LLM Fallback Handler - Use OpenAI for complex/ambiguous logic.
"""

import os
import json
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

from .models import RuleSelection, GeneratedRule, IdGenerator


class LLMFallback:
    """Handles LLM fallback for complex logic extraction."""

    def __init__(self, api_key: Optional[str] = None, threshold: float = 0.7):
        """
        Initialize LLM fallback handler.

        Args:
            api_key: OpenAI API key (optional, reads from env if not provided).
            threshold: Confidence threshold below which LLM is used.
        """
        load_dotenv()
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.threshold = threshold
        self.client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                print("Warning: openai package not installed. LLM fallback disabled.")

    @property
    def is_available(self) -> bool:
        """Check if LLM fallback is available."""
        return self.client is not None

    def should_use_llm(self, confidence: float) -> bool:
        """Check if LLM should be used based on confidence."""
        return confidence < self.threshold

    def extract_rule(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        schema_context: str = "",
        all_fields: Optional[List[Dict]] = None
    ) -> RuleSelection:
        """
        Extract rule using LLM.

        Args:
            logic_text: Natural language logic text.
            field_info: Information about the field.
            schema_context: Context about available rule schemas.
            all_fields: List of all fields for reference resolution.

        Returns:
            RuleSelection from LLM extraction.
        """
        if not self.is_available:
            return RuleSelection(
                action_type="UNKNOWN",
                confidence=0.0,
                match_reason="LLM unavailable",
                needs_llm_fallback=True
            )

        prompt = self._build_prompt(logic_text, field_info, schema_context, all_fields)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a business rules extraction expert. Extract form field rules from logic statements."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return self._parse_llm_response(result)

        except Exception as e:
            print(f"LLM extraction error: {e}")
            return RuleSelection(
                action_type="UNKNOWN",
                confidence=0.0,
                match_reason=f"LLM error: {str(e)}",
                needs_llm_fallback=True
            )

    def _build_prompt(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        schema_context: str,
        all_fields: Optional[List[Dict]]
    ) -> str:
        """Build prompt for LLM."""
        prompt = f"""Analyze this field logic and extract the rule type.

Field Information:
- Name: {field_info.get('name', 'Unknown')}
- Type: {field_info.get('field_type', 'Unknown')}
- Variable: {field_info.get('variable_name', 'Unknown')}

Logic/Rules: {logic_text}

{schema_context}

Identify the rule type from these options:
- MAKE_VISIBLE: Show field based on condition
- MAKE_INVISIBLE: Hide field based on condition
- MAKE_MANDATORY: Make field required based on condition
- MAKE_NON_MANDATORY: Make field optional based on condition
- MAKE_DISABLED: Make field non-editable
- MAKE_ENABLED: Make field editable
- VERIFY: Validation rule (PAN, GSTIN, Bank, MSME, etc.)
- OCR: Extract data from document image
- EXT_DROP_DOWN: External dropdown with filtered values
- EXT_VALUE: External data value
- COPY_TO: Copy value from another field
- CONVERT_TO: Convert text (e.g., uppercase)
- SKIP: This is an expression/execute rule that should be skipped

Return JSON:
{{
  "action_type": "RULE_TYPE",
  "source_type": "optional source type for VERIFY/OCR",
  "confidence": 0.0-1.0,
  "reason": "explanation",
  "conditional_values": ["values that trigger the rule"],
  "is_destination_field": true/false (if field receives data from elsewhere)
}}
"""
        return prompt

    def _parse_llm_response(self, result: Dict) -> RuleSelection:
        """Parse LLM response into RuleSelection."""
        return RuleSelection(
            action_type=result.get('action_type', 'UNKNOWN'),
            source_type=result.get('source_type'),
            confidence=result.get('confidence', 0.5),
            match_reason=result.get('reason', 'LLM extraction'),
            needs_llm_fallback=False
        )

    def extract_multiple_rules(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        schema_context: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Extract multiple rules from complex logic.

        Args:
            logic_text: Natural language logic text.
            field_info: Information about the field.
            schema_context: Context about available rule schemas.

        Returns:
            List of rule dictionaries.
        """
        if not self.is_available:
            return []

        prompt = f"""Analyze this field logic and extract ALL applicable rules.

Field Information:
- Name: {field_info.get('name', 'Unknown')}
- Type: {field_info.get('field_type', 'Unknown')}

Logic/Rules: {logic_text}

{schema_context}

Extract ALL rules that apply. Common combinations:
- "visible and mandatory" = MAKE_VISIBLE + MAKE_MANDATORY
- "invisible and non-mandatory" = MAKE_INVISIBLE + MAKE_NON_MANDATORY
- "non-editable" = MAKE_DISABLED
- "Perform X validation" = VERIFY
- "from OCR rule" = OCR

Return JSON:
{{
  "rules": [
    {{
      "action_type": "RULE_TYPE",
      "source_type": "optional",
      "conditional_values": ["values"],
      "condition": "IN or NOT_IN",
      "confidence": 0.0-1.0
    }}
  ]
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a business rules extraction expert. Extract ALL form field rules from logic statements."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result.get('rules', [])

        except Exception as e:
            print(f"LLM multi-rule extraction error: {e}")
            return []


class MatchingPipeline:
    """Two-stage matching: deterministic patterns → LLM fallback."""

    def __init__(
        self,
        schema_lookup=None,
        field_matcher=None,
        llm_threshold: float = 0.7
    ):
        """
        Initialize the matching pipeline.

        Args:
            schema_lookup: RuleSchemaLookup instance.
            field_matcher: FieldMatcher instance.
            llm_threshold: Confidence threshold for LLM fallback.
        """
        from .rule_tree import DeterministicMatcher

        self.deterministic = DeterministicMatcher()
        self.llm_fallback = LLMFallback(threshold=llm_threshold)
        self.schema_lookup = schema_lookup
        self.field_matcher = field_matcher
        self.llm_threshold = llm_threshold

    def match(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        use_llm: bool = True
    ) -> RuleSelection:
        """
        Match logic text to rule(s) using two-stage approach.

        Stage 1: Deterministic pattern matching
        Stage 2: LLM fallback (if confidence < threshold)

        Args:
            logic_text: Natural language logic text.
            field_info: Information about the field.
            use_llm: Whether to use LLM fallback.

        Returns:
            Best matching RuleSelection.
        """
        # Stage 1: Deterministic pattern matching
        result = self.deterministic.match(logic_text)

        if result.confidence >= self.llm_threshold or not use_llm:
            return result

        # Stage 2: LLM fallback
        if self.llm_fallback.is_available:
            schema_context = ""
            if self.schema_lookup and result.possible_action_types:
                candidates = self.schema_lookup.find_candidates(
                    logic_text,
                    result.possible_action_types
                )
                if candidates:
                    schema_context = "\n".join([
                        self.schema_lookup.build_llm_context(c.get('id'))
                        for c in candidates[:3]
                    ])

            llm_result = self.llm_fallback.extract_rule(
                logic_text,
                field_info,
                schema_context
            )

            # Use LLM result if higher confidence
            if llm_result.confidence > result.confidence:
                return llm_result

        return result

    def match_all(
        self,
        logic_text: str,
        field_info: Dict[str, Any],
        use_llm: bool = True
    ) -> List[RuleSelection]:
        """
        Match logic text to all applicable rules.

        Args:
            logic_text: Natural language logic text.
            field_info: Information about the field.
            use_llm: Whether to use LLM for complex cases.

        Returns:
            List of all matching RuleSelections.
        """
        # Get deterministic matches
        results = self.deterministic.match_all(logic_text)

        # If no matches and LLM available, try LLM
        if not results and use_llm and self.llm_fallback.is_available:
            llm_rules = self.llm_fallback.extract_multiple_rules(
                logic_text,
                field_info
            )

            for rule_data in llm_rules:
                results.append(RuleSelection(
                    action_type=rule_data.get('action_type', 'UNKNOWN'),
                    source_type=rule_data.get('source_type'),
                    confidence=rule_data.get('confidence', 0.5),
                    match_reason="LLM extraction"
                ))

        return results
