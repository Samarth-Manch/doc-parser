#!/usr/bin/env python3
"""
Mini Agent Orchestrator for Rule Extraction

This orchestrator runs mini agents sequentially with eval checks after each stage:
1. Rule Type Placement Agent - Determines rule types and places skeleton rules
2. Source Destination Agent - Populates sourceIds and destinationIds
3. EDV Rule Agent - Generates params for EXT_DROP_DOWN, EXT_VALUE, VALIDATION rules
4. Post Trigger Chain Agent - Links rules via postTriggerRuleIds
5. Assembly Agent - Consolidates rules, assigns IDs, validates structure

Self-healing: If eval fails below threshold, agent is called again with feedback.
API validation: After final stage, validates output against the API.
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


def setup_logging(workspace_dir: str, verbose: bool = False) -> None:
    """
    Configure logging for the orchestrator.

    Args:
        workspace_dir: Workspace directory for log file
        verbose: If True, set console to DEBUG level
    """
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    # File handler - logs everything to file
    log_file = os.path.join(workspace_dir, "orchestrator.log")
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler - INFO or DEBUG based on verbose flag
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


# Stage configuration with thresholds
STAGE_CONFIG = {
    1: {
        "name": "Rule Type Placement",
        "agent_file": ".claude/agents/mini/01_rule_type_placement_agent.md",
        "threshold": 0.60,  # Lower threshold for early stage
        "max_retries": 2,
        "inputs": ["intra_panel", "inter_panel", "rule_info"],
    },
    2: {
        "name": "Source Destination",
        "agent_file": ".claude/agents/mini/02_source_destination_agent.md",
        "threshold": 0.70,
        "max_retries": 2,
        "inputs": ["intra_panel", "inter_panel", "rule_info"],
    },
    3: {
        "name": "EDV Rule",
        "agent_file": ".claude/agents/mini/03_edv_rule_agent.md",
        "threshold": 0.75,
        "max_retries": 2,
        "inputs": ["edv_mapping", "rule_info"],
    },
    4: {
        "name": "Post Trigger Chain",
        "agent_file": ".claude/agents/mini/04_post_trigger_chain_agent.md",
        "threshold": 0.80,
        "max_retries": 2,
        "inputs": ["rule_info"],
    },
    5: {
        "name": "Assembly",
        "agent_file": ".claude/agents/mini/05_assembly_agent.md",
        "threshold": 0.90,  # Higher threshold for final stage
        "max_retries": 3,
        "inputs": ["rule_info"],
    },
}


def create_workspace(base_dir: str = "adws") -> Tuple[str, str, str]:
    """
    Create timestamped workspace directory structure.

    Args:
        base_dir: Base directory for workspaces (default: adws)

    Returns:
        Tuple of (workspace_dir, templates_output_dir, stage_outputs_dir)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    workspace_dir = os.path.join(base_dir, timestamp)
    templates_output_dir = os.path.join(workspace_dir, "templates_output")
    stage_outputs_dir = os.path.join(workspace_dir, "stage_outputs")

    os.makedirs(templates_output_dir, exist_ok=True)
    os.makedirs(stage_outputs_dir, exist_ok=True)

    return workspace_dir, templates_output_dir, stage_outputs_dir


