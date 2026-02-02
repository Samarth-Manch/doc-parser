"""
Rule selection tree for deterministic rule type selection.

Uses a decision tree structure to map parsed logic to specific rule types
based on keywords, document types, and patterns.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from .models import ParsedLogic, RuleMatch
from .schema_lookup import RuleSchemaLookup


@dataclass
class TreeNode:
    """Node in the rule selection tree."""
    name: str
    action_type: Optional[str] = None
    source_type: Optional[str] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    children: Dict[str, "TreeNode"] = field(default_factory=dict)
    match_keywords: List[str] = field(default_factory=list)
    match_patterns: List[str] = field(default_factory=list)

    def add_child(self, key: str, node: "TreeNode") -> None:
        self.children[key] = node


class RuleSelectionTree:
    """
    Decision tree for selecting rule types from parsed logic.

    Structure:
    ROOT
    +-- VISIBILITY_CONTROL
    |   +-- MAKE_VISIBLE
    |   +-- MAKE_INVISIBLE
    +-- MANDATORY_CONTROL
    |   +-- MAKE_MANDATORY
    |   +-- MAKE_NON_MANDATORY
    +-- EDITABILITY_CONTROL
    |   +-- MAKE_DISABLED
    |   +-- MAKE_ENABLED
    +-- VALIDATION
    |   +-- PAN_VALIDATION
    |   +-- GSTIN_VALIDATION
    |   +-- BANK_VALIDATION
    |   +-- ...
    +-- OCR_EXTRACTION
    |   +-- PAN_OCR
    |   +-- GSTIN_OCR
    |   +-- ...
    +-- DATA_OPERATIONS
        +-- COPY_TO
        +-- EDV
    """

    # Document type to source type mappings
    DOC_TO_VERIFY_SOURCE = {
        "PAN": "PAN_NUMBER",
        "GSTIN": "GSTIN",
        "BANK": "BANK_ACCOUNT_NUMBER",
        "MSME": "MSME_UDYAM_REG_NUMBER",
        "CIN": "CIN_ID",
        "TAN": "TAN_NUMBER",
        "FSSAI": "FSSAI",
        "PINCODE": "PINCODE",
    }

    DOC_TO_OCR_SOURCE = {
        "PAN": "PAN_IMAGE",
        "GSTIN": "GSTIN_IMAGE",
        "AADHAAR": "AADHAR_IMAGE",
        "AADHAAR_BACK": "AADHAR_BACK_IMAGE",
        "CHEQUE": "CHEQUEE",
        "CIN": "CIN",
        "MSME": "MSME",
    }

    # Schema IDs for common rules
    VERIFY_SCHEMA_IDS = {
        "PAN_NUMBER": 360,
        "GSTIN": 355,
        "BANK_ACCOUNT_NUMBER": 361,
        "MSME_UDYAM_REG_NUMBER": 337,
        "CIN_ID": 349,
        "TAN_NUMBER": 322,
        "FSSAI": 356,
        "PINCODE": 333,
        "GSTIN_WITH_PAN": 329,
    }

    OCR_SCHEMA_IDS = {
        "PAN_IMAGE": 344,
        "GSTIN_IMAGE": 347,
        "AADHAR_IMAGE": 359,
        "AADHAR_BACK_IMAGE": 348,
        "CHEQUEE": 269,
        "CIN": 357,
        "MSME": 214,
    }

    def __init__(self, schema_lookup: Optional[RuleSchemaLookup] = None):
        """
        Initialize the rule selection tree.

        Args:
            schema_lookup: Optional RuleSchemaLookup for schema ID validation
        """
        self.schema_lookup = schema_lookup
        self._build_tree()

    def _build_tree(self) -> None:
        """Build the decision tree structure."""
        self.root = TreeNode(name="ROOT")

        # Visibility control branch
        visibility = TreeNode(
            name="VISIBILITY_CONTROL",
            match_keywords=["visible", "invisible", "show", "hide", "display"]
        )
        visibility.add_child("MAKE_VISIBLE", TreeNode(
            name="MAKE_VISIBLE",
            action_type="MAKE_VISIBLE",
            confidence=0.95,
            match_keywords=["visible", "show", "display"]
        ))
        visibility.add_child("MAKE_INVISIBLE", TreeNode(
            name="MAKE_INVISIBLE",
            action_type="MAKE_INVISIBLE",
            confidence=0.95,
            match_keywords=["invisible", "hide", "hidden"]
        ))
        self.root.add_child("VISIBILITY", visibility)

        # Mandatory control branch
        mandatory = TreeNode(
            name="MANDATORY_CONTROL",
            match_keywords=["mandatory", "required", "optional"]
        )
        mandatory.add_child("MAKE_MANDATORY", TreeNode(
            name="MAKE_MANDATORY",
            action_type="MAKE_MANDATORY",
            confidence=0.95,
            match_keywords=["mandatory", "required"]
        ))
        mandatory.add_child("MAKE_NON_MANDATORY", TreeNode(
            name="MAKE_NON_MANDATORY",
            action_type="MAKE_NON_MANDATORY",
            confidence=0.95,
            match_keywords=["non-mandatory", "optional", "not mandatory"]
        ))
        self.root.add_child("MANDATORY", mandatory)

        # Editability control branch
        editability = TreeNode(
            name="EDITABILITY_CONTROL",
            match_keywords=["editable", "disabled", "non-editable", "enable"]
        )
        editability.add_child("MAKE_DISABLED", TreeNode(
            name="MAKE_DISABLED",
            action_type="MAKE_DISABLED",
            confidence=0.95,
            match_keywords=["disabled", "disable", "non-editable", "read-only"]
        ))
        editability.add_child("MAKE_ENABLED", TreeNode(
            name="MAKE_ENABLED",
            action_type="MAKE_ENABLED",
            confidence=0.85,
            match_keywords=["editable", "enable", "enabled"]
        ))
        self.root.add_child("EDITABILITY", editability)

        # Validation branch
        validation = TreeNode(
            name="VALIDATION",
            match_keywords=["validate", "validation", "verify", "verification"]
        )
        for doc_type, source in self.DOC_TO_VERIFY_SOURCE.items():
            schema_id = self.VERIFY_SCHEMA_IDS.get(source)
            validation.add_child(f"{doc_type}_VALIDATION", TreeNode(
                name=f"{doc_type}_VALIDATION",
                action_type="VERIFY",
                source_type=source,
                schema_id=schema_id,
                confidence=0.95,
                match_keywords=[doc_type.lower(), "validation", "verify"]
            ))
        self.root.add_child("VALIDATION", validation)

        # OCR extraction branch
        ocr = TreeNode(
            name="OCR_EXTRACTION",
            match_keywords=["ocr", "extract", "scan", "image"]
        )
        for doc_type, source in self.DOC_TO_OCR_SOURCE.items():
            schema_id = self.OCR_SCHEMA_IDS.get(source)
            ocr.add_child(f"{doc_type}_OCR", TreeNode(
                name=f"{doc_type}_OCR",
                action_type="OCR",
                source_type=source,
                schema_id=schema_id,
                confidence=0.95,
                match_keywords=[doc_type.lower(), "ocr", "image"]
            ))
        self.root.add_child("OCR", ocr)

        # Data operations branch
        data_ops = TreeNode(
            name="DATA_OPERATIONS",
            match_keywords=["copy", "derive", "populate", "dropdown", "external"]
        )
        data_ops.add_child("COPY_TO", TreeNode(
            name="COPY_TO",
            action_type="COPY_TO",
            confidence=0.85,
            match_keywords=["copy", "derive", "auto-fill", "populate"]
        ))
        data_ops.add_child("EXT_DROP_DOWN", TreeNode(
            name="EXT_DROP_DOWN",
            action_type="EXT_DROP_DOWN",
            confidence=0.85,
            match_keywords=["dropdown", "reference table", "external data"]
        ))
        data_ops.add_child("EXT_VALUE", TreeNode(
            name="EXT_VALUE",
            action_type="EXT_VALUE",
            confidence=0.85,
            match_keywords=["external data", "edv", "derived value"]
        ))
        self.root.add_child("DATA_OPS", data_ops)

    def select_rules(self, parsed_logic: ParsedLogic) -> List[RuleMatch]:
        """
        Select appropriate rules based on parsed logic.

        Args:
            parsed_logic: ParsedLogic from LogicParser

        Returns:
            List of RuleMatch objects
        """
        if parsed_logic.skip_reason:
            return []

        matches = []

        # Traverse tree based on keywords and action types
        for action_type in parsed_logic.action_types:
            match = self._find_match_for_action(action_type, parsed_logic)
            if match:
                matches.append(match)

        # If no matches from action types, try keyword-based matching
        if not matches:
            matches = self._match_by_keywords(parsed_logic)

        # Handle conditional logic - generate rule pairs
        if parsed_logic.is_conditional and parsed_logic.has_else_branch:
            matches = self._expand_conditional_rules(matches, parsed_logic)

        return matches

    def _find_match_for_action(
        self,
        action_type: str,
        parsed_logic: ParsedLogic
    ) -> Optional[RuleMatch]:
        """Find a match for a specific action type."""
        # Direct action type matches
        if action_type == "MAKE_VISIBLE":
            return RuleMatch(
                action_type="MAKE_VISIBLE",
                confidence=0.95,
                matched_pattern="visibility"
            )
        elif action_type == "MAKE_INVISIBLE":
            return RuleMatch(
                action_type="MAKE_INVISIBLE",
                confidence=0.95,
                matched_pattern="visibility"
            )
        elif action_type == "MAKE_MANDATORY":
            return RuleMatch(
                action_type="MAKE_MANDATORY",
                confidence=0.95,
                matched_pattern="mandatory"
            )
        elif action_type == "MAKE_NON_MANDATORY":
            return RuleMatch(
                action_type="MAKE_NON_MANDATORY",
                confidence=0.95,
                matched_pattern="mandatory"
            )
        elif action_type == "MAKE_DISABLED":
            return RuleMatch(
                action_type="MAKE_DISABLED",
                confidence=0.95,
                matched_pattern="disable"
            )
        elif action_type == "MAKE_ENABLED":
            return RuleMatch(
                action_type="MAKE_ENABLED",
                confidence=0.85,
                matched_pattern="enable"
            )
        elif action_type == "VERIFY":
            return self._match_verify(parsed_logic)
        elif action_type == "OCR":
            return self._match_ocr(parsed_logic)
        elif action_type == "EXT_DROP_DOWN":
            return RuleMatch(
                action_type="EXT_DROP_DOWN",
                confidence=0.85,
                matched_pattern="dropdown"
            )
        elif action_type == "EXT_VALUE":
            return RuleMatch(
                action_type="EXT_VALUE",
                confidence=0.85,
                matched_pattern="external data"
            )
        elif action_type == "COPY_TO":
            return RuleMatch(
                action_type="COPY_TO",
                confidence=0.85,
                matched_pattern="copy/derive"
            )

        return None

    def _match_verify(self, parsed_logic: ParsedLogic) -> Optional[RuleMatch]:
        """Match VERIFY rule with appropriate source type."""
        doc_type = parsed_logic.document_type

        if doc_type and doc_type in self.DOC_TO_VERIFY_SOURCE:
            source_type = self.DOC_TO_VERIFY_SOURCE[doc_type]
            schema_id = self.VERIFY_SCHEMA_IDS.get(source_type)
            return RuleMatch(
                action_type="VERIFY",
                source_type=source_type,
                schema_id=schema_id,
                confidence=0.95,
                matched_pattern=f"{doc_type} validation"
            )

        # Try to infer from text
        text_lower = parsed_logic.original_text.lower()
        for doc, source in self.DOC_TO_VERIFY_SOURCE.items():
            if doc.lower() in text_lower:
                schema_id = self.VERIFY_SCHEMA_IDS.get(source)
                return RuleMatch(
                    action_type="VERIFY",
                    source_type=source,
                    schema_id=schema_id,
                    confidence=0.90,
                    matched_pattern=f"{doc} validation (inferred)"
                )

        return RuleMatch(
            action_type="VERIFY",
            confidence=0.70,
            matched_pattern="generic validation",
            requires_llm=True
        )

    def _match_ocr(self, parsed_logic: ParsedLogic) -> Optional[RuleMatch]:
        """Match OCR rule with appropriate source type."""
        doc_type = parsed_logic.document_type
        text_lower = parsed_logic.original_text.lower()

        # Check for specific OCR mentions
        if doc_type:
            # Check if it's back image (for Aadhaar)
            if doc_type == "AADHAAR" and "back" in text_lower:
                source_type = "AADHAR_BACK_IMAGE"
            elif doc_type in self.DOC_TO_OCR_SOURCE:
                source_type = self.DOC_TO_OCR_SOURCE[doc_type]
            else:
                source_type = None

            if source_type:
                schema_id = self.OCR_SCHEMA_IDS.get(source_type)
                return RuleMatch(
                    action_type="OCR",
                    source_type=source_type,
                    schema_id=schema_id,
                    confidence=0.95,
                    matched_pattern=f"{doc_type} OCR"
                )

        # Try to infer from text
        for doc, source in self.DOC_TO_OCR_SOURCE.items():
            doc_lower = doc.lower().replace("_", " ")
            if doc_lower in text_lower:
                schema_id = self.OCR_SCHEMA_IDS.get(source)
                return RuleMatch(
                    action_type="OCR",
                    source_type=source,
                    schema_id=schema_id,
                    confidence=0.90,
                    matched_pattern=f"{doc} OCR (inferred)"
                )

        return RuleMatch(
            action_type="OCR",
            confidence=0.70,
            matched_pattern="generic OCR",
            requires_llm=True
        )

    def _match_by_keywords(self, parsed_logic: ParsedLogic) -> List[RuleMatch]:
        """Match rules based on keywords when action types aren't explicit."""
        matches = []
        keywords = set(parsed_logic.keywords)
        text_lower = parsed_logic.original_text.lower()

        # Check visibility keywords
        if keywords & {"visible", "show", "display"}:
            matches.append(RuleMatch(
                action_type="MAKE_VISIBLE",
                confidence=0.85,
                matched_pattern="keyword: visible"
            ))
        if keywords & {"invisible", "hide", "hidden"}:
            matches.append(RuleMatch(
                action_type="MAKE_INVISIBLE",
                confidence=0.85,
                matched_pattern="keyword: invisible"
            ))

        # Check mandatory keywords
        if "mandatory" in keywords and "non" not in text_lower:
            matches.append(RuleMatch(
                action_type="MAKE_MANDATORY",
                confidence=0.85,
                matched_pattern="keyword: mandatory"
            ))
        if "non-mandatory" in keywords or "optional" in keywords:
            matches.append(RuleMatch(
                action_type="MAKE_NON_MANDATORY",
                confidence=0.85,
                matched_pattern="keyword: non-mandatory"
            ))

        # Check disable keywords
        if keywords & {"disable", "disabled", "non-editable"}:
            matches.append(RuleMatch(
                action_type="MAKE_DISABLED",
                confidence=0.85,
                matched_pattern="keyword: disable"
            ))

        return matches

    def _expand_conditional_rules(
        self,
        matches: List[RuleMatch],
        parsed_logic: ParsedLogic
    ) -> List[RuleMatch]:
        """
        Expand rules for conditional logic with else branches.

        For "if X then visible otherwise invisible" pattern,
        generates both MAKE_VISIBLE and MAKE_INVISIBLE rules.
        """
        expanded = []

        for match in matches:
            expanded.append(match)

            # Add inverse rule for conditionals
            if match.action_type == "MAKE_VISIBLE":
                expanded.append(RuleMatch(
                    action_type="MAKE_INVISIBLE",
                    confidence=match.confidence,
                    matched_pattern=f"{match.matched_pattern} (else branch)"
                ))
            elif match.action_type == "MAKE_INVISIBLE":
                expanded.append(RuleMatch(
                    action_type="MAKE_VISIBLE",
                    confidence=match.confidence,
                    matched_pattern=f"{match.matched_pattern} (else branch)"
                ))
            elif match.action_type == "MAKE_MANDATORY":
                expanded.append(RuleMatch(
                    action_type="MAKE_NON_MANDATORY",
                    confidence=match.confidence,
                    matched_pattern=f"{match.matched_pattern} (else branch)"
                ))
            elif match.action_type == "MAKE_NON_MANDATORY":
                expanded.append(RuleMatch(
                    action_type="MAKE_MANDATORY",
                    confidence=match.confidence,
                    matched_pattern=f"{match.matched_pattern} (else branch)"
                ))

        return expanded

    def get_verify_schema_id(self, doc_type: str) -> Optional[int]:
        """Get VERIFY schema ID for a document type."""
        source = self.DOC_TO_VERIFY_SOURCE.get(doc_type)
        if source:
            return self.VERIFY_SCHEMA_IDS.get(source)
        return None

    def get_ocr_schema_id(self, doc_type: str) -> Optional[int]:
        """Get OCR schema ID for a document type."""
        source = self.DOC_TO_OCR_SOURCE.get(doc_type)
        if source:
            return self.OCR_SCHEMA_IDS.get(source)
        return None
