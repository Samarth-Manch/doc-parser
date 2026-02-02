"""
Main Evaluator for the Eval framework.

Orchestrates the complete evaluation pipeline:
1. Load and parse JSON files
2. Compare fields
3. Compare rules for matched fields
4. Generate evaluation report
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .models import (
    EvalResult,
    EvalReport,
    FieldEvalResult,
    Discrepancy,
    DiscrepancyType,
    DiscrepancySeverity,
    SelfHealInstruction,
)
from .field_comparator import FieldComparator
from .rule_comparator import RuleComparator, count_rules_by_type


class FormFillEvaluator:
    """
    Main evaluator class for comparing generated vs reference form fill JSON.

    Performs comprehensive evaluation including:
    - Field matching (name + type)
    - Rule comparison (action types, IDs, params, etc.)
    - Metrics calculation
    - Report generation
    """

    def __init__(
        self,
        use_llm: bool = True,
        llm_threshold: float = 0.8,
        pass_threshold: float = 0.90
    ):
        """
        Initialize the evaluator.

        Args:
            use_llm: Whether to use LLM for fuzzy matching
            llm_threshold: Confidence threshold for LLM matches
            pass_threshold: Overall score threshold for passing evaluation
        """
        self.use_llm = use_llm
        self.llm_threshold = llm_threshold
        self.pass_threshold = pass_threshold
        self.field_comparator = FieldComparator(
            use_llm=use_llm,
            llm_threshold=llm_threshold
        )

    def load_json(self, path: str) -> Dict[str, Any]:
        """
        Load and parse a JSON file.

        Args:
            path: Path to JSON file

        Returns:
            Parsed JSON data

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, 'r') as f:
            return json.load(f)

    def extract_form_fill_metadatas(
        self,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract formFillMetadatas from the JSON structure.

        Handles the path: template -> documentTypes -> formFillMetadatas

        Args:
            data: Parsed JSON data

        Returns:
            List of formFillMetadata objects
        """
        template = data.get("template", data)  # Handle both with and without template wrapper

        document_types = template.get("documentTypes", [])

        all_fields = []
        for doc_type in document_types:
            fields = doc_type.get("formFillMetadatas", [])
            all_fields.extend(fields)

        return all_fields

    def evaluate(
        self,
        generated_path: str,
        reference_path: str,
        verbose: bool = False
    ) -> EvalResult:
        """
        Perform full evaluation of generated JSON against reference.

        Args:
            generated_path: Path to generated JSON file
            reference_path: Path to reference JSON file
            verbose: Whether to print verbose output

        Returns:
            EvalResult with complete evaluation data
        """
        if verbose:
            print(f"Loading generated JSON: {generated_path}")
            print(f"Loading reference JSON: {reference_path}")

        # Load JSON files
        generated_data = self.load_json(generated_path)
        reference_data = self.load_json(reference_path)

        # Extract formFillMetadatas
        generated_fields = self.extract_form_fill_metadatas(generated_data)
        reference_fields = self.extract_form_fill_metadatas(reference_data)

        if verbose:
            print(f"Generated fields: {len(generated_fields)}")
            print(f"Reference fields: {len(reference_fields)}")

        # Compare fields
        if verbose:
            print("Comparing fields...")

        field_comparison_result = self.field_comparator.compare_all_fields(
            generated_fields,
            reference_fields
        )

        matched_pairs = field_comparison_result["matched_pairs"]
        field_id_mapping = field_comparison_result["field_id_mapping"]
        field_discrepancies = field_comparison_result["discrepancies"]

        if verbose:
            print(f"Matched fields: {len(matched_pairs)}")
            print(f"Field discrepancies: {len(field_discrepancies)}")

        # Compare rules for matched fields
        if verbose:
            print("Comparing rules for matched fields...")

        rule_comparator = RuleComparator(
            generated_fields,
            reference_fields,
            field_id_mapping,
            self.field_comparator
        )

        field_evaluations = []
        all_discrepancies = list(field_discrepancies)
        total_generated_rules = 0
        total_reference_rules = 0
        total_matched_rules = 0

        for gen_field, ref_field, field_comparison in matched_pairs:
            # Compare rules
            rule_comparison = rule_comparator.compare_field_rules(gen_field, ref_field)

            total_generated_rules += rule_comparison.total_generated_rules
            total_reference_rules += rule_comparison.total_reference_rules
            total_matched_rules += rule_comparison.matched_rules

            all_discrepancies.extend(rule_comparison.discrepancies)

            # Build FieldEvalResult
            gen_form_tag = gen_field.get("formTag", {})
            field_eval = FieldEvalResult(
                field_id=gen_field.get("id", 0),
                field_name=gen_form_tag.get("name", "Unknown"),
                field_type=gen_form_tag.get("type", "UNKNOWN"),
                is_matched=True,
                matched_reference_field_id=ref_field.get("id", 0),
                matched_reference_field_name=ref_field.get("formTag", {}).get("name", "Unknown"),
                name_match_type=field_comparison.name_match.match_type,
                type_match=field_comparison.type_match,
                rule_comparison=rule_comparison,
            )
            field_evaluations.append(field_eval)

        # Add evaluations for unmatched generated fields
        for gen_field in field_comparison_result["unmatched_generated"]:
            gen_form_tag = gen_field.get("formTag", {})
            gen_rules = gen_field.get("formFillRules", [])
            total_generated_rules += len(gen_rules)

            field_eval = FieldEvalResult(
                field_id=gen_field.get("id", 0),
                field_name=gen_form_tag.get("name", "Unknown"),
                field_type=gen_form_tag.get("type", "UNKNOWN"),
                is_matched=False,
                matched_reference_field_id=None,
                matched_reference_field_name=None,
                name_match_type="not_found",
                type_match=False,
                rule_comparison=None,
            )
            field_evaluations.append(field_eval)

        # Count reference rules from unmatched fields
        for ref_field in field_comparison_result["unmatched_reference"]:
            ref_rules = ref_field.get("formFillRules", [])
            total_reference_rules += len(ref_rules)

        # Calculate metrics
        field_coverage = len(matched_pairs) / len(reference_fields) if reference_fields else 1.0
        rule_coverage = total_matched_rules / total_reference_rules if total_reference_rules else 1.0
        rule_accuracy = total_matched_rules / total_generated_rules if total_generated_rules else 1.0

        # Calculate overall score
        # Weight: 40% field coverage, 40% rule coverage, 20% rule accuracy
        overall_score = (
            0.4 * field_coverage +
            0.4 * rule_coverage +
            0.2 * rule_accuracy
        )

        passed = overall_score >= self.pass_threshold

        # Build rule type comparison
        gen_rule_counts = count_rules_by_type(generated_fields)
        ref_rule_counts = count_rules_by_type(reference_fields)
        rule_type_comparison = {
            "generated": gen_rule_counts,
            "reference": ref_rule_counts,
        }

        if verbose:
            print(f"\nEvaluation complete:")
            print(f"  Field coverage: {field_coverage:.1%}")
            print(f"  Rule coverage: {rule_coverage:.1%}")
            print(f"  Rule accuracy: {rule_accuracy:.1%}")
            print(f"  Overall score: {overall_score:.1%}")
            print(f"  Passed: {passed}")

        return EvalResult(
            passed=passed,
            overall_score=overall_score,
            field_coverage=field_coverage,
            rule_coverage=rule_coverage,
            rule_accuracy=rule_accuracy,
            total_generated_fields=len(generated_fields),
            total_reference_fields=len(reference_fields),
            matched_fields=len(matched_pairs),
            total_generated_rules=total_generated_rules,
            total_reference_rules=total_reference_rules,
            matched_rules=total_matched_rules,
            field_evaluations=field_evaluations,
            all_discrepancies=all_discrepancies,
            rule_type_comparison=rule_type_comparison,
        )

    def generate_report(
        self,
        eval_result: EvalResult,
        generated_path: str,
        reference_path: str,
        include_llm_analysis: bool = True
    ) -> EvalReport:
        """
        Generate a full evaluation report from eval result.

        Args:
            eval_result: EvalResult from evaluate()
            generated_path: Path to generated JSON
            reference_path: Path to reference JSON
            include_llm_analysis: Whether to include LLM-generated analysis

        Returns:
            EvalReport with complete report data
        """
        report = EvalReport.create_from_eval_result(
            eval_result,
            generated_path,
            reference_path,
            self.pass_threshold
        )

        # Generate self-heal instructions from discrepancies
        self._generate_self_heal_instructions(report, eval_result)

        # Generate priority fixes
        self._generate_priority_fixes(report, eval_result)

        # Generate missing rules breakdown
        self._generate_missing_rules_breakdown(report, eval_result)

        # Generate critical checks summary
        self._generate_critical_checks(report, eval_result)

        # LLM analysis (if enabled)
        if include_llm_analysis and self.use_llm:
            try:
                from .report_generator import ReportGenerator
                generator = ReportGenerator()
                report.llm_analysis = generator.generate_summary(eval_result.to_dict())
            except Exception as e:
                report.llm_analysis = f"Error generating LLM analysis: {str(e)}"

        return report

    def _generate_self_heal_instructions(
        self,
        report: EvalReport,
        eval_result: EvalResult
    ) -> None:
        """Generate self-heal instructions from discrepancies."""
        priority = 1

        # Group discrepancies by severity
        critical = [d for d in eval_result.all_discrepancies if d.severity == DiscrepancySeverity.CRITICAL]
        high = [d for d in eval_result.all_discrepancies if d.severity == DiscrepancySeverity.HIGH]
        medium = [d for d in eval_result.all_discrepancies if d.severity == DiscrepancySeverity.MEDIUM]

        # Critical discrepancies first
        for disc in critical:
            report.self_heal_instructions.append(SelfHealInstruction(
                priority=priority,
                category=disc.type.value,
                action=disc.fix_instruction or disc.message,
                field_name=disc.field_name,
                rule_type=None,
                details={
                    "expected": disc.expected,
                    "actual": disc.actual,
                    "severity": disc.severity.value,
                }
            ))
            priority += 1

        # High priority discrepancies
        for disc in high[:20]:  # Limit to top 20
            report.self_heal_instructions.append(SelfHealInstruction(
                priority=priority,
                category=disc.type.value,
                action=disc.fix_instruction or disc.message,
                field_name=disc.field_name,
                rule_type=None,
                details={
                    "expected": disc.expected,
                    "actual": disc.actual,
                    "severity": disc.severity.value,
                }
            ))
            priority += 1

        # Medium priority (limited)
        for disc in medium[:10]:
            report.self_heal_instructions.append(SelfHealInstruction(
                priority=priority,
                category=disc.type.value,
                action=disc.fix_instruction or disc.message,
                field_name=disc.field_name,
                rule_type=None,
                details={
                    "expected": disc.expected,
                    "actual": disc.actual,
                    "severity": disc.severity.value,
                }
            ))
            priority += 1

    def _generate_priority_fixes(
        self,
        report: EvalReport,
        eval_result: EvalResult
    ) -> None:
        """Generate priority fixes list for coding agent."""
        # Aggregate missing rules by type
        missing_rule_types = {}
        for disc in eval_result.all_discrepancies:
            if disc.type == DiscrepancyType.RULE_MISSING:
                action_type = disc.expected or "UNKNOWN"
                if action_type not in missing_rule_types:
                    missing_rule_types[action_type] = {
                        "count": 0,
                        "fields": [],
                    }
                missing_rule_types[action_type]["count"] += 1
                missing_rule_types[action_type]["fields"].append(disc.field_name)

        # Add missing rule fixes
        for action_type, info in sorted(missing_rule_types.items(), key=lambda x: -x[1]["count"]):
            report.priority_fixes.append({
                "priority": len(report.priority_fixes) + 1,
                "category": "missing_rules",
                "action": f"Add {info['count']} missing {action_type} rules",
                "rule_type": action_type,
                "affected_fields": list(set(info["fields"]))[:10],
                "count": info["count"],
            })

        # Add ID mismatch fixes
        id_mismatches = [
            d for d in eval_result.all_discrepancies
            if d.type in [DiscrepancyType.RULE_SOURCE_ID_MISMATCH, DiscrepancyType.RULE_DESTINATION_ID_MISMATCH]
        ]
        if id_mismatches:
            report.priority_fixes.append({
                "priority": len(report.priority_fixes) + 1,
                "category": "id_mismatch",
                "action": f"Fix {len(id_mismatches)} ID reference mismatches in rules",
                "affected_fields": list(set(d.field_name for d in id_mismatches if d.field_name))[:10],
                "count": len(id_mismatches),
            })

        # Add post-trigger rule fixes
        post_trigger_issues = [
            d for d in eval_result.all_discrepancies
            if d.type in [DiscrepancyType.POST_TRIGGER_RULE_MISSING, DiscrepancyType.POST_TRIGGER_RULE_WRONG_FIELD]
        ]
        if post_trigger_issues:
            report.priority_fixes.append({
                "priority": len(report.priority_fixes) + 1,
                "category": "post_trigger_rules",
                "action": f"Fix {len(post_trigger_issues)} postTriggerRuleId issues",
                "affected_fields": list(set(d.field_name for d in post_trigger_issues if d.field_name))[:10],
                "count": len(post_trigger_issues),
            })

    def _generate_missing_rules_breakdown(
        self,
        report: EvalReport,
        eval_result: EvalResult
    ) -> None:
        """Generate breakdown of missing rules by type."""
        for field_eval in eval_result.field_evaluations:
            if field_eval.rule_comparison:
                for disc in field_eval.rule_comparison.discrepancies:
                    if disc.type == DiscrepancyType.RULE_MISSING:
                        action_type = disc.expected or "UNKNOWN"
                        if action_type not in report.missing_rules_by_type:
                            report.missing_rules_by_type[action_type] = []
                        report.missing_rules_by_type[action_type].append({
                            "field_name": field_eval.field_name,
                            "field_id": field_eval.field_id,
                            "message": disc.message,
                        })

    def _generate_critical_checks(
        self,
        report: EvalReport,
        eval_result: EvalResult
    ) -> None:
        """Generate critical checks summary."""
        gen_counts = eval_result.rule_type_comparison.get("generated", {})
        ref_counts = eval_result.rule_type_comparison.get("reference", {})

        # Check OCR -> VERIFY chaining
        ocr_gen = gen_counts.get("OCR", 0)
        verify_gen = gen_counts.get("VERIFY", 0)
        ocr_ref = ref_counts.get("OCR", 0)
        verify_ref = ref_counts.get("VERIFY", 0)

        report.critical_checks["ocr_verify_chaining"] = {
            "ocr_generated": ocr_gen,
            "ocr_reference": ocr_ref,
            "verify_generated": verify_gen,
            "verify_reference": verify_ref,
            "issue": "Missing OCR->VERIFY chains" if (ocr_ref > 0 and verify_gen < verify_ref) else None,
        }

        # Check visibility pairs
        make_visible_gen = gen_counts.get("MAKE_VISIBLE", 0)
        make_invisible_gen = gen_counts.get("MAKE_INVISIBLE", 0)
        make_visible_ref = ref_counts.get("MAKE_VISIBLE", 0)
        make_invisible_ref = ref_counts.get("MAKE_INVISIBLE", 0)

        report.critical_checks["visibility_pairs"] = {
            "make_visible_generated": make_visible_gen,
            "make_visible_reference": make_visible_ref,
            "make_invisible_generated": make_invisible_gen,
            "make_invisible_reference": make_invisible_ref,
        }

        # Check external dropdown rules
        ext_dropdown_gen = gen_counts.get("EXT_DROP_DOWN", 0) + gen_counts.get("EXT_VALUE", 0)
        ext_dropdown_ref = ref_counts.get("EXT_DROP_DOWN", 0) + ref_counts.get("EXT_VALUE", 0)

        report.critical_checks["external_dropdowns"] = {
            "generated": ext_dropdown_gen,
            "reference": ext_dropdown_ref,
            "gap": ext_dropdown_ref - ext_dropdown_gen,
        }

    def evaluate_and_save_report(
        self,
        generated_path: str,
        reference_path: str,
        output_path: str,
        verbose: bool = False,
        include_llm_analysis: bool = True
    ) -> Tuple[bool, EvalReport]:
        """
        Evaluate and save report to file.

        Args:
            generated_path: Path to generated JSON
            reference_path: Path to reference JSON
            output_path: Path to save evaluation report
            verbose: Whether to print verbose output
            include_llm_analysis: Whether to include LLM analysis

        Returns:
            Tuple of (passed, report)
        """
        # Run evaluation
        eval_result = self.evaluate(generated_path, reference_path, verbose=verbose)

        # Generate report
        report = self.generate_report(
            eval_result,
            generated_path,
            reference_path,
            include_llm_analysis=include_llm_analysis
        )

        # Save report
        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

        if verbose:
            print(f"Report saved to: {output_path}")

        return eval_result.passed, report


def run_evaluation(
    generated_path: str,
    reference_path: str,
    output_path: Optional[str] = None,
    use_llm: bool = True,
    llm_threshold: float = 0.8,
    pass_threshold: float = 0.90,
    verbose: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convenience function to run evaluation.

    Args:
        generated_path: Path to generated JSON
        reference_path: Path to reference JSON
        output_path: Optional path to save report (default: same dir as generated)
        use_llm: Whether to use LLM for fuzzy matching
        llm_threshold: Confidence threshold for LLM matches
        pass_threshold: Overall score threshold for passing
        verbose: Whether to print verbose output

    Returns:
        Tuple of (passed, report_dict)
    """
    if output_path is None:
        generated_dir = os.path.dirname(generated_path)
        output_path = os.path.join(generated_dir, "eval_report.json")

    evaluator = FormFillEvaluator(
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        pass_threshold=pass_threshold
    )

    passed, report = evaluator.evaluate_and_save_report(
        generated_path,
        reference_path,
        output_path,
        verbose=verbose
    )

    return passed, report.to_dict()
