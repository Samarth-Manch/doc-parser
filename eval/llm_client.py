"""
LLM Client for the Eval framework.

Provides a unified interface for making LLM calls for:
- Field name matching
- Report generation
- Semantic comparison
"""

import os
import json
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Try to import Anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        """Make a completion request."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the client is available."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI-based LLM client."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = None
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._client = OpenAI(api_key=api_key)

    def is_available(self) -> bool:
        return self._client is not None

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI client is not available")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


class AnthropicClient(LLMClient):
    """Anthropic Claude-based LLM client."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._client = None
        if ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        return self._client is not None

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        if not self.is_available():
            raise RuntimeError("Anthropic client is not available")

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        return response.content[0].text


class MockLLMClient(LLMClient):
    """Mock LLM client for testing or when no LLM is available."""

    def is_available(self) -> bool:
        return True

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
    ) -> str:
        # Return a simple response for field matching
        if "match" in prompt.lower() and "field" in prompt.lower():
            return json.dumps({
                "is_match": False,
                "confidence": 0.5,
                "reasoning": "Mock response - no LLM available"
            })
        return "Mock LLM response - no LLM available"


def get_llm_client(prefer: str = "openai") -> LLMClient:
    """
    Get an LLM client based on availability and preference.

    Args:
        prefer: Preferred LLM provider ("openai" or "anthropic")

    Returns:
        An LLM client instance
    """
    if prefer == "openai":
        client = OpenAIClient()
        if client.is_available():
            return client
        # Fall back to Anthropic
        client = AnthropicClient()
        if client.is_available():
            return client
    elif prefer == "anthropic":
        client = AnthropicClient()
        if client.is_available():
            return client
        # Fall back to OpenAI
        client = OpenAIClient()
        if client.is_available():
            return client

    # Return mock client if no LLM available
    return MockLLMClient()


class FieldMatchLLM:
    """LLM-based field name matcher."""

    SYSTEM_PROMPT = """You are a field name matching expert. Your task is to determine if two field names refer to the same field in a form.

Consider the following when matching:
1. Semantic equivalence (e.g., "Name" and "Full Name" could be the same)
2. Abbreviations (e.g., "Org" and "Organization")
3. Different word orders (e.g., "First Name" and "Name First")
4. Common synonyms in forms (e.g., "Email" and "Email Address")
5. Technical vs user-friendly names (e.g., "_vendorName_" and "Vendor Name")

However, be strict about:
1. Different field purposes (e.g., "Billing Address" vs "Shipping Address" are different)
2. Different data types implied (e.g., "Phone" vs "Email" are different)
3. Different form sections (e.g., "Bank Name" in Bank Details vs "Company Name" in Basic Details)

Respond with a JSON object containing:
- is_match: boolean indicating if fields match
- confidence: float between 0 and 1
- reasoning: brief explanation of your decision"""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or get_llm_client()

    def match_field_names(
        self,
        name1: str,
        name2: str,
        context1: Optional[str] = None,
        context2: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check if two field names match using LLM.

        Args:
            name1: First field name
            name2: Second field name
            context1: Optional context for first field (e.g., panel name)
            context2: Optional context for second field

        Returns:
            Dict with is_match, confidence, and reasoning
        """
        prompt = f"""Compare these two field names:

Field 1: "{name1}"
Field 2: "{name2}"
"""
        if context1:
            prompt += f"\nField 1 Context: {context1}"
        if context2:
            prompt += f"\nField 2 Context: {context2}"

        prompt += "\n\nDo these field names refer to the same form field? Respond with JSON only."

        try:
            response = self.client.complete(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=200,
            )

            # Parse JSON from response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            result = json.loads(response)
            return {
                "is_match": result.get("is_match", False),
                "confidence": result.get("confidence", 0.0),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            return {
                "is_match": False,
                "confidence": 0.0,
                "reasoning": f"Error during LLM matching: {str(e)}",
            }


class ReportGeneratorLLM:
    """LLM-based report generator."""

    SYSTEM_PROMPT = """You are an expert at analyzing form builder evaluation results and generating clear, actionable reports.

Your task is to:
1. Summarize the evaluation results
2. Identify the most critical issues
3. Provide clear, prioritized fix instructions
4. Highlight patterns in discrepancies

Be concise but thorough. Focus on actionable insights."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or get_llm_client()

    def generate_summary(self, eval_data: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of evaluation results.

        Args:
            eval_data: Evaluation data dictionary

        Returns:
            Generated summary text
        """
        # Prepare a condensed version of the data
        summary_input = {
            "passed": eval_data.get("passed", False),
            "overall_score": eval_data.get("overall_score", 0),
            "field_coverage": eval_data.get("field_coverage", 0),
            "rule_coverage": eval_data.get("rule_coverage", 0),
            "matched_fields": eval_data.get("matched_fields", 0),
            "total_reference_fields": eval_data.get("total_reference_fields", 0),
            "matched_rules": eval_data.get("matched_rules", 0),
            "total_reference_rules": eval_data.get("total_reference_rules", 0),
            "critical_discrepancies": sum(
                1 for d in eval_data.get("all_discrepancies", [])
                if d.get("severity") == "critical"
            ),
            "high_discrepancies": sum(
                1 for d in eval_data.get("all_discrepancies", [])
                if d.get("severity") == "high"
            ),
            "sample_discrepancies": eval_data.get("all_discrepancies", [])[:10],
        }

        prompt = f"""Analyze this form builder evaluation result and provide a brief summary with:
1. Overall assessment (1-2 sentences)
2. Key issues found (bullet points)
3. Top 3 recommended fixes

Evaluation Data:
{json.dumps(summary_input, indent=2)}"""

        try:
            return self.client.complete(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=500,
            )
        except Exception as e:
            return f"Error generating summary: {str(e)}"

    def generate_priority_fixes(
        self,
        discrepancies: List[Dict[str, Any]],
        max_fixes: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate prioritized fix instructions from discrepancies.

        Args:
            discrepancies: List of discrepancy dictionaries
            max_fixes: Maximum number of fixes to return

        Returns:
            List of priority fix dictionaries
        """
        if not discrepancies:
            return []

        # Sort by severity first
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_discrepancies = sorted(
            discrepancies,
            key=lambda d: severity_order.get(d.get("severity", "info"), 5)
        )

        # Take top discrepancies for LLM processing
        top_discrepancies = sorted_discrepancies[:min(max_fixes * 2, 20)]

        prompt = f"""Given these discrepancies from a form builder evaluation, generate {max_fixes} prioritized fix instructions.

Discrepancies:
{json.dumps(top_discrepancies, indent=2)}

For each fix, provide:
- priority: integer (1 = highest priority)
- category: type of fix (e.g., "missing_rule", "id_mismatch")
- action: clear instruction on what to fix
- field_name: affected field (if applicable)
- rule_type: affected rule type (if applicable)

Respond with a JSON array only."""

        try:
            response = self.client.complete(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=1500,
            )

            # Parse JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

            fixes = json.loads(response)
            return fixes[:max_fixes] if isinstance(fixes, list) else []
        except Exception as e:
            # Fall back to simple extraction from discrepancies
            return [
                {
                    "priority": i + 1,
                    "category": d.get("type", "unknown"),
                    "action": d.get("fix_instruction") or d.get("message", "Fix this issue"),
                    "field_name": d.get("field_name"),
                    "rule_type": None,
                }
                for i, d in enumerate(sorted_discrepancies[:max_fixes])
            ]
