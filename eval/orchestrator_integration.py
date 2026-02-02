"""
Orchestrator Integration for the Eval framework.

Provides integration with the self-healing orchestrator:
1. run_evaluation() - Drop-in replacement for Claude-based eval
2. format_for_agent() - Format eval report for coding agent
3. extract_self_heal_instructions() - Extract instructions for next iteration
"""

import json
import os
from typing import Dict, Any, Tuple, Optional

from .evaluator import FormFillEvaluator
from .report_generator import ReportGenerator, generate_console_report
from .models import EvalReport


def run_evaluation(
    generated_path: str,
    reference_path: str,
    workspace_dir: str,
    iteration: int = 1,
    threshold: float = 0.90,
    bud_path: Optional[str] = None,
    use_llm: bool = True,
    llm_threshold: float = 0.8,
    verbose: bool = True
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run comprehensive evaluation of generated output against reference.

    This is a drop-in replacement for the Claude skill-based evaluation
    in orchestrator_self_healing.py.

    Args:
        generated_path: Path to generated output
        reference_path: Path to reference output
        workspace_dir: Workspace directory for saving report
        iteration: Iteration number
        threshold: Pass threshold (default: 0.90)
        bud_path: Path to BUD document (for future BUD verification)
        use_llm: Whether to use LLM for fuzzy matching
        llm_threshold: Confidence threshold for LLM matches
        verbose: Whether to print verbose output

    Returns:
        Tuple of (passed: bool, eval_report: dict)
    """
    print("\n" + "=" * 70)
    print(f"STAGE 3: EVALUATION (Iteration {iteration})")
    print("=" * 70)
    print(f"Generated: {generated_path}")
    print(f"Reference: {reference_path}")
    if bud_path:
        print(f"BUD Source: {bud_path}")

    # Validate input files
    if not os.path.exists(generated_path):
        print(f" Generated file not found: {generated_path}")
        return False, None

    if not os.path.exists(reference_path):
        print(f" Reference file not found: {reference_path}")
        return False, None

    # Create evaluator
    evaluator = FormFillEvaluator(
        use_llm=use_llm,
        llm_threshold=llm_threshold,
        pass_threshold=threshold
    )

    # Run evaluation
    eval_report_path = os.path.join(workspace_dir, f"eval_report_v{iteration}.json")

    try:
        passed, report = evaluator.evaluate_and_save_report(
            generated_path,
            reference_path,
            eval_report_path,
            verbose=verbose,
            include_llm_analysis=use_llm
        )

        # Convert report to dict
        eval_report = report.to_dict()

        # Print summary
        if verbose:
            summary = eval_report.get("evaluation_summary", {})
            score = summary.get("overall_score", 0)

            print(f"\n{'=' * 50}")
            print(f"EVAL RESULT: {'PASS ' if passed else 'FAIL '}")
            print(f"Score: {score:.0%} (Threshold: {threshold:.0%})")
            print(f"{'=' * 50}")

            # Print rule type comparison
            eval_result = eval_report.get("eval_result", {})
            rule_comparison = eval_result.get("rule_type_comparison", {})
            if rule_comparison:
                gen_rules = rule_comparison.get("generated", {})
                ref_rules = rule_comparison.get("reference", {})
                print("\nRule Type Summary:")
                for rt in ["VERIFY", "OCR", "EXT_DROP_DOWN", "MAKE_DISABLED"]:
                    gen = gen_rules.get(rt, 0)
                    ref = ref_rules.get(rt, 0)
                    status = "" if gen >= ref * 0.8 else ""
                    print(f"  {rt}: {gen}/{ref} {status}")

            # Print priority fixes count
            fixes = eval_report.get("priority_fixes", [])
            print(f"\nPriority Fixes Needed: {len(fixes)}")

        return passed, eval_report

    except Exception as e:
        print(f" Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def extract_self_heal_instructions(
    eval_report: Dict[str, Any],
    iteration: int = 1
) -> Dict[str, Any]:
    """
    Extract self-heal instructions from eval report for coding agent.

    Args:
        eval_report: Evaluation report dictionary
        iteration: Current iteration number

    Returns:
        Dictionary with structured self-heal instructions
    """
    if not eval_report:
        return {}

    # Get report generator for formatting
    generator = ReportGenerator()

    # Generate self-heal report
    self_heal_report = generator.generate_self_heal_report(eval_report, iteration)

    # Enrich with additional context from eval report
    eval_result = eval_report.get("eval_result", {})

    self_heal_report["rule_type_comparison"] = eval_result.get("rule_type_comparison", {})
    self_heal_report["missing_rules"] = eval_report.get("missing_rules_by_type", {})
    self_heal_report["critical_checks"] = eval_report.get("critical_checks", {})
    self_heal_report["evaluation_summary"] = eval_report.get("evaluation_summary", {})

    return self_heal_report


def format_self_heal_for_agent(
    self_heal_instructions: Dict[str, Any]
) -> str:
    """
    Format self-heal instructions as a prompt for the coding agent.

    Args:
        self_heal_instructions: Self-heal instructions dictionary

    Returns:
        Formatted string for agent consumption
    """
    generator = ReportGenerator()
    return generator.format_for_agent(self_heal_instructions)


def save_self_heal_instructions(
    self_heal_instructions: Dict[str, Any],
    workspace_dir: str,
    iteration: int
) -> str:
    """
    Save self-heal instructions to file.

    Args:
        self_heal_instructions: Self-heal instructions dictionary
        workspace_dir: Workspace directory
        iteration: Iteration number

    Returns:
        Path to saved file
    """
    output_path = os.path.join(workspace_dir, f"self_heal_instructions_v{iteration}.json")
    with open(output_path, 'w') as f:
        json.dump(self_heal_instructions, f, indent=2)
    return output_path


def build_agent_prompt(
    self_heal_instructions: Dict[str, Any],
    workspace_dir: str,
    iteration: int
) -> str:
    """
    Build a complete prompt for the coding agent with self-heal instructions.

    Args:
        self_heal_instructions: Self-heal instructions dictionary
        workspace_dir: Workspace directory
        iteration: Iteration number

    Returns:
        Complete prompt string for agent
    """
    # Save instructions to file
    self_heal_json = save_self_heal_instructions(
        self_heal_instructions,
        workspace_dir,
        iteration
    )

    # Format instructions
    formatted = format_self_heal_for_agent(self_heal_instructions)

    prompt = f"""

## SELF-HEALING MODE: Previous Evaluation FAILED

The previous iteration was evaluated and FAILED. You MUST fix ALL issues below.

### Full Eval Report
Read the complete eval report at: {self_heal_json}

{formatted}

### Critical Requirements

1. **OCR  VERIFY Chaining**: Every OCR rule MUST have postTriggerRuleIds pointing to VERIFY
2. **Ordinal Mapping**: VERIFY destinationIds must match Rule-Schemas.json structure
3. **Rule Consolidation**: MAKE_DISABLED should be 5 rules, not 53
4. **EXT_DROP_DOWN**: Detect external table references in logic
5. **Valid Field IDs**: All sourceIds and destinationIds must reference valid field IDs in the schema

The evaluation AND API validation will run again after this iteration. All checks must pass.
"""
    return prompt


# Example usage in orchestrator_self_healing.py:
#
# from eval.orchestrator_integration import (
#     run_evaluation,
#     extract_self_heal_instructions,
#     build_agent_prompt
# )
#
# # Stage 3: Run evaluation
# passed, eval_report = run_evaluation(
#     output_path,
#     args.reference,
#     workspace_dir,
#     iteration=iteration,
#     threshold=args.threshold,
#     bud_path=args.document_path
# )
#
# if passed:
#     print("Evaluation PASSED!")
#     break
#
# # Extract self-heal instructions for next iteration
# self_heal_instructions = extract_self_heal_instructions(eval_report, iteration)
#
# # Build prompt for coding agent
# agent_prompt = build_agent_prompt(self_heal_instructions, workspace_dir, iteration)
