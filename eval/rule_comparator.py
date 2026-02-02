"""
Rule Comparator for the Eval framework.

Compares rules between generated and reference JSON including:
1. Rule action types
2. Source and destination IDs (via field name resolution)
3. Conditions and conditional values
4. postTriggerRuleIds
5. params
"""

import json
from typing import Dict, Any, List, Optional, Tuple, Set
from .models import (
    RuleComparison,
    RuleEvalResult,
    IdResolution,
    Discrepancy,
    DiscrepancyType,
    DiscrepancySeverity,
)
from .field_comparator import (
    FieldComparator,
    build_field_id_to_name_map,
    build_field_id_to_type_map,
    build_rule_id_to_field_map,
)


class RuleComparator:
    """
    Compares rules between generated and reference JSON.

    Uses field name resolution for comparing IDs, as IDs may differ
    between generated and reference outputs.
    """

    def __init__(
        self,
        generated_fields: List[Dict[str, Any]],
        reference_fields: List[Dict[str, Any]],
        field_id_mapping: Dict[int, int],
        field_comparator: Optional[FieldComparator] = None
    ):
        """
        Initialize the RuleComparator.

        Args:
            generated_fields: List of fields from generated JSON
            reference_fields: List of fields from reference JSON
            field_id_mapping: Mapping from generated field IDs to reference field IDs
            field_comparator: Optional FieldComparator for name matching
        """
        self.generated_fields = generated_fields
        self.reference_fields = reference_fields
        self.field_id_mapping = field_id_mapping
        self.field_comparator = field_comparator or FieldComparator(use_llm=True)

        # Build helper maps
        self.gen_id_to_name = build_field_id_to_name_map(generated_fields)
        self.ref_id_to_name = build_field_id_to_name_map(reference_fields)
        self.gen_id_to_type = build_field_id_to_type_map(generated_fields)
        self.ref_id_to_type = build_field_id_to_type_map(reference_fields)
        self.gen_rule_to_field = build_rule_id_to_field_map(generated_fields)
        self.ref_rule_to_field = build_rule_id_to_field_map(reference_fields)

        # Reverse mapping: reference ID to generated ID
        self.reverse_field_mapping = {v: k for k, v in field_id_mapping.items()}

    def resolve_id(
        self,
        field_id: int,
        source: str = "generated"
    ) -> IdResolution:
        """
        Resolve a field ID to its name and type.

        Args:
            field_id: The field ID to resolve
            source: "generated" or "reference"

        Returns:
            IdResolution with resolved info
        """
        if source == "generated":
            id_to_name = self.gen_id_to_name
            id_to_type = self.gen_id_to_type
        else:
            id_to_name = self.ref_id_to_name
            id_to_type = self.ref_id_to_type

        if field_id in id_to_name:
            return IdResolution(
                original_id=field_id,
                resolved_field_name=id_to_name[field_id],
                resolved_field_type=id_to_type.get(field_id, "UNKNOWN"),
                is_valid=True,
                source_json=source,
            )
        else:
            return IdResolution(
                original_id=field_id,
                resolved_field_name=None,
                resolved_field_type=None,
                is_valid=False,
                source_json=source,
                error=f"Field ID {field_id} not found in {source} fields",
            )

    def compare_id_lists(
        self,
        generated_ids: List[int],
        reference_ids: List[int],
        id_type: str = "source"
    ) -> Tuple[bool, List[Tuple[IdResolution, IdResolution]], List[Discrepancy]]:
        """
        Compare two lists of IDs by resolving to field names.

        Args:
            generated_ids: List of IDs from generated rule
            reference_ids: List of IDs from reference rule
            id_type: "source" or "destination"

        Returns:
            Tuple of (all_match, resolutions, discrepancies)
        """
        resolutions = []
        discrepancies = []

        # Resolve all generated IDs to names
        gen_names = set()
        for gen_id in generated_ids:
            gen_resolution = self.resolve_id(gen_id, "generated")
            if gen_resolution.is_valid:
                gen_names.add(gen_resolution.resolved_field_name.lower())

        # Resolve all reference IDs to names
        ref_names = set()
        for ref_id in reference_ids:
            ref_resolution = self.resolve_id(ref_id, "reference")
            if ref_resolution.is_valid:
                ref_names.add(ref_resolution.resolved_field_name.lower())

        # Compare using field names (case-insensitive)
        # For each reference name, check if there's a matching generated name
        all_match = True
        matched_gen_names = set()
        matched_ref_names = set()

        for gen_id in generated_ids:
            gen_resolution = self.resolve_id(gen_id, "generated")
            best_ref_resolution = None

            if gen_resolution.is_valid:
                gen_name = gen_resolution.resolved_field_name

                # Try to find matching reference ID
                for ref_id in reference_ids:
                    ref_resolution = self.resolve_id(ref_id, "reference")
                    if ref_resolution.is_valid:
                        ref_name = ref_resolution.resolved_field_name

                        # Check name match
                        name_match = self.field_comparator.compare_names(gen_name, ref_name)
                        if name_match.is_match:
                            best_ref_resolution = ref_resolution
                            matched_gen_names.add(gen_name.lower())
                            matched_ref_names.add(ref_name.lower())
                            break

            if best_ref_resolution:
                resolutions.append((gen_resolution, best_ref_resolution))
            else:
                # No match found for this generated ID
                resolutions.append((gen_resolution, IdResolution(
                    original_id=-1,
                    resolved_field_name=None,
                    resolved_field_type=None,
                    is_valid=False,
                    source_json="reference",
                    error=f"No matching reference field for '{gen_resolution.resolved_field_name}'"
                )))

        # Check for unmatched reference IDs (missing in generated)
        for ref_id in reference_ids:
            ref_resolution = self.resolve_id(ref_id, "reference")
            if ref_resolution.is_valid:
                if ref_resolution.resolved_field_name.lower() not in matched_ref_names:
                    all_match = False
                    discrepancy_type = (
                        DiscrepancyType.RULE_SOURCE_ID_MISMATCH
                        if id_type == "source"
                        else DiscrepancyType.RULE_DESTINATION_ID_MISMATCH
                    )
                    discrepancies.append(Discrepancy(
                        type=discrepancy_type,
                        severity=DiscrepancySeverity.HIGH,
                        field_name=ref_resolution.resolved_field_name,
                        rule_id=None,
                        message=f"Reference {id_type}Id field '{ref_resolution.resolved_field_name}' not found in generated rule",
                        expected=ref_resolution.resolved_field_name,
                        actual=None,
                        fix_instruction=f"Add '{ref_resolution.resolved_field_name}' to {id_type}Ids",
                    ))

        # Check for extra generated IDs (not in reference)
        for gen_id in generated_ids:
            gen_resolution = self.resolve_id(gen_id, "generated")
            if gen_resolution.is_valid:
                if gen_resolution.resolved_field_name.lower() not in matched_gen_names:
                    # This is an extra ID - not necessarily wrong, but note it
                    pass  # Don't mark as mismatch if it's just extra

        return all_match, resolutions, discrepancies

    def compare_post_trigger_rules(
        self,
        generated_rule: Dict[str, Any],
        reference_rule: Dict[str, Any],
        field_name: str
    ) -> Tuple[bool, List[Dict[str, Any]], List[Discrepancy]]:
        """
        Compare postTriggerRuleIds between rules.

        For each postTriggerRuleId, fetch the rule and check if it's
        properly placed on its corresponding field.

        Args:
            generated_rule: Rule from generated JSON
            reference_rule: Rule from reference JSON
            field_name: Name of the field containing this rule

        Returns:
            Tuple of (all_match, checks, discrepancies)
        """
        gen_post_trigger_ids = generated_rule.get("postTriggerRuleIds", [])
        ref_post_trigger_ids = reference_rule.get("postTriggerRuleIds", [])
        checks = []
        discrepancies = []

        # Check if postTriggerRuleIds exist when they should
        if ref_post_trigger_ids and not gen_post_trigger_ids:
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.POST_TRIGGER_RULE_MISSING,
                severity=DiscrepancySeverity.HIGH,
                field_name=field_name,
                rule_id=generated_rule.get("id"),
                message=f"Rule is missing postTriggerRuleIds (reference has {len(ref_post_trigger_ids)})",
                expected=ref_post_trigger_ids,
                actual=[],
                fix_instruction="Add postTriggerRuleIds to chain this rule to subsequent rules",
            ))
            return False, checks, discrepancies

        if not ref_post_trigger_ids:
            # No post-trigger rules expected
            return True, checks, discrepancies

        all_match = True

        # For each reference post-trigger rule, verify:
        # 1. There's a corresponding rule in generated
        # 2. The rule is on the correct field
        for ref_trigger_id in ref_post_trigger_ids:
            ref_trigger_info = self.ref_rule_to_field.get(ref_trigger_id)

            if not ref_trigger_info:
                # Reference rule ID not found - skip
                continue

            ref_trigger_field_name = ref_trigger_info["field_name"]
            ref_trigger_rule = ref_trigger_info["rule"]
            ref_trigger_action_type = ref_trigger_rule.get("actionType", "")

            # Find matching generated post-trigger rule
            found_match = False
            for gen_trigger_id in gen_post_trigger_ids:
                gen_trigger_info = self.gen_rule_to_field.get(gen_trigger_id)

                if not gen_trigger_info:
                    continue

                gen_trigger_field_name = gen_trigger_info["field_name"]
                gen_trigger_rule = gen_trigger_info["rule"]
                gen_trigger_action_type = gen_trigger_rule.get("actionType", "")

                # Check if action types match
                if gen_trigger_action_type != ref_trigger_action_type:
                    continue

                # Check if field names match
                name_match = self.field_comparator.compare_names(
                    gen_trigger_field_name,
                    ref_trigger_field_name
                )

                if name_match.is_match:
                    found_match = True
                    checks.append({
                        "reference_trigger_id": ref_trigger_id,
                        "generated_trigger_id": gen_trigger_id,
                        "action_type": ref_trigger_action_type,
                        "field_name_match": True,
                        "reference_field": ref_trigger_field_name,
                        "generated_field": gen_trigger_field_name,
                        "status": "matched",
                    })
                    break

            if not found_match:
                all_match = False
                checks.append({
                    "reference_trigger_id": ref_trigger_id,
                    "generated_trigger_id": None,
                    "action_type": ref_trigger_action_type,
                    "field_name_match": False,
                    "reference_field": ref_trigger_field_name,
                    "generated_field": None,
                    "status": "missing",
                })
                discrepancies.append(Discrepancy(
                    type=DiscrepancyType.POST_TRIGGER_RULE_MISSING,
                    severity=DiscrepancySeverity.HIGH,
                    field_name=field_name,
                    rule_id=generated_rule.get("id"),
                    message=f"Missing post-trigger rule of type '{ref_trigger_action_type}' on field '{ref_trigger_field_name}'",
                    expected=f"{ref_trigger_action_type} on {ref_trigger_field_name}",
                    actual=None,
                    fix_instruction=f"Add {ref_trigger_action_type} rule to field '{ref_trigger_field_name}' and link via postTriggerRuleIds",
                ))

        return all_match, checks, discrepancies

    def compare_params(
        self,
        generated_params: Optional[str],
        reference_params: Optional[str],
        field_name: str,
        rule_id: Optional[int]
    ) -> Tuple[bool, List[Discrepancy]]:
        """
        Compare params between rules.

        Args:
            generated_params: params from generated rule
            reference_params: params from reference rule
            field_name: Name of the field
            rule_id: ID of the rule

        Returns:
            Tuple of (match, discrepancies)
        """
        discrepancies = []

        # Handle None/empty cases
        if not reference_params and not generated_params:
            return True, discrepancies

        if not generated_params and reference_params:
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.RULE_PARAMS_MISMATCH,
                severity=DiscrepancySeverity.MEDIUM,
                field_name=field_name,
                rule_id=rule_id,
                message="Generated rule is missing params",
                expected=reference_params[:100] + "..." if len(reference_params) > 100 else reference_params,
                actual=None,
                fix_instruction="Add params to rule",
            ))
            return False, discrepancies

        if generated_params and not reference_params:
            # Extra params - not necessarily wrong
            return True, discrepancies

        # Both have params - compare
        # Try to parse as JSON for structured comparison
        try:
            gen_parsed = json.loads(generated_params) if isinstance(generated_params, str) else generated_params
            ref_parsed = json.loads(reference_params) if isinstance(reference_params, str) else reference_params

            # Deep comparison for JSON
            if gen_parsed == ref_parsed:
                return True, discrepancies

            # Check for semantic equivalence in key fields
            # For now, just report mismatch
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.RULE_PARAMS_MISMATCH,
                severity=DiscrepancySeverity.LOW,
                field_name=field_name,
                rule_id=rule_id,
                message="Rule params differ (may be acceptable)",
                expected=str(reference_params)[:200],
                actual=str(generated_params)[:200],
                fix_instruction="Review params configuration",
            ))
            return False, discrepancies

        except (json.JSONDecodeError, TypeError):
            # String comparison
            if generated_params.strip() == reference_params.strip():
                return True, discrepancies

            # Case-insensitive comparison for simple strings
            if generated_params.strip().lower() == reference_params.strip().lower():
                return True, discrepancies

            discrepancies.append(Discrepancy(
                type=DiscrepancyType.RULE_PARAMS_MISMATCH,
                severity=DiscrepancySeverity.LOW,
                field_name=field_name,
                rule_id=rule_id,
                message="Rule params differ",
                expected=reference_params[:100] if len(reference_params) > 100 else reference_params,
                actual=generated_params[:100] if len(generated_params) > 100 else generated_params,
                fix_instruction="Update params to match reference",
            ))
            return False, discrepancies

    def compare_single_rule(
        self,
        generated_rule: Dict[str, Any],
        reference_rule: Dict[str, Any],
        field_name: str
    ) -> RuleEvalResult:
        """
        Compare a single generated rule against a reference rule.

        Args:
            generated_rule: Rule from generated JSON
            reference_rule: Rule from reference JSON
            field_name: Name of the field containing these rules

        Returns:
            RuleEvalResult with comparison result
        """
        discrepancies = []

        # Compare action types
        gen_action = generated_rule.get("actionType", "")
        ref_action = reference_rule.get("actionType", "")
        action_type_match = gen_action == ref_action

        if not action_type_match:
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.RULE_ACTION_TYPE_MISMATCH,
                severity=DiscrepancySeverity.HIGH,
                field_name=field_name,
                rule_id=generated_rule.get("id"),
                message=f"Action type mismatch: '{gen_action}' vs '{ref_action}'",
                expected=ref_action,
                actual=gen_action,
                fix_instruction=f"Change actionType from {gen_action} to {ref_action}",
            ))

        # Compare sourceIds
        gen_source_ids = generated_rule.get("sourceIds", [])
        ref_source_ids = reference_rule.get("sourceIds", [])
        source_ids_match, source_resolutions, source_discrepancies = self.compare_id_lists(
            gen_source_ids, ref_source_ids, "source"
        )
        discrepancies.extend(source_discrepancies)

        # Compare destinationIds
        gen_dest_ids = generated_rule.get("destinationIds", [])
        ref_dest_ids = reference_rule.get("destinationIds", [])
        dest_ids_match, dest_resolutions, dest_discrepancies = self.compare_id_lists(
            gen_dest_ids, ref_dest_ids, "destination"
        )
        discrepancies.extend(dest_discrepancies)

        # Compare condition
        gen_condition = generated_rule.get("condition", "")
        ref_condition = reference_rule.get("condition", "")
        condition_match = gen_condition == ref_condition

        if not condition_match:
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.RULE_CONDITION_MISMATCH,
                severity=DiscrepancySeverity.MEDIUM,
                field_name=field_name,
                rule_id=generated_rule.get("id"),
                message=f"Condition mismatch: '{gen_condition}' vs '{ref_condition}'",
                expected=ref_condition,
                actual=gen_condition,
                fix_instruction=f"Change condition from {gen_condition} to {ref_condition}",
            ))

        # Compare conditionalValues
        gen_cond_values = generated_rule.get("conditionalValues", [])
        ref_cond_values = reference_rule.get("conditionalValues", [])
        cond_values_match = set(gen_cond_values) == set(ref_cond_values)

        if not cond_values_match:
            discrepancies.append(Discrepancy(
                type=DiscrepancyType.RULE_CONDITIONAL_VALUES_MISMATCH,
                severity=DiscrepancySeverity.MEDIUM,
                field_name=field_name,
                rule_id=generated_rule.get("id"),
                message="Conditional values mismatch",
                expected=ref_cond_values,
                actual=gen_cond_values,
                fix_instruction="Update conditionalValues to match reference",
            ))

        # Compare params
        gen_params = generated_rule.get("params", "")
        ref_params = reference_rule.get("params", "")
        params_match, params_discrepancies = self.compare_params(
            gen_params, ref_params, field_name, generated_rule.get("id")
        )
        discrepancies.extend(params_discrepancies)

        # Compare postTriggerRuleIds
        post_trigger_match, post_trigger_checks, post_trigger_discrepancies = self.compare_post_trigger_rules(
            generated_rule, reference_rule, field_name
        )
        discrepancies.extend(post_trigger_discrepancies)

        # Overall match
        is_match = all([
            action_type_match,
            source_ids_match,
            dest_ids_match,
            condition_match,
            cond_values_match,
            post_trigger_match,
        ])

        return RuleEvalResult(
            generated_rule_id=generated_rule.get("id"),
            reference_rule_id=reference_rule.get("id"),
            action_type=ref_action,
            action_type_match=action_type_match,
            source_ids_match=source_ids_match,
            destination_ids_match=dest_ids_match,
            condition_match=condition_match,
            conditional_values_match=cond_values_match,
            params_match=params_match,
            post_trigger_rules_match=post_trigger_match,
            is_match=is_match,
            discrepancies=discrepancies,
            source_id_resolutions=source_resolutions,
            destination_id_resolutions=dest_resolutions,
            post_trigger_rule_checks=post_trigger_checks,
        )

    def find_matching_rule(
        self,
        generated_rule: Dict[str, Any],
        reference_rules: List[Dict[str, Any]],
        field_name: str,
        already_matched: Set[int] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[RuleEvalResult]]:
        """
        Find a matching reference rule for a generated rule.

        Args:
            generated_rule: Rule from generated JSON
            reference_rules: List of rules from reference JSON
            field_name: Name of the field
            already_matched: Set of already matched reference rule IDs

        Returns:
            Tuple of (matched_reference_rule, eval_result) or (None, None)
        """
        if already_matched is None:
            already_matched = set()

        gen_action = generated_rule.get("actionType", "")

        # First, filter by action type
        candidate_rules = [
            r for r in reference_rules
            if r.get("id") not in already_matched
            and r.get("actionType") == gen_action
        ]

        if not candidate_rules:
            return None, None

        # Score each candidate and pick the best match
        best_match = None
        best_score = -1
        best_eval = None

        for ref_rule in candidate_rules:
            eval_result = self.compare_single_rule(generated_rule, ref_rule, field_name)

            # Calculate score based on matches
            score = 0
            if eval_result.action_type_match:
                score += 10
            if eval_result.source_ids_match:
                score += 5
            if eval_result.destination_ids_match:
                score += 5
            if eval_result.condition_match:
                score += 3
            if eval_result.conditional_values_match:
                score += 2

            if score > best_score:
                best_score = score
                best_match = ref_rule
                best_eval = eval_result

        return best_match, best_eval

    def compare_field_rules(
        self,
        generated_field: Dict[str, Any],
        reference_field: Dict[str, Any]
    ) -> RuleComparison:
        """
        Compare all rules between two matched fields.

        Args:
            generated_field: Field from generated JSON
            reference_field: Field from reference JSON

        Returns:
            RuleComparison with comparison result
        """
        gen_form_tag = generated_field.get("formTag", {})
        field_name = gen_form_tag.get("name", "Unknown")

        gen_rules = generated_field.get("formFillRules", [])
        ref_rules = reference_field.get("formFillRules", [])

        rule_evaluations = []
        matched_ref_ids = set()
        discrepancies = []

        # Find matches for each generated rule
        matched_count = 0
        for gen_rule in gen_rules:
            ref_rule, eval_result = self.find_matching_rule(
                gen_rule, ref_rules, field_name, matched_ref_ids
            )

            if ref_rule and eval_result:
                rule_evaluations.append(eval_result)
                matched_ref_ids.add(ref_rule.get("id"))
                discrepancies.extend(eval_result.discrepancies)
                if eval_result.is_match:
                    matched_count += 1
            else:
                # Extra rule in generated - may or may not be correct
                rule_evaluations.append(RuleEvalResult(
                    generated_rule_id=gen_rule.get("id"),
                    reference_rule_id=None,
                    action_type=gen_rule.get("actionType", ""),
                    action_type_match=False,
                    source_ids_match=False,
                    destination_ids_match=False,
                    condition_match=False,
                    conditional_values_match=False,
                    params_match=False,
                    post_trigger_rules_match=False,
                    is_match=False,
                    discrepancies=[Discrepancy(
                        type=DiscrepancyType.RULE_EXTRA,
                        severity=DiscrepancySeverity.INFO,
                        field_name=field_name,
                        rule_id=gen_rule.get("id"),
                        message=f"Extra rule of type '{gen_rule.get('actionType')}' not in reference",
                        expected=None,
                        actual=gen_rule.get("actionType"),
                        fix_instruction="Verify if this rule is correct or should be removed",
                    )],
                ))

        # Find missing rules (in reference but not in generated)
        missing_count = 0
        for ref_rule in ref_rules:
            if ref_rule.get("id") not in matched_ref_ids:
                missing_count += 1
                discrepancies.append(Discrepancy(
                    type=DiscrepancyType.RULE_MISSING,
                    severity=DiscrepancySeverity.HIGH,
                    field_name=field_name,
                    rule_id=ref_rule.get("id"),
                    message=f"Missing rule of type '{ref_rule.get('actionType')}' on field '{field_name}'",
                    expected=ref_rule.get("actionType"),
                    actual=None,
                    fix_instruction=f"Add {ref_rule.get('actionType')} rule to field '{field_name}'",
                ))

        return RuleComparison(
            field_name=field_name,
            total_generated_rules=len(gen_rules),
            total_reference_rules=len(ref_rules),
            matched_rules=matched_count,
            missing_rules=missing_count,
            extra_rules=len(gen_rules) - len([r for r in rule_evaluations if r.reference_rule_id]),
            rule_evaluations=rule_evaluations,
            discrepancies=discrepancies,
        )


def count_rules_by_type(fields: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Count rules by action type across all fields.

    Args:
        fields: List of field dictionaries

    Returns:
        Dictionary mapping action types to counts
    """
    counts = {}
    for field in fields:
        rules = field.get("formFillRules", [])
        for rule in rules:
            action_type = rule.get("actionType", "UNKNOWN")
            counts[action_type] = counts.get(action_type, 0) + 1
    return counts


def get_all_rules(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get all rules from all fields.

    Args:
        fields: List of field dictionaries

    Returns:
        List of all rules with their field info attached
    """
    all_rules = []
    for field in fields:
        field_id = field.get("id", 0)
        form_tag = field.get("formTag", {})
        field_name = form_tag.get("name", f"field_{field_id}")

        rules = field.get("formFillRules", [])
        for rule in rules:
            rule_copy = dict(rule)
            rule_copy["_field_id"] = field_id
            rule_copy["_field_name"] = field_name
            all_rules.append(rule_copy)

    return all_rules
