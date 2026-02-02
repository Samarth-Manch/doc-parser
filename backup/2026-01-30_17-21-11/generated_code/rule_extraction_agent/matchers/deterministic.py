"""
Deterministic pattern-based matcher for rule extraction.

Uses regex patterns to match logic text to rule types with confidence scores.
"""

import re
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from ..models import RuleMatch, ParsedLogic
from ..logic_parser import LogicParser


@dataclass
class PatternMatch:
    """Result of a pattern match."""
    pattern: str
    action_type: str
    confidence: float
    matched_text: str
    category: str


class DeterministicMatcher:
    """
    Pattern-based matcher for common rule types.

    Uses regex patterns organized by category to match logic text
    to specific action types with confidence scores.
    """

    # Pattern categories with (regex, action_type, confidence)
    PATTERNS = {
        "visibility": [
            (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
            (r"\bthen\s+visible\b", "MAKE_VISIBLE", 0.95),
            (r"\bis\s+visible\b", "MAKE_VISIBLE", 0.90),
            (r"(?:make\s+)?invisible", "MAKE_INVISIBLE", 0.95),
            (r"\bhide(?:n)?\b", "MAKE_INVISIBLE", 0.90),
            (r"\bhidden\b", "MAKE_INVISIBLE", 0.90),
            (r"show\s+(?:this|the)?\s*field", "MAKE_VISIBLE", 0.85),
            (r"\bdisplay(?:ed)?\b", "MAKE_VISIBLE", 0.80),
            (r"otherwise\s+invisible", "MAKE_INVISIBLE", 0.95),
        ],
        "mandatory": [
            (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
            (r"\bthen\s+.*mandatory\b", "MAKE_MANDATORY", 0.95),
            (r"\bis\s+mandatory\b", "MAKE_MANDATORY", 0.90),
            (r"non-?mandatory", "MAKE_NON_MANDATORY", 0.95),
            (r"not\s+mandatory", "MAKE_NON_MANDATORY", 0.95),
            (r"\boptional\b", "MAKE_NON_MANDATORY", 0.85),
            (r"required\s+(?:if|when)", "MAKE_MANDATORY", 0.85),
            (r"otherwise\s+non-?mandatory", "MAKE_NON_MANDATORY", 0.95),
        ],
        "disable": [
            (r"\bdisable[d]?\b", "MAKE_DISABLED", 0.95),
            (r"non-?editable", "MAKE_DISABLED", 0.95),
            (r"read-?only", "MAKE_DISABLED", 0.90),
            # Only match editable when not preceded by non- and not followed by "if"
            (r"(?<!non-)(?<!non )\beditable\b(?!\s+(?:if|when|based))", "MAKE_ENABLED", 0.80),
            (r"(?<!non-)(?<!non )\benable[d]?\b", "MAKE_ENABLED", 0.80),
        ],
        "verify": [
            (r"(?:PAN|pan)\s*(?:validation|verify|verification)", "VERIFY", 0.95),
            (r"validat(?:e|ion)\s+(?:PAN|pan)", "VERIFY", 0.95),
            (r"perform\s+PAN\s+validation", "VERIFY", 0.98),
            (r"(?:GSTIN?|gstin?|GST|gst)\s*(?:validation|verify|verification)", "VERIFY", 0.95),
            (r"validat(?:e|ion)\s+(?:GSTIN?|gstin?|GST|gst)", "VERIFY", 0.95),
            (r"perform\s+GST(?:IN)?\s+validation", "VERIFY", 0.98),
            (r"(?:bank|BANK)\s*(?:account)?\s*(?:validation|verify|verification)", "VERIFY", 0.95),
            (r"validat(?:e|ion)\s+(?:bank|BANK)\s*(?:account)?", "VERIFY", 0.95),
            (r"(?:MSME|msme|udyam|UDYAM)\s*(?:validation|verify|verification)", "VERIFY", 0.95),
            (r"validat(?:e|ion)\s+(?:MSME|msme|udyam)", "VERIFY", 0.95),
            (r"(?:CIN|cin)\s*(?:validation|verify|verification)", "VERIFY", 0.95),
            (r"validat(?:e|ion)\s+(?:CIN|cin)", "VERIFY", 0.95),
            (r"PIN\s*code\s*validation", "VERIFY", 0.90),
            (r"perform\s+\w+\s+validation", "VERIFY", 0.85),
            (r"verify\s+and\s+store", "VERIFY", 0.90),
            (r"data\s+will\s+come\s+from\s+\w+\s+validation", "VERIFY", 0.90),
        ],
        "ocr": [
            (r"(?:from|using)\s+OCR", "OCR", 0.95),
            (r"OCR\s+rule", "OCR", 0.95),
            (r"get\s+\w+\s+from\s+OCR", "OCR", 0.95),
            (r"data\s+will\s+come\s+from\s+\w*\s*OCR", "OCR", 0.90),
            (r"extract(?:ed)?\s+from\s+(?:image|document)", "OCR", 0.85),
            (r"OCR\s+(?:will\s+)?populat(?:e|ed)", "OCR", 0.90),
            (r"auto-?derived?\s+(?:from|via)\s+\w*\s*OCR", "OCR", 0.90),
            (r"upload.*OCR", "OCR", 0.85),
        ],
        "edv": [
            (r"dropdown\s+values?\s+(?:from|based|will\s+come)", "EXT_DROP_DOWN", 0.90),
            (r"reference\s+table\s+\d+", "EXT_DROP_DOWN", 0.90),
            (r"column\s+\d+\s+(?:of|from|on)\s+(?:reference\s+)?table", "EXT_VALUE", 0.85),
            (r"external\s+data\s+value", "EXT_VALUE", 0.85),
            (r"parent\s+dropdown\s+field", "EXT_DROP_DOWN", 0.90),
            (r"EDV\s+rule", "EXT_VALUE", 0.95),
            (r"derive.*from.*table", "EXT_VALUE", 0.85),
        ],
        "copy": [
            (r"copy\s+(?:from|to|the\s+data)", "COPY_TO", 0.85),
            (r"deriv(?:e|ed)\s+(?:from|as|it)", "COPY_TO", 0.80),
            (r"auto-?fill(?:ed)?", "COPY_TO", 0.80),
            (r"populat(?:e|ed)\s+(?:from|with|default)", "COPY_TO", 0.80),
        ],
    }

    def __init__(self):
        """Initialize with compiled patterns."""
        self._compile_patterns()
        self.logic_parser = LogicParser()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.compiled_patterns: Dict[str, List[Tuple[re.Pattern, str, float]]] = {}
        for category, patterns in self.PATTERNS.items():
            self.compiled_patterns[category] = [
                (re.compile(p, re.IGNORECASE), action, conf)
                for p, action, conf in patterns
            ]

    def match(self, logic_text: str) -> List[RuleMatch]:
        """
        Match logic text to rule types.

        Args:
            logic_text: Raw logic text from BUD

        Returns:
            List of RuleMatch objects with confidence scores
        """
        # Check if should skip
        should_skip, _ = self.logic_parser.should_skip(logic_text)
        if should_skip:
            return []

        matches = []
        seen_actions = set()

        for category, patterns in self.compiled_patterns.items():
            for pattern, action_type, confidence in patterns:
                match = pattern.search(logic_text)
                if match:
                    if action_type not in seen_actions:
                        matches.append(RuleMatch(
                            action_type=action_type,
                            confidence=confidence,
                            matched_pattern=pattern.pattern,
                        ))
                        seen_actions.add(action_type)

        # Sort by confidence descending
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches

    def match_with_details(self, logic_text: str) -> List[PatternMatch]:
        """
        Match logic text with detailed pattern information.

        Args:
            logic_text: Raw logic text from BUD

        Returns:
            List of PatternMatch objects with detailed info
        """
        matches = []

        for category, patterns in self.compiled_patterns.items():
            for pattern, action_type, confidence in patterns:
                match = pattern.search(logic_text)
                if match:
                    matches.append(PatternMatch(
                        pattern=pattern.pattern,
                        action_type=action_type,
                        confidence=confidence,
                        matched_text=match.group(0),
                        category=category,
                    ))

        return matches

    def get_highest_confidence_match(self, logic_text: str) -> Optional[RuleMatch]:
        """
        Get the highest confidence match for logic text.

        Args:
            logic_text: Raw logic text from BUD

        Returns:
            RuleMatch with highest confidence, or None
        """
        matches = self.match(logic_text)
        return matches[0] if matches else None

    def categorize_logic(self, logic_text: str) -> Dict[str, List[str]]:
        """
        Categorize logic text by matched patterns.

        Args:
            logic_text: Raw logic text from BUD

        Returns:
            Dict mapping category to list of matched action types
        """
        result = {}

        for category, patterns in self.compiled_patterns.items():
            actions = []
            for pattern, action_type, confidence in patterns:
                if pattern.search(logic_text):
                    if action_type not in actions:
                        actions.append(action_type)
            if actions:
                result[category] = actions

        return result

    def detect_document_type(self, logic_text: str) -> Optional[str]:
        """
        Detect document type from logic text.

        Args:
            logic_text: Raw logic text from BUD

        Returns:
            Document type (PAN, GSTIN, etc.) or None
        """
        doc_patterns = [
            (r"\bPAN\b", "PAN"),
            (r"\bGSTIN?\b|\bGST\b", "GSTIN"),
            (r"\bbank\b", "BANK"),
            (r"\bMSME\b|\budyam\b", "MSME"),
            (r"\bCIN\b", "CIN"),
            (r"\bTAN\b", "TAN"),
            (r"\bFSSAI\b", "FSSAI"),
            (r"\baadhaa?r\b", "AADHAAR"),
            (r"\bcheque\b", "CHEQUE"),
            (r"\bPIN\s*code\b", "PINCODE"),
        ]

        for pattern, doc_type in doc_patterns:
            if re.search(pattern, logic_text, re.IGNORECASE):
                return doc_type

        return None

    def is_conditional(self, logic_text: str) -> bool:
        """Check if logic has conditional structure."""
        conditional_patterns = [
            r"\bif\b.*\bthen\b",
            r"\bwhen\b.*\bthen\b",
            r"\bbased\s+on\b",
        ]
        for pattern in conditional_patterns:
            if re.search(pattern, logic_text, re.IGNORECASE):
                return True
        return False

    def has_else_branch(self, logic_text: str) -> bool:
        """Check if logic has else/otherwise branch."""
        else_patterns = [
            r"\botherwise\b",
            r"\belse\b",
            r"\bif\s+not\b",
        ]
        for pattern in else_patterns:
            if re.search(pattern, logic_text, re.IGNORECASE):
                return True
        return False
