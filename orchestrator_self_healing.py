#!/usr/bin/env python3
"""
Self-Healing Rule Extraction Orchestrator

This orchestrator:
1. Calls intra_panel_rule_field_references to extract field dependencies
2. Calls rule extraction coding agent to generate code
3. Evaluates output against reference using Claude intelligence
4. Calls API to validate generated output
5. If evaluation or API fails, feeds issues back to code agent for self-healing
6. Repeats eval + fix cycle until pass or max iterations reached
"""

import argparse
import json
import subprocess
import sys
import os
import shutil
import traceback
import uuid
import re
from datetime import datetime
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    import urllib.request
    import urllib.error
    REQUESTS_AVAILABLE = False

# Import the eval framework
from eval.evaluator import FormFillEvaluator
from eval.orchestrator_integration import extract_self_heal_instructions


# API Configuration
API_CONFIG = {
    "base_url": "https://qa.manchtech.com/app/v2/companies/128/process",
    "auth_header": "X-Authorization",
    "auth_token": "8DK9RLd5gaxDVbo7BuHFsxvn67hNvr",
    "content_type": "application/json"
}

# Error patterns that can be self-solved by orchestrator
SELF_SOLVABLE_ERRORS = [
    r"code.*already\s*(present|exists)",
    r"name.*already\s*(present|exists)",
    r"template.*already\s*(present|exists)",
    r"duplicate.*key",
    r"unique.*constraint.*violated",
]

# Error patterns that indicate auth issues
AUTH_ERROR_PATTERNS = [
    r"unauthorized",
    r"authentication.*failed",
    r"invalid.*token",
    r"token.*expired",
    r"access.*denied",
    r"forbidden",
]

# Error patterns that need to be sent to coding agent
CODING_AGENT_ERRORS = [
    r"id.*not\s*(present|found)",
    r"mandatory.*field",
    r"required.*field",
    r"invalid.*rule",
    r"missing.*destination",
    r"sourceIds.*invalid",
    r"destinationIds.*invalid",
    r"actionType.*invalid",
    r"schema.*mismatch",
]


def prompt_for_auth_key() -> str:
    """
    Prompt the user for a new authorization key.

    Returns:
        The new authorization key entered by the user
    """
    print("\n" + "="*50)
    print("⚠️  AUTHORIZATION ERROR")
    print("="*50)
    print("The API returned an unauthorized error.")
    print("Please enter a new authorization key:")
    print()

    try:
        new_key = input("Authorization Key: ").strip()
        if new_key:
            API_CONFIG["auth_token"] = new_key
            print(f"✓ Authorization key updated")
            return new_key
        else:
            print("✗ No key entered, keeping existing key")
            return API_CONFIG["auth_token"]
    except (EOFError, KeyboardInterrupt):
        print("\n✗ Input cancelled, keeping existing key")
        return API_CONFIG["auth_token"]


def is_auth_error(status_code: int, error_message: str) -> bool:
    """
    Check if the error is an authentication/authorization error.

    Args:
        status_code: HTTP status code
        error_message: Error message from API

    Returns:
        True if this is an auth error
    """
    # Check status code
    if status_code in [401, 403]:
        return True

    # Check error message patterns
    error_lower = error_message.lower()
    for pattern in AUTH_ERROR_PATTERNS:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return True

    return False


def make_template_unique(schema_data: dict, iteration: int, workspace_id: str) -> dict:
    """
    Make template name and code unique for each iteration.

    Args:
        schema_data: The schema JSON data
        iteration: Current iteration number
        workspace_id: Unique workspace identifier

    Returns:
        Modified schema data with unique name/code
    """
    # Generate unique suffix
    unique_suffix = f"_v{iteration}_{workspace_id[:8]}"

    if "template" in schema_data:
        template = schema_data["template"]

        # Update templateName
        if "templateName" in template:
            base_name = re.sub(r'_v\d+_[a-f0-9]+$', '', template["templateName"])
            template["templateName"] = f"{base_name}{unique_suffix}"

        # Update code
        if "code" in template:
            base_code = re.sub(r'_v\d+_[a-f0-9]+$', '', template["code"])
            template["code"] = f"{base_code}{unique_suffix}"

        # Update documentTypes codes if present
        if "documentTypes" in template:
            for doc_type in template["documentTypes"]:
                if "code" in doc_type:
                    base_code = re.sub(r'_v\d+_[a-f0-9]+$', '', doc_type["code"])
                    doc_type["code"] = f"{base_code}{unique_suffix}"

    return schema_data


def classify_api_error(error_message: str) -> tuple:
    """
    Classify API error as self-solvable or needs coding agent.

    Args:
        error_message: The error message from API

    Returns:
        Tuple of (is_self_solvable: bool, error_type: str)
    """
    error_lower = error_message.lower()

    # Check if self-solvable
    for pattern in SELF_SOLVABLE_ERRORS:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return True, "duplicate_name_code"

    # Check if needs coding agent
    for pattern in CODING_AGENT_ERRORS:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return False, "rule_structure_error"

    # Unknown error - pass to coding agent to be safe
    return False, "unknown_error"


