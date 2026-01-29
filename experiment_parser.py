"""
Comprehensive experiment to validate document parsing.
Tests if all fields, rules, workflows, and metadata are correctly extracted.
"""

import json
from pathlib import Path
from typing import Dict, Any
from doc_parser.parser import DocumentParser
from doc_parser.models import ParsedDocument


def analyze_extraction_completeness(parsed: ParsedDocument) -> Dict[str, Any]:
    """Analyze how complete the extraction is."""

    analysis = {
        "file_name": Path(parsed.file_path).name,
        "metadata": {
            "title": parsed.metadata.title,
            "author": parsed.metadata.author,
            "process_name": parsed.metadata.process_name,
            "created": parsed.metadata.created,
            "modified": parsed.metadata.modified,
        },
        "statistics": {
            "sections": len(parsed.sections),
            "all_fields": len(parsed.all_fields),
            "initiator_fields": len(parsed.initiator_fields),
            "spoc_fields": len(parsed.spoc_fields),
            "approver_fields": len(parsed.approver_fields),
            "workflows": {actor: len(steps) for actor, steps in parsed.workflows.items()},
            "approval_rules": len(parsed.approval_rules),
            "version_history": len(parsed.version_history),
            "terminology_entries": len(parsed.terminology),
            "reference_tables": len(parsed.reference_tables),
            "integration_fields": len(parsed.integration_fields),
            "document_requirements": len(parsed.document_requirements),
            "dropdown_mappings": len(parsed.dropdown_mappings),
            "raw_tables": len(parsed.raw_tables),
        },
        "completeness_checks": {},
        "field_types_distribution": {},
        "mandatory_field_counts": {"mandatory": 0, "optional": 0},
        "sample_fields": [],
        "sample_workflows": {},
        "issues": [],
    }

    # Field type distribution
    for field in parsed.all_fields:
        field_type_name = field.field_type.value
        if field_type_name not in analysis["field_types_distribution"]:
            analysis["field_types_distribution"][field_type_name] = 0
        analysis["field_types_distribution"][field_type_name] += 1

        # Count mandatory vs optional
        if field.is_mandatory:
            analysis["mandatory_field_counts"]["mandatory"] += 1
        else:
            analysis["mandatory_field_counts"]["optional"] += 1

    # Sample first 5 fields with details
    for field in parsed.all_fields[:5]:
        analysis["sample_fields"].append({
            "name": field.name,
            "type": field.field_type.value,
            "type_raw": field.field_type_raw,
            "mandatory": field.is_mandatory,
            "logic": field.logic[:100] if field.logic else "",
            "rules": field.rules[:100] if field.rules else "",
            "section": field.section,
            "dropdown_values": field.dropdown_values[:5] if field.dropdown_values else [],
            "visibility_condition": field.visibility_condition,
        })

    # Sample workflow steps
    for actor, steps in list(parsed.workflows.items())[:3]:
        analysis["sample_workflows"][actor] = [
            {
                "step": step.step_number,
                "description": step.description[:100],
                "action_type": step.action_type,
            }
            for step in steps[:3]
        ]

    # Completeness checks
    analysis["completeness_checks"]["has_metadata"] = bool(parsed.metadata.title or parsed.metadata.process_name)
    analysis["completeness_checks"]["has_fields"] = len(parsed.all_fields) > 0
    analysis["completeness_checks"]["has_workflows"] = len(parsed.workflows) > 0
    analysis["completeness_checks"]["has_version_history"] = len(parsed.version_history) > 0
    analysis["completeness_checks"]["has_categorized_fields"] = (
        len(parsed.initiator_fields) > 0 or
        len(parsed.spoc_fields) > 0 or
        len(parsed.approver_fields) > 0
    )

    # Check for potential issues
    if len(parsed.all_fields) == 0:
        analysis["issues"].append("No fields extracted - possible parsing issue")

    if len(parsed.raw_tables) > 0 and len(parsed.all_fields) == 0:
        analysis["issues"].append(f"Found {len(parsed.raw_tables)} tables but no fields extracted")

    # Check for fields without proper categorization
    categorized_count = len(parsed.initiator_fields) + len(parsed.spoc_fields) + len(parsed.approver_fields)
    if categorized_count < len(parsed.all_fields):
        analysis["issues"].append(
            f"Some fields not categorized: {len(parsed.all_fields)} total, {categorized_count} categorized"
        )

    # Check for unknown field types
    unknown_fields = [f for f in parsed.all_fields if f.field_type.value == "UNKNOWN"]
    if unknown_fields:
        unknown_types = set(f.field_type_raw for f in unknown_fields)
        analysis["issues"].append(
            f"Found {len(unknown_fields)} fields with UNKNOWN type. Raw types: {unknown_types}"
        )

    return analysis


