#!/usr/bin/env python3
"""
EDV (External Data Value) Table Mapping Dispatcher

This script:
1. Parses a BUD document using DocumentParser
2. Extracts reference tables and their structure
3. Identifies fields that reference EDV tables (from logic text)
4. Generates EDV table names based on content
5. Detects parent-child dropdown relationships
6. Outputs EDV tables registry and field-EDV mapping JSONs
"""

import argparse
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from doc_parser import DocumentParser


def sanitize_name(name: str) -> str:
    """
    Sanitize name for use in filenames.

    Args:
        name: Original name

    Returns:
        Sanitized string safe for filenames
    """
    sanitized = name.replace(" ", "_")
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)
    return sanitized


def generate_edv_table_name(table_id: str, headers: list, content_sample: list = None) -> str:
    """
    Generate EDV table name from table reference ID and headers.

    Args:
        table_id: Reference table ID (e.g., "1.3", "2.1")
        headers: List of column headers
        content_sample: Sample data from first few rows

    Returns:
        EDV table name in UPPER_CASE_WITH_UNDERSCORES format
    """
    # Common mappings based on headers
    header_mappings = {
        ("vendor", "type"): "VC_VENDOR_TYPES",
        ("vendor", "group"): "VC_VENDOR_TYPES",
        ("account", "group"): "VC_VENDOR_TYPES",
        ("company", "code"): "COMPANY_CODE_PURCHASE_ORGANIZATION",
        ("purchase", "organization"): "COMPANY_CODE_PURCHASE_ORGANIZATION",
        ("country",): "COUNTRY",
        ("state",): "STATE",
        ("city",): "CITY",
        ("bank",): "BANK_OPTIONS",
        ("ifsc",): "BANK_IFSC",
        ("currency",): "CURRENCY_COUNTRY",
        ("title", "salutation"): "TITLE",
        ("tax", "withholding"): "WITHHOLDING_TAX_DATA",
        ("yes", "no"): "YES_NO",
        ("incoterm",): "INCOTERMS",
        ("payment", "term"): "PAYMENT_TERMS",
    }

    # Normalize headers for matching
    headers_lower = [h.lower() if h else "" for h in headers]
    headers_text = " ".join(headers_lower)

    # Try to match against known patterns
    for keywords, edv_name in header_mappings.items():
        if all(kw in headers_text for kw in keywords):
            return edv_name

    # Generate name from headers if no match
    if headers:
        # Use first 2-3 meaningful headers
        meaningful = [h for h in headers if h and len(h) > 2][:3]
        if meaningful:
            name = "_".join(meaningful)
            name = re.sub(r'[^a-zA-Z0-9]+', '_', name)
            return name.upper()

    # Fallback to table ID
    return f"TABLE_{table_id.replace('.', '_')}"


def extract_reference_tables(parsed_document) -> list:
    """
    Extract reference tables from parsed document.

    Args:
        parsed_document: ParsedDocument from DocumentParser

    Returns:
        List of reference table dictionaries
    """
    reference_tables = []

    # Get tables from parsed document
    if hasattr(parsed_document, 'reference_tables'):
        for i, table in enumerate(parsed_document.reference_tables):
            table_data = {
                "index": i + 1,
                "reference_id": f"1.{i + 1}",  # Default numbering
                "headers": [],
                "rows": [],
                "row_count": 0
            }

            if hasattr(table, 'headers'):
                table_data["headers"] = table.headers
            if hasattr(table, 'rows'):
                table_data["rows"] = table.rows[:5]  # Sample first 5 rows
                table_data["row_count"] = len(table.rows)
            if hasattr(table, 'title'):
                table_data["title"] = table.title
                # Try to extract reference ID from title
                match = re.search(r'(?:reference\s+)?table\s+(\d+\.?\d*)', table.title, re.I)
                if match:
                    table_data["reference_id"] = match.group(1)

            reference_tables.append(table_data)

    return reference_tables