def call_api(schema_path: str, iteration: int, workspace_id: str,
             workspace_dir: str, max_auth_retries: int = 3) -> tuple:
    """
    Call the API with the generated schema.

    Args:
        schema_path: Path to the generated schema JSON
        iteration: Current iteration number
        workspace_id: Unique workspace identifier
        workspace_dir: Workspace directory for saving API response
        max_auth_retries: Maximum retries for auth errors

    Returns:
        Tuple of (success: bool, response_data: dict, errors_for_agent: list)
    """
    print(f"\n📡 Calling API with generated schema (Iteration {iteration})...")

    auth_retry_count = 0

    while auth_retry_count < max_auth_retries:
        try:
            # Load schema
            with open(schema_path, 'r') as f:
                schema_data = json.load(f)

            # Make template unique
            schema_data = make_template_unique(schema_data, iteration, workspace_id)

            # Save the modified schema
            api_schema_path = os.path.join(workspace_dir, f"api_schema_v{iteration}.json")
            with open(api_schema_path, 'w') as f:
                json.dump(schema_data, f, indent=2)
            print(f"   Modified schema saved to: {api_schema_path}")

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
                    timeout=60
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
            api_response_path = os.path.join(workspace_dir, f"api_response_v{iteration}.json")
            with open(api_response_path, 'w') as f:
                json.dump({
                    "status_code": status_code,
                    "response": response_data,
                    "timestamp": datetime.now().isoformat(),
                    "auth_retry_count": auth_retry_count
                }, f, indent=2)
            print(f"   API response saved to: {api_response_path}")

            # Check if successful
            if 200 <= status_code < 300:
                print(f"   ✓ API call successful (Status: {status_code})")
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
                print(f"   ⚠️  Authorization error detected (attempt {auth_retry_count}/{max_auth_retries})")

                if auth_retry_count < max_auth_retries:
                    # Prompt for new key
                    prompt_for_auth_key()
                    continue  # Retry with new key
                else:
                    print(f"   ✗ Max auth retries exceeded")
                    return False, response_data, [{
                        "source": "api",
                        "error_type": "auth_error",
                        "status_code": status_code,
                        "message": "Authorization failed after multiple retries",
                        "instruction": "Check API credentials"
                    }]

            # Handle other (non-auth) errors
            print(f"   Error: {error_message[:200]}...")

            # Classify the error
            is_self_solvable, error_type = classify_api_error(error_message)

            if is_self_solvable:
                print(f"   ℹ️  Self-solvable error ({error_type}): Will retry with new unique name/code")
                return False, response_data, []
            else:
                print(f"   ⚠️  Error needs coding agent ({error_type})")
                errors_for_agent = [{
                    "source": "api",
                    "error_type": error_type,
                    "status_code": status_code,
                    "message": error_message,
                    "instruction": "Fix the schema/rules based on this API error"
                }]
                return False, response_data, errors_for_agent

        except Exception as e:
            print(f"   ✗ API call exception: {e}")
            error_details = traceback.format_exc()

            # Save error
            api_error_path = os.path.join(workspace_dir, f"api_error_v{iteration}.json")
            with open(api_error_path, 'w') as f:
                json.dump({
                    "error": str(e),
                    "traceback": error_details,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)

            # Network errors are not coding agent issues
            return False, {"error": str(e)}, []

    # Should not reach here, but return failure if we do
    return False, {"error": "Max retries exceeded"}, []


def create_timestamped_workspace(base_dir: str = "adws") -> tuple:
    """
    Create timestamped directory structure in adws/.

    Args:
        base_dir: Base directory for workspaces (default: adws)

    Returns:
        Tuple of (workspace_dir, templates_output_dir)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    workspace_dir = os.path.join(base_dir, timestamp)
    templates_output_dir = os.path.join(workspace_dir, "templates_output")

    os.makedirs(templates_output_dir, exist_ok=True)

    return workspace_dir, templates_output_dir


def find_latest_previous_run(base_dir: str = "adws") -> dict:
    """
    Find the latest previous run in adws/ and get paths to all relevant files.

    Args:
        base_dir: Base directory for workspaces (default: adws)

    Returns:
        Dict with paths to latest files from previous run, or empty dict if none found.
        Keys: previous_workspace, self_heal_instructions, populated_schema,
              eval_report, extraction_report, api_schema, api_response
    """
    result = {}

    if not os.path.exists(base_dir):
        return result

    # Get all timestamped directories, sorted by timestamp (newest first)
    dirs = []
    for entry in os.listdir(base_dir):
        entry_path = os.path.join(base_dir, entry)
        if os.path.isdir(entry_path):
            # Validate timestamp format YYYY-MM-DD_HH-MM-SS
            try:
                datetime.strptime(entry, "%Y-%m-%d_%H-%M-%S")
                dirs.append(entry)
            except ValueError:
                continue

    if not dirs:
        return result

    # Sort by timestamp descending (newest first)
    dirs.sort(reverse=True)

    # Skip the current run (it's still being created) - get the second newest
    # Actually, we want the newest completed run
    for workspace_name in dirs:
        workspace_path = os.path.join(base_dir, workspace_name)

        # Check if this workspace has iteration outputs (meaning it was a real run)
        has_outputs = any(
            f.startswith("populated_schema_v") and f.endswith(".json")
            for f in os.listdir(workspace_path) if os.path.isfile(os.path.join(workspace_path, f))
        )

        if not has_outputs:
            continue

        result["previous_workspace"] = workspace_path

        # Find latest version of each file type
        def find_latest_version(prefix: str, extension: str = ".json") -> str:
            """Find the highest versioned file matching pattern."""
            pattern = re.compile(rf"{prefix}_v(\d+){re.escape(extension)}$")
            max_version = 0
            latest_file = None

            for f in os.listdir(workspace_path):
                match = pattern.match(f)
                if match:
                    version = int(match.group(1))
                    if version > max_version:
                        max_version = version
                        latest_file = os.path.join(workspace_path, f)

            return latest_file

        # Find latest versions of each file type
        result["self_heal_instructions"] = find_latest_version("self_heal_instructions")
        result["populated_schema"] = find_latest_version("populated_schema")
        result["eval_report"] = find_latest_version("eval_report")
        result["extraction_report"] = find_latest_version("extraction_report")
        result["api_schema"] = find_latest_version("api_schema")
        result["api_response"] = find_latest_version("api_response")
        result["iteration_summary"] = os.path.join(workspace_path, "iteration_summary.json") \
            if os.path.exists(os.path.join(workspace_path, "iteration_summary.json")) else None

        # Check for intra-panel references in templates_output/
        templates_output_dir = os.path.join(workspace_path, "templates_output")
        if os.path.exists(templates_output_dir):
            # Look for *_intra_panel_references.json
            for f in os.listdir(templates_output_dir):
                if f.endswith("_intra_panel_references.json"):
                    intra_panel_path = os.path.join(templates_output_dir, f)
                    if os.path.exists(intra_panel_path):
                        result["intra_panel_references"] = intra_panel_path
                        break

            # Look for EDV mapping files
            for f in os.listdir(templates_output_dir):
                if f.endswith("_edv_tables.json"):
                    edv_tables_path = os.path.join(templates_output_dir, f)
                    if os.path.exists(edv_tables_path):
                        result["edv_tables"] = edv_tables_path
                elif f.endswith("_field_edv_mapping.json"):
                    field_edv_path = os.path.join(templates_output_dir, f)
                    if os.path.exists(field_edv_path):
                        result["field_edv_mapping"] = field_edv_path

        # Filter out None values
        result = {k: v for k, v in result.items() if v is not None}

        print(f"\n📂 Found previous run: {workspace_path}")
        print(f"   Latest files found:")
        for key, path in result.items():
            if key != "previous_workspace":
                print(f"   - {key}: {os.path.basename(path)}")

        break  # Use the first (newest) complete run

    return result


def run_intra_panel_extraction(document_path: str, output_dir: str) -> str:
    """
    Run the intra-panel field references dispatcher.

    Args:
        document_path: Path to the BUD document
        output_dir: Output directory for templates

    Returns:
        Path to the consolidated intra-panel references JSON
    """
    print("\n" + "="*70)
    print("STAGE 1: INTRA-PANEL FIELD REFERENCES EXTRACTION")
    print("="*70)
    print(f"Document: {document_path}")
    print(f"Output directory: {output_dir}")

    try:
        result = subprocess.run(
            [
                "python3",
                "dispatchers/intra_panel_rule_field_references.py",
                document_path,
                "--output-dir", output_dir
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )

        if result.returncode != 0:
            print(f"✗ Intra-panel extraction failed:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return None

        print(result.stdout)

        # Find the consolidated JSON file
        doc_name = Path(document_path).stem
        consolidated_path = os.path.join(output_dir, f"{doc_name}_intra_panel_references.json")

        if os.path.exists(consolidated_path):
            print(f"✓ Intra-panel references extracted: {consolidated_path}")
            return consolidated_path
        else:
            print(f"✗ Consolidated file not found: {consolidated_path}", file=sys.stderr)
            return None

    except Exception as e:
        print(f"✗ Error running intra-panel extraction: {e}", file=sys.stderr)
        return None


def run_edv_table_mapping(document_path: str, output_dir: str) -> tuple:
    """
    Run the EDV table mapping extraction.

    Args:
        document_path: Path to BUD document
        output_dir: Output directory for results

    Returns:
        Tuple of (edv_tables_path, field_edv_mapping_path) or (None, None) if failed
    """
    print("\n" + "="*70)
    print("STAGE 1b: EDV TABLE MAPPING EXTRACTION")
    print("="*70)
    print(f"Document: {document_path}")
    print(f"Output directory: {output_dir}")

    try:
        # Check if dispatcher exists
        dispatcher_path = "dispatchers/edv_table_mapping.py"
        if not os.path.exists(dispatcher_path):
            print(f"⚠️  EDV dispatcher not found: {dispatcher_path}")
            print("   Skipping EDV mapping extraction (optional)")
            return None, None

        result = subprocess.run(
            [
                "python3",
                dispatcher_path,
                document_path,
                "--output-dir", output_dir
            ],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            print(f"⚠️  EDV extraction failed (non-zero exit): {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr[:500]}")
            return None, None

        # Find the EDV output files
        doc_name = Path(document_path).stem.replace(" ", "_")
        edv_tables_path = os.path.join(output_dir, f"{doc_name}_edv_tables.json")
        field_edv_path = os.path.join(output_dir, f"{doc_name}_field_edv_mapping.json")

        edv_tables_found = os.path.exists(edv_tables_path)
        field_edv_found = os.path.exists(field_edv_path)

        if edv_tables_found or field_edv_found:
            print(f"✓ EDV mapping extracted:")
            if edv_tables_found:
                print(f"   - EDV tables: {edv_tables_path}")
            if field_edv_found:
                print(f"   - Field mapping: {field_edv_path}")
            return (
                edv_tables_path if edv_tables_found else None,
                field_edv_path if field_edv_found else None
            )
        else:
            print(f"⚠️  EDV output files not found")
            return None, None

    except subprocess.TimeoutExpired:
        print(f"✗ EDV extraction timed out after 10 minutes", file=sys.stderr)
        return None, None
    except Exception as e:
        print(f"⚠️  Error running EDV extraction: {e}")
        return None, None


def run_rule_extraction_agent(schema_path: str, intra_panel_path: str,
                              workspace_dir: str, iteration: int = 1,
                              self_heal_instructions: dict = None,
                              verbose: bool = False, validate: bool = False,
                              llm_threshold: float = 0.7,
                              previous_run_files: dict = None,
                              edv_tables_path: str = None,
                              field_edv_mapping_path: str = None) -> tuple:
    """
    Run the rule extraction coding agent.

    Args:
        schema_path: Path to schema JSON
        intra_panel_path: Path to intra-panel references JSON
        workspace_dir: Workspace directory for outputs
        iteration: Iteration number (for self-healing)
        self_heal_instructions: Instructions from previous eval (if any)
        verbose: Enable verbose logging
        validate: Enable rule validation
        llm_threshold: Confidence threshold for LLM fallback
        previous_run_files: Dict with paths to files from previous run
        edv_tables_path: Path to EDV tables mapping JSON (optional)
        field_edv_mapping_path: Path to field-EDV mapping JSON (optional)

    Returns:
        Tuple of (output_path, report_path)
    """
    print("\n" + "="*70)
    print(f"STAGE 2: RULE EXTRACTION CODING AGENT (Iteration {iteration})")
    print("="*70)
    print(f"Schema: {schema_path}")
    print(f"Intra-panel refs: {intra_panel_path}")
    if edv_tables_path:
        print(f"EDV tables: {edv_tables_path}")
    if field_edv_mapping_path:
        print(f"Field-EDV mapping: {field_edv_mapping_path}")

    if self_heal_instructions:
        print("\n🔧 Self-Healing Mode: Applying fixes from previous evaluation")
        priority_fixes = self_heal_instructions.get("priority_fixes", [])
        print(f"   - {len(priority_fixes)} priority fixes to apply")

    # Set output paths - all iterations versioned for easy review
    output_path = os.path.join(workspace_dir, f"populated_schema_v{iteration}.json")
    report_path = os.path.join(workspace_dir, f"extraction_report_v{iteration}.json")

    # Log iteration outputs for manual review
    print(f"\n📁 Iteration {iteration} outputs will be saved to:")
    print(f"   - Schema: {output_path}")
    print(f"   - Report: {report_path}")

    # Build prompt with comprehensive self-heal instructions if available
    if self_heal_instructions:
        self_heal_json = os.path.join(workspace_dir, f"self_heal_instructions_v{iteration}.json")
        with open(self_heal_json, 'w') as f:
            json.dump(self_heal_instructions, f, indent=2)

        additional_prompt = f"""

## ⚠️ SELF-HEALING MODE: Previous Evaluation FAILED

The previous iteration was evaluated and FAILED. You MUST fix ALL issues below.

### Full Eval Report
Read the complete eval report at: {self_heal_json}

### Priority Fixes (Address ALL)
"""
        for i, fix in enumerate(self_heal_instructions.get("priority_fixes", []), 1):
            # Handle both old format (fix_type/description) and new format (category/action)
            if isinstance(fix, dict):
                fix_type = fix.get('fix_type') or fix.get('category') or fix.get('rule_type') or 'Unknown'
                description = fix.get('description') or fix.get('action') or 'N/A'
                implementation = fix.get('implementation', '')
                affected = fix.get('affected_fields') or fix.get('missing_fields') or []
                priority = fix.get('priority', '')
                expected = fix.get('expected')
                actual = fix.get('actual')

                additional_prompt += f"\n#### Fix {i}: {fix_type}"
                if priority:
                    additional_prompt += f" ({priority})"
                additional_prompt += f"\n- **Description**: {description}"
                if expected is not None and actual is not None:
                    additional_prompt += f"\n- **Expected**: {expected}, **Actual**: {actual}"
                if affected:
                    # Handle both string and dict formats for affected_fields
                    field_names = []
                    for f in affected[:5]:
                        if isinstance(f, dict):
                            field_names.append(f.get('name', str(f)))
                        else:
                            field_names.append(str(f))
                    additional_prompt += f"\n- **Affected Fields**: {', '.join(field_names)}"
                if implementation:
                    additional_prompt += f"\n- **Implementation**: `{implementation}`"
            else:
                # Handle if fix is just a string
                additional_prompt += f"\n#### Fix {i}: {fix}"
            additional_prompt += "\n"

        # Add missing rules details
        missing_rules = self_heal_instructions.get("missing_rules", [])
        if missing_rules:
            additional_prompt += "\n### Missing Rules to Add\n"

            # Handle both dict format (keys are rule types) and list format (list of category objects)
            if isinstance(missing_rules, dict):
                # New format: {"SET_DATE": [...], "MAKE_VISIBLE": [...], ...}
                for rule_type, fields_list in missing_rules.items():
                    if isinstance(fields_list, list) and fields_list:
                        additional_prompt += f"\n**{rule_type}** ({len(fields_list)} missing):\n"
                        for field in fields_list[:5]:
                            # Handle both string and dict formats
                            if isinstance(field, dict):
                                field_name = field.get('field_name') or field.get('name', 'Unknown')
                                additional_prompt += f"- {field_name}"
                                if field.get('schema_id') or field.get('field_id'):
                                    additional_prompt += f" (id: {field.get('schema_id') or field.get('field_id')})"
                            else:
                                additional_prompt += f"- {field}"
                            additional_prompt += "\n"
            else:
                # Old format: [{"category": "...", "missing_count": N, "fields": [...]}, ...]
                for category in missing_rules:
                    if isinstance(category, dict):
                        cat_name = category.get("category", "Unknown")
                        count = category.get("missing_count", 0)
                        additional_prompt += f"\n**{cat_name}** ({count} missing):\n"
                        for field in category.get("fields", [])[:5]:
                            # Handle both string and dict formats
                            if isinstance(field, dict):
                                additional_prompt += f"- {field.get('name', 'Unknown')}"
                                if field.get('schema_id'):
                                    additional_prompt += f" (schema: {field.get('schema_id')})"
                            else:
                                additional_prompt += f"- {field}"
                            additional_prompt += "\n"
                    elif isinstance(category, str):
                        # Handle if category is just a string
                        additional_prompt += f"- {category}\n"

        # Add rule type comparison
        rule_comparison = self_heal_instructions.get("rule_type_comparison", {})
        if rule_comparison:
            gen_rules = rule_comparison.get("generated", {})
            ref_rules = rule_comparison.get("reference", {})
            additional_prompt += "\n### Rule Type Gaps\n"
            additional_prompt += "| Type | Generated | Expected | Gap |\n"
            additional_prompt += "|------|-----------|----------|-----|\n"
            for rt in ["VERIFY", "OCR", "EXT_DROP_DOWN", "MAKE_VISIBLE", "MAKE_DISABLED"]:
                gen = gen_rules.get(rt, 0)
                ref = ref_rules.get(rt, 0)
                gap = ref - gen
                if gap > 0:
                    additional_prompt += f"| {rt} | {gen} | {ref} | -{gap} |\n"

        # Add API errors if any
        api_errors = self_heal_instructions.get("api_errors", [])
        if api_errors:
            additional_prompt += "\n### API Validation Errors\n"
            additional_prompt += "The following errors were returned by the API and MUST be fixed:\n\n"
            for i, err in enumerate(api_errors, 1):
                if isinstance(err, dict):
                    err_type = err.get('error_type', 'Unknown')
                    err_msg = err.get('message', 'N/A')
                    instruction = err.get('instruction', '')
                    additional_prompt += f"#### API Error {i}: {err_type}\n"
                    err_msg_str = str(err_msg) if err_msg else 'N/A'
                    additional_prompt += f"- **Message**: {err_msg_str[:500]}\n"
                    if instruction:
                        additional_prompt += f"- **Fix Required**: {instruction}\n"
                elif isinstance(err, str):
                    additional_prompt += f"#### API Error {i}\n"
                    additional_prompt += f"- **Message**: {err[:500]}\n"
                additional_prompt += "\n"

        additional_prompt += """

### Critical Requirements

1. **OCR → VERIFY Chaining**: Every OCR rule MUST have postTriggerRuleIds pointing to VERIFY
2. **Ordinal Mapping**: VERIFY destinationIds must match Rule-Schemas.json structure
3. **Rule Consolidation**: MAKE_DISABLED should be 5 rules, not 53
4. **EXT_DROP_DOWN**: Detect external table references in logic
5. **Valid Field IDs**: All sourceIds and destinationIds must reference valid field IDs in the schema

The evaluation AND API validation will run again after this iteration. All checks must pass.
"""
    else:
        additional_prompt = ""

    try:
        cmd = [
            "python3",
            "dispatchers/rule_extraction_coding_agent.py",
            "--schema", schema_path,
            "--intra-panel", intra_panel_path,
            "--output", output_path,
            "--report", report_path,
            "--llm-threshold", str(llm_threshold)
        ]

        if verbose:
            cmd.append("--verbose")

        if validate:
            cmd.append("--validate")

        # Add previous run files for context (learning from past iterations)
        if previous_run_files:
            if previous_run_files.get("previous_workspace"):
                cmd.extend(["--prev-workspace", previous_run_files["previous_workspace"]])
            if previous_run_files.get("self_heal_instructions"):
                cmd.extend(["--prev-self-heal", previous_run_files["self_heal_instructions"]])
            if previous_run_files.get("populated_schema"):
                cmd.extend(["--prev-schema", previous_run_files["populated_schema"]])
            if previous_run_files.get("eval_report"):
                cmd.extend(["--prev-eval", previous_run_files["eval_report"]])
            if previous_run_files.get("extraction_report"):
                cmd.extend(["--prev-extraction", previous_run_files["extraction_report"]])
            if previous_run_files.get("api_schema"):
                cmd.extend(["--prev-api-schema", previous_run_files["api_schema"]])
            if previous_run_files.get("api_response"):
                cmd.extend(["--prev-api-response", previous_run_files["api_response"]])

        # Add EDV mapping files if available
        if edv_tables_path and os.path.exists(edv_tables_path):
            cmd.extend(["--edv-tables", edv_tables_path])
        if field_edv_mapping_path and os.path.exists(field_edv_mapping_path):
            cmd.extend(["--field-edv-mapping", field_edv_mapping_path])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )

        if result.returncode != 0:
            print(f"✗ Rule extraction agent failed:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return None, None

        print(result.stdout)

        if os.path.exists(output_path):
            print(f"✓ Rules extracted and populated: {output_path}")
            return output_path, report_path
        else:
            print(f"✗ Output file not created: {output_path}", file=sys.stderr)
            return None, None

    except Exception as e:
        print(f"✗ Error running rule extraction agent: {e}", file=sys.stderr)
        return None, None


def run_evaluation(generated_path: str, reference_path: str,
                  workspace_dir: str, iteration: int = 1,
                  threshold: float = 0.90, bud_path: str = None,
                  use_llm: bool = True, llm_threshold: float = 0.8) -> tuple:
    """
    Run comprehensive evaluation of generated output against reference.

    Uses the eval framework for intelligent comparison.

    Args:
        generated_path: Path to generated output
        reference_path: Path to reference output
        workspace_dir: Workspace directory
        iteration: Iteration number
        threshold: Pass threshold
        bud_path: Path to BUD document (for future BUD verification)
        use_llm: Whether to use LLM for fuzzy field matching
        llm_threshold: Confidence threshold for LLM matches

    Returns:
        Tuple of (passed: bool, eval_report: dict)
    """
    print("\n" + "="*70)
    print(f"STAGE 3: EVALUATION (Iteration {iteration})")
    print("="*70)
    print(f"Generated: {generated_path}")
    print(f"Reference: {reference_path}")
    if bud_path:
        print(f"BUD Source: {bud_path}")

    # Validate input files
    if not os.path.exists(generated_path):
        print(f"✗ Generated file not found: {generated_path}", file=sys.stderr)
        return False, None

    if not os.path.exists(reference_path):
        print(f"✗ Reference file not found: {reference_path}", file=sys.stderr)
        return False, None

    eval_report_path = os.path.join(workspace_dir, f"eval_report_v{iteration}.json")

    try:
        # Create evaluator using the eval framework
        evaluator = FormFillEvaluator(
            use_llm=use_llm,
            llm_threshold=llm_threshold,
            pass_threshold=threshold
        )

        # Run evaluation and save report
        passed, report = evaluator.evaluate_and_save_report(
            generated_path,
            reference_path,
            eval_report_path,
            verbose=True,
            include_llm_analysis=use_llm
        )

        # Convert report to dict
        eval_report = report.to_dict()

        # Get summary info
        summary = eval_report.get("evaluation_summary", {})
        score = summary.get("overall_score", 0)

        # Print summary
        print(f"\n{'='*50}")
        print(f"EVAL RESULT: {'PASS ✓' if passed else 'FAIL ✗'}")
        print(f"Score: {score:.0%} (Threshold: {threshold:.0%})")
        print(f"{'='*50}")

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
                status = "✓" if gen >= ref * 0.8 else "✗"
                print(f"  {rt}: {gen}/{ref} {status}")

        # Print priority fixes count
        fixes = eval_report.get("priority_fixes", [])
        print(f"\nPriority Fixes Needed: {len(fixes)}")

        return passed, eval_report

    except Exception as e:
        print(f"✗ Error running evaluation: {e}", file=sys.stderr)
        traceback.print_exc()
        return False, None


def save_iteration_summary(workspace_dir: str, iteration: int, output_path: str,
                           eval_report: dict, error: Exception = None):
    """
    Save a summary of the iteration for manual review.

    Args:
        workspace_dir: Workspace directory
        iteration: Current iteration number
        output_path: Path to generated output
        eval_report: Evaluation report (if available)
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
        "iteration": iteration,
        "timestamp": datetime.now().isoformat(),
        "output_file": output_path,
        "eval_report_file": os.path.join(workspace_dir, f"eval_report_v{iteration}.json"),
        "extraction_report_file": os.path.join(workspace_dir, f"extraction_report_v{iteration}.json"),
        "self_heal_file": os.path.join(workspace_dir, f"self_heal_instructions_v{iteration}.json"),
    }

    if eval_report:
        summary_data = eval_report.get("evaluation_summary", {})
        iteration_record["score"] = summary_data.get("overall_score", 0)
        # Handle both old format (evaluation_passed) and new format (passed)
        iteration_record["passed"] = summary_data.get("passed", summary_data.get("evaluation_passed", False))
        # Handle both old format (self_heal_instructions.priority_fixes) and new format (priority_fixes)
        priority_fixes = eval_report.get("priority_fixes", [])
        if not priority_fixes:
            priority_fixes = eval_report.get("self_heal_instructions", {}).get("priority_fixes", [])
        iteration_record["priority_fixes_count"] = len(priority_fixes)
    else:
        iteration_record["score"] = None
        iteration_record["passed"] = False

    if error:
        iteration_record["error"] = {
            "type": type(error).__name__,
            "message": str(error)
        }

    # Update or append iteration record
    existing_idx = next((i for i, r in enumerate(summary["iterations"]) if r["iteration"] == iteration), None)
    if existing_idx is not None:
        summary["iterations"][existing_idx] = iteration_record
    else:
        summary["iterations"].append(iteration_record)

    summary["current_iteration"] = iteration
    summary["last_updated"] = datetime.now().isoformat()

    # Save summary
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n📊 Iteration {iteration} summary saved to: {summary_path}")


