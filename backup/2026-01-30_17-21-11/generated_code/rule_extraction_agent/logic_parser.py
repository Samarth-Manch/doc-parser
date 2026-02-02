"""
Logic parser module for extracting structured data from natural language logic.

Parses BUD logic/rules text to extract keywords, conditions, field references,
and action types using regex pattern matching.
"""

import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from .models import ParsedLogic, Condition


# Patterns to skip (expression rules, execute rules)
SKIP_PATTERNS = [
    # Expression rules
    r"mvi\s*\(",              # mvi('fieldName')
    r"mm\s*\(",               # mm('fieldName')
    r"expr-eval",             # expr-eval expressions
    r"expr\s*:",              # expr: syntax
    r"\$\{.*\}",              # ${expression} syntax
    r"vo\s*\(",               # vo('variableName')
    r"ctfd\s*\(",             # ctfd() functions
    r"asdff\s*\(",            # asdff() functions
    r"rffdd\s*\(",            # rffdd() functions

    # Execute rules
    r"\bEXECUTE\b",           # EXECUTE keyword
    r"execute\s+rule",        # execute rule
    r"execute\s+script",      # execute script
    r"custom\s+script",       # custom script

    # Complex calculations (code-like)
    r"\b\w+\s*\(\s*['\"].*['\"]\s*\)\s*[\+\-\*\/]",  # func('x') + ...
]


# Action keyword patterns with confidence scores
ACTION_PATTERNS = {
    "visibility": [
        (r"\b(?:make\s+)?visible\b(?:\s+(?:if|when))?", "MAKE_VISIBLE", 0.95),
        (r"\b(?:make\s+)?invisible\b", "MAKE_INVISIBLE", 0.95),
        (r"\bhide(?:n)?\b", "MAKE_INVISIBLE", 0.90),
        (r"\bshow\s+(?:this|field|the\s+field)?\b", "MAKE_VISIBLE", 0.85),
        (r"\bdisplay(?:ed)?\b", "MAKE_VISIBLE", 0.80),
    ],
    "mandatory": [
        (r"\b(?:make\s+)?mandatory\b(?:\s+(?:if|when))?", "MAKE_MANDATORY", 0.95),
        (r"\bnon-?mandatory\b", "MAKE_NON_MANDATORY", 0.95),
        (r"\boptional\b", "MAKE_NON_MANDATORY", 0.85),
        (r"\brequired\b(?:\s+(?:if|when))?", "MAKE_MANDATORY", 0.85),
        (r"\bnot\s+mandatory\b", "MAKE_NON_MANDATORY", 0.90),
    ],
    "disable": [
        (r"\bdisable[d]?\b", "MAKE_DISABLED", 0.95),
        (r"\bnon-?editable\b", "MAKE_DISABLED", 0.95),
        (r"\bread-?only\b", "MAKE_DISABLED", 0.90),
        # Only match editable when not preceded by non-
        (r"(?<!non-)(?<!non )\beditable\b", "MAKE_ENABLED", 0.85),
        (r"(?<!non-)(?<!non )\benable[d]?\b", "MAKE_ENABLED", 0.85),
    ],
    "verify": [
        (r"\b(?:PAN|pan)\s*(?:validation|verify|verification)\b", "VERIFY", 0.95),
        (r"\bvalidat(?:e|ion)\s+(?:PAN|pan)\b", "VERIFY", 0.95),
        (r"\b(?:GSTIN?|gstin?|GST|gst)\s*(?:validation|verify|verification)\b", "VERIFY", 0.95),
        (r"\bvalidat(?:e|ion)\s+(?:GSTIN?|gstin?|GST|gst)\b", "VERIFY", 0.95),
        (r"\b(?:bank|BANK)\s*(?:account)?\s*(?:validation|verify|verification)\b", "VERIFY", 0.95),
        (r"\bvalidat(?:e|ion)\s+(?:bank|BANK)\s*(?:account)?\b", "VERIFY", 0.95),
        (r"\b(?:MSME|msme|udyam)\s*(?:validation|verify|verification)\b", "VERIFY", 0.95),
        (r"\bvalidat(?:e|ion)\s+(?:MSME|msme|udyam)\b", "VERIFY", 0.95),
        (r"\b(?:CIN|cin)\s*(?:validation|verify|verification)\b", "VERIFY", 0.95),
        (r"\bvalidat(?:e|ion)\s+(?:CIN|cin)\b", "VERIFY", 0.95),
        (r"\bperform\s+\w+\s+validation\b", "VERIFY", 0.90),
        (r"\bverify\s+and\s+store\b", "VERIFY", 0.90),
        (r"\bPIN\s*code\s*validation\b", "VERIFY", 0.85),
    ],
    "ocr": [
        (r"\b(?:from|using)\s+OCR\b", "OCR", 0.95),
        (r"\bOCR\s+rule\b", "OCR", 0.95),
        (r"\bget\s+\w+\s+from\s+OCR\b", "OCR", 0.95),
        (r"\bdata\s+will\s+come\s+from\s+\w*\s*OCR\b", "OCR", 0.90),
        (r"\bextract(?:ed)?\s+from\s+(?:image|document)\b", "OCR", 0.85),
        (r"\bOCR\s+(?:will\s+)?populat(?:e|ed)\b", "OCR", 0.90),
        (r"\bauto-?derived?\s+(?:from|via)\s+\w*\s*OCR\b", "OCR", 0.90),
    ],
    "edv": [
        (r"\bdropdown\s+values?\s+(?:from|based|will\s+come)\b", "EXT_DROP_DOWN", 0.90),
        (r"\breference\s+table\b", "EXT_DROP_DOWN", 0.85),
        (r"\bexternal\s+data\b", "EXT_VALUE", 0.85),
        (r"\bparent\s+dropdown\s+field\b", "EXT_DROP_DOWN", 0.90),
        (r"\bEDV\s+rule\b", "EXT_VALUE", 0.95),
        (r"\bcolumn\s+\d+\s+(?:of|from|on)\s+(?:reference\s+)?table\b", "EXT_VALUE", 0.85),
    ],
    "copy": [
        (r"\bcopy\s+(?:from|to|the\s+data)\b", "COPY_TO", 0.90),
        (r"\bderiv(?:e|ed)\s+(?:from|as|it)\b", "COPY_TO", 0.85),
        (r"\bauto-?fill(?:ed)?\b", "COPY_TO", 0.85),
        (r"\bpopulat(?:e|ed)\s+(?:from|with|default)\b", "COPY_TO", 0.85),
    ],
}


