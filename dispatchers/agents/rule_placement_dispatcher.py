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
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict

# Import doc_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from doc_parser import DocumentParser


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


def group_fields_by_panel(parsed_doc) -> Dict[str, List[Dict]]:
    """Group fields by their panel from parsed document"""
    panels = defaultdict(list)
    current_panel = "default_panel"

    for field in parsed_doc.all_fields:
        # If field is a PANEL type, it becomes the current panel
        if field.field_type.value == 'PANEL':
            current_panel = field.name
            continue

        field_data = {
            'field_name': field.name,
            'type': field.field_type.value,
            'mandatory': field.is_mandatory,
            'logic': field.logic if field.logic else ''
        }

        panels[current_panel].append(field_data)

    return panels


def extract_fields_from_bud(bud_path: str) -> object:
    """Extract fields from BUD document using doc_parser"""
    print(f"Parsing BUD document: {bud_path}")
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    total_fields = len(parsed.all_fields)
    fields_with_logic = sum(1 for f in parsed.all_fields if f.logic and f.logic.strip())

    print(f"Extracted {total_fields} fields ({fields_with_logic} with logic)")
    return parsed


def get_relevant_rules(fields: List[Dict], matcher: KeywordTreeMatcher,
                      action_to_rules: Dict) -> Set[str]:
    """Get relevant rule names for a set of fields using keyword matching"""
    relevant_rules = set()

    for field in fields:
        logic = field['logic']
        if not logic:
            continue

        # Match action types from logic
        matched_actions = matcher.match_action_types(logic)

        # Get rule names for matched actions
        for action in matched_actions:
            if action in action_to_rules:
                relevant_rules.update(action_to_rules[action])

    return relevant_rules


def call_mini_agent(fields_with_logic: List[Dict], rule_names: Set[str],
                   panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
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

    prompt = f"""Process fields for panel "{panel_name}" and determine which rules apply to each field.

## Input Data
Read the input from: {input_file}

The input contains:
- fields_with_logic: Array of fields with their logic text
- rule_names: List of available rule names

## Task
For each field in fields_with_logic:
1. Read and understand the field's logic text
2. Determine which rules from rule_names should be applied
3. Consider the field type and mandatory flag
4. Multiple rules can apply to a single field
5. If no specific rules apply, use empty array

## Instructions
1) For **ALL** dropdown types always use **EDV Dropdown (Client)** rule.
2) There will be logic, where it mentions it will be Auto Derived from some rule, no rule is required in that case **unless** other rules are specified.

## Output
Write a JSON array to: {output_file}

Format:
```json
[
  {{
    "field_name": "Field Name",
    "type": "TEXT",
    "mandatory": true,
    "logic": "original logic text",
    "rules": ["RULE_NAME_1", "RULE_NAME_2"],
    "variableName": "__fieldname__"
  }}
]
```

Each field must have:
- field_name: exact name from input
- type: exact type from input
- mandatory: exact value from input
- logic: exact logic text from input
- rules: array of rule names (can be empty)
- variableName: generated by converting field_name to lowercase and replacing spaces with underscores, wrapped in double underscores (e.g., "Field Name" -> "__field_name__")
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name} ({len(fields_with_logic)} fields)")
        print('='*70)

        # Call claude -p with the mini agent
        process = subprocess.Popen(
            [
                "claude",
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
            print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"✗ Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
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
    panels = group_fields_by_panel(parsed_doc)
    print(f"Found {len(panels)} panels")

    # Step 5: Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, fields in panels.items():
        # Filter fields with logic
        fields_with_logic = [f for f in fields if f['logic'].strip()]

        if not fields_with_logic:
            print(f"\nSkipping panel '{panel_name}' - no fields with logic")
            continue

        # Get relevant rules for this panel's fields
        relevant_rules = get_relevant_rules(fields_with_logic, matcher, action_to_rules)

        print(f"\nPanel '{panel_name}': {len(fields)} total, {len(fields_with_logic)} with logic, {len(relevant_rules)} relevant rules")

        result = call_mini_agent(
            fields_with_logic,
            relevant_rules,
            panel_name,
            temp_dir
        )

        if result:
            successful_panels += 1
            total_fields_processed += len(result)
            all_results[panel_name] = result
        else:
            failed_panels += 1
            print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)

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