def detect_table_references_in_logic(logic: str) -> list:
    """
    Detect reference table mentions in field logic.

    Args:
        logic: Field logic text

    Returns:
        List of table reference IDs found (e.g., ["1.3", "2.1"])
    """
    if not logic:
        return []

    references = []

    # Pattern: "reference table X.Y" or "table X.Y"
    patterns = [
        r'reference\s+table\s+(\d+\.?\d*)',
        r'table\s+(\d+\.?\d*)',
        r'ref\.?\s*table\s+(\d+\.?\d*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, logic, re.I)
        references.extend(matches)

    return list(set(references))


def detect_column_references(logic: str) -> dict:
    """
    Detect column references in logic text.

    Args:
        logic: Field logic text

    Returns:
        Dict with 'columns' list and 'display_column' if detected
    """
    result = {"columns": [], "display_column": None}

    if not logic:
        return result

    # Patterns for column references
    ordinal_map = {
        "first": 1, "1st": 1,
        "second": 2, "2nd": 2,
        "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5,
        "sixth": 6, "6th": 6,
        "seventh": 7, "7th": 7,
    }

    logic_lower = logic.lower()

    # "first and second columns"
    match = re.search(r'(first|second|third|fourth|fifth)\s+(?:and\s+)?(first|second|third|fourth|fifth)?\s*columns?', logic_lower)
    if match:
        for g in match.groups():
            if g and g in ordinal_map:
                result["columns"].append(ordinal_map[g])

    # "column N"
    for match in re.finditer(r'column\s+(\d+)', logic_lower):
        result["columns"].append(int(match.group(1)))

    # "Nth column"
    for ordinal, num in ordinal_map.items():
        if f"{ordinal} column" in logic_lower:
            if num not in result["columns"]:
                result["columns"].append(num)

    # "as Nth column" - indicates display column
    match = re.search(r'as\s+(\d+)(?:st|nd|rd|th)?\s+column', logic_lower)
    if match:
        result["display_column"] = int(match.group(1))

    for ordinal, num in ordinal_map.items():
        if f"as {ordinal} column" in logic_lower:
            result["display_column"] = num
            break

    return result


def detect_parent_child_relationship(logic: str, field_name: str, all_fields: list) -> dict:
    """
    Detect if field has parent-child dropdown relationship.

    Args:
        logic: Field logic text
        field_name: Current field name
        all_fields: All fields in document

    Returns:
        Dict with parent info if found, else None
    """
    if not logic:
        return None

    logic_lower = logic.lower()

    # Patterns indicating parent-child relationship
    patterns = [
        r'based\s+on\s+(?:the\s+)?["\']?([^"\']+?)["\']?\s+selection',
        r'based\s+on\s+(?:the\s+)?["\']?([^"\']+?)["\']?\s+field',
        r'parent\s+dropdown\s+field\s*:\s*["\']?([^"\']+)["\']?',
        r'dependent\s+on\s+(?:field\s+)?["\']?([^"\']+)["\']?',
        r'filtered\s+by\s+["\']?([^"\']+)["\']?',
        r'cascading\s+(?:dropdown\s+)?(?:from|based\s+on)\s+["\']?([^"\']+)["\']?',
    ]

    for pattern in patterns:
        match = re.search(pattern, logic, re.I)
        if match:
            parent_name = match.group(1).strip()
            # Verify parent exists in fields
            for f in all_fields:
                if f.name.lower() == parent_name.lower() or parent_name.lower() in f.name.lower():
                    return {
                        "parent_field": f.name,
                        "parent_variable": f.variable_name,
                        "relationship_type": "cascading_dropdown"
                    }

    return None


def build_edv_tables_registry(reference_tables: list, fields_with_refs: list) -> dict:
    """
    Build EDV tables registry from reference tables.

    Args:
        reference_tables: List of extracted reference tables
        fields_with_refs: Fields that reference tables

    Returns:
        EDV tables registry dictionary
    """
    edv_tables = []
    table_name_mapping = {}

    for table in reference_tables:
        ref_id = table.get("reference_id", f"unknown_{table.get('index', 0)}")
        headers = table.get("headers", [])

        # Generate EDV name
        edv_name = generate_edv_table_name(ref_id, headers, table.get("rows"))

        # Build column info
        columns = []
        for i, header in enumerate(headers):
            columns.append({
                "index": i + 1,
                "attribute": f"a{i + 1}",
                "header": header or f"Column {i + 1}"
            })

        # Find fields using this table
        used_by = []
        for field_info in fields_with_refs:
            if ref_id in field_info.get("table_refs", []):
                used_by.append(field_info["field_name"])

        edv_table = {
            "reference_id": ref_id,
            "edv_name": edv_name,
            "original_title": table.get("title", f"Reference Table {ref_id}"),
            "columns": columns,
            "row_count": table.get("row_count", 0),
            "sample_data": [],
            "used_by_fields": used_by
        }

        # Add sample data if available
        if table.get("rows"):
            for row in table["rows"][:3]:
                if isinstance(row, list):
                    sample = {f"a{i+1}": val for i, val in enumerate(row)}
                    edv_table["sample_data"].append(sample)

        edv_tables.append(edv_table)
        table_name_mapping[ref_id] = edv_name

    return {
        "edv_tables": edv_tables,
        "table_name_mapping": table_name_mapping
    }


def build_field_edv_mapping(all_fields: list, table_name_mapping: dict) -> list:
    """
    Build field-to-EDV mapping for all fields with table references.

    Args:
        all_fields: All fields from document
        table_name_mapping: Reference ID to EDV name mapping

    Returns:
        List of field EDV mapping dictionaries
    """
    mappings = []
    parent_child_pairs = []

    for field in all_fields:
        logic = field.logic or ""

        # Detect table references
        table_refs = detect_table_references_in_logic(logic)
        if not table_refs:
            continue

        # Get first referenced table
        primary_table = table_refs[0]
        edv_name = table_name_mapping.get(primary_table, f"TABLE_{primary_table.replace('.', '_')}")

        # Detect column references
        col_refs = detect_column_references(logic)

        # Detect parent-child relationship
        parent_info = detect_parent_child_relationship(logic, field.name, all_fields)

        # Determine rule type
        is_child = parent_info is not None
        field_type = field.field_type.value if hasattr(field.field_type, 'value') else str(field.field_type)

        if is_child:
            rule_type = "EXT_VALUE"
        elif field_type in ["DROPDOWN", "MULTI_DROPDOWN", "EXTERNAL_DROPDOWN"]:
            rule_type = "EXT_DROP_DOWN"
        else:
            rule_type = "EXT_VALUE"

        # Build params template
        if rule_type == "EXT_DROP_DOWN" and not is_child:
            # Simple dropdown - string params
            params_template = edv_name
            is_simple = True
        else:
            # Complex EXT_VALUE with conditionList
            display_col = f"a{col_refs['display_column']}" if col_refs.get('display_column') else "a1"

            if is_child:
                filter_col = f"a{col_refs['columns'][0]}" if col_refs.get('columns') else "a1"
                params_template = {
                    "conditionList": [{
                        "ddType": [edv_name],
                        "criterias": [{filter_col: "{{parent_field_id}}"}],
                        "da": [display_col],
                        "criteriaSearchAttr": [],
                        "additionalOptions": None,
                        "emptyAddOptionCheck": None,
                        "ddProperties": None
                    }]
                }
            else:
                params_template = {
                    "conditionList": [{
                        "ddType": [edv_name],
                        "da": [display_col],
                        "criteriaSearchAttr": [],
                        "additionalOptions": None,
                        "emptyAddOptionCheck": None,
                        "ddProperties": None
                    }]
                }
            is_simple = False

        mapping = {
            "field_name": field.name,
            "field_id": None,  # Will be filled when matched with schema
            "panel_name": field.section or "Unknown",
            "field_type": field_type,
            "edv_config": {
                "rule_type": rule_type,
                "edv_table": edv_name,
                "params_template": params_template,
                "is_simple": is_simple
            },
            "relationship": {
                "is_parent": False,  # Will be updated below
                "is_child": is_child,
                "children": [],
                "parent": parent_info["parent_field"] if parent_info else None
            },
            "table_refs": table_refs,
            "column_refs": col_refs,
            "logic_excerpt": logic[:200] if logic else ""
        }

        if parent_info:
            parent_child_pairs.append({
                "parent": parent_info["parent_field"],
                "child": field.name,
                "edv_table": edv_name
            })

        mappings.append(mapping)

    # Update parent flags and children lists
    for pair in parent_child_pairs:
        for m in mappings:
            if m["field_name"] == pair["parent"]:
                m["relationship"]["is_parent"] = True
                if pair["child"] not in m["relationship"]["children"]:
                    m["relationship"]["children"].append(pair["child"])

    return mappings


def build_parent_child_chains(field_mappings: list) -> list:
    """
    Build parent-child dropdown chains from field mappings.

    Args:
        field_mappings: List of field EDV mappings

    Returns:
        List of chain dictionaries
    """
    chains = []
    chain_id = 1

    # Find parent fields
    parents = [m for m in field_mappings if m["relationship"]["is_parent"]]

    for parent in parents:
        chain = {
            "chain_id": chain_id,
            "edv_table": parent["edv_config"]["edv_table"],
            "chain": [
                {
                    "field": parent["field_name"],
                    "role": "parent",
                    "column": "a1"
                }
            ]
        }

        # Add children
        for child_name in parent["relationship"]["children"]:
            for m in field_mappings:
                if m["field_name"] == child_name:
                    col_refs = m.get("column_refs", {})
                    filter_col = f"a{col_refs.get('columns', [1])[0]}" if col_refs.get('columns') else "a1"
                    display_col = f"a{col_refs.get('display_column', 2)}" if col_refs.get('display_column') else "a2"

                    chain["chain"].append({
                        "field": child_name,
                        "role": "child",
                        "filter_by": filter_col,
                        "display": display_col
                    })
                    break

        if len(chain["chain"]) > 1:
            chains.append(chain)
            chain_id += 1

    return chains


def main():
    parser = argparse.ArgumentParser(
        description="Extract EDV (External Data Value) table mappings from a BUD document"
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: extraction/edv_mapping_output/<timestamp>/)"
    )
    parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Only extract and output reference tables (skip field mapping)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Validate document path
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    # Set up output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"extraction/edv_mapping_output/{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    # Parse document
    print(f"Parsing document: {args.document_path}")
    try:
        doc_parser = DocumentParser()
        parsed = doc_parser.parse(args.document_path)
    except Exception as e:
        print(f"Error parsing document: {e}", file=sys.stderr)
        sys.exit(1)

    doc_name = sanitize_name(Path(args.document_path).stem)

    # Extract reference tables
    print("Extracting reference tables...")
    reference_tables = extract_reference_tables(parsed)
    print(f"  Found {len(reference_tables)} reference tables")

    if args.verbose and reference_tables:
        for table in reference_tables:
            print(f"    - Table {table.get('reference_id')}: {len(table.get('headers', []))} columns, {table.get('row_count', 0)} rows")

    # Extract fields with table references
    print("Analyzing fields for table references...")
    fields_with_refs = []
    all_fields = list(parsed.all_fields)

    for field in all_fields:
        logic = field.logic or ""
        table_refs = detect_table_references_in_logic(logic)
        if table_refs:
            fields_with_refs.append({
                "field_name": field.name,
                "table_refs": table_refs,
                "logic": logic
            })

    print(f"  Found {len(fields_with_refs)} fields with table references")

    if args.verbose and fields_with_refs:
        for f in fields_with_refs[:10]:
            print(f"    - {f['field_name']}: refs {f['table_refs']}")

    # Build EDV tables registry
    print("Building EDV tables registry...")
    edv_registry = build_edv_tables_registry(reference_tables, fields_with_refs)

    # Add document info
    edv_tables_output = {
        "document_info": {
            "file_name": Path(args.document_path).name,
            "extraction_timestamp": datetime.now().isoformat()
        },
        "edv_tables": edv_registry["edv_tables"],
        "table_name_mapping": edv_registry["table_name_mapping"],
        "summary": {
            "total_reference_tables": len(reference_tables),
            "total_edv_tables_generated": len(edv_registry["edv_tables"])
        }
    }

    # Save EDV tables JSON
    edv_tables_path = os.path.join(output_dir, f"{doc_name}_edv_tables.json")
    with open(edv_tables_path, 'w') as f:
        json.dump(edv_tables_output, f, indent=2)
    print(f"  Saved: {edv_tables_path}")

    if args.tables_only:
        print("\n" + "="*60)
        print("EDV TABLE EXTRACTION COMPLETE (tables only)")
        print("="*60)
        sys.exit(0)

    # Build field-EDV mapping
    print("Building field-EDV mappings...")
    field_mappings = build_field_edv_mapping(all_fields, edv_registry["table_name_mapping"])

    # Build parent-child chains
    parent_child_chains = build_parent_child_chains(field_mappings)

    # Count stats
    parent_count = len([m for m in field_mappings if m["relationship"]["is_parent"]])
    child_count = len([m for m in field_mappings if m["relationship"]["is_child"]])
    ext_dropdown_count = len([m for m in field_mappings if m["edv_config"]["rule_type"] == "EXT_DROP_DOWN"])
    ext_value_count = len([m for m in field_mappings if m["edv_config"]["rule_type"] == "EXT_VALUE"])

    # Build output
    field_mapping_output = {
        "document_info": {
            "file_name": Path(args.document_path).name,
            "extraction_timestamp": datetime.now().isoformat()
        },
        "field_edv_mappings": field_mappings,
        "parent_child_chains": parent_child_chains,
        "validation_edv_fields": [],  # Could be populated if validation patterns detected
        "summary": {
            "total_fields_with_edv": len(field_mappings),
            "parent_fields": parent_count,
            "child_fields": child_count,
            "validation_fields": 0,
            "ext_dropdown_rules_needed": ext_dropdown_count,
            "ext_value_rules_needed": ext_value_count
        }
    }

    # Save field-EDV mapping JSON
    field_mapping_path = os.path.join(output_dir, f"{doc_name}_field_edv_mapping.json")
    with open(field_mapping_path, 'w') as f:
        json.dump(field_mapping_output, f, indent=2)
    print(f"  Saved: {field_mapping_path}")

    # Final summary
    print("\n" + "="*60)
    print("EDV TABLE MAPPING COMPLETE")
    print("="*60)
    print(f"Document: {Path(args.document_path).name}")
    print()
    print(f"Reference Tables Found: {len(reference_tables)}")
    print(f"EDV Tables Generated: {len(edv_registry['edv_tables'])}")
    print()
    print("Table Mappings:")
    for ref_id, edv_name in edv_registry["table_name_mapping"].items():
        print(f"  - {ref_id} → {edv_name}")
    print()
    print(f"Fields with EDV Configuration: {len(field_mappings)}")
    print(f"  - Parent dropdowns: {parent_count}")
    print(f"  - Child dropdowns (cascading): {child_count}")
    print(f"  - EXT_DROP_DOWN rules needed: {ext_dropdown_count}")
    print(f"  - EXT_VALUE rules needed: {ext_value_count}")
    print()
    print(f"Parent-Child Relationships: {len(parent_child_chains)}")
    for chain in parent_child_chains:
        chain_fields = [c["field"] for c in chain["chain"]]
        print(f"  - {' → '.join(chain_fields)}")
    print()
    print("Output Files:")
    print(f"  - EDV Tables: {edv_tables_path}")
    print(f"  - Field Mapping: {field_mapping_path}")
    print("="*60)


if __name__ == "__main__":
    main()
