"""
Field Comparator for the Eval framework.

Compares fields between generated and reference JSON using:
1. Equality check first (deterministic)
2. LLM fallback for fuzzy matching
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from .models import FieldMatch, FieldComparison, Discrepancy, DiscrepancyType, DiscrepancySeverity
from .llm_client import FieldMatchLLM, get_llm_client


class FieldComparator:
    """
    Compares fields between generated and reference JSON.

    Uses a deterministic-first approach:
    1. Exact string match (case-insensitive)
    2. Normalized string match (remove special chars, spaces)
    3. LLM-based semantic matching (if enabled)
    """

    def __init__(
        self,
        use_llm: bool = True,
        llm_threshold: float = 0.8,
        llm_client: Optional[Any] = None
    ):
        """
        Initialize the FieldComparator.

        Args:
            use_llm: Whether to use LLM for fuzzy matching
            llm_threshold: Confidence threshold for LLM matches
            llm_client: Optional LLM client instance
        """
        self.use_llm = use_llm
        self.llm_threshold = llm_threshold
        self.field_match_llm = FieldMatchLLM(llm_client) if use_llm else None

        # Cache for LLM matches to avoid redundant calls
        self._llm_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize a field name for comparison.

        Args:
            name: Original field name

        Returns:
            Normalized field name (lowercase, no special chars)
        """
        # Remove leading/trailing whitespace
        name = name.strip()

        # Convert to lowercase
        name = name.lower()

        # Remove variable-style prefixes/suffixes (_fieldName_ -> fieldName)
        name = re.sub(r'^_+|_+$', '', name)

        # Replace special characters and multiple spaces with single space
        name = re.sub(r'[^a-z0-9\s]', ' ', name)
        name = re.sub(r'\s+', ' ', name)

        return name.strip()

    def exact_match(self, name1: str, name2: str) -> bool:
        """
        Check for exact match (case-insensitive).

        Args:
            name1: First field name
            name2: Second field name

        Returns:
            True if names match exactly (case-insensitive)
        """
        return name1.strip().lower() == name2.strip().lower()

    def normalized_match(self, name1: str, name2: str) -> bool:
        """
        Check for normalized match.

        Args:
            name1: First field name
            name2: Second field name

        Returns:
            True if normalized names match
        """
        return self.normalize_name(name1) == self.normalize_name(name2)

    def llm_match(
        self,
        name1: str,
        name2: str,
        context1: Optional[str] = None,
        context2: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check for semantic match using LLM.

        Args:
            name1: First field name
            name2: Second field name
            context1: Optional context for first field
            context2: Optional context for second field

        Returns:
            Dict with is_match, confidence, reasoning
        """
        if not self.use_llm or not self.field_match_llm:
            return {
                "is_match": False,
                "confidence": 0.0,
                "reasoning": "LLM matching disabled"
            }

        # Check cache
        cache_key = (name1.lower(), name2.lower())
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]

        # Also check reverse
        cache_key_rev = (name2.lower(), name1.lower())
        if cache_key_rev in self._llm_cache:
            return self._llm_cache[cache_key_rev]

        # Make LLM call
        result = self.field_match_llm.match_field_names(
            name1, name2, context1, context2
        )

        # Cache result
        self._llm_cache[cache_key] = result

        return result

    def compare_names(
        self,
        generated_name: str,
        reference_name: str,
        generated_context: Optional[str] = None,
        reference_context: Optional[str] = None
    ) -> FieldMatch:
        """
        Compare two field names using the deterministic-first approach.

        Args:
            generated_name: Field name from generated JSON
            reference_name: Field name from reference JSON
            generated_context: Context for generated field (e.g., panel name)
            reference_context: Context for reference field

        Returns:
            FieldMatch object with match result
        """
        # Step 1: Exact match
        if self.exact_match(generated_name, reference_name):
            return FieldMatch(
                is_match=True,
                match_type="exact",
                confidence=1.0,
                generated_name=generated_name,
                reference_name=reference_name,
            )

        # Step 2: Normalized match
        if self.normalized_match(generated_name, reference_name):
            return FieldMatch(
                is_match=True,
                match_type="normalized",
                confidence=0.95,
                generated_name=generated_name,
                reference_name=reference_name,
            )

        # Step 3: LLM match (if enabled)
        if self.use_llm:
            llm_result = self.llm_match(
                generated_name,
                reference_name,
                generated_context,
                reference_context
            )

            if llm_result["is_match"] and llm_result["confidence"] >= self.llm_threshold:
                return FieldMatch(
                    is_match=True,
                    match_type="llm",
                    confidence=llm_result["confidence"],
                    generated_name=generated_name,
                    reference_name=reference_name,
                    llm_reasoning=llm_result.get("reasoning"),
                )

        # No match found
        return FieldMatch(
            is_match=False,
            match_type="no_match",
            confidence=0.0,
            generated_name=generated_name,
            reference_name=reference_name,
        )

    def compare_types(
        self,
        generated_type: str,
        reference_type: str
    ) -> bool:
        """
        Compare field types using equality check only.

        Args:
            generated_type: Field type from generated JSON
            reference_type: Field type from reference JSON

        Returns:
            True if types match
        """
        # Normalize types
        gen_type = generated_type.strip().upper()
        ref_type = reference_type.strip().upper()

        # Direct match
        if gen_type == ref_type:
            return True

        # Handle known equivalents
        type_equivalents = {
            ("EXTERNAL_DROP_DOWN_VALUE", "EXTERNAL_DROP_DOWN"): True,
            ("EXTERNAL_DROP_DOWN", "EXTERNAL_DROP_DOWN_VALUE"): True,
            ("DROP_DOWN", "DROPDOWN"): True,
            ("DROPDOWN", "DROP_DOWN"): True,
            ("MULTI_DROP_DOWN", "MULTI_DROPDOWN"): True,
            ("MULTI_DROPDOWN", "MULTI_DROP_DOWN"): True,
        }

        return type_equivalents.get((gen_type, ref_type), False)

    def compare_field(
        self,
        generated_field: Dict[str, Any],
        reference_field: Dict[str, Any]
    ) -> FieldComparison:
        """
        Compare a single generated field against a reference field.

        Args:
            generated_field: Field from generated JSON
            reference_field: Field from reference JSON

        Returns:
            FieldComparison object with comparison result
        """
        # Extract field info
        gen_id = generated_field.get("id", 0)
        ref_id = reference_field.get("id", 0)

        gen_form_tag = generated_field.get("formTag", {})
        ref_form_tag = reference_field.get("formTag", {})

        gen_name = gen_form_tag.get("name", "")
        ref_name = ref_form_tag.get("name", "")

        gen_type = gen_form_tag.get("type", "")
        ref_type = ref_form_tag.get("type", "")

        is_panel = gen_type.upper() == "PANEL" or ref_type.upper() == "PANEL"

        # Compare names
        name_match = self.compare_names(gen_name, ref_name)

        # Compare types
        type_match = self.compare_types(gen_type, ref_type)

        return FieldComparison(
            generated_field_id=gen_id,
            reference_field_id=ref_id,
            generated_field_name=gen_name,
            reference_field_name=ref_name,
            name_match=name_match,
            type_match=type_match,
            generated_type=gen_type,
            reference_type=ref_type,
            is_panel=is_panel,
        )

    def find_matching_field(
        self,
        generated_field: Dict[str, Any],
        reference_fields: List[Dict[str, Any]],
        already_matched: set = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[FieldComparison]]:
        """
        Find a matching reference field for a generated field.

        Args:
            generated_field: Field from generated JSON
            reference_fields: List of fields from reference JSON
            already_matched: Set of already matched reference field IDs

        Returns:
            Tuple of (matched_reference_field, comparison) or (None, None)
        """
        if already_matched is None:
            already_matched = set()

        gen_form_tag = generated_field.get("formTag", {})
        gen_name = gen_form_tag.get("name", "")

        best_match = None
        best_comparison = None
        best_confidence = 0.0

        for ref_field in reference_fields:
            ref_id = ref_field.get("id", 0)

            # Skip already matched fields
            if ref_id in already_matched:
                continue

            comparison = self.compare_field(generated_field, ref_field)

            if comparison.name_match.is_match:
                # Prioritize by confidence
                if comparison.name_match.confidence > best_confidence:
                    best_match = ref_field
                    best_comparison = comparison
                    best_confidence = comparison.name_match.confidence

                    # Perfect match - return immediately
                    if comparison.name_match.match_type == "exact":
                        break

        return best_match, best_comparison

    def compare_all_fields(
        self,
        generated_fields: List[Dict[str, Any]],
        reference_fields: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare all fields between generated and reference JSON.

        Args:
            generated_fields: List of fields from generated JSON
            reference_fields: List of fields from reference JSON

        Returns:
            Dictionary with comparison results including:
            - matched_pairs: List of (generated_field, reference_field, comparison)
            - unmatched_generated: List of generated fields without matches
            - unmatched_reference: List of reference fields without matches
            - field_id_mapping: Dict mapping generated IDs to reference IDs
            - discrepancies: List of Discrepancy objects
        """
        matched_pairs = []
        unmatched_generated = []
        matched_ref_ids = set()
        field_id_mapping = {}
        discrepancies = []

        # First pass: find matches
        for gen_field in generated_fields:
            ref_field, comparison = self.find_matching_field(
                gen_field, reference_fields, matched_ref_ids
            )

            if ref_field and comparison:
                matched_pairs.append((gen_field, ref_field, comparison))
                matched_ref_ids.add(ref_field.get("id", 0))
                field_id_mapping[gen_field.get("id", 0)] = ref_field.get("id", 0)

                # Check for type mismatch
                if not comparison.type_match:
                    discrepancies.append(Discrepancy(
                        type=DiscrepancyType.FIELD_TYPE_MISMATCH,
                        severity=DiscrepancySeverity.MEDIUM,
                        field_name=comparison.generated_field_name,
                        rule_id=None,
                        message=f"Field type mismatch: generated '{comparison.generated_type}' vs reference '{comparison.reference_type}'",
                        expected=comparison.reference_type,
                        actual=comparison.generated_type,
                        fix_instruction=f"Change field type from {comparison.generated_type} to {comparison.reference_type}",
                    ))
            else:
                unmatched_generated.append(gen_field)

        # Find unmatched reference fields
        unmatched_reference = [
            ref_field for ref_field in reference_fields
            if ref_field.get("id", 0) not in matched_ref_ids
        ]

        # Create discrepancies for unmatched fields
        for gen_field in unmatched_generated:
            gen_form_tag = gen_field.get("formTag", {})
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.FIELD_MISSING,
                severity=DiscrepancySeverity.LOW,  # Extra field in generated
                field_name=gen_form_tag.get("name", "Unknown"),
                rule_id=None,
                message=f"Generated field '{gen_form_tag.get('name', 'Unknown')}' has no matching reference field",
                expected=None,
                actual=gen_form_tag.get("name", "Unknown"),
                fix_instruction="This may be an extra field not in reference",
            ))

        for ref_field in unmatched_reference:
            ref_form_tag = ref_field.get("formTag", {})
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.FIELD_MISSING,
                severity=DiscrepancySeverity.HIGH,  # Missing field in generated
                field_name=ref_form_tag.get("name", "Unknown"),
                rule_id=None,
                message=f"Reference field '{ref_form_tag.get('name', 'Unknown')}' not found in generated output",
                expected=ref_form_tag.get("name", "Unknown"),
                actual=None,
                fix_instruction=f"Add field '{ref_form_tag.get('name', 'Unknown')}' to generated output",
            ))

        return {
            "matched_pairs": matched_pairs,
            "unmatched_generated": unmatched_generated,
            "unmatched_reference": unmatched_reference,
            "field_id_mapping": field_id_mapping,
            "discrepancies": discrepancies,
            "summary": {
                "total_generated": len(generated_fields),
                "total_reference": len(reference_fields),
                "matched": len(matched_pairs),
                "unmatched_generated": len(unmatched_generated),
                "unmatched_reference": len(unmatched_reference),
            }
        }


