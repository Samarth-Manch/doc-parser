#!/usr/bin/env python3
"""
Rule Placement Mini Agent Dispatcher

This script:
1. Reads BUD document using doc_parser to extract fields with logic
2. Uses keyword tree matching to identify relevant rules for each field
3. Groups fields by panel
4. For each panel, calls mini agent with fields and filtered rule names
5. Outputs single JSON file containing all panels with rule placements
"""

import argparse
import json
import subprocess
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

# Import doc_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from doc_parser import DocumentParser

PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


def query_context_usage(panel_name: str, agent_name: str) -> Optional[str]:
    """
    Query the last claude agent session for context/token usage.
    Uses --continue to resume the last conversation and ask for usage stats.

    Returns:
        Usage report string, or None if failed
    """
    usage_prompt = (
        "Report the context window usage for this conversation. "
        "Include: (1) number of input tokens used, "
        "(2) number of output tokens used, "
        "(3) total tokens used, and "
        "(4) percentage of the context window (200K tokens) that is filled. "
        "Format as a brief one-line summary."
    )

    try:
        process = subprocess.run(
            ["claude", "--continue", "-p", usage_prompt],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )

        if process.returncode == 0 and process.stdout.strip():
            return process.stdout.strip()
        return None
    except Exception:
        return None


