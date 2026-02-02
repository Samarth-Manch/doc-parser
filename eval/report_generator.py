"""
Report Generator for the Eval framework.

Uses LLM to generate human-readable reports and actionable fix instructions.
"""

import json
from typing import Dict, Any, List, Optional
from .llm_client import ReportGeneratorLLM, get_llm_client


class ReportGenerator:
    """
    Generates comprehensive evaluation reports using LLM intelligence.

    Features:
    - Human-readable summaries
    - Prioritized fix instructions
    - Pattern identification
    - Actionable recommendations
    """

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the ReportGenerator.

        Args:
            llm_client: Optional LLM client instance
        """
        self.llm_generator = ReportGeneratorLLM(llm_client)

    def generate_summary(self, eval_data: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of evaluation results.

        Args:
            eval_data: Evaluation data dictionary

        Returns:
            Generated summary text
        """
        return self.llm_generator.generate_summary(eval_data)

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
        return self.llm_generator.generate_priority_fixes(discrepancies, max_fixes)

    def generate_self_heal_report(
        self,
        eval_report_data: Dict[str, Any],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Generate a complete self-healing report for the coding agent.

        Args:
            eval_report_data: Complete evaluation report data
            iteration: Current iteration number

        Returns:
            Dictionary with structured self-heal instructions
        """
        # Extract key information
        summary = eval_report_data.get("evaluation_summary", {})
        passed = summary.get("passed", False)
        score = summary.get("overall_score", 0)
        threshold = summary.get("threshold", 0.90)

        priority_fixes = eval_report_data.get("priority_fixes", [])
        self_heal_instructions = eval_report_data.get("self_heal_instructions", [])
        missing_rules = eval_report_data.get("missing_rules_by_type", {})
        critical_checks = eval_report_data.get("critical_checks", {})

        # Build self-heal report
        report = {
            "iteration": iteration,
            "evaluation_passed": passed,
            "score": score,
            "threshold": threshold,
            "needs_fixes": not passed,
            "priority_fixes": priority_fixes,
            "self_heal_instructions": [
                instr if isinstance(instr, dict) else instr.to_dict()
                for instr in self_heal_instructions
            ],
            "missing_rules": missing_rules,
            "critical_checks": critical_checks,
        }

        # Generate LLM summary if there are issues
        if not passed:
            try:
                llm_summary = self.generate_summary(eval_report_data.get("eval_result", {}))
                report["llm_summary"] = llm_summary
            except Exception as e:
                report["llm_summary"] = f"Error generating summary: {str(e)}"

        return report

    def format_for_agent(
        self,
        self_heal_report: Dict[str, Any]
    ) -> str:
        """
        Format self-heal report as a prompt for the coding agent.

        Args:
            self_heal_report: Self-heal report dictionary

        Returns:
            Formatted string for agent consumption
        """
        lines = []
        lines.append("## SELF-HEALING INSTRUCTIONS")
        lines.append("")

        # Status
        passed = self_heal_report.get("evaluation_passed", False)
        score = self_heal_report.get("score", 0)
        iteration = self_heal_report.get("iteration", 0)

        status = "PASSED" if passed else "FAILED"
        lines.append(f"**Iteration {iteration} Status**: {status}")
        lines.append(f"**Score**: {score:.1%}")
        lines.append("")

        if passed:
            lines.append("Evaluation passed. No fixes needed.")
            return "\n".join(lines)

        # Priority fixes
        priority_fixes = self_heal_report.get("priority_fixes", [])
        if priority_fixes:
            lines.append("### Priority Fixes")
            lines.append("")
            for i, fix in enumerate(priority_fixes[:10], 1):
                category = fix.get("category", "unknown")
                action = fix.get("action", "")
                count = fix.get("count", 0)
                affected = fix.get("affected_fields", [])

                lines.append(f"{i}. **[{category.upper()}]** {action}")
                if affected:
                    lines.append(f"   - Affected fields: {', '.join(affected[:5])}")
                lines.append("")

        # Missing rules breakdown
        missing_rules = self_heal_report.get("missing_rules", {})
        if missing_rules:
            lines.append("### Missing Rules by Type")
            lines.append("")
            for rule_type, entries in missing_rules.items():
                lines.append(f"**{rule_type}** ({len(entries)} missing):")
                for entry in entries[:5]:
                    field_name = entry.get("field_name", "Unknown")
                    lines.append(f"  - {field_name}")
                if len(entries) > 5:
                    lines.append(f"  - ... and {len(entries) - 5} more")
                lines.append("")

        # Critical checks
        critical_checks = self_heal_report.get("critical_checks", {})
        if critical_checks:
            lines.append("### Critical Checks")
            lines.append("")
            for check_name, check_data in critical_checks.items():
                if isinstance(check_data, dict):
                    issue = check_data.get("issue")
                    if issue:
                        lines.append(f"- **{check_name}**: {issue}")
            lines.append("")

        # LLM summary
        llm_summary = self_heal_report.get("llm_summary")
        if llm_summary:
            lines.append("### Analysis")
            lines.append("")
            lines.append(llm_summary)
            lines.append("")

        return "\n".join(lines)


def generate_console_report(eval_report: Dict[str, Any]) -> str:
    """
    Generate a console-friendly report string.

    Args:
        eval_report: Evaluation report dictionary

    Returns:
        Formatted report string for console output
    """
    lines = []
    lines.append("=" * 70)
    lines.append("FORM FILL EVALUATION REPORT")
    lines.append("=" * 70)

    summary = eval_report.get("evaluation_summary", {})
    eval_result = eval_report.get("eval_result", {})

    passed = summary.get("passed", False)
    score = summary.get("overall_score", 0)
    threshold = summary.get("threshold", 0.90)

    status = "PASSED" if passed else "FAILED"
    lines.append(f"\nStatus: {status}")
    lines.append(f"Overall Score: {score:.1%} (Threshold: {threshold:.1%})")

    lines.append("\n--- Field Coverage ---")
    field_coverage = summary.get("field_coverage", 0)
    matched_fields = eval_result.get("matched_fields", 0)
    total_ref_fields = eval_result.get("total_reference_fields", 0)
    lines.append(f"Field Coverage: {field_coverage:.1%} ({matched_fields}/{total_ref_fields})")

    lines.append("\n--- Rule Coverage ---")
    rule_coverage = summary.get("rule_coverage", 0)
    matched_rules = eval_result.get("matched_rules", 0)
    total_ref_rules = eval_result.get("total_reference_rules", 0)
    lines.append(f"Rule Coverage: {rule_coverage:.1%} ({matched_rules}/{total_ref_rules})")

    lines.append("\n--- Rule Type Comparison ---")
    rule_type_comp = eval_result.get("rule_type_comparison", {})
    gen_rules = rule_type_comp.get("generated", {})
    ref_rules = rule_type_comp.get("reference", {})

    all_types = set(gen_rules.keys()) | set(ref_rules.keys())
    for rt in sorted(all_types):
        gen = gen_rules.get(rt, 0)
        ref = ref_rules.get(rt, 0)
        status_icon = "" if gen >= ref else ""
        lines.append(f"  {rt}: {gen}/{ref} {status_icon}")

    lines.append("\n--- Discrepancy Summary ---")
    total_disc = summary.get("total_discrepancies", 0)
    critical_disc = summary.get("critical_discrepancies", 0)
    high_disc = summary.get("high_discrepancies", 0)
    lines.append(f"Total Discrepancies: {total_disc}")
    lines.append(f"  Critical: {critical_disc}")
    lines.append(f"  High: {high_disc}")

    # Priority fixes
    priority_fixes = eval_report.get("priority_fixes", [])
    if priority_fixes:
        lines.append("\n--- Priority Fixes ---")
        for i, fix in enumerate(priority_fixes[:5], 1):
            category = fix.get("category", "unknown")
            action = fix.get("action", "")
            lines.append(f"{i}. [{category}] {action}")

    lines.append("\n" + "=" * 70)

    return "\n".join(lines)