def detailed_field_report(parsed: ParsedDocument) -> str:
    """Generate detailed report of all fields."""
    lines = []
    lines.append("\n" + "="*100)
    lines.append("DETAILED FIELD REPORT")
    lines.append("="*100)

    # Group fields by category
    categories = [
        ("ALL FIELDS", parsed.all_fields),
        ("INITIATOR FIELDS", parsed.initiator_fields),
        ("SPOC/VENDOR FIELDS", parsed.spoc_fields),
        ("APPROVER FIELDS", parsed.approver_fields),
    ]

    for category_name, fields in categories:
        if not fields:
            continue

        lines.append(f"\n{category_name} ({len(fields)} fields)")
        lines.append("-" * 100)

        for field in fields:
            lines.append(f"\nField: {field.name}")
            lines.append(f"  Type: {field.field_type.value} (raw: {field.field_type_raw})")
            lines.append(f"  Mandatory: {field.is_mandatory}")
            if field.section:
                lines.append(f"  Section: {field.section}")
            if field.logic:
                lines.append(f"  Logic: {field.logic[:150]}")
            if field.rules:
                lines.append(f"  Rules: {field.rules[:150]}")
            if field.visibility_condition:
                lines.append(f"  Visibility: {field.visibility_condition}")
            if field.dropdown_values:
                lines.append(f"  Dropdown Values: {field.dropdown_values[:10]}")

    return "\n".join(lines)


def detailed_workflow_report(parsed: ParsedDocument) -> str:
    """Generate detailed report of all workflows."""
    lines = []
    lines.append("\n" + "="*100)
    lines.append("DETAILED WORKFLOW REPORT")
    lines.append("="*100)

    for actor, steps in parsed.workflows.items():
        lines.append(f"\n{actor.upper()} WORKFLOW ({len(steps)} steps)")
        lines.append("-" * 100)

        for step in steps:
            lines.append(f"\nStep {step.step_number}: {step.description}")
            if step.action_type:
                lines.append(f"  Action Type: {step.action_type}")
            if step.conditions:
                lines.append(f"  Conditions: {step.conditions}")
            if step.notes:
                lines.append(f"  Notes: {step.notes}")

    return "\n".join(lines)


def detailed_table_report(parsed: ParsedDocument) -> str:
    """Generate detailed report of all raw tables."""
    lines = []
    lines.append("\n" + "="*100)
    lines.append("DETAILED RAW TABLES REPORT")
    lines.append("="*100)

    for i, table in enumerate(parsed.raw_tables):
        lines.append(f"\nTable {i+1}: {table.table_type}")
        lines.append(f"Context: {table.context}")
        lines.append(f"Size: {table.row_count} rows x {table.column_count} columns")
        lines.append(f"Headers: {table.headers}")
        lines.append("Sample rows:")
        for j, row in enumerate(table.rows[:3]):
            lines.append(f"  Row {j+1}: {row}")
        if table.row_count > 3:
            lines.append(f"  ... and {table.row_count - 3} more rows")
        lines.append("-" * 100)

    return "\n".join(lines)