def build_field_id_to_name_map(fields: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Build a mapping from field ID to field name.

    Args:
        fields: List of field dictionaries

    Returns:
        Dictionary mapping field IDs to names
    """
    id_to_name = {}
    for field in fields:
        field_id = field.get("id", 0)
        form_tag = field.get("formTag", {})
        name = form_tag.get("name", f"field_{field_id}")
        id_to_name[field_id] = name
    return id_to_name


def build_field_id_to_type_map(fields: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Build a mapping from field ID to field type.

    Args:
        fields: List of field dictionaries

    Returns:
        Dictionary mapping field IDs to types
    """
    id_to_type = {}
    for field in fields:
        field_id = field.get("id", 0)
        form_tag = field.get("formTag", {})
        field_type = form_tag.get("type", "UNKNOWN")
        id_to_type[field_id] = field_type
    return id_to_type


def build_rule_id_to_field_map(fields: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    Build a mapping from rule ID to the field it belongs to.

    Args:
        fields: List of field dictionaries

    Returns:
        Dictionary mapping rule IDs to field info
    """
    rule_to_field = {}
    for field in fields:
        field_id = field.get("id", 0)
        form_tag = field.get("formTag", {})
        field_name = form_tag.get("name", f"field_{field_id}")
        field_type = form_tag.get("type", "UNKNOWN")

        rules = field.get("formFillRules", [])
        for rule in rules:
            rule_id = rule.get("id", 0)
            rule_to_field[rule_id] = {
                "field_id": field_id,
                "field_name": field_name,
                "field_type": field_type,
                "rule": rule,
            }

    return rule_to_field