# Document type patterns
DOCUMENT_TYPE_PATTERNS = [
    (r"\bPAN\b", "PAN"),
    (r"\bGSTIN?\b", "GSTIN"),
    (r"\bGST\b", "GSTIN"),
    (r"\bbank\s*(?:account)?\b", "BANK"),
    (r"\bMSME\b", "MSME"),
    (r"\budyam\b", "MSME"),
    (r"\bCIN\b", "CIN"),
    (r"\bTAN\b", "TAN"),
    (r"\bFSSAI\b", "FSSAI"),
    (r"\baadhaa?r\b", "AADHAAR"),
    (r"\bcheque\b", "CHEQUE"),
    (r"\bPIN\s*code\b", "PINCODE"),
]


# Condition patterns
CONDITION_PATTERNS = [
    # if field 'X' is Y then ... otherwise ...
    (r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+(?:value\s+)?(?:is|=|==|equals?)\s+['\"]?(\w+)['\"]?\s+then\s+(.+?)(?:\s+otherwise\s+(.+))?$",
     "field_value_conditional"),
    # if 'X' is Y then ...
    (r"if\s+['\"]([^'\"]+)['\"]\s+(?:is|=|==|equals?)\s+['\"]?(\w+)['\"]?\s+then\s+(.+?)(?:\s+otherwise\s+(.+))?$",
     "simple_conditional"),
    # if X is selected as Y
    (r"if\s+(?:the\s+)?(?:field\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:is\s+)?(?:selected|chosen|set)\s+(?:as\s+)?['\"]?(\w+)['\"]?",
     "selection_conditional"),
    # when X = Y
    (r"when\s+['\"]?([^'\"]+?)['\"]?\s+(?:is|=|==|equals?)\s+['\"]?(\w+)['\"]?",
     "when_conditional"),
    # based on X selection/value
    (r"based\s+on\s+(?:the\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:selection|value)",
     "based_on"),
]


# Field reference patterns
FIELD_REFERENCE_PATTERNS = [
    r"field\s+['\"]([^'\"]+)['\"]",
    r"['\"]([^'\"]+)['\"](?:\s+field)?",
    r"from\s+(?:the\s+)?([A-Za-z][A-Za-z0-9\s]+?)\s+field",
    r"(?:in|on|of|to|from)\s+(?:the\s+)?['\"]?([A-Za-z][A-Za-z0-9\s\/\-]+?)['\"]?\s+(?:field|panel)",
]


class LogicParser:
    """
    Parser for BUD logic/rules text.

    Extracts:
    - Action keywords (visible, mandatory, validate, etc.)
    - Conditional expressions (if/then/else)
    - Field references
    - Document types (PAN, GSTIN, etc.)
    """

    def __init__(self):
        """Initialize the parser with compiled patterns."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.skip_patterns = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]
        self.action_patterns = {}
        for category, patterns in ACTION_PATTERNS.items():
            self.action_patterns[category] = [
                (re.compile(p, re.IGNORECASE), action, conf)
                for p, action, conf in patterns
            ]
        self.doc_type_patterns = [
            (re.compile(p, re.IGNORECASE), doc_type)
            for p, doc_type in DOCUMENT_TYPE_PATTERNS
        ]
        self.condition_patterns = [
            (re.compile(p, re.IGNORECASE | re.DOTALL), cond_type)
            for p, cond_type in CONDITION_PATTERNS
        ]
        self.field_ref_patterns = [
            re.compile(p, re.IGNORECASE) for p in FIELD_REFERENCE_PATTERNS
        ]

    def should_skip(self, logic_text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if logic statement should be skipped.

        Returns:
            Tuple of (should_skip, reason)
        """
        if not logic_text or not logic_text.strip():
            return True, "Empty logic text"

        for pattern in self.skip_patterns:
            if pattern.search(logic_text):
                return True, f"Matches skip pattern: expression/execute rule"

        return False, None

    def parse(self, logic_text: str) -> ParsedLogic:
        """
        Parse logic text and extract structured components.

        Args:
            logic_text: Raw logic/rules text from BUD

        Returns:
            ParsedLogic with extracted components
        """
        result = ParsedLogic(original_text=logic_text)

        # Check if should be skipped
        should_skip, skip_reason = self.should_skip(logic_text)
        if should_skip:
            result.skip_reason = skip_reason
            return result

        # Normalize text
        text = self._normalize_text(logic_text)

        # Extract components
        result.keywords = self._extract_keywords(text)
        result.action_types, result.confidence = self._extract_action_types(text)
        result.document_type = self._extract_document_type(text)
        result.field_references = self._extract_field_references(text)

        # Parse conditions
        conditions = self._extract_conditions(text)
        if conditions:
            result.conditions = conditions

        # Detect conditional pattern ("if...then" or "when...then")
        result.is_conditional = self._is_conditional(text)
        result.has_else_branch = self._has_else_branch(text)

        # Determine positive/negative actions for conditionals
        if result.is_conditional and result.has_else_branch:
            result.positive_actions, result.negative_actions = self._split_conditional_actions(text)

    def _is_conditional(self, text: str) -> bool:
        """Check if the logic has conditional structure."""
        text_lower = text.lower()
        conditional_patterns = [
            r'\bif\b.*\bthen\b',
            r'\bwhen\b.*\bthen\b',
            r'\bbased\s+on\b',
            r'\bif\b.*\bvisible\b',
            r'\bif\b.*\bmandatory\b',
        ]
        for pattern in conditional_patterns:
            if re.search(pattern, text_lower, re.DOTALL):
                return True
        return False

        return result

    def _normalize_text(self, text: str) -> str:
        """Normalize logic text for parsing."""
        # Remove bullet points and list markers
        text = re.sub(r'^[\s\-\*\u2022\u25cf]+', '', text, flags=re.MULTILINE)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.strip()

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract action keywords from text."""
        keywords = []
        text_lower = text.lower()

        keyword_list = [
            "visible", "invisible", "show", "hide", "display",
            "mandatory", "non-mandatory", "required", "optional",
            "disable", "disabled", "non-editable", "editable", "enable",
            "validate", "validation", "verify", "verification",
            "ocr", "extract",
            "dropdown", "reference table", "external data", "edv",
            "copy", "derive", "auto-fill", "populate",
            "if", "then", "otherwise", "else", "when"
        ]

        for keyword in keyword_list:
            if keyword in text_lower:
                keywords.append(keyword)

        return keywords

    def _extract_action_types(self, text: str) -> Tuple[List[str], float]:
        """
        Extract action types with confidence scores.

        Returns:
            Tuple of (action_types list, highest confidence)
        """
        actions = []
        max_confidence = 0.0

        for category, patterns in self.action_patterns.items():
            for pattern, action, confidence in patterns:
                if pattern.search(text):
                    if action not in actions:
                        actions.append(action)
                    max_confidence = max(max_confidence, confidence)

        return actions, max_confidence

    def _extract_document_type(self, text: str) -> Optional[str]:
        """Extract document type (PAN, GSTIN, etc.) from text."""
        for pattern, doc_type in self.doc_type_patterns:
            if pattern.search(text):
                return doc_type
        return None

    def _extract_field_references(self, text: str) -> List[str]:
        """Extract field name references from text."""
        references = []
        seen = set()

        for pattern in self.field_ref_patterns:
            matches = pattern.findall(text)
            for match in matches:
                field_name = match.strip()
                # Filter out common non-field words
                if field_name and field_name.lower() not in {
                    "yes", "no", "true", "false", "visible", "invisible",
                    "mandatory", "non-mandatory", "editable", "disabled"
                }:
                    normalized = field_name.lower()
                    if normalized not in seen:
                        references.append(field_name)
                        seen.add(normalized)

        return references

    def _extract_conditions(self, text: str) -> List[Condition]:
        """Extract conditional expressions from text."""
        conditions = []
        text_lower = text.lower()

        for pattern, cond_type in self.condition_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    field_name = match[0].strip()
                    value = match[1].strip() if len(match) > 1 else ""

                    # Clean up the value - filter out action words
                    if value.lower() in {'visible', 'invisible', 'mandatory', 'non-mandatory', 'editable', 'disabled', 'then', 'otherwise', 'else'}:
                        # Try to extract the actual value
                        value = self._extract_actual_value(text)

                    # Determine operator based on context
                    operator = "IN"
                    if "not" in text_lower or "!=" in text or "is not" in text_lower:
                        operator = "NOT_IN"

                    if field_name and value:
                        conditions.append(Condition(
                            field_name=field_name,
                            operator=operator,
                            value=value,
                            value_type="TEXT"
                        ))

        # If no conditions found, try to extract from common patterns
        if not conditions:
            extracted = self._extract_condition_from_text(text)
            if extracted:
                conditions.append(extracted)

        return conditions

    def _extract_actual_value(self, text: str) -> str:
        """Extract the actual conditional value from text."""
        text_lower = text.lower()

        # Pattern: "is yes", "is no", "= yes", etc.
        value_patterns = [
            r'\bis\s+(yes|no|true|false)\b',
            r'[=]\s*(yes|no|true|false)\b',
            r'values?\s+(?:is|=)\s+["\']?(\w+)["\']?',
            r'selected\s+(?:as|=)\s+["\']?(\w+)["\']?',
        ]

        for pattern in value_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = match.group(1)
                if val not in {'visible', 'invisible', 'mandatory', 'then', 'otherwise'}:
                    return val

        return "yes"  # Default

    def _extract_condition_from_text(self, text: str) -> Optional[Condition]:
        """Extract condition from natural language text."""
        text_lower = text.lower()

        # Pattern: "if 'Field Name' is yes then..."
        pattern = r"if\s+(?:the\s+)?(?:field\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:value\s+)?(?:is|=|==)\s+['\"]?(\w+)['\"]?"
        match = re.search(pattern, text_lower)
        if match:
            field_name = match.group(1).strip()
            value = match.group(2).strip()

            # Clean up field name
            field_name = re.sub(r'\s+(?:field|values?)$', '', field_name)

            # Filter out non-values
            if value in {'visible', 'invisible', 'mandatory', 'then', 'otherwise', 'else'}:
                value = "yes"

            return Condition(
                field_name=field_name,
                operator="IN",
                value=value,
                value_type="TEXT"
            )

        return None

    def _has_else_branch(self, text: str) -> bool:
        """Check if the logic has an else/otherwise branch."""
        text_lower = text.lower()
        return any(word in text_lower for word in ["otherwise", "else", "if not", "if no"])

    def _split_conditional_actions(self, text: str) -> Tuple[List[str], List[str]]:
        """
        Split actions into positive (when true) and negative (when false).

        Returns:
            Tuple of (positive_actions, negative_actions)
        """
        positive = []
        negative = []
        text_lower = text.lower()

        # Common pattern: "then X otherwise Y"
        then_match = re.search(
            r'then\s+(.+?)(?:otherwise|else)\s+(.+?)(?:$|\.)',
            text_lower,
            re.DOTALL
        )

        if then_match:
            then_part = then_match.group(1)
            else_part = then_match.group(2)

            # Extract actions from each part
            for action in ["visible", "mandatory"]:
                if action in then_part:
                    positive.append(f"MAKE_{action.upper()}")
                if action in else_part:
                    negative.append(f"MAKE_{action.upper()}")

            for action in ["invisible", "non-mandatory", "non mandatory"]:
                base = action.replace("non-", "").replace("non ", "")
                if action in then_part:
                    positive.append(f"MAKE_NON_{base.upper()}" if "non" in action else f"MAKE_IN{base.upper()}")
                if action in else_part:
                    negative.append(f"MAKE_NON_{base.upper()}" if "non" in action else f"MAKE_IN{base.upper()}")

            # Normalize action names
            positive = [self._normalize_action(a) for a in positive if a]
            negative = [self._normalize_action(a) for a in negative if a]

        return positive, negative

    def _normalize_action(self, action: str) -> str:
        """Normalize action type names."""
        action = action.upper()
        replacements = {
            "MAKE_INVISIBLEBLE": "MAKE_INVISIBLE",
            "MAKE_NON_MANDATORYATORY": "MAKE_NON_MANDATORY",
        }
        return replacements.get(action, action)

    def get_pattern_categories(self) -> Dict[str, List[str]]:
        """Get all pattern categories for debugging."""
        return {
            category: [
                (pattern.pattern, action, conf)
                for pattern, action, conf in patterns
            ]
            for category, patterns in self.action_patterns.items()
        }


class KeywordExtractor:
    """Extracts specific keywords and phrases from logic text."""

    # Document type keywords
    DOC_KEYWORDS = {
        "pan": "PAN",
        "gstin": "GSTIN",
        "gst": "GSTIN",
        "bank": "BANK",
        "msme": "MSME",
        "udyam": "MSME",
        "cin": "CIN",
        "tan": "TAN",
        "fssai": "FSSAI",
        "aadhaar": "AADHAAR",
        "aadhar": "AADHAAR",
        "cheque": "CHEQUE",
    }

    @classmethod
    def extract_document_keywords(cls, text: str) -> Set[str]:
        """Extract document type keywords from text."""
        text_lower = text.lower()
        found = set()
        for keyword, doc_type in cls.DOC_KEYWORDS.items():
            if keyword in text_lower:
                found.add(doc_type)
        return found

    @classmethod
    def extract_conditional_values(cls, text: str) -> List[str]:
        """Extract conditional values like 'yes', 'no', specific values."""
        values = []
        text_lower = text.lower()

        # FIRST: Look for "values is <value>" pattern - most specific
        values_match = re.search(r'values?\s+(?:is|=)\s+["\']?(\w+)["\']?', text_lower)
        if values_match:
            val = values_match.group(1)
            if val not in {'if', 'then', 'otherwise', 'else', 'the', 'field', 'visible', 'invisible', 'mandatory', 'when'}:
                values.append(val)

        # Look for "is yes", "is no" patterns (NOT inside quotes)
        # But skip if part of a field name pattern like '"field name" is yes'
        is_yes_match = re.search(r'(?<!["\'])\b(?:is|=)\s+(yes|no|true|false)\b', text_lower)
        if is_yes_match and is_yes_match.group(1) not in [v.lower() for v in values]:
            values.append(is_yes_match.group(1))

        # Look for "selected as X" or "chosen as X"
        for pattern in [r"selected\s+(?:as|=)\s+['\"]?(\w+)['\"]?",
                        r"chosen\s+(?:as|=)\s+['\"]?(\w+)['\"]?"]:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                if m not in {'if', 'then', 'otherwise', 'else', 'the', 'field', 'visible', 'invisible', 'mandatory'}:
                    if m not in [v.lower() for v in values]:
                        values.append(m)

        # Default to 'yes' if no values found but text has "if" and "then"
        if not values and 'if' in text_lower and 'then' in text_lower:
            # Check for negation patterns
            if any(neg in text_lower for neg in ['is no,', 'is no ', 'is not ', '!= yes', 'not yes']):
                values.append("no")
            else:
                values.append("yes")

        # Deduplicate while preserving order
        seen = set()
        result = []
        for v in values:
            v_lower = v.lower()
            if v_lower not in seen:
                seen.add(v_lower)
                result.append(v_lower)

        return result