def experiment_on_document(doc_path: Path, parser: DocumentParser) -> Dict[str, Any]:
    """Run complete experiment on a single document."""
    print(f"\n{'='*100}")
    print(f"PROCESSING: {doc_path.name}")
    print('='*100)

    try:
        # Parse the document
        parsed = parser.parse(str(doc_path))

        # Analyze completeness
        analysis = analyze_extraction_completeness(parsed)

        # Generate detailed reports
        field_report = detailed_field_report(parsed)
        workflow_report = detailed_workflow_report(parsed)
        table_report = detailed_table_report(parsed)

        # Print summary
        print(f"\nMETADATA:")
        print(f"  Title: {parsed.metadata.title}")
        print(f"  Author: {parsed.metadata.author}")
        print(f"  Process: {parsed.metadata.process_name}")

        print(f"\nSTATISTICS:")
        for key, value in analysis["statistics"].items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    - {k}: {v}")
            else:
                print(f"  {key}: {value}")

        print(f"\nFIELD TYPE DISTRIBUTION:")
        for field_type, count in sorted(analysis["field_types_distribution"].items()):
            print(f"  {field_type}: {count}")

        print(f"\nMANDATORY FIELDS:")
        print(f"  Mandatory: {analysis['mandatory_field_counts']['mandatory']}")
        print(f"  Optional: {analysis['mandatory_field_counts']['optional']}")

        print(f"\nCOMPLETENESS CHECKS:")
        for check, passed in analysis["completeness_checks"].items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}")

        if analysis["issues"]:
            print(f"\nISSUES FOUND:")
            for issue in analysis["issues"]:
                print(f"  ⚠ {issue}")
        else:
            print(f"\n✓ No issues found!")

        # Save detailed reports
        output_dir = Path("experiment_results")
        output_dir.mkdir(exist_ok=True)

        base_name = doc_path.stem

        # Save JSON analysis
        with open(output_dir / f"{base_name}_analysis.json", "w") as f:
            json.dump(analysis, f, indent=2)

        # Save field report
        with open(output_dir / f"{base_name}_fields.txt", "w") as f:
            f.write(field_report)

        # Save workflow report
        with open(output_dir / f"{base_name}_workflows.txt", "w") as f:
            f.write(workflow_report)

        # Save table report
        with open(output_dir / f"{base_name}_tables.txt", "w") as f:
            f.write(table_report)

        # Save full parsed document as JSON
        with open(output_dir / f"{base_name}_full.json", "w") as f:
            json.dump(parsed.to_dict(), f, indent=2)

        print(f"\nReports saved to experiment_results/{base_name}_*")

        return {
            "success": True,
            "analysis": analysis,
            "parsed": parsed,
        }

    except Exception as e:
        print(f"\n✗ ERROR processing {doc_path.name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }


def main():
    """Run experiments on all documents."""
    print("\n" + "="*100)
    print("DOCUMENT PARSER EXPERIMENT")
    print("Validating extraction of fields, rules, workflows, and metadata")
    print("="*100)

    docs_dir = Path("documents")
    parser = DocumentParser()

    results = []

    # Process each document
    for doc_path in sorted(docs_dir.glob("*.docx")):
        result = experiment_on_document(doc_path, parser)
        results.append({
            "file": doc_path.name,
            "success": result["success"],
            "statistics": result.get("analysis", {}).get("statistics", {}) if result["success"] else {},
        })

    # Overall summary
    print(f"\n{'='*100}")
    print("EXPERIMENT SUMMARY")
    print('='*100)

    successful = sum(1 for r in results if r["success"])
    print(f"\nProcessed: {len(results)} documents")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")

    print(f"\nDOCUMENT COMPARISON:")
    print("-" * 100)
    print(f"{'Document':<40} {'Fields':<10} {'Workflows':<15} {'Tables':<10}")
    print("-" * 100)

    for result in results:
        if result["success"]:
            stats = result["statistics"]
            doc_name = result["file"][:38]
            fields = stats.get("all_fields", 0)
            workflows = sum(stats.get("workflows", {}).values())
            tables = stats.get("raw_tables", 0)
            print(f"{doc_name:<40} {fields:<10} {workflows:<15} {tables:<10}")

    print("\n" + "="*100)
    print("All reports saved in experiment_results/ directory")
    print("="*100)


if __name__ == "__main__":
    main()