class KeywordTreeMatcher:
    """Handles keyword tree matching for action type detection"""

    def __init__(self, keyword_tree_path: str):
        """Load and compile keyword tree patterns"""
        with open(keyword_tree_path, 'r') as f:
            data = json.load(f)

        self.tree_nodes = data.get('tree', {})
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for action types"""
        self.action_patterns = {}
        for action_type, config in self.tree_nodes.items():
            keywords = config.get('keywords', [])
            if keywords:
                pattern = '|'.join(re.escape(kw) for kw in keywords)
                self.action_patterns[action_type] = re.compile(
                    f'\\b({pattern})\\b',
                    re.IGNORECASE
                )

    def match_action_types(self, logic: str) -> List[str]:
        """Match action types from logic text"""
        matched_actions = []
        for action_type, pattern in self.action_patterns.items():
            if pattern.search(logic):
                matched_actions.append(action_type)
        return matched_actions


def load_rule_schemas(rule_schemas_path: str) -> Dict:
    """Load Rule-Schemas.json and create action->rules mapping"""
    with open(rule_schemas_path, 'r') as f:
        schemas = json.load(f)

    # Create mapping of action type to rule names
    action_to_rules = defaultdict(set)

    for rule in schemas.get('content', []):
        action = rule.get('action', '')
        name = rule.get('name', '')
        if action and name:
            action_to_rules[action].add(name)

    return dict(action_to_rules)


def group_fields_by_panel(parsed_doc) -> Tuple[Dict[str, List[Dict]], Dict[str, Dict]]:
    """Group fields by their panel from parsed document.

    Returns:
        (panels, panel_headers) where panel_headers maps panel_name -> panel field entry
        with a deterministically computed variableName and empty rules list.
    """
    panels = defaultdict(list)
    panel_headers: Dict[str, Dict] = {}
    current_panel = "default_panel"

    for field in parsed_doc.all_fields:
        # If field is a PANEL type, it becomes the current panel
        if field.field_type.value == 'PANEL':
            current_panel = field.name
            panel_var = '_' + re.sub(r'[^a-z0-9]', '', field.name.lower()) + '_'
            panel_headers[current_panel] = {
                'field_name': field.name,
                'type': 'PANEL',
                'mandatory': False,
                'logic': field.logic if field.logic else '',
                'variableName': panel_var,
                'rules': []
            }
            continue

        field_data = {
            'field_name': field.name,
            'type': field.field_type.value,
            'mandatory': field.is_mandatory,
            'logic': field.logic if field.logic else ''
        }

        panels[current_panel].append(field_data)

    return dict(panels), panel_headers


def extract_fields_from_bud(bud_path: str) -> object:
    """Extract fields from BUD document using doc_parser"""
    print(f"Parsing BUD document: {bud_path}")
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    total_fields = len(parsed.all_fields)
    fields_with_logic = sum(1 for f in parsed.all_fields if f.logic and f.logic.strip())

    print(f"Extracted {total_fields} fields ({fields_with_logic} with logic)")
    return parsed


# Patterns that indicate conditional derivation (handled by Derivation Agent, not Copy To)
DERIVATION_PATTERNS = [
    re.compile(r'\bif\b.+\bthen\b.+\b(value|derived|default|populate)', re.IGNORECASE),
    re.compile(r'\bif\b.+\b(else|otherwise)\b', re.IGNORECASE),
    re.compile(r'\bderived?\s+(it\s+)?as\b', re.IGNORECASE),
    re.compile(r'\bdefault\s+value\b', re.IGNORECASE),
    re.compile(r'\bbased\s+on\b.+\bvalue\b', re.IGNORECASE),
    re.compile(r'\bif\b.+\bselected\b.+\bvalue\s+is\b', re.IGNORECASE),
    re.compile(r'\bpopulate\s+default\b', re.IGNORECASE),
]

def _is_derivation_logic(logic: str) -> bool:
    """Check if field logic describes conditional derivation (not a simple copy)."""
    return any(p.search(logic) for p in DERIVATION_PATTERNS)


def get_relevant_rules(fields: List[Dict], matcher: KeywordTreeMatcher,
                      action_to_rules: Dict) -> Set[str]:
    """Get relevant rule names for a set of fields using keyword matching"""
    relevant_rules = set()
    has_non_derivation_copy = False

    for field in fields:
        logic = field['logic']
        if not logic:
            continue

        # Match action types from logic
        matched_actions = matcher.match_action_types(logic)

        # Get rule names for matched actions
        for action in matched_actions:
            if action in action_to_rules:
                # Skip COPY_TO for fields with conditional derivation logic
                if action == 'COPY_TO' and _is_derivation_logic(logic):
                    continue
                relevant_rules.update(action_to_rules[action])
                if action == 'COPY_TO':
                    has_non_derivation_copy = True

    # If no field genuinely needs COPY_TO, strip it from the candidate list
    if not has_non_derivation_copy:
        copy_to_rules = action_to_rules.get('COPY_TO', set())
        relevant_rules -= copy_to_rules

    return relevant_rules


def call_mini_agent(fields_with_logic: List[Dict], rule_names: Set[str],
                   panel_name: str, temp_dir: Path,
                   context_usage: bool = False,
                   verbose: bool = True,
                   model: str = "opus") -> Optional[List[Dict]]:
    """
    Call the Rule Type Placement mini agent via claude -p

    Returns:
        List of fields with assigned rules, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    input_file = temp_dir / f"{safe_panel_name}_input.json"
    output_file = temp_dir / f"{safe_panel_name}_rules.json"

    # Prepare input data
    input_data = {
        'fields_with_logic': fields_with_logic,
        'rule_names': sorted(list(rule_names))
    }

    # Write input to temp file
    with open(input_file, 'w') as f:
        json.dump(input_data, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input
- FIELDS_WITH_LOGIC: {input_file} (contains fields_with_logic array and rule_names list)
- LOG_FILE: {temp_dir / f"{re.sub(r'[^\\w\\-]', '_', panel_name)}_log.txt"}

## Output
Write JSON array to: {output_file}

Follow the agent prompt instructions. The panel name for variableName generation is "{panel_name}".
"""

    try:
        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING PANEL: {panel_name} ({len(fields_with_logic)} fields)")
            print('='*70)

        # Call claude -p with the mini agent
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--agent", "mini/01_rule_type_placement_agent_v2",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        # Collect output
        output_lines = []
        for line in process.stdout:
            if verbose:
                print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"✗ Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Query context usage from the agent session (opt-in)
        if context_usage:
            print(f"\n--- Context Usage ({panel_name}) ---")
            usage = query_context_usage(panel_name, "Rule Type Placement")
            if usage:
                print(usage)
            else:
                print("(Could not retrieve context usage)")
            print("---")

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
                if verbose:
                    print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                return result
            except json.JSONDecodeError as e:
                print(f"✗ Failed to parse output JSON: {e}", file=sys.stderr)
                return None
        else:
            print(f"✗ Output file not found: {output_file}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("✗ Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"✗ Error calling mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Rule Placement Dispatcher - Panel-by-panel processing"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to BUD document (.docx)"
    )
    parser.add_argument(
        "--keyword-tree",
        default="rule_extractor/static/keyword_tree.json",
        help="Path to keyword_tree.json (default: rule_extractor/static/keyword_tree.json)"
    )
    parser.add_argument(
        "--rule-schemas",
        default="rules/Rule-Schemas.json",
        help="Path to Rule-Schemas.json (default: rules/Rule-Schemas.json)"
    )
    parser.add_argument(
        "--output",
        default="output/rule_placement/all_panels_rules.json",
        help="Output file for all panels (default: output/rule_placement/all_panels_rules.json)"
    )
    parser.add_argument(
        "--context-usage",
        action="store_true",
        default=False,
        help="Query and display context window usage after each panel (adds ~30s per panel)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel panels to process (default: 4, use 1 for sequential)"
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude model to use (default: opus)"
    )

    args = parser.parse_args()

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load keyword tree matcher
    print(f"Loading keyword tree: {args.keyword_tree}")
    matcher = KeywordTreeMatcher(args.keyword_tree)

    # Step 2: Load rule schemas
    print(f"Loading rule schemas: {args.rule_schemas}")
    action_to_rules = load_rule_schemas(args.rule_schemas)
    total_rules = sum(len(rules) for rules in action_to_rules.values())
    print(f"Found {len(action_to_rules)} action types with {total_rules} total rules")

    # Step 3: Parse BUD document
    parsed_doc = extract_fields_from_bud(args.bud)

    # Step 4: Group fields by panel
    print("\nGrouping fields by panel...")
    panels, panel_headers = group_fields_by_panel(parsed_doc)
    print(f"Found {len(panels)} panels")

    # Step 5: Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS")
    print("="*70)

    max_workers = args.max_workers

    # Prepare jobs
    jobs = []
    for panel_name, fields in panels.items():
        fields_with_logic = [f for f in fields if f['logic'].strip()]

        if not fields_with_logic:
            print(f"\nSkipping panel '{panel_name}' - no fields with logic")
            continue

        relevant_rules = get_relevant_rules(fields_with_logic, matcher, action_to_rules)
        print(f"\nPanel '{panel_name}': {len(fields)} total, {len(fields_with_logic)} with logic, {len(relevant_rules)} relevant rules")
        jobs.append((panel_name, fields_with_logic, relevant_rules))

    successful_panels = 0
    failed_panels = 0
    total_fields_processed = 0
    all_results = {}

    if max_workers <= 1:
        # Sequential processing
        for panel_name, fields_with_logic, relevant_rules in jobs:
            result = call_mini_agent(
                fields_with_logic, relevant_rules, panel_name, temp_dir,
                context_usage=args.context_usage, verbose=True, model=args.model
            )
            if result:
                successful_panels += 1
                total_fields_processed += len(result)
                all_results[panel_name] = result
            else:
                failed_panels += 1
                print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)
    else:
        # Parallel processing
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={max_workers})")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_panel = {}
            for panel_name, fields_with_logic, relevant_rules in jobs:
                future = executor.submit(
                    call_mini_agent,
                    fields_with_logic, relevant_rules, panel_name, temp_dir,
                    context_usage=args.context_usage, verbose=False, model=args.model
                )
                future_to_panel[future] = panel_name

            for future in as_completed(future_to_panel):
                panel_name = future_to_panel[future]
                try:
                    result = future.result()
                    if result:
                        successful_panels += 1
                        total_fields_processed += len(result)
                        all_results[panel_name] = result
                        print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                    else:
                        failed_panels += 1
                        print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)
                except Exception as e:
                    failed_panels += 1
                    print(f"✗ Panel '{panel_name}' error: {e}", file=sys.stderr)

    # Reorder results to match original panel sequence and prepend PANEL field entries
    ordered_results = {}
    for panel_name in panels:
        if panel_name in all_results:
            fields = all_results[panel_name]
            # Prepend the PANEL field entry deterministically (panels are also fields)
            if panel_name in panel_headers:
                fields = [panel_headers[panel_name]] + fields
            ordered_results[panel_name] = fields
    all_results = ordered_results

    # Step 6: Write all results to single output file
    if all_results:
        print(f"\nWriting all results to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"✓ Successfully wrote {len(all_results)} panels to output file")

    # Print final summary
    print("\n" + "="*70)
    print("DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(panels)}")
    print(f"Successful: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