def run_dispatcher(
    dispatcher_name: str,
    document_path: str,
    output_dir: str,
    additional_args: List[str] = None
) -> Optional[str]:
    """
    Run a dispatcher command and return output path.

    Args:
        dispatcher_name: Name of dispatcher (e.g., "intra_panel_rule_field_references")
        document_path: Path to BUD document
        output_dir: Output directory
        additional_args: Additional command line arguments

    Returns:
        Path to output file or None if failed
    """
    dispatcher_path = f"dispatchers/{dispatcher_name}.py"

    if not os.path.exists(dispatcher_path):
        logger.warning(f"Dispatcher not found: {dispatcher_path}")
        return None

    cmd = ["python3", dispatcher_path, document_path, "--output-dir", output_dir]
    if additional_args:
        cmd.extend(additional_args)

    logger.debug(f"Running dispatcher: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.warning(f"Dispatcher {dispatcher_name} failed: {result.stderr[:500]}")
            return None

        logger.debug(f"Dispatcher output: {result.stdout[:500]}")
        return output_dir

    except subprocess.TimeoutExpired:
        logger.error(f"Dispatcher {dispatcher_name} timed out after 10 minutes")
        return None
    except Exception as e:
        logger.error(f"Error running dispatcher {dispatcher_name}: {e}")
        return None


def run_pre_extraction(
    document_path: str,
    templates_output_dir: str,
    verbose: bool = False  # noqa: ARG001 - reserved for future use
) -> Dict[str, str]:
    """
    Run pre-extraction dispatchers for all required inputs.

    All outputs are saved to templates_output_dir (similar to self-healing orchestrator).

    Args:
        document_path: Path to BUD document
        templates_output_dir: Directory for template outputs (adws/<timestamp>/templates_output/)
        verbose: Enable verbose output (reserved for future use)

    Returns:
        Dict mapping input type to output file path
    """
    logger.info("=" * 70)
    logger.info("STAGE 0: PRE-EXTRACTION (Dispatchers)")
    logger.info("=" * 70)

    outputs = {}

    # 1. Intra-panel references
    logger.info("Running intra-panel field references extraction...")
    result = run_dispatcher("intra_panel_rule_field_references", document_path, templates_output_dir)
    if result:
        # Find the consolidated JSON
        for f in os.listdir(templates_output_dir):
            if f.endswith("_intra_panel_references.json"):
                outputs["intra_panel"] = os.path.join(templates_output_dir, f)
                logger.info(f"Intra-panel output: {outputs['intra_panel']}")
                break

    # 2. Inter-panel references
    logger.info("Running inter-panel field references extraction...")
    result = run_dispatcher("inter_panel_rule_field_references", document_path, templates_output_dir)
    if result:
        for f in os.listdir(templates_output_dir):
            if f.endswith("_inter_panel_references.json"):
                outputs["inter_panel"] = os.path.join(templates_output_dir, f)
                logger.info(f"Inter-panel output: {outputs['inter_panel']}")
                break

    # 3. Rule info extraction
    logger.info("Running rule info extraction...")
    result = run_dispatcher("rule_info_extractor", document_path, templates_output_dir)
    if result:
        for f in os.listdir(templates_output_dir):
            if f.endswith("_meta_rules.json"):
                outputs["rule_info"] = os.path.join(templates_output_dir, f)
                logger.info(f"Rule info output: {outputs['rule_info']}")
                break

    # 4. EDV table mapping
    logger.info("Running EDV table mapping extraction...")
    result = run_dispatcher("edv_table_mapping", document_path, templates_output_dir)
    if result:
        for f in os.listdir(templates_output_dir):
            if f.endswith("_edv_tables.json"):
                outputs["edv_tables"] = os.path.join(templates_output_dir, f)
            elif f.endswith("_field_edv_mapping.json"):
                outputs["edv_mapping"] = os.path.join(templates_output_dir, f)
        if "edv_tables" in outputs:
            logger.info(f"EDV tables output: {outputs['edv_tables']}")
        if "edv_mapping" in outputs:
            logger.info(f"EDV mapping output: {outputs['edv_mapping']}")

    logger.info(f"Pre-extraction complete. {len(outputs)} outputs generated.")
    return outputs


def build_agent_prompt(
    stage: int,
    schema_path: str,
    pre_extraction_outputs: Dict[str, str],
    previous_output: Optional[str],
    workspace_dir: str,
    iteration: int,
    self_heal_instructions: Optional[Dict] = None,
    document_path: str = None,
    reference_path: str = None,
    api_error_context: Optional[Dict] = None
) -> str:
    """
    Build the prompt for a mini agent.

    Args:
        stage: Stage number (1-5)
        schema_path: Path to schema JSON
        pre_extraction_outputs: Dict of pre-extraction output paths
        previous_output: Output from previous stage (for stages 2-5)
        workspace_dir: Workspace directory
        iteration: Current iteration within stage
        self_heal_instructions: Instructions from failed eval (if any)
        document_path: Path to BUD document
        reference_path: Path to reference JSON

    Returns:
        Complete prompt string for the agent
    """
    config = STAGE_CONFIG[stage]

    # Read the agent file
    agent_file = config["agent_file"]
    with open(agent_file, 'r') as f:
        agent_content = f.read()

    # Build prompt
    prompt_parts = [
        f"# {config['name']} Agent (Stage {stage})",
        "",
        "## Agent Instructions",
        agent_content,
        "",
        "## Input Files",
        f"- **Schema JSON**: {schema_path}",
        f"- **BUD Document**: {document_path}" if document_path else "",
        f"- **Reference JSON**: {reference_path}" if reference_path else "",
    ]

    # Add stage-specific inputs
    for input_type in config["inputs"]:
        if input_type in pre_extraction_outputs:
            prompt_parts.append(f"- **{input_type.replace('_', ' ').title()}**: {pre_extraction_outputs[input_type]}")

    # Add previous stage output for stages 2-5
    if previous_output and stage > 1:
        prompt_parts.append(f"- **Previous Stage Output**: {previous_output}")

    # Add output path
    stage_output_dir = os.path.join(workspace_dir, "stage_outputs")
    output_path = os.path.join(stage_output_dir, f"stage_{stage}_output_v{iteration}.json")
    prompt_parts.extend([
        "",
        "## Output",
        f"Write the output JSON to: {output_path}",
    ])

    # Add self-heal instructions if present
    if self_heal_instructions:
        prompt_parts.extend([
            "",
            "## ⚠️ SELF-HEALING MODE",
            "The previous iteration FAILED evaluation. You MUST fix ALL issues below.",
            "",
            "### Priority Fixes",
        ])

        for i, fix in enumerate(self_heal_instructions.get("priority_fixes", [])[:10], 1):
            if isinstance(fix, dict):
                category = fix.get("category", "Unknown")
                action = fix.get("action", "N/A")
                prompt_parts.append(f"{i}. **{category}**: {action}")

        # Add rule type comparison
        rule_comparison = self_heal_instructions.get("rule_type_comparison", {})
        if rule_comparison:
            gen_rules = rule_comparison.get("generated", {})
            ref_rules = rule_comparison.get("reference", {})
            prompt_parts.extend([
                "",
                "### Rule Type Gaps",
                "| Type | Generated | Expected | Gap |",
                "|------|-----------|----------|-----|",
            ])
            for rt in ["VERIFY", "OCR", "EXT_DROP_DOWN", "EXT_VALUE", "MAKE_VISIBLE", "MAKE_DISABLED"]:
                gen = gen_rules.get(rt, 0)
                ref = ref_rules.get(rt, 0)
                gap = ref - gen
                if gap != 0:
                    prompt_parts.append(f"| {rt} | {gen} | {ref} | {'+' if gap < 0 else '-'}{abs(gap)} |")

    # Add API error context if present (for pipeline retry)
    if api_error_context:
        prompt_parts.extend([
            "",
            "## ⚠️ API VALIDATION FAILED",
            "The previous pipeline iteration was rejected by the API. You MUST fix these issues.",
            "",
            "### API Errors",
        ])
        api_errors = api_error_context.get("api_errors", [])
        for i, err in enumerate(api_errors[:5], 1):
            if isinstance(err, dict):
                error_type = err.get("error_type", "Unknown")
                message = str(err.get("message", "N/A"))[:500]
                status_code = err.get("status_code", "N/A")
                prompt_parts.append(f"{i}. **{error_type}** (Status: {status_code})")
                prompt_parts.append(f"   Message: {message}")
            else:
                prompt_parts.append(f"{i}. {str(err)[:500]}")

        if "instruction" in api_error_context:
            prompt_parts.extend([
                "",
                f"**Instruction**: {api_error_context['instruction']}",
            ])

    return "\n".join(prompt_parts)


def run_mini_agent(
    stage: int,
    prompt: str,
    workspace_dir: str,
    iteration: int,
    verbose: bool = False
) -> Optional[str]:
    """
    Run a mini agent using claude -p command.

    Args:
        stage: Stage number
        prompt: Agent prompt
        workspace_dir: Workspace directory
        iteration: Current iteration
        verbose: Enable verbose output

    Returns:
        Path to output file or None if failed
    """
    config = STAGE_CONFIG[stage]

    logger.info(f"Running {config['name']} Agent (Iteration {iteration})...")

    # Save prompt to file
    prompt_file = os.path.join(workspace_dir, f"stage_{stage}_prompt_v{iteration}.md")
    with open(prompt_file, 'w') as f:
        f.write(prompt)
    logger.debug(f"Prompt saved to: {prompt_file}")

    # Expected output path
    output_path = os.path.join(workspace_dir, "stage_outputs", f"stage_{stage}_output_v{iteration}.json")

    # Run claude with the prompt
    try:
        cmd = [
            "claude",
            "-p", prompt,
            "--allowedTools", "Read,Write,Edit,Bash,Glob,Grep"
        ]

        logger.debug(f"Executing: claude -p <prompt> --allowedTools ...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        if result.returncode != 0:
            logger.error(f"Agent failed with return code {result.returncode}: {result.stderr[:500]}")
            return None

        if verbose:
            logger.debug(f"Agent stdout: {result.stdout[:2000]}")

        # Check if output was created
        if os.path.exists(output_path):
            logger.info(f"Agent output created: {output_path}")
            return output_path
        else:
            logger.error(f"Agent output not created: {output_path}")
            return None

    except subprocess.TimeoutExpired:
        logger.error(f"Agent timed out after 15 minutes")
        return None
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        return None


def run_stage_eval(
    stage: int,
    generated_path: str,
    reference_path: str,
    workspace_dir: str,
    iteration: int
) -> Tuple[bool, float, Dict]:
    """
    Run evaluation for a stage output.

    Returns:
        Tuple of (passed, score, eval_report)
    """
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
            logger.info(f"Evaluation PASSED - Score: {score:.0%} (Threshold: {threshold:.0%})")
        else:
            logger.warning(f"Evaluation FAILED - Score: {score:.0%} (Threshold: {threshold:.0%})")

        logger.debug(f"Eval report saved to: {eval_report_path}")

        return passed, score, eval_report

    except Exception as e:
        logger.error(f"Evaluation error: {e}", exc_info=True)
        return False, 0.0, {}


def run_stage_with_healing(
    stage: int,
    schema_path: str,
    pre_extraction_outputs: Dict[str, str],
    previous_output: Optional[str],
    workspace_dir: str,
    document_path: str,
    reference_path: str,
    verbose: bool = False,
    api_error_context: Optional[Dict] = None
) -> Tuple[bool, Optional[str], float]:
    """
    Run a stage with self-healing retries.

    Args:
        stage: Stage number (1-5)
        schema_path: Path to schema JSON
        pre_extraction_outputs: Dict of pre-extraction output paths
        previous_output: Output from previous stage
        workspace_dir: Workspace directory
        document_path: Path to BUD document
        reference_path: Path to reference JSON
        verbose: Enable verbose output
        api_error_context: API errors from previous pipeline iteration (for retry)

    Returns:
        Tuple of (success, output_path, final_score)
    """
    config = STAGE_CONFIG[stage]
    max_retries = config["max_retries"]

    logger.info("=" * 70)
    logger.info(f"STAGE {stage}: {config['name'].upper()}")
    logger.info("=" * 70)

    self_heal_instructions = None
    output_path = None
    final_score = 0.0

    for iteration in range(1, max_retries + 1):
        logger.info(f"Stage {stage} - Iteration {iteration}/{max_retries}")

        # Build prompt
        prompt = build_agent_prompt(
            stage=stage,
            schema_path=schema_path,
            pre_extraction_outputs=pre_extraction_outputs,
            previous_output=previous_output,
            workspace_dir=workspace_dir,
            iteration=iteration,
            self_heal_instructions=self_heal_instructions,
            document_path=document_path,
            reference_path=reference_path,
            api_error_context=api_error_context if iteration == 1 else None  # Only on first iter
        )

        # Run agent
        output_path = run_mini_agent(
            stage=stage,
            prompt=prompt,
            workspace_dir=workspace_dir,
            iteration=iteration,
            verbose=verbose
        )

        if not output_path:
            logger.warning(f"Agent produced no output, retrying...")
            continue

        # Run evaluation
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
            return True, output_path, final_score

        if iteration < max_retries:
            logger.info(f"Extracting self-heal instructions for retry...")
            self_heal_instructions = extract_self_heal_instructions(eval_report, iteration)
            logger.info(f"Priority fixes to apply: {len(self_heal_instructions.get('priority_fixes', []))}")

    logger.warning(f"Stage {stage} FAILED after {max_retries} iterations (best score: {final_score:.0%})")
    return False, output_path, final_score


def save_iteration_summary(
    workspace_dir: str,
    pipeline_iteration: int,
    stage_results: Dict[int, Dict],
    api_result: Optional[Dict] = None,
    error: Optional[Exception] = None
):
    """
    Save a summary of the iteration for manual review.

    Args:
        workspace_dir: Workspace directory
        pipeline_iteration: Current pipeline iteration number
        stage_results: Results from all stages
        api_result: API validation result (if any)
        error: Exception that occurred (if any)
    """
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
            "output": result.get("output")
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


def save_orchestration_summary(
    workspace_dir: str,
    stage_results: Dict[int, Dict],
    overall_passed: bool,
    final_output: Optional[str],
    api_result: Optional[Dict] = None,
    total_pipeline_iterations: int = 1
):
    """Save final orchestration summary to file."""
    # Update iteration_summary.json with final status
    summary_path = os.path.join(workspace_dir, "iteration_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        summary["final_status"] = "passed" if overall_passed else "failed"
        summary["total_pipeline_iterations"] = total_pipeline_iterations
        summary["completed_at"] = datetime.now().isoformat()
        summary["final_output"] = final_output
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

    # Also save orchestration_summary.json for compatibility
    orchestration_summary = {
        "workspace": workspace_dir,
        "timestamp": datetime.now().isoformat(),
        "overall_passed": overall_passed,
        "final_output": final_output,
        "total_pipeline_iterations": total_pipeline_iterations,
        "stages": {},
        "api_validation": api_result
    }

    for stage, result in stage_results.items():
        orchestration_summary["stages"][f"stage_{stage}"] = {
            "name": STAGE_CONFIG[stage]["name"],
            "passed": result.get("passed", False),
            "score": result.get("score", 0.0),
            "output": result.get("output"),
            "iterations": result.get("iterations", 0)
        }

    orch_summary_path = os.path.join(workspace_dir, "orchestration_summary.json")
    with open(orch_summary_path, 'w') as f:
        json.dump(orchestration_summary, f, indent=2)

    logger.info(f"Orchestration summary saved: {orch_summary_path}")


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
    """Make template name and code unique."""
    unique_suffix = f"_mini_{workspace_id[:8]}"

    if "template" in schema_data:
        template = schema_data["template"]

        if "templateName" in template:
            base_name = re.sub(r'_mini_[a-f0-9]+$', '', template["templateName"])
            template["templateName"] = f"{base_name}{unique_suffix}"

        if "code" in template:
            base_code = re.sub(r'_mini_[a-f0-9]+$', '', template["code"])
            template["code"] = f"{base_code}{unique_suffix}"

        if "documentTypes" in template:
            for doc_type in template["documentTypes"]:
                if "code" in doc_type:
                    base_code = re.sub(r'_mini_[a-f0-9]+$', '', doc_type["code"])
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
                    with urllib.request.urlopen(req, timeout=60) as resp:
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


def main():
    parser = argparse.ArgumentParser(
        description="Mini Agent Orchestrator for Rule Extraction"
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Path to schema JSON from extract_fields_complete.py"
    )
    parser.add_argument(
        "--reference",
        required=True,
        help="Path to reference output JSON (human-made)"
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace directory (default: adws/<timestamp>/)"
    )
    parser.add_argument(
        "--start-stage",
        type=int,
        default=1,
        choices=[1, 2, 3, 4, 5],
        help="Stage to start from (default: 1)"
    )
    parser.add_argument(
        "--end-stage",
        type=int,
        default=5,
        choices=[1, 2, 3, 4, 5],
        help="Stage to end at (default: 5)"
    )
    parser.add_argument(
        "--skip-pre-extraction",
        action="store_true",
        help="Skip pre-extraction if outputs already exist"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--overall-threshold",
        type=float,
        default=0.85,
        help="Overall pass threshold (default: 0.85)"
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip API validation after final stage"
    )
    parser.add_argument(
        "--api-token",
        default=None,
        help="API authorization token (overrides default)"
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="API base URL (overrides default)"
    )
    parser.add_argument(
        "--max-pipeline-iterations",
        type=int,
        default=3,
        help="Max iterations of full pipeline if API fails (default: 3)"
    )

    args = parser.parse_args()

    # Update API config if arguments provided
    if args.api_token:
        API_CONFIG["auth_token"] = args.api_token
    if args.api_url:
        API_CONFIG["base_url"] = args.api_url

    # Validate inputs (before logging is setup)
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.schema):
        print(f"Error: Schema not found: {args.schema}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.reference):
        print(f"Error: Reference not found: {args.reference}", file=sys.stderr)
        sys.exit(1)

    # Create workspace (matches self-healing orchestrator structure)
    if args.workspace:
        workspace_dir = args.workspace
        templates_output_dir = os.path.join(workspace_dir, "templates_output")
        stage_outputs_dir = os.path.join(workspace_dir, "stage_outputs")
        os.makedirs(templates_output_dir, exist_ok=True)
        os.makedirs(stage_outputs_dir, exist_ok=True)
    else:
        workspace_dir, templates_output_dir, stage_outputs_dir = create_workspace()

    # Setup logging (now that workspace exists)
    setup_logging(workspace_dir, verbose=args.verbose)

    logger.info("=" * 70)
    logger.info("MINI AGENT ORCHESTRATOR")
    logger.info("=" * 70)
    logger.info(f"Document: {args.document_path}")
    logger.info(f"Schema: {args.schema}")
    logger.info(f"Reference: {args.reference}")
    logger.info(f"Workspace: {workspace_dir}")
    logger.info(f"Templates Output: {templates_output_dir}")
    logger.info(f"Stages: {args.start_stage} -> {args.end_stage}")
    logger.info(f"Overall Threshold: {args.overall_threshold:.0%}")
    logger.info("=" * 70)

    # Run pre-extraction (only once) - outputs go to templates_output/
    pre_extraction_outputs = {}
    if not args.skip_pre_extraction:
        pre_extraction_outputs = run_pre_extraction(
            args.document_path,
            templates_output_dir,
            verbose=args.verbose
        )

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
            stage_api_error_context = None
            if api_errors_feedback and stage == 5:  # Feed API errors to Assembly agent
                stage_api_error_context = {
                    "api_errors": api_errors_feedback,
                    "instruction": "The API rejected the previous output. Fix the schema based on these errors."
                }

            passed, output_path, score = run_stage_with_healing(
                stage=stage,
                schema_path=args.schema,
                pre_extraction_outputs=pre_extraction_outputs,
                previous_output=previous_output,
                workspace_dir=workspace_dir,
                document_path=args.document_path,
                reference_path=args.reference,
                verbose=args.verbose,
                api_error_context=stage_api_error_context
            )

            stage_results[stage] = {
                "passed": passed,
                "score": score,
                "output": output_path,
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
        workspace_dir,
        stage_results,
        overall_passed,
        final_output,
        api_result,
        total_pipeline_iterations=pipeline_iteration - 1
    )

    # Log final summary
    logger.info("=" * 70)
    logger.info("MINI AGENT ORCHESTRATION COMPLETE")
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
    logger.info(f"  1. Pre-extraction outputs: {templates_output_dir}/")
    logger.info(f"  2. Stage outputs: {workspace_dir}/stage_outputs/")
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
