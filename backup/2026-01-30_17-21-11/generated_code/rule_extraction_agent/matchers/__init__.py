"""
Matchers module for rule extraction.

Provides multi-stage matching pipeline with deterministic pattern matching
and LLM fallback for complex cases.
"""

from .pipeline import MatchingPipeline
from .deterministic import DeterministicMatcher
from .llm_fallback import LLMFallback

__all__ = [
    "MatchingPipeline",
    "DeterministicMatcher",
    "LLMFallback",
]
