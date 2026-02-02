#!/usr/bin/env python3
"""
Rule Extraction Agent - Main Entry Point

This is the main entry point for the rule extraction agent.
It provides a cleaner interface and handles the complete workflow.

Usage:
    python main.py --bud documents/Vendor\ Creation\ Sample\ BUD.docx \
                   --intra-panel intra_panel_references.json \
                   --output populated_schema.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent
from models import IdGenerator


def generate_summary_report(
    agent: RuleExtractionAgent,
    fields_count: int,
    rules_count: int,
    output_path: str = None
) -> dict:
    """
    Generate a summary report of the rule extraction.

    Args:
        agent: The rule extraction agent instance
        fields_count: Number of fields processed
        rules_count: Number of rules generated
        output_path: Path to save the report

    Returns:
        Summary report dict
    """
    # Count rules by action type
    action_counts = {}
    for rule in agent.all_rules:
        action = rule.get('actionType', 'UNKNOWN')
        action_counts[action] = action_counts.get(action, 0) + 1

    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_fields": fields_count,
            "total_rules": rules_count,
            "ocr_verify_chains": len(agent.ocr_verify_chains)
        },
        "rules_by_action_type": action_counts,
        "ocr_verify_chains": [
            {
                "ocr_source_type": chain.ocr_source_type,
                "verify_source_type": chain.verify_source_type,
                "upload_field": chain.upload_field_name,
                "text_field": chain.text_field_name,
                "ocr_rule_id": chain.ocr_rule_id,
                "verify_rule_id": chain.verify_rule_id
            }
            for chain in agent.ocr_verify_chains
        ]
    }

    if output_path:
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Rule Extraction Agent - Extract rules from BUD documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with BUD document
  python main.py --bud "documents/Vendor Creation Sample BUD.docx" --output schema.json

  # With intra-panel references and verbose output
  python main.py --bud document.docx --intra-panel refs.json --output schema.json --verbose

  # Generate summary report
  python main.py --bud document.docx --output schema.json --report summary.json
        """
    )

    parser.add_argument(
        '--bud',
        required=True,
        help='Path to BUD .docx document'
    )

    parser.add_argument(
        '--intra-panel',
        help='Path to intra-panel references JSON'
    )

    parser.add_argument(
        '--output',
        help='Path to save populated schema JSON'
    )

    parser.add_argument(
        '--schema-rules',
        help='Path to Rule-Schemas.json (default: rules/Rule-Schemas.json)'
    )

    parser.add_argument(
        '--report',
        help='Path to save summary report JSON'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate generated rules'
    )

    args = parser.parse_args()

    # Validate BUD path
    bud_path = Path(args.bud)
    if not bud_path.exists():
        print(f"Error: BUD file not found: {args.bud}")
        sys.exit(1)

    # Create output path if not specified
    output_path = args.output
    if not output_path:
        output_path = str(bud_path.parent / f"{bud_path.stem}_populated.json")

    print(f"Rule Extraction Agent")
    print(f"=" * 50)
    print(f"BUD Document: {args.bud}")
    print(f"Output Path: {output_path}")

    if args.intra_panel:
        print(f"Intra-Panel References: {args.intra_panel}")

    print()

    # Create and initialize agent
    agent = RuleExtractionAgent(verbose=args.verbose)

    if args.schema_rules:
        agent.initialize(args.schema_rules)
    else:
        agent.initialize()

    # Extract and generate
    print("Processing BUD document...")
    result = agent.extract_and_generate(
        args.bud,
        args.intra_panel,
        output_path
    )

    if not result:
        print("Error: Failed to generate rules")
        sys.exit(1)

    # Count results
    fields_count = len(agent.fields)
    rules_count = len(agent.all_rules)

    print()
    print(f"Results:")
    print(f"  Fields processed: {fields_count}")
    print(f"  Rules generated: {rules_count}")
    print(f"  OCR->VERIFY chains: {len(agent.ocr_verify_chains)}")

    # Generate summary report
    if args.report:
        report = generate_summary_report(agent, fields_count, rules_count, args.report)
        print(f"  Summary report saved to: {args.report}")

        # Print action type breakdown
        print()
        print("Rules by Action Type:")
        for action, count in sorted(report['rules_by_action_type'].items()):
            print(f"  {action}: {count}")

    # Validate if requested
    if args.validate:
        print()
        print("Validation:")
        validation_errors = validate_rules(agent.all_rules, agent.fields)
        if validation_errors:
            for error in validation_errors:
                print(f"  WARNING: {error}")
        else:
            print("  All rules validated successfully")

    print()
    print(f"Output saved to: {output_path}")
    print("Done!")


def validate_rules(rules: list, fields: list) -> list:
    """
    Validate generated rules.

    Args:
        rules: List of generated rules
        fields: List of fields

    Returns:
        List of validation error messages
    """
    errors = []
    field_ids = {f.get('id') for f in fields}

    for rule in rules:
        rule_id = rule.get('id')
        action_type = rule.get('actionType')

        # Check source IDs exist
        for source_id in rule.get('sourceIds', []):
            if source_id not in field_ids:
                errors.append(f"Rule {rule_id}: Unknown source field ID {source_id}")

        # Check destination IDs exist (except -1 for unmapped ordinals)
        for dest_id in rule.get('destinationIds', []):
            if dest_id != -1 and dest_id not in field_ids:
                errors.append(f"Rule {rule_id}: Unknown destination field ID {dest_id}")

        # Check OCR rules have postTriggerRuleIds when needed
        if action_type == 'OCR':
            source_type = rule.get('sourceType', '')
            if source_type in ['PAN_IMAGE', 'GSTIN_IMAGE', 'CHEQUEE', 'MSME']:
                if not rule.get('postTriggerRuleIds'):
                    errors.append(f"Rule {rule_id}: OCR rule missing postTriggerRuleIds for {source_type}")

    return errors


if __name__ == '__main__':
    main()