def print_final_summary(workspace_dir: str, iterations: int, final_passed: bool,
                       final_score: float, intra_panel_path: str, output_path: str):
    """
    Print final summary of the self-healing orchestration.

    Args:
        workspace_dir: Workspace directory
        iterations: Total iterations performed
        final_passed: Whether final evaluation passed
        final_score: Final overall score
        intra_panel_path: Path to intra-panel references
        output_path: Path to final populated schema
    """
    # Update iteration_summary.json with final status
    summary_path = os.path.join(workspace_dir, "iteration_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        summary["final_status"] = "passed" if final_passed else "failed"
        summary["final_score"] = final_score
        summary["total_iterations"] = iterations
        summary["completed_at"] = datetime.now().isoformat()
        summary["final_output"] = output_path
        summary["intra_panel_path"] = intra_panel_path
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

    print("\n" + "="*70)
    print("SELF-HEALING ORCHESTRATION COMPLETE")
    print("="*70)
    print(f"Workspace: {workspace_dir}")
    print(f"Total Iterations: {iterations}")
    print(f"Final Status: {'PASSED ✓' if final_passed else 'FAILED ✗'}")
    print(f"Final Score: {final_score:.0%}")
    print()
    print("Generated Files:")
    print(f"  1. Intra-panel references: {intra_panel_path}")
    print(f"  2. Final populated schema: {output_path}")
    print(f"  3. Evaluation reports: {workspace_dir}/eval_report_v*.json")
    print(f"  4. Extraction reports: {workspace_dir}/extraction_report_v*.json")
    print(f"  5. API schemas: {workspace_dir}/api_schema_v*.json")
    print(f"  6. API responses: {workspace_dir}/api_response_v*.json")
    print(f"  7. Iteration summary: {summary_path}")

    if not final_passed:
        print()
        print("⚠️  Evaluation did not pass after maximum iterations.")
        print("    Review eval_report_v{}.json for remaining issues.".format(iterations))

    print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Self-healing rule extraction orchestrator with eval feedback loop"
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
        help="Path to reference output JSON (human-made) in documents/json_output/"
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace directory (default: adws/<timestamp>/)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum self-healing iterations (default: 3)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.90,
        help="Evaluation pass threshold (default: 0.90)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated rules"
    )
    parser.add_argument(
        "--llm-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for LLM fallback (default: 0.7)"
    )
    parser.add_argument(
        "--api-token",
        default=None,
        help="API authorization token (default: uses built-in token)"
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip API validation (only run eval)"
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Override API base URL"
    )

    args = parser.parse_args()

    # Update API config if arguments provided
    if args.api_token:
        API_CONFIG["auth_token"] = args.api_token
    if args.api_url:
        API_CONFIG["base_url"] = args.api_url

    # Validate inputs
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.schema):
        print(f"Error: Schema file not found: {args.schema}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.reference):
        print(f"Error: Reference file not found: {args.reference}", file=sys.stderr)
        sys.exit(1)

    # Create timestamped workspace
    if args.workspace:
        workspace_dir = args.workspace
        templates_output_dir = os.path.join(workspace_dir, "templates_output")
        os.makedirs(templates_output_dir, exist_ok=True)
    else:
        workspace_dir, templates_output_dir = create_timestamped_workspace()

    print("="*70)
    print("SELF-HEALING RULE EXTRACTION ORCHESTRATOR")
    print("="*70)
    print(f"Document: {args.document_path}")
    print(f"Schema: {args.schema}")
    print(f"Reference: {args.reference}")
    print(f"Workspace: {workspace_dir}")
    print(f"Max Iterations: {args.max_iterations}")
    print(f"Pass Threshold: {args.threshold:.0%}")
    print("="*70)

    # Stage 0: Find previous run for context (learning from past iterations)
    previous_run_files = find_latest_previous_run()
    if previous_run_files:
        print(f"\n📚 Will use context from previous run for improved extraction")
    else:
        print(f"\n📝 No previous runs found - starting fresh")

    # Stage 1: Extract intra-panel references (or reuse from previous run)
    intra_panel_path = None

    # Check if intra-panel references exist from previous run
    if previous_run_files.get("intra_panel_references"):
        prev_intra_panel = previous_run_files["intra_panel_references"]
        if os.path.exists(prev_intra_panel):
            # Verify the file is valid JSON and matches our BUD document
            try:
                with open(prev_intra_panel, 'r') as f:
                    intra_data = json.load(f)

                # Check if this intra-panel was generated for the same BUD
                # (by checking if the BUD name is in the filename or metadata)
                bud_name = Path(args.document_path).stem
                intra_filename = os.path.basename(prev_intra_panel)

                if bud_name in intra_filename or intra_data.get("source_document", "").endswith(bud_name + ".docx"):
                    print(f"\n♻️  Reusing intra-panel references from previous run:")
                    print(f"   Source: {prev_intra_panel}")

                    # Copy to current workspace for reference
                    dest_path = os.path.join(templates_output_dir, os.path.basename(prev_intra_panel))
                    shutil.copy2(prev_intra_panel, dest_path)
                    intra_panel_path = dest_path

                    print(f"   Copied to: {intra_panel_path}")
                else:
                    print(f"\n⚠️  Previous intra-panel references are for a different BUD document")
                    print(f"   Previous: {intra_filename}")
                    print(f"   Current BUD: {bud_name}")
                    print(f"   Will generate fresh intra-panel references")

            except (json.JSONDecodeError, Exception) as e:
                print(f"\n⚠️  Could not read previous intra-panel references: {e}")
                print(f"   Will generate fresh intra-panel references")

    # If no previous intra-panel found or reuse failed, generate new one
    if not intra_panel_path:
        intra_panel_path = run_intra_panel_extraction(args.document_path, templates_output_dir)

    if not intra_panel_path:
        print("\n✗ Orchestration failed at Stage 1", file=sys.stderr)
        sys.exit(1)

    # Stage 1b: Extract EDV table mappings (or reuse from previous run)
    edv_tables_path = None
    field_edv_mapping_path = None

    # Check if EDV mappings exist from previous run
    if previous_run_files.get("edv_tables") or previous_run_files.get("field_edv_mapping"):
        bud_name = Path(args.document_path).stem

        # Reuse EDV tables if available
        if previous_run_files.get("edv_tables"):
            prev_edv = previous_run_files["edv_tables"]
            if bud_name.replace(" ", "_") in os.path.basename(prev_edv):
                dest_path = os.path.join(templates_output_dir, os.path.basename(prev_edv))
                shutil.copy2(prev_edv, dest_path)
                edv_tables_path = dest_path
                print(f"\n♻️  Reusing EDV tables from previous run: {edv_tables_path}")

        # Reuse field-EDV mapping if available
        if previous_run_files.get("field_edv_mapping"):
            prev_edv = previous_run_files["field_edv_mapping"]
            if bud_name.replace(" ", "_") in os.path.basename(prev_edv):
                dest_path = os.path.join(templates_output_dir, os.path.basename(prev_edv))
                shutil.copy2(prev_edv, dest_path)
                field_edv_mapping_path = dest_path
                print(f"♻️  Reusing field-EDV mapping from previous run: {field_edv_mapping_path}")

    # If no previous EDV mappings found, try to generate new ones
    if not edv_tables_path and not field_edv_mapping_path:
        edv_tables_path, field_edv_mapping_path = run_edv_table_mapping(
            args.document_path, templates_output_dir
        )
        # EDV is optional - don't fail if it's not available

    # Self-healing loop
    iteration = 1
    passed = False
    self_heal_instructions = None
    output_path = None
    final_score = 0.0
    last_error = None

    while iteration <= args.max_iterations and not passed:
        try:
            # If previous iteration had an error, include it in self-heal instructions
            if last_error:
                if self_heal_instructions is None:
                    self_heal_instructions = {}
                self_heal_instructions["previous_iteration_error"] = {
                    "error_type": type(last_error).__name__,
                    "error_message": str(last_error),
                    "instruction": "The previous iteration crashed with this error. Fix the issue and continue."
                }
                last_error = None

            # Stage 2: Run rule extraction agent
            output_path, report_path = run_rule_extraction_agent(
                args.schema,
                intra_panel_path,
                workspace_dir,
                iteration=iteration,
                self_heal_instructions=self_heal_instructions,
                verbose=args.verbose,
                validate=args.validate,
                llm_threshold=args.llm_threshold,
                previous_run_files=previous_run_files,
                edv_tables_path=edv_tables_path,
                field_edv_mapping_path=field_edv_mapping_path
            )

            if not output_path:
                print(f"\n⚠️  Rule extraction agent failed (Iteration {iteration}), will retry...", file=sys.stderr)
                last_error = Exception("Rule extraction agent returned no output")
                iteration += 1
                continue

            # Stage 3: Run evaluation (ALWAYS after code generation)
            # Pass BUD document path for primary verification
            passed, eval_report = run_evaluation(
                output_path,
                args.reference,
                workspace_dir,
                iteration=iteration,
                threshold=args.threshold,
                bud_path=args.document_path  # BUD is primary source of truth
            )

            if passed:
                final_score = eval_report.get("evaluation_summary", {}).get("overall_score", 0)
                print(f"\n✓ Evaluation PASSED on iteration {iteration}!")
                # Save iteration summary for review
                save_iteration_summary(workspace_dir, iteration, output_path, eval_report)
                break

            if not eval_report:
                print(f"\n⚠️  Evaluation returned no report (Iteration {iteration}), will retry...", file=sys.stderr)
                last_error = Exception("Evaluation returned no report")
                # Save iteration summary even on failure
                save_iteration_summary(workspace_dir, iteration, output_path, None, last_error)
                iteration += 1
                continue

            final_score = eval_report.get("evaluation_summary", {}).get("overall_score", 0)

            # Save iteration summary for manual review
            save_iteration_summary(workspace_dir, iteration, output_path, eval_report)

            # Stage 4: Call API to validate generated output (unless skipped)
            api_errors_for_agent = []
            if not args.skip_api:
                # Generate unique workspace ID for this run
                workspace_id = uuid.uuid4().hex

                api_success, api_response, api_errors_for_agent = call_api(
                    output_path,
                    iteration,
                    workspace_id,
                    workspace_dir
                )

                if api_success:
                    print(f"\n✓ API validation successful!")
                    # If eval passed and API passed, we're done
                    if passed:
                        break
                else:
                    # API failed - check if errors need to go to coding agent
                    if api_errors_for_agent:
                        print(f"\n⚠️  API returned errors that need coding agent attention")

            # Check if we should continue
            if iteration >= args.max_iterations:
                print(f"\n⚠️  Maximum iterations ({args.max_iterations}) reached without passing evaluation")
                break

            # Extract comprehensive self-heal instructions for next iteration
            # Use the eval framework's extraction function
            self_heal_instructions = extract_self_heal_instructions(eval_report, iteration)
            if self_heal_instructions is None:
                self_heal_instructions = {}

            # Add API errors if any
            if api_errors_for_agent:
                self_heal_instructions["api_errors"] = api_errors_for_agent
                print(f"   API errors to fix: {len(api_errors_for_agent)}")

            if not self_heal_instructions.get("priority_fixes"):
                print("\n⚠️  No priority fixes in self-heal instructions.")
                # Still try to continue with the general eval data
                if not self_heal_instructions.get("missing_rules") and not self_heal_instructions.get("rule_type_comparison"):
                    print("No actionable feedback available. Cannot continue.")
                    break

            print(f"\n🔄 Starting self-healing iteration {iteration + 1}...")
            print(f"   Priority fixes to apply: {len(self_heal_instructions.get('priority_fixes', []))}")
            print(f"   Missing rule categories: {len(self_heal_instructions.get('missing_rules', []))}")
            print(f"   API errors to fix: {len(self_heal_instructions.get('api_errors', []))}")
            iteration += 1

        except Exception as e:
            # Catch any unexpected errors and feed them back to the agent
            error_details = traceback.format_exc()
            print(f"\n⚠️  Error during iteration {iteration}: {e}", file=sys.stderr)
            print(f"    Will feed error to agent and retry...", file=sys.stderr)

            # Store error for next iteration
            last_error = e

            # Save iteration summary with error for manual review
            save_iteration_summary(workspace_dir, iteration, output_path, None, e)

            # Create error-focused self-heal instructions
            if self_heal_instructions is None:
                self_heal_instructions = {}
            self_heal_instructions["orchestrator_error"] = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": error_details,
                "iteration": iteration,
                "instruction": "The orchestrator encountered an error processing the output. Please ensure the output format is correct and all data types match expected formats (e.g., affected_fields should contain strings or dicts with 'name' keys)."
            }

            iteration += 1

            # Safety check to prevent infinite loops
            if iteration > args.max_iterations:
                print(f"\n✗ Maximum iterations exceeded after errors", file=sys.stderr)
                break

    # Print final summary
    print_final_summary(
        workspace_dir,
        iteration,
        passed,
        final_score,
        intra_panel_path,
        output_path
    )

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
