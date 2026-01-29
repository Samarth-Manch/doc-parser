#!/usr/bin/env python3
"""
Demo script for rules extraction - processes a document and shows extracted rules.
"""

import sys
import json
from pathlib import Path

# Add virtual env activation hint
venv_python = Path("venv/bin/python")
if venv_python.exists() and sys.executable != str(venv_python.absolute()):
    print("⚠️  Please run this script using the virtual environment:")
    print(f"    source venv/bin/activate && python {__file__}")
    print("\nOr directly:")
    print(f"    venv/bin/python {__file__}")
    sys.exit(1)

from rules_extractor import RulesExtractor, FieldWithRules
from doc_parser.parser import DocumentParser


def print_field_with_rules(field_with_rules: FieldWithRules, index: int):
    """Pretty print a field with its extracted rules."""
    print(f"\n{'='*80}")
    print(f"[{index}] {field_with_rules.field_name}")
    print(f"{'='*80}")
    print(f"Type: {field_with_rules.field_type}")
    print(f"Mandatory: {'Yes' if field_with_rules.is_mandatory else 'No'}")

    if field_with_rules.source_info:
        print(f"Source: {field_with_rules.source_info}")

    if field_with_rules.original_logic:
        print(f"\nOriginal Logic:")
        print(f"  {field_with_rules.original_logic[:200]}")
        if len(field_with_rules.original_logic) > 200:
            print(f"  ... ({len(field_with_rules.original_logic) - 200} more characters)")

    if field_with_rules.extracted_rules:
        print(f"\n✓ Extracted {len(field_with_rules.extracted_rules)} Rule(s):")
        for i, rule in enumerate(field_with_rules.extracted_rules, 1):
            print(f"\n  Rule {i}: {rule.rule_name}")
            print(f"    Action: {rule.action}")
            print(f"    Type: {rule.rule_type}")
            print(f"    Processing: {rule.processing_type}")
            print(f"    Confidence: {rule.confidence:.0%}")

            if rule.source:
                print(f"    Source: {rule.source}")

            if rule.destination_fields:
                print(f"    Destinations: {', '.join(rule.destination_fields[:3])}")
                if len(rule.destination_fields) > 3:
                    print(f"                  (and {len(rule.destination_fields) - 3} more)")

            if rule.conditions:
                print(f"    Conditions: {rule.conditions}")

            if rule.expression:
                expr_preview = rule.expression[:100]
                print(f"    Expression: {expr_preview}")
                if len(rule.expression) > 100:
                    print(f"                ... ({len(rule.expression) - 100} more chars)")

        # Show flags
        flags = []
        if field_with_rules.has_validation:
            flags.append("Validation")
        if field_with_rules.has_visibility_rules:
            flags.append("Visibility")
        if field_with_rules.has_mandatory_rules:
            flags.append("Mandatory")

        if flags:
            print(f"\n  Rule Types: {', '.join(flags)}")
    else:
        print(f"\n⚠️  No rules extracted")


