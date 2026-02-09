#!/usr/bin/env python3
"""
Coding Mini Agent Orchestrator

This orchestrator runs mini agents that GENERATE PYTHON CODE for rule extraction.
Each agent writes a Python script that uses deterministic-first approach with LLM fallback.

Flow:
1. Agent generates Python code (stage_N_*.py)
2. Orchestrator executes the generated code
3. Code produces JSON output
4. Eval checks output against reference
5. If failed, agent regenerates code with feedback
"""

import argparse
import json
import logging
import subprocess
import sys
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    import urllib.request
    import urllib.error
    REQUESTS_AVAILABLE = False

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.evaluator import FormFillEvaluator
from eval.orchestrator_integration import extract_self_heal_instructions

# Module logger
logger = logging.getLogger(__name__)


def extract_code_improvement_feedback(eval_report: Dict, iteration: int) -> Dict:
    """
    Extract detailed feedback for code improvement from eval report.

    This function extracts specific issues that can guide code generation:
    - Missing rules that need to be added
    - Incorrect rule types that need to be fixed
    - Missing field mappings
    - Structural issues

    Returns:
        Dict with priority_fixes, field_issues, and code_hints
    """
    feedback = {
        "priority_fixes": [],
        "field_issues": [],
        "code_hints": [],
        "rule_type_issues": [],
        "iteration": iteration
    }

    # Extract from standard self-heal instructions
    base_instructions = extract_self_heal_instructions(eval_report, iteration)
    feedback["priority_fixes"] = base_instructions.get("priority_fixes", [])

    # Extract field-level discrepancies
    discrepancies = eval_report.get("field_discrepancies", [])
    for disc in discrepancies:
        if isinstance(disc, dict):
            field_name = disc.get("field_name", "")
            issue_type = disc.get("issue_type", disc.get("discrepancy_type", ""))

            if "missing" in str(issue_type).lower():
                feedback["field_issues"].append({
                    "field": field_name,
                    "issue": "missing_rule",
                    "hint": f"Add rule for field '{field_name}'"
                })
            elif "mismatch" in str(issue_type).lower() or "wrong" in str(issue_type).lower():
                feedback["field_issues"].append({
                    "field": field_name,
                    "issue": "wrong_rule_type",
                    "hint": f"Check actionType/sourceType for field '{field_name}'"
                })

    # Extract rule type distribution issues
    rule_metrics = eval_report.get("rule_metrics", {})
    if rule_metrics:
        gen_by_type = rule_metrics.get("generated_by_type", {})
        ref_by_type = rule_metrics.get("reference_by_type", {})

        for rule_type, ref_count in ref_by_type.items():
            gen_count = gen_by_type.get(rule_type, 0)
            if gen_count < ref_count:
                feedback["rule_type_issues"].append({
                    "rule_type": rule_type,
                    "generated": gen_count,
                    "expected": ref_count,
                    "missing": ref_count - gen_count
                })

    # Generate code hints based on issues
    if len(feedback["field_issues"]) > 5:
        feedback["code_hints"].append("Many fields missing rules - check pattern matching logic")

    if feedback["rule_type_issues"]:
        missing_types = [r["rule_type"] for r in feedback["rule_type_issues"]]
        feedback["code_hints"].append(f"Check keyword patterns for: {', '.join(missing_types)}")

    return feedback


def setup_logging(workspace_dir: str, verbose: bool = False) -> None:
    """Configure logging for the orchestrator."""
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    log_file = os.path.join(workspace_dir, "orchestrator.log")
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")


# API Configuration
API_CONFIG = {
    "base_url": "https://qa.manchtech.com/app/v2/companies/128/process",
    "auth_header": "X-Authorization",
    "auth_token": "8DK9RLd5gaxDVbo7BuHFsxvn67hNvr",
    "content_type": "application/json"
}

# Error patterns for API responses
SELF_SOLVABLE_ERRORS = [
    r"code.*already\s*(present|exists)",
    r"name.*already\s*(present|exists)",
    r"template.*already\s*(present|exists)",
    r"duplicate.*key",
]

AUTH_ERROR_PATTERNS = [
    r"unauthorized",
    r"authentication.*failed",
    r"invalid.*token",
    r"access.*denied",
    r"forbidden",
]

# Stage configuration
STAGE_CONFIG = {
    1: {
        "name": "Rule Type Placement",
        "agent_file": ".claude/agents/coding_mini_agents/01_rule_type_placement_agent.md",
        "code_file": "stage_1_rule_placement",
        "threshold": 0.60,
        "max_retries": 2,
        "inputs": ["intra_panel", "inter_panel", "rule_info"],
    },
    2: {
        "name": "Source Destination",
        "agent_file": ".claude/agents/coding_mini_agents/02_source_destination_agent.md",
        "code_file": "stage_2_source_dest",
        "threshold": 0.70,
        "max_retries": 2,
        "inputs": ["intra_panel", "inter_panel", "rule_info"],
    },
    3: {
        "name": "EDV Rule",
        "agent_file": ".claude/agents/coding_mini_agents/03_edv_rule_agent.md",
        "code_file": "stage_3_edv_rules",
        "threshold": 0.75,
        "max_retries": 2,
        "inputs": ["edv_tables", "field_edv_mapping"],
    },
    4: {
        "name": "Post Trigger Chain",
        "agent_file": ".claude/agents/coding_mini_agents/04_post_trigger_chain_agent.md",
        "code_file": "stage_4_post_trigger",
        "threshold": 0.80,
        "max_retries": 2,
        "inputs": ["rule_info"],
    },
    5: {
        "name": "Assembly",
        "agent_file": ".claude/agents/coding_mini_agents/05_assembly_agent.md",
        "code_file": "stage_5_assembly",
        "threshold": 0.90,
        "max_retries": 3,
        "inputs": ["rule_info"],
    },
}


