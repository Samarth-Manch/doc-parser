#!/usr/bin/env python3
"""
Run enhanced rule extraction v3 for Vendor Creation Sample BUD.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rule_extraction_agent.enhanced_main_v3 import EnhancedRuleExtractionAgentV3


def main():
    # Input paths
    schema_path = "/home/samart/project/doc-parser/output/complete_format/6421-schema.json"
    intra_panel_path = "/home/samart/project/doc-parser/adws/2026-01-31_17-32-48/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"

    # Output paths
    output_dir = Path("/home/samart/project/doc-parser/adws/2026-01-31_17-32-48")
    output_schema = output_dir / "populated_schema_v3.json"
    output_report = output_dir / "extraction_report_v3.json"

    print("=" * 60)
    print("Enhanced Rule Extraction Agent v3")
    print("=" * 60)
    print(f"Schema: {schema_path}")
    print(f"Intra-panel: {intra_panel_path}")
    print(f"Output: {output_schema}")
    print("=" * 60)

    # Run extraction
    agent = EnhancedRuleExtractionAgentV3(
        schema_path=schema_path,
        intra_panel_path=intra_panel_path,
        verbose=True
    )

    populated = agent.save_output(str(output_schema), str(output_report))

    # Print summary
    print("\n" + "=" * 60)
    print("Extraction Summary")
    print("=" * 60)

    rules_by_type = {}
    for rule in agent.all_rules:
        action = rule.action_type
        if action not in rules_by_type:
            rules_by_type[action] = 0
        rules_by_type[action] += 1

    print(f"Total fields: {len(agent.fields)}")
    print(f"Total rules: {len(agent.all_rules)}")
    print(f"Fields with rules: {len(agent.rules_by_field)}")
    print("\nRules by type:")
    for action, count in sorted(rules_by_type.items()):
        print(f"  {action}: {count}")

    # Check OCR chains
    print("\nOCR -> VERIFY chains:")
    for source, rule in agent.ocr_rules.items():
        post_trigger = rule.post_trigger_rule_ids
        print(f"  {source}: rule_id={rule.id}, post_trigger={post_trigger}")

    # Check VERIFY ordinal mappings
    print("\nVERIFY ordinal mappings:")
    for source, rule in agent.verify_rules.items():
        dest_count = sum(1 for d in rule.destination_ids if d != -1)
        total = len(rule.destination_ids)
        print(f"  {source}: {dest_count}/{total} ordinals mapped")

    print("\n" + "=" * 60)
    print(f"Output saved to: {output_schema}")
    print(f"Report saved to: {output_report}")
    print("=" * 60)


if __name__ == '__main__':
    main()