def main():
    print("Document Parser - Rules Extraction Demo")
    print("=" * 80)

    # Check if document exists
    doc_path = "documents/Vendor Creation Sample BUD(1).docx"
    if not Path(doc_path).exists():
        print(f"\n❌ Document not found: {doc_path}")
        print("\nAvailable documents:")
        for doc in Path("documents").glob("*.docx"):
            print(f"  - {doc.name}")
        return

    # Parse document
    print(f"\n1️⃣  Parsing document: {doc_path}")
    parser = DocumentParser()
    parsed_doc = parser.parse(doc_path)
    print(f"   ✓ Found {len(parsed_doc.all_fields)} fields")

    # Ask how many fields to process
    print(f"\n2️⃣  Rules Extraction")
    print(f"   Total fields available: {len(parsed_doc.all_fields)}")
    print(f"   Processing all fields may take several minutes and API calls.")

    try:
        num_fields = input("\n   How many fields to process? (default: 10): ").strip()
        num_fields = int(num_fields) if num_fields else 10
        num_fields = min(num_fields, len(parsed_doc.all_fields))
    except (ValueError, KeyboardInterrupt):
        print("\n   Using default: 10 fields")
        num_fields = 10

    # Initialize extractor
    print(f"\n3️⃣  Initializing Rules Extractor...")
    try:
        extractor = RulesExtractor()
        print(f"   ✓ Loaded {len(extractor.knowledge_base.rules)} rule schemas")
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Make sure OPENAI_API_KEY is set in .env file")
        return

    # Process fields
    print(f"\n4️⃣  Extracting rules from {num_fields} fields...")
    print(f"   (This may take a minute...)\n")

    fields_with_rules = []
    fields_to_process = parsed_doc.all_fields[:num_fields]

    for i, field in enumerate(fields_to_process, 1):
        print(f"   [{i}/{num_fields}] Processing: {field.name}", end="")

        extracted_rules = extractor.extract_rules_with_llm(field)
        src_dest_info = extractor.extract_source_destination_info(field.logic)

        has_validation = any(r.action in ['VALIDATION', 'OCR', 'COMPARE'] for r in extracted_rules)
        has_visibility = any('visible' in r.rule_name.lower() or 'visible' in str(r.expression).lower()
                           for r in extracted_rules)
        has_mandatory = any('mandatory' in r.rule_name.lower() or 'mandatory' in str(r.expression).lower()
                          for r in extracted_rules)

        field_with_rules = FieldWithRules(
            field_name=field.name,
            field_type=field.field_type.name,
            is_mandatory=field.is_mandatory,
            original_logic=field.logic,
            extracted_rules=extracted_rules,
            source_info=src_dest_info.get('source'),
            has_validation=has_validation,
            has_visibility_rules=has_visibility,
            has_mandatory_rules=has_mandatory
        )

        fields_with_rules.append(field_with_rules)
        print(f" → {len(extracted_rules)} rule(s) ✓")

    # Summary statistics
    total_rules = sum(len(f.extracted_rules) for f in fields_with_rules)
    fields_with_any_rules = sum(1 for f in fields_with_rules if f.extracted_rules)
    avg_confidence = sum(
        rule.confidence
        for f in fields_with_rules
        for rule in f.extracted_rules
    ) / total_rules if total_rules > 0 else 0

    print(f"\n{'='*80}")
    print(f"📊 SUMMARY")
    print(f"{'='*80}")
    print(f"Total fields processed:      {len(fields_with_rules)}")
    print(f"Fields with rules:           {fields_with_any_rules}")
    print(f"Total rules extracted:       {total_rules}")
    print(f"Average confidence:          {avg_confidence:.0%}")

    # Count by rule type
    expression_rules = sum(1 for f in fields_with_rules for r in f.extracted_rules if r.rule_type == 'EXPRESSION')
    standard_rules = sum(1 for f in fields_with_rules for r in f.extracted_rules if r.rule_type == 'STANDARD')

    print(f"\nRule Types:")
    print(f"  Expression rules:          {expression_rules}")
    print(f"  Standard rules:            {standard_rules}")

    print(f"\nField Categories:")
    print(f"  With validation:           {sum(1 for f in fields_with_rules if f.has_validation)}")
    print(f"  With visibility rules:     {sum(1 for f in fields_with_rules if f.has_visibility_rules)}")
    print(f"  With mandatory rules:      {sum(1 for f in fields_with_rules if f.has_mandatory_rules)}")

    # Export to JSON
    output_file = "extracted_rules.json"
    print(f"\n5️⃣  Exporting to JSON: {output_file}")
    extractor.export_to_json(fields_with_rules, output_file)
    print(f"   ✓ Exported successfully")

    # Show details
    print(f"\n{'='*80}")
    show_details = input("\nShow detailed rules for each field? (y/n, default: n): ").strip().lower()

    if show_details == 'y':
        for i, field_with_rules in enumerate(fields_with_rules, 1):
            print_field_with_rules(field_with_rules, i)

    print(f"\n{'='*80}")
    print(f"✅ Done! Check {output_file} for full JSON output.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