def create_workspace(base_dir: str = "adws") -> Tuple[str, str, str, str]:
    """Create timestamped workspace directory structure."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    workspace_dir = os.path.join(base_dir, timestamp)
    templates_output_dir = os.path.join(workspace_dir, "templates_output")
    generated_code_dir = os.path.join(workspace_dir, "generated_code")
    stage_outputs_dir = os.path.join(workspace_dir, "stage_outputs")

    os.makedirs(templates_output_dir, exist_ok=True)
    os.makedirs(generated_code_dir, exist_ok=True)
    os.makedirs(stage_outputs_dir, exist_ok=True)

    return workspace_dir, templates_output_dir, generated_code_dir, stage_outputs_dir


def run_dispatcher(dispatcher_name: str, document_path: str, output_dir: str) -> Optional[str]:
    """Run a dispatcher command and return output path."""
    dispatcher_path = f"dispatchers/{dispatcher_name}.py"

    if not os.path.exists(dispatcher_path):
        logger.warning(f"Dispatcher not found: {dispatcher_path}")
        return None

    cmd = ["python3", dispatcher_path, document_path, "--output-dir", output_dir]
    logger.debug(f"Running dispatcher: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.warning(f"Dispatcher {dispatcher_name} failed: {result.stderr[:500]}")
            return None

        return output_dir

    except subprocess.TimeoutExpired:
        logger.error(f"Dispatcher {dispatcher_name} timed out")
        return None
    except Exception as e:
        logger.error(f"Error running dispatcher {dispatcher_name}: {e}")
        return None


def run_pre_extraction(document_path: str, templates_output_dir: str) -> Dict[str, str]:
    """Run pre-extraction dispatchers."""
    logger.info("=" * 70)
    logger.info("STAGE 0: PRE-EXTRACTION (Dispatchers)")
    logger.info("=" * 70)

    outputs = {}

    # Run dispatchers
    dispatchers = [
        ("intra_panel_rule_field_references", "_intra_panel_references.json", "intra_panel"),
        ("inter_panel_rule_field_references", "_inter_panel_references.json", "inter_panel"),
        ("rule_info_extractor", "_meta_rules.json", "rule_info"),
        ("edv_table_mapping", "_edv_tables.json", "edv_tables"),
    ]

    for dispatcher_name, suffix, key in dispatchers:
        logger.info(f"Running {dispatcher_name}...")
        result = run_dispatcher(dispatcher_name, document_path, templates_output_dir)
        if result:
            for f in os.listdir(templates_output_dir):
                if f.endswith(suffix):
                    outputs[key] = os.path.join(templates_output_dir, f)
                    logger.info(f"  {key}: {outputs[key]}")
                    break

    # Also look for field_edv_mapping
    for f in os.listdir(templates_output_dir):
        if f.endswith("_field_edv_mapping.json"):
            outputs["field_edv_mapping"] = os.path.join(templates_output_dir, f)
            logger.info(f"  field_edv_mapping: {outputs['field_edv_mapping']}")

    logger.info(f"Pre-extraction complete. {len(outputs)} outputs generated.")
    return outputs


def build_code_gen_prompt(
    stage: int,
    schema_path: str,
    pre_extraction_outputs: Dict[str, str],
    previous_output: Optional[str],
    workspace_dir: str,
    generated_code_dir: str,
    iteration: int,
    self_heal_instructions: Optional[Dict] = None,
    document_path: str = None,
    reference_path: str = None,
    execution_error: Optional[str] = None,
    previous_code_path: Optional[str] = None,
    eval_report: Optional[Dict] = None
) -> str:
    """Build the prompt for code generation agent."""
    config = STAGE_CONFIG[stage]

    # Read the agent file
    with open(config["agent_file"], 'r') as f:
        agent_content = f.read()

    # Code output path
    code_file = os.path.join(generated_code_dir, f"{config['code_file']}_v{iteration}.py")
    output_file = os.path.join(workspace_dir, "stage_outputs", f"stage_{stage}_output_v{iteration}.json")

    prompt_parts = [
        f"# {config['name']} Coding Agent (Stage {stage})",
        "",
        "## Task",
        f"Generate Python code that implements Stage {stage} of the rule extraction pipeline.",
        "The code should use DETERMINISTIC pattern matching first, with LLM fallback only when needed.",
        "",
        "## Agent Instructions",
        agent_content,
        "",
        "## Input Files",
        f"- **Schema JSON**: `{schema_path}`",
        f"- **BUD Document**: `{document_path}`" if document_path else "",
        f"- **Reference JSON**: `{reference_path}`" if reference_path else "",
        f"- **Keyword Tree**: `rule_extractor/static/keyword_tree.json`",
        f"- **Rule Schemas**: `rules/Rule-Schemas.json`",
    ]

    # Add stage-specific inputs
    for input_type in config["inputs"]:
        if input_type in pre_extraction_outputs:
            prompt_parts.append(f"- **{input_type.replace('_', ' ').title()}**: `{pre_extraction_outputs[input_type]}`")

    # Add previous stage output
    if previous_output and stage > 1:
        prompt_parts.append(f"- **Previous Stage Output**: `{previous_output}`")

    prompt_parts.extend([
        "",
        "## Output",
        f"Write the Python code to: `{code_file}`",
        f"When executed, the code should output JSON to: `{output_file}`",
        "",
        "## Code Requirements",
        "1. **Deterministic-First**: Use pattern matching from keyword_tree.json",
        "2. **LLM Fallback**: Only for ambiguous cases, track in stats",
        "3. **Logging**: Use Python logging module with DEBUG/INFO/WARNING/ERROR levels",
        "4. **CLI Interface**: Use argparse for all input/output paths",
        "5. **Statistics**: Print processing stats at the end",
    ])

    # Add self-heal instructions if present (from previous iteration eval)
    if self_heal_instructions:
        prompt_parts.extend([
            "",
            "## ⚠️ SELF-HEALING MODE - ITERATION " + str(iteration),
            "The previous code iteration FAILED evaluation. You MUST improve the code to fix these issues.",
            "",
        ])

        # Add previous evaluation score
        if eval_report:
            summary = eval_report.get("evaluation_summary", {})
            score = summary.get("overall_score", 0)
            threshold = config["threshold"]
            prompt_parts.extend([
                f"### Previous Evaluation Score: {score:.0%} (Required: {threshold:.0%})",
                "",
            ])

        # Add priority fixes
        prompt_parts.append("### Priority Fixes (MUST address all)")
        for i, fix in enumerate(self_heal_instructions.get("priority_fixes", [])[:15], 1):
            if isinstance(fix, dict):
                category = fix.get("category", "Unknown")
                action = fix.get("action", "N/A")
                field = fix.get("field_name", "")
                if field:
                    prompt_parts.append(f"{i}. **[{category}]** Field `{field}`: {action}")
                else:
                    prompt_parts.append(f"{i}. **[{category}]**: {action}")
            else:
                prompt_parts.append(f"{i}. {str(fix)[:200]}")

        # Add field-level issues from self_heal_instructions
        field_issues = self_heal_instructions.get("field_issues", [])
        if field_issues:
            prompt_parts.extend([
                "",
                "### Field-Level Issues to Fix",
            ])
            for i, issue in enumerate(field_issues[:15], 1):
                if isinstance(issue, dict):
                    field = issue.get("field", "Unknown")
                    issue_type = issue.get("issue", "unknown")
                    hint = issue.get("hint", "")
                    prompt_parts.append(f"{i}. **{field}** ({issue_type}): {hint}")

        # Add rule type distribution issues
        rule_type_issues = self_heal_instructions.get("rule_type_issues", [])
        if rule_type_issues:
            prompt_parts.extend([
                "",
                "### Missing Rules by Type",
            ])
            for issue in rule_type_issues:
                if isinstance(issue, dict):
                    rule_type = issue.get("rule_type", "Unknown")
                    generated = issue.get("generated", 0)
                    expected = issue.get("expected", 0)
                    missing = issue.get("missing", 0)
                    prompt_parts.append(f"- **{rule_type}**: Generated {generated}, Expected {expected} (missing {missing})")

        # Add code hints
        code_hints = self_heal_instructions.get("code_hints", [])
        if code_hints:
            prompt_parts.extend([
                "",
                "### Code Improvement Hints",
            ])
            for hint in code_hints:
                prompt_parts.append(f"- {hint}")

        # Add field-level discrepancies from eval report
        if eval_report:
            discrepancies = eval_report.get("field_discrepancies", [])
            if discrepancies:
                prompt_parts.extend([
                    "",
                    "### Field-Level Discrepancies Found",
                ])
                for i, disc in enumerate(discrepancies[:10], 1):
                    if isinstance(disc, dict):
                        field_name = disc.get("field_name", "Unknown")
                        issue = disc.get("issue_type", disc.get("discrepancy_type", "Unknown"))
                        details = disc.get("details", disc.get("description", ""))
                        prompt_parts.append(f"{i}. **{field_name}**: {issue}")
                        if details:
                            prompt_parts.append(f"   Details: {str(details)[:150]}")

            # Add rule count comparison
            rule_metrics = eval_report.get("rule_metrics", {})
            if rule_metrics:
                gen_count = rule_metrics.get("generated_rules", 0)
                ref_count = rule_metrics.get("reference_rules", 0)
                prompt_parts.extend([
                    "",
                    "### Rule Count Comparison",
                    f"- Generated: {gen_count} rules",
                    f"- Reference: {ref_count} rules",
                    f"- Difference: {gen_count - ref_count:+d}",
                ])

        # Add instruction to read previous code
        if previous_code_path and os.path.exists(previous_code_path):
            prompt_parts.extend([
                "",
                "### Previous Code (IMPROVE THIS)",
                f"Read the previous code at `{previous_code_path}` and improve it based on the issues above.",
                "Do NOT start from scratch - refine and fix the existing implementation.",
            ])

    # Add execution error if present
    if execution_error:
        prompt_parts.extend([
            "",
            "## ⚠️ EXECUTION ERROR",
            "The previous code failed to execute. You MUST fix these errors:",
            "```",
            execution_error[:2000],
            "```",
            "",
            "Common fixes:",
            "- Check import statements",
            "- Verify file paths exist",
            "- Fix syntax errors",
            "- Handle missing keys in dictionaries",
        ])

    return "\n".join(prompt_parts)


def run_code_gen_agent(stage: int, prompt: str, workspace_dir: str, iteration: int) -> Optional[str]:
    """Run agent to generate Python code."""
    config = STAGE_CONFIG[stage]

    logger.info(f"Generating code for {config['name']} (Iteration {iteration})...")

    # Save prompt
    prompt_file = os.path.join(workspace_dir, f"stage_{stage}_prompt_v{iteration}.md")
    with open(prompt_file, 'w') as f:
        f.write(prompt)

    # Expected code path
    generated_code_dir = os.path.join(workspace_dir, "generated_code")
    code_path = os.path.join(generated_code_dir, f"{config['code_file']}_v{iteration}.py")

    # Run claude
    try:
        cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Write,Edit,Bash,Glob,Grep"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
            cwd=str(Path(__file__).parent.parent)
        )

        if result.returncode != 0:
            logger.error(f"Agent failed: {result.stderr[:500]}")
            return None

        if os.path.exists(code_path):
            logger.info(f"Code generated: {code_path}")
            return code_path
        else:
            logger.error(f"Code not created: {code_path}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("Agent timed out")
        return None
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        return None


def execute_generated_code(
    code_path: str,
    stage: int,
    schema_path: str,
    pre_extraction_outputs: Dict[str, str],
    previous_output: Optional[str],
    workspace_dir: str,
    iteration: int,
    reference_path: str = None
) -> Tuple[Optional[str], Optional[str]]:
    """Execute the generated Python code."""
    config = STAGE_CONFIG[stage]
    output_path = os.path.join(workspace_dir, "stage_outputs", f"stage_{stage}_output_v{iteration}.json")

    logger.info(f"Executing generated code: {code_path}")

    # Build command
    cmd = [
        "python3", code_path,
        "--schema", previous_output if previous_output and stage > 1 else schema_path,
        "--output", output_path,
        "--keyword-tree", "rule_extractor/static/keyword_tree.json",
        "--verbose"
    ]

    # Add stage-specific args
    if stage == 2:
        cmd.extend(["--rule-schemas", "rules/Rule-Schemas.json"])
    if stage == 5 and reference_path:
        cmd.extend(["--reference", reference_path])

    # Add pre-extraction inputs
    for input_type in config["inputs"]:
        if input_type in pre_extraction_outputs:
            arg_name = f"--{input_type.replace('_', '-')}"
            cmd.extend([arg_name, pre_extraction_outputs[input_type]])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(Path(__file__).parent.parent)
        )

        # Save execution log
        log_path = os.path.join(workspace_dir, f"stage_{stage}_execution_v{iteration}.log")
        with open(log_path, 'w') as f:
            f.write(f"Command: {' '.join(cmd)}\n\n")
            f.write(f"Return code: {result.returncode}\n\n")
            f.write(f"STDOUT:\n{result.stdout}\n\n")
            f.write(f"STDERR:\n{result.stderr}\n")

        if result.returncode != 0:
            logger.error(f"Code execution failed: {result.stderr[:500]}")
            return None, result.stderr

        if os.path.exists(output_path):
            logger.info(f"Output generated: {output_path}")
            return output_path, None
        else:
            logger.error(f"Output not created: {output_path}")
            return None, "Output file not created"

    except subprocess.TimeoutExpired:
        logger.error("Code execution timed out")
        return None, "Execution timed out"
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return None, str(e)


def run_stage_eval(stage: int, generated_path: str, reference_path: str,
                   workspace_dir: str, iteration: int) -> Tuple[bool, float, Dict]:
    """Run evaluation for a stage output."""
    config = STAGE_CONFIG[stage]
    threshold = config["threshold"]

    logger.info(f"Evaluating Stage {stage} (Threshold: {threshold:.0%})...")

    eval_report_path = os.path.join(workspace_dir, f"stage_{stage}_eval_v{iteration}.json")

    try:
        evaluator = FormFillEvaluator(
            use_llm=True,
            llm_threshold=0.8,
            pass_threshold=threshold
        )

        passed, report = evaluator.evaluate_and_save_report(
            generated_path,
            reference_path,
            eval_report_path,
            verbose=True,
            include_llm_analysis=False
        )

        eval_report = report.to_dict()
        summary = eval_report.get("evaluation_summary", {})
        score = summary.get("overall_score", 0)

        if passed:
            logger.info(f"Evaluation PASSED - Score: {score:.0%}")
        else:
            logger.warning(f"Evaluation FAILED - Score: {score:.0%}")

        return passed, score, eval_report

    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return False, 0.0, {}


def run_stage_with_healing(
    stage: int,
    schema_path: str,
    pre_extraction_outputs: Dict[str, str],
    previous_output: Optional[str],
    workspace_dir: str,
    generated_code_dir: str,
    document_path: str,
    reference_path: str,
    verbose: bool = False
) -> Tuple[bool, Optional[str], float, Optional[str]]:
    """
    Run a stage with code generation and self-healing retries.

    Returns:
        Tuple of (success, output_path, final_score, final_code_path)
    """
    config = STAGE_CONFIG[stage]
    max_retries = config["max_retries"]

    logger.info("=" * 70)
    logger.info(f"STAGE {stage}: {config['name'].upper()}")
    logger.info("=" * 70)

    self_heal_instructions = None
    execution_error = None
    output_path = None
    final_score = 0.0
    previous_code_path = None
    eval_report = None
    final_code_path = None

    for iteration in range(1, max_retries + 1):
        logger.info(f"Stage {stage} - Iteration {iteration}/{max_retries}")

        # Step 1: Generate code
        prompt = build_code_gen_prompt(
            stage=stage,
            schema_path=schema_path,
            pre_extraction_outputs=pre_extraction_outputs,
            previous_output=previous_output,
            workspace_dir=workspace_dir,
            generated_code_dir=generated_code_dir,
            iteration=iteration,
            self_heal_instructions=self_heal_instructions,
            document_path=document_path,
            reference_path=reference_path,
            execution_error=execution_error,
            previous_code_path=previous_code_path,
            eval_report=eval_report
        )

        code_path = run_code_gen_agent(stage, prompt, workspace_dir, iteration)

        if not code_path:
            logger.warning("Code generation failed, retrying...")
            continue

        final_code_path = code_path

        # Step 2: Execute generated code
        output_path, execution_error = execute_generated_code(
            code_path=code_path,
            stage=stage,
            schema_path=schema_path,
            pre_extraction_outputs=pre_extraction_outputs,
            previous_output=previous_output,
            workspace_dir=workspace_dir,
            iteration=iteration,
            reference_path=reference_path
        )

        if not output_path:
            logger.warning(f"Code execution failed: {execution_error}")
            previous_code_path = code_path  # Pass failed code for improvement
            continue

        # Step 3: Evaluate output
        passed, score, eval_report = run_stage_eval(
            stage=stage,
            generated_path=output_path,
            reference_path=reference_path,
            workspace_dir=workspace_dir,
            iteration=iteration
        )

        final_score = score

        if passed:
            logger.info(f"Stage {stage} PASSED on iteration {iteration}")
            return True, output_path, final_score, final_code_path

        # Prepare for retry with detailed code improvement feedback
        if iteration < max_retries:
            logger.info("Extracting code improvement feedback for retry...")
            self_heal_instructions = extract_code_improvement_feedback(eval_report, iteration)
            logger.info(f"Priority fixes: {len(self_heal_instructions.get('priority_fixes', []))}")
            logger.info(f"Field issues: {len(self_heal_instructions.get('field_issues', []))}")
            logger.info(f"Rule type issues: {len(self_heal_instructions.get('rule_type_issues', []))}")
            if self_heal_instructions.get("code_hints"):
                for hint in self_heal_instructions["code_hints"]:
                    logger.info(f"Code hint: {hint}")

            # Save code path for next iteration to read and improve
            previous_code_path = code_path
            execution_error = None  # Reset execution error

    logger.warning(f"Stage {stage} FAILED after {max_retries} iterations (best score: {final_score:.0%})")
    return False, output_path, final_score, final_code_path


def save_orchestration_summary(workspace_dir: str, stage_results: Dict[int, Dict],
                                overall_passed: bool, final_output: Optional[str],
                                total_iterations: int = 1,
                                document_path: str = None,
                                reference_path: str = None,
                                api_result: Optional[Dict] = None):
    """Save orchestration summary."""
    # Update iteration_summary.json with final status
    iteration_summary_path = os.path.join(workspace_dir, "iteration_summary.json")
    if os.path.exists(iteration_summary_path):
        with open(iteration_summary_path, 'r') as f:
            iteration_summary = json.load(f)
        iteration_summary["final_status"] = "passed" if overall_passed else "failed"
        iteration_summary["total_pipeline_iterations"] = total_iterations
        iteration_summary["completed_at"] = datetime.now().isoformat()
        iteration_summary["final_output"] = final_output
        with open(iteration_summary_path, 'w') as f:
            json.dump(iteration_summary, f, indent=2)

    # Save orchestration_summary.json
    summary = {
        "workspace": workspace_dir,
        "timestamp": datetime.now().isoformat(),
        "overall_passed": overall_passed,
        "final_output": final_output,
        "total_pipeline_iterations": total_iterations,
        "inputs": {
            "document": document_path,
            "reference": reference_path
        },
        "stages": {},
        "api_validation": api_result,
        "statistics": {
            "total_stages": len(stage_results),
            "passed_stages": sum(1 for r in stage_results.values() if r.get("passed")),
            "average_score": sum(r.get("score", 0) for r in stage_results.values()) / len(stage_results) if stage_results else 0
        }
    }

    for stage, result in stage_results.items():
        summary["stages"][f"stage_{stage}"] = {
            "name": STAGE_CONFIG[stage]["name"],
            "passed": result.get("passed", False),
            "score": result.get("score", 0.0),
            "threshold": result.get("threshold", STAGE_CONFIG[stage]["threshold"]),
            "score_vs_threshold": f"{result.get('score', 0):.0%} / {result.get('threshold', 0):.0%}",
            "output_json": result.get("output"),
            "generated_code": result.get("code_file"),
            "pipeline_iteration": result.get("pipeline_iteration", 1)
        }

    summary_path = os.path.join(workspace_dir, "orchestration_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Summary saved: {summary_path}")
    return summary_path


def prompt_for_auth_key() -> str:
    """Prompt user for new authorization key."""
    logger.warning("=" * 50)
    logger.warning("AUTHORIZATION ERROR")
    logger.warning("=" * 50)
    logger.warning("The API returned an unauthorized error.")
    print("Please enter a new authorization key:")

    try:
        new_key = input("Authorization Key: ").strip()
        if new_key:
            API_CONFIG["auth_token"] = new_key
            logger.info("Authorization key updated")
            return new_key
        else:
            logger.warning("No key entered, keeping existing key")
            return API_CONFIG["auth_token"]
    except (EOFError, KeyboardInterrupt):
        logger.warning("Input cancelled, keeping existing key")
        return API_CONFIG["auth_token"]


def is_auth_error(status_code: int, error_message: str) -> bool:
    """Check if error is authentication related."""
    if status_code in [401, 403]:
        return True

    error_lower = error_message.lower()
    for pattern in AUTH_ERROR_PATTERNS:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return True
    return False


def make_template_unique(schema_data: dict, workspace_id: str) -> dict:
    """Make template name and code unique to avoid duplicate errors."""
    unique_suffix = f"_coding_{workspace_id[:8]}"

    if "template" in schema_data:
        template = schema_data["template"]

        if "templateName" in template:
            base_name = re.sub(r'_coding_[a-f0-9]+$', '', template["templateName"])
            template["templateName"] = f"{base_name}{unique_suffix}"

        if "code" in template:
            base_code = re.sub(r'_coding_[a-f0-9]+$', '', template["code"])
            template["code"] = f"{base_code}{unique_suffix}"

        if "documentTypes" in template:
            for doc_type in template["documentTypes"]:
                if "code" in doc_type:
                    base_code = re.sub(r'_coding_[a-f0-9]+$', '', doc_type["code"])
                    doc_type["code"] = f"{base_code}{unique_suffix}"

    return schema_data


def call_api(
    schema_path: str,
    workspace_dir: str,
    max_auth_retries: int = 3
) -> Tuple[bool, Dict, List]:
    """
    Call the API to validate the generated schema.

    Args:
        schema_path: Path to the generated schema JSON
        workspace_dir: Workspace directory for saving API response
        max_auth_retries: Maximum retries for auth errors

    Returns:
        Tuple of (success, response_data, errors_for_agent)
    """
    logger.info("=" * 70)
    logger.info("API VALIDATION")
    logger.info("=" * 70)
    logger.info(f"Schema: {schema_path}")

    workspace_id = uuid.uuid4().hex
    auth_retry_count = 0

    while auth_retry_count < max_auth_retries:
        try:
            # Load schema
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)

            # Make template unique
            schema_data = make_template_unique(schema_data, workspace_id)

            # Save modified schema
            api_schema_path = os.path.join(workspace_dir, "api_schema.json")
            with open(api_schema_path, 'w') as f:
                json.dump(schema_data, f, indent=2)
            logger.debug(f"Modified schema saved: {api_schema_path}")

            # Make API call
            headers = {
                API_CONFIG["auth_header"]: API_CONFIG["auth_token"],
                "Content-Type": API_CONFIG["content_type"]
            }

            if REQUESTS_AVAILABLE:
                response = requests.post(
                    API_CONFIG["base_url"],
                    headers=headers,
                    json=schema_data,
                    timeout=120
                )
                status_code = response.status_code
                try:
                    response_data = response.json()
                except Exception:
                    response_data = {"raw_response": response.text}
            else:
                # Use urllib as fallback
                req = urllib.request.Request(
                    API_CONFIG["base_url"],
                    data=json.dumps(schema_data).encode('utf-8'),
                    headers=headers,
                    method='POST'
                )
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        status_code = resp.status
                        response_data = json.loads(resp.read().decode('utf-8'))
                except urllib.error.HTTPError as e:
                    status_code = e.code
                    try:
                        response_data = json.loads(e.read().decode('utf-8'))
                    except Exception:
                        response_data = {"error": str(e)}

            # Save API response
            api_response_path = os.path.join(workspace_dir, "api_response.json")
            with open(api_response_path, 'w') as f:
                json.dump({
                    "status_code": status_code,
                    "response": response_data,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
            logger.debug(f"API response saved: {api_response_path}")

            # Check success
            if 200 <= status_code < 300:
                logger.info(f"API call successful (Status: {status_code})")
                return True, response_data, []

            # Extract error message
            error_message = ""
            if isinstance(response_data, dict):
                error_message = response_data.get("message", "") or response_data.get("error", "") or str(response_data)
            else:
                error_message = str(response_data)

            # Check for auth error
            if is_auth_error(status_code, error_message):
                auth_retry_count += 1
                logger.warning(f"Authorization error (attempt {auth_retry_count}/{max_auth_retries})")

                if auth_retry_count < max_auth_retries:
                    prompt_for_auth_key()
                    continue
                else:
                    logger.error("Max auth retries exceeded")
                    return False, response_data, [{"error_type": "auth_error", "message": error_message}]

            # Check for self-solvable errors (duplicate name/code)
            error_lower = error_message.lower()
            for pattern in SELF_SOLVABLE_ERRORS:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    logger.warning(f"Self-solvable error (duplicate name/code), retrying with new unique suffix...")
                    workspace_id = uuid.uuid4().hex  # Generate new unique ID
                    continue

            # Other errors - return for agent to fix
            logger.error(f"API error (Status {status_code}): {error_message[:200]}")
            return False, response_data, [{
                "error_type": "api_validation_error",
                "status_code": status_code,
                "message": error_message
            }]

        except Exception as e:
            logger.error(f"API call exception: {e}", exc_info=True)
            return False, {"error": str(e)}, []

    return False, {"error": "Max retries exceeded"}, []


def save_iteration_summary(
    workspace_dir: str,
    pipeline_iteration: int,
    stage_results: Dict[int, Dict],
    api_result: Optional[Dict] = None,
    error: Optional[Exception] = None
):
    """Save a summary of the iteration for manual review."""
    summary_path = os.path.join(workspace_dir, "iteration_summary.json")

    # Load existing summary or create new
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            summary = json.load(f)
    else:
        summary = {
            "workspace": workspace_dir,
            "iterations": [],
            "current_iteration": 0,
            "final_status": "in_progress"
        }

    # Create iteration record
    iteration_record = {
        "pipeline_iteration": pipeline_iteration,
        "timestamp": datetime.now().isoformat(),
        "stages": {}
    }

    for stage, result in stage_results.items():
        iteration_record["stages"][f"stage_{stage}"] = {
            "name": STAGE_CONFIG[stage]["name"],
            "passed": result.get("passed", False),
            "score": result.get("score", 0.0),
            "output": result.get("output"),
            "code_file": result.get("code_file")
        }

    if api_result:
        iteration_record["api_validation"] = {
            "success": api_result.get("success", False),
            "errors": api_result.get("errors", [])
        }

    if error:
        iteration_record["error"] = {
            "type": type(error).__name__,
            "message": str(error)
        }

    # Update or append iteration record
    existing_idx = next(
        (i for i, r in enumerate(summary["iterations"])
         if r["pipeline_iteration"] == pipeline_iteration),
        None
    )
    if existing_idx is not None:
        summary["iterations"][existing_idx] = iteration_record
    else:
        summary["iterations"].append(iteration_record)

    summary["current_iteration"] = pipeline_iteration
    summary["last_updated"] = datetime.now().isoformat()

    # Save summary
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Iteration {pipeline_iteration} summary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Coding Mini Agent Orchestrator - Generates Python code for rule extraction"
    )
    parser.add_argument("document_path", help="Path to the BUD document (.docx)")
    parser.add_argument("--schema", required=True, help="Path to schema JSON")
    parser.add_argument("--reference", required=True, help="Path to reference output JSON")
    parser.add_argument("--workspace", default=None, help="Workspace directory")
    parser.add_argument("--start-stage", type=int, default=1, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--end-stage", type=int, default=5, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--skip-pre-extraction", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skip-api", action="store_true", help="Skip API validation after final stage")
    parser.add_argument("--api-token", default=None, help="API authorization token")
    parser.add_argument("--api-url", default=None, help="API base URL (overrides default)")
    parser.add_argument("--max-pipeline-iterations", type=int, default=3,
                        help="Max iterations of full pipeline if API fails (default: 3)")

    args = parser.parse_args()

    # Update API config
    if args.api_token:
        API_CONFIG["auth_token"] = args.api_token
    if args.api_url:
        API_CONFIG["base_url"] = args.api_url

    # Validate inputs
    for path, name in [(args.document_path, "Document"), (args.schema, "Schema"), (args.reference, "Reference")]:
        if not os.path.exists(path):
            print(f"Error: {name} not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Create workspace
    if args.workspace:
        workspace_dir = args.workspace
        templates_output_dir = os.path.join(workspace_dir, "templates_output")
        generated_code_dir = os.path.join(workspace_dir, "generated_code")
        stage_outputs_dir = os.path.join(workspace_dir, "stage_outputs")
        for d in [templates_output_dir, generated_code_dir, stage_outputs_dir]:
            os.makedirs(d, exist_ok=True)
    else:
        workspace_dir, templates_output_dir, generated_code_dir, stage_outputs_dir = create_workspace()

    # Setup logging
    setup_logging(workspace_dir, verbose=args.verbose)

    logger.info("=" * 70)
    logger.info("CODING MINI AGENT ORCHESTRATOR")
    logger.info("=" * 70)
    logger.info(f"Document: {args.document_path}")
    logger.info(f"Schema: {args.schema}")
    logger.info(f"Reference: {args.reference}")
    logger.info(f"Workspace: {workspace_dir}")
    logger.info(f"Generated Code: {generated_code_dir}")
    logger.info(f"Stages: {args.start_stage} -> {args.end_stage}")
    logger.info(f"API Validation: {'Disabled' if args.skip_api else 'Enabled'}")
    logger.info(f"Max Pipeline Iterations: {args.max_pipeline_iterations}")
    logger.info("=" * 70)

    # Pre-extraction (only once)
    pre_extraction_outputs = {}
    if not args.skip_pre_extraction:
        pre_extraction_outputs = run_pre_extraction(args.document_path, templates_output_dir)

    # Pipeline iteration loop (stages + API validation)
    max_pipeline_iterations = args.max_pipeline_iterations
    pipeline_iteration = 1
    overall_passed = False
    api_result = None
    api_errors_feedback = None  # API errors to feed back to agents
    final_output = None
    stage_results = {}

    while pipeline_iteration <= max_pipeline_iterations and not overall_passed:
        logger.info("#" * 70)
        logger.info(f"PIPELINE ITERATION {pipeline_iteration}/{max_pipeline_iterations}")
        logger.info("#" * 70)

        if api_errors_feedback:
            logger.info("Re-running pipeline with API error feedback:")
            for err in api_errors_feedback[:3]:
                if isinstance(err, dict):
                    logger.info(f"  - {err.get('error_type', 'error')}: {str(err.get('message', ''))[:100]}")

        # Run all stages
        previous_output = args.schema  # Start with schema as input
        stages_passed = True

        for stage in range(args.start_stage, args.end_stage + 1):
            # Build additional context from API errors if available
            # Feed API errors to Assembly agent (stage 5)
            stage_api_error_context = None
            if api_errors_feedback and stage == 5:
                stage_api_error_context = {
                    "api_errors": api_errors_feedback,
                    "instruction": "The API rejected the previous output. Fix the schema based on these errors."
                }

            passed, output_path, score, code_path = run_stage_with_healing(
                stage=stage,
                schema_path=args.schema,
                pre_extraction_outputs=pre_extraction_outputs,
                previous_output=previous_output,
                workspace_dir=workspace_dir,
                generated_code_dir=generated_code_dir,
                document_path=args.document_path,
                reference_path=args.reference,
                verbose=args.verbose
            )

            stage_results[stage] = {
                "passed": passed,
                "score": score,
                "output": output_path,
                "code_file": code_path or os.path.join(generated_code_dir, f"{STAGE_CONFIG[stage]['code_file']}_v1.py"),
                "threshold": STAGE_CONFIG[stage]["threshold"],
                "pipeline_iteration": pipeline_iteration
            }

            if not passed:
                stages_passed = False
                logger.warning(f"Stage {stage} failed. Continuing with best effort...")

            # Use output as input for next stage
            if output_path:
                previous_output = output_path

        # Final output from this iteration
        final_output = previous_output

        # Run API validation (unless skipped)
        if not args.skip_api and final_output:
            logger.info("=" * 70)
            logger.info(f"API VALIDATION (Pipeline Iteration {pipeline_iteration})")
            logger.info("=" * 70)

            api_success, api_response, api_errors = call_api(
                final_output,
                workspace_dir
            )

            api_result = {
                "success": api_success,
                "response": api_response,
                "errors": api_errors,
                "pipeline_iteration": pipeline_iteration
            }

            if api_success:
                logger.info(f"API validation PASSED on pipeline iteration {pipeline_iteration}")
                overall_passed = True
            else:
                logger.warning(f"API validation FAILED on pipeline iteration {pipeline_iteration}")

                if pipeline_iteration < max_pipeline_iterations:
                    # Extract errors to feed back to agents
                    api_errors_feedback = api_errors if api_errors else [{
                        "error_type": "api_error",
                        "message": str(api_response)
                    }]
                    logger.info("Will retry pipeline with error feedback...")
                else:
                    logger.warning("Max pipeline iterations reached")
                    overall_passed = False
        else:
            logger.info("API validation skipped")
            overall_passed = stages_passed  # If skipping API, use stage results

        # Save iteration summary for this pipeline iteration
        save_iteration_summary(
            workspace_dir,
            pipeline_iteration,
            stage_results,
            api_result
        )

        pipeline_iteration += 1

    # Save final summary
    save_orchestration_summary(
        workspace_dir=workspace_dir,
        stage_results=stage_results,
        overall_passed=overall_passed,
        final_output=final_output,
        total_iterations=pipeline_iteration - 1,
        document_path=args.document_path,
        reference_path=args.reference,
        api_result=api_result
    )

    # Print final summary
    logger.info("=" * 70)
    logger.info("CODING MINI AGENT ORCHESTRATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Workspace: {workspace_dir}")
    logger.info(f"Total Pipeline Iterations: {pipeline_iteration - 1}")
    logger.info("")
    logger.info("Stage Results:")
    for stage, result in stage_results.items():
        status = "PASS" if result["passed"] else "FAIL"
        logger.info(f"  Stage {stage} ({STAGE_CONFIG[stage]['name']}): {result['score']:.0%} {status}")
    logger.info("")
    if not args.skip_api and api_result:
        api_passed = api_result.get("success", False)
        logger.info(f"API Validation: {'PASS' if api_passed else 'FAIL'}")
    logger.info(f"Overall: {'PASSED' if overall_passed else 'FAILED'}")
    logger.info("")
    logger.info("Generated Files:")
    logger.info(f"  1. Generated code: {generated_code_dir}/")
    logger.info(f"  2. Stage outputs: {stage_outputs_dir}/")
    logger.info(f"  3. Evaluation reports: {workspace_dir}/stage_*_eval_v*.json")
    logger.info(f"  4. API schemas: {workspace_dir}/api_schema.json")
    logger.info(f"  5. API responses: {workspace_dir}/api_response.json")
    logger.info(f"  6. Iteration summary: {workspace_dir}/iteration_summary.json")
    logger.info(f"  7. Orchestrator log: {workspace_dir}/orchestrator.log")
    logger.info(f"  8. Final output: {final_output}")
    logger.info("=" * 70)

    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
