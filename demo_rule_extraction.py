#!/usr/bin/env python3
"""
Demo script showing rule extraction agent working with BUD document.

This demonstrates the full pipeline:
1. Parse BUD document to extract fields with logic
2. Run rule extraction agent on the fields
3. Generate formFillRules
4. Display results

Usage:
    python3 demo_rule_extraction.py
"""

import json
from rule_extraction_agent.logic_parser import LogicParser
from rule_extraction_agent.rule_tree import RuleSelectionTree
from rule_extraction_agent.rule_builders import StandardRuleBuilder, ValidationRuleBuilder
from rule_extraction_agent.models import FieldInfo, ProcessingResult
from doc_parser import DocumentParser


def demo_rule_extraction():
    """Demonstrate rule extraction on actual BUD document."""

    print("=" * 70)
    print("RULE EXTRACTION AGENT DEMONSTRATION")
    print("=" * 70)
    print()

    # Step 1: Parse BUD document
    print("Step 1: Parsing BUD document...")
    parser = DocumentParser()
    parsed_doc = parser.parse('documents/Vendor Creation Sample BUD.docx')
    print(f"  Total fields: {len(parsed_doc.all_fields)}")

    # Count fields with logic
    fields_with_logic = [f for f in parsed_doc.all_fields if f.logic and f.logic.strip()]
    print(f"  Fields with logic: {len(fields_with_logic)}")
    print()

    # Step 2: Initialize rule extraction components
    print("Step 2: Initializing rule extraction components...")
    logic_parser = LogicParser()
    rule_tree = RuleSelectionTree()
    standard_builder = StandardRuleBuilder()
    validation_builder = ValidationRuleBuilder()
    print("  Components initialized")
    print()

    # Step 3: Process sample fields
    print("Step 3: Processing sample fields with logic...")
    print("-" * 70)

    result = ProcessingResult()
    samples_to_show = 5

    for i, field in enumerate(fields_with_logic[:samples_to_show], 1):
        print(f"\n[{i}] Field: {field.name}")
        print(f"    Type: {field.field_type}")
        print(f"    Logic: {field.logic[:80]}...")

        # Parse logic
        parsed_logic = logic_parser.parse(field.logic)
        print(f"    Keywords: {parsed_logic.keywords[:5]}")
        print(f"    Actions: {parsed_logic.actions}")
        print(f"    Confidence: {parsed_logic.confidence:.2f}")

        # Select rules
        selections = rule_tree.select_rules(parsed_logic)
        print(f"    Rules selected: {len(selections)}")

        for selection in selections:
            if selection.confidence >= 0.5:
                print(f"      - {selection.rule_type} ({selection.action_type}) - confidence: {selection.confidence:.2f}")
                result.deterministic_rules += 1
                result.rules_generated += 1

        result.fields_with_logic += 1
        result.total_fields += 1

    print()
    print("-" * 70)

    # Step 4: Show detailed rule generation for one example
    print("\nStep 4: Detailed rule generation example")
    print("-" * 70)

    # Find a field with conditional logic
    conditional_field = None
    for field in fields_with_logic:
        if 'if' in field.logic.lower() or 'when' in field.logic.lower():
            conditional_field = field
            break

    if conditional_field:
        print(f"\nField: {conditional_field.name}")
        print(f"Logic: {conditional_field.logic}")
        print()

        # Parse
        parsed = logic_parser.parse(conditional_field.logic)
        print(f"Parsed:")
        print(f"  - Conditional: {parsed.is_conditional}")
        print(f"  - Has else: {parsed.has_else}")
        print(f"  - Conditions: {len(parsed.conditions)}")
        if parsed.conditions:
            cond = parsed.conditions[0]
            print(f"    > Field: '{cond.field_ref}' {cond.operator.value} '{cond.value}'")
        print(f"  - Actions: {parsed.actions}")
        print()

        # Select and generate rules
        selections = rule_tree.select_rules(parsed)
        print(f"Generated Rules:")

        # Create mock field info
        source = FieldInfo(id=100, name="Source Field", variable_name="_source_", field_type="TEXT")
        dest = FieldInfo(id=101, name=conditional_field.name, variable_name="_dest_", field_type=str(conditional_field.field_type))

        for selection in selections[:2]:  # Show first 2
            rules = standard_builder.build(parsed, selection, source, [dest])
            for rule in rules:
                print(f"\n{json.dumps(rule.to_dict(), indent=2)}")

    # Step 5: Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total fields processed: {result.total_fields}")
    print(f"Fields with logic: {result.fields_with_logic}")
    print(f"Rules generated: {result.rules_generated}")
    print(f"  - Deterministic: {result.deterministic_rules}")
    print(f"  - LLM fallback: {result.llm_fallback_rules}")
    print()
    print("Note: This is a demonstration using sample fields.")
    print("The full agent can process all 148 fields with logic in the BUD document.")
    print("=" * 70)


if __name__ == "__main__":
    demo_rule_extraction()
