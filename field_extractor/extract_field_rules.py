#!/usr/bin/env python3
"""
Extract field-specific rules and logic from BUD documents.

This script processes BUD documents section by section to extract:
- Field validation rules
- Field dependencies
- Visibility/mandatory conditions
- Default value logic
- Data copying/clearing rules
- Dropdown dependency logic
- Field calculations
- Field formatting rules

It EXCLUDES:
- Workflow steps
- Approver routing logic
- Communication templates
- Process descriptions
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from get_section_by_index import SectionIterator


# Rule type keywords mapping
RULE_TYPE_PATTERNS = {
    'field_validation': [
        'must be', 'should be', 'valid', 'invalid', 'validate', 'validation',
        'characters', 'digits', 'format', 'pattern', 'regex', 'length'
    ],
    'field_dependency': [
        'depends on', 'dependent on', 'based on', 'when', 'if', 'then',
        'affects', 'controls', 'triggers'
    ],
    'visibility_rule': [
        'visible', 'invisible', 'show', 'hide', 'display', 'hidden',
        'appear', 'disappear'
    ],
    'mandatory_rule': [
        'mandatory', 'required', 'optional', 'non-mandatory', 'compulsory'
    ],
    'default_value_logic': [
        'default', 'prefilled', 'pre-filled', 'auto-populate', 'auto-fill',
        'automatically set', 'initial value'
    ],
    'data_copy_rule': [
        'copy', 'copied', 'copying', 'duplicate', 'replicate', 'clear',
        'cleared', 'clearing'
    ],
    'dropdown_dependency': [
        'dropdown', 'parent dropdown', 'child dropdown', 'dependent dropdown',
        'cascading'
    ],
    'field_calculation': [
        'calculate', 'computed', 'sum', 'total', 'multiply', 'divide',
        'formula', 'equation'
    ],
    'field_format': [
        'format', 'formatting', 'mask', 'pattern', 'display format'
    ]
}

# Keywords that suggest field-level rules (not workflow)
FIELD_RULE_INDICATORS = [
    'field', 'FFD', 'dropdown', 'value', 'data', 'input',
    'mandatory', 'optional', 'visible', 'hidden', 'default',
    'validate', 'validation', 'format', 'pattern', 'copy',
    'clear', 'dependent', 'parent', 'child'
]

# Keywords that indicate workflow (to exclude)
WORKFLOW_INDICATORS = [
    'initiator submits', 'approver reviews', 'approval', 'route to',
    'send email', 'notification', 'user logs in', 'user navigates',
    'workflow step', 'process flow', 'submit form', 'MDC team',
    'communication template', 'system integration', 'access management'
]


def classify_rule_type(text: str) -> str:
    """
    Classify the rule type based on keywords in the text.

    Args:
        text: Rule text to classify

    Returns:
        Rule type string
    """
    text_lower = text.lower()

    # Check each rule type pattern
    for rule_type, keywords in RULE_TYPE_PATTERNS.items():
        if any(keyword in text_lower for keyword in keywords):
            return rule_type

    return 'general_field_rule'


def is_field_related_rule(text: str) -> bool:
    """
    Check if the text describes a field-related rule (not workflow).

    Args:
        text: Text to check

    Returns:
        True if field-related, False otherwise
    """
    text_lower = text.lower()

    # Exclude workflow-related content
    if any(indicator in text_lower for indicator in WORKFLOW_INDICATORS):
        return False

    # Check for field-related indicators
    if any(indicator in text_lower for indicator in FIELD_RULE_INDICATORS):
        return True

    return False


def extract_field_names(text: str) -> List[str]:
    """
    Extract field names from rule text.

    This is a simple heuristic-based extraction. It looks for:
    - Quoted field names
    - Capitalized words that might be field names
    - Known field-related terms

    Args:
        text: Rule text

    Returns:
        List of potential field names
    """
    import re

    fields = []

    # Extract quoted text (likely field names)
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", text)
    fields.extend(quoted)

    # Extract capitalized terms (potential field names)
    # Look for patterns like "PAN", "GST", "Address Panel"
    capitalized = re.findall(r'\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\b', text)
    fields.extend([cap for cap in capitalized if len(cap) > 2 and cap not in ['Note', 'If', 'The', 'When']])

    # Common field-related terms
    field_terms = ['dropdown', 'field', 'panel', 'address', 'GST', 'PAN', 'value']
    for term in field_terms:
        if term.lower() in text.lower() and term not in fields:
            fields.append(term)

    # Remove duplicates and empty strings
    fields = list(set([f.strip() for f in fields if f.strip()]))

    return fields if fields else []


def extract_rules_from_section(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract field-specific rules from a section.

    Args:
        section: Section data from SectionIterator

    Returns:
        List of extracted rules
    """
    rules = []

    # Process each paragraph in the section
    for paragraph in section.get('content', []):
        # Skip empty paragraphs
        if not paragraph.strip():
            continue

        # Check if this paragraph contains a field-related rule
        if is_field_related_rule(paragraph):
            rule_type = classify_rule_type(paragraph)
            affected_fields = extract_field_names(paragraph)

            rules.append({
                'section_name': section['heading'],
                'section_level': section['level'],
                'parent_path': section['parent_path'],
                'section_index': section['index'],
                'rule_type': rule_type,
                'text': paragraph.strip(),
                'affected_fields': affected_fields
            })

    return rules


def process_document(document_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Process a BUD document and extract field rules.

    Args:
        document_path: Path to the .docx document
        output_dir: Directory to save output

    Returns:
        Dictionary with extraction results
    """
    print(f"\nProcessing: {Path(document_path).name}")
    print("=" * 70)

    # Initialize iterator and parse
    iterator = SectionIterator(document_path)
    iterator.parse()
    total_sections = iterator.get_section_count()

    print(f"Total sections: {total_sections}")
    print()

    # Process each section
    all_rules = []

    for i in range(total_sections):
        section = iterator.get_section_by_index(i)

        # Extract rules from this section
        section_rules = extract_rules_from_section(section)

        if section_rules:
            print(f"[{i+1}/{total_sections}] ✓ {section['heading']}: {len(section_rules)} rule(s)")
            all_rules.extend(section_rules)
        else:
            print(f"[{i+1}/{total_sections}] ○ {section['heading']}")

    # Create output data
    doc_name = Path(document_path).stem
    output_data = {
        'document_name': doc_name,
        'total_sections': total_sections,
        'field_rules_extracted': len(all_rules),
        'unstructured_field_rules': all_rules
    }

    # Save output
    output_file = Path(output_dir) / f"{doc_name}_meta_rules.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"Extraction complete!")
    print(f"Field rules extracted: {len(all_rules)}")
    print(f"Output saved to: {output_file}")

    return output_data


def generate_summary(all_results: List[Dict[str, Any]]) -> None:
    """
    Generate summary of all extractions.

    Args:
        all_results: List of extraction results
    """
    print("\n" + "=" * 70)
    print("SUMMARY OF ALL DOCUMENTS")
    print("=" * 70)

    total_docs = len(all_results)
    total_sections = sum(r['total_sections'] for r in all_results)
    total_rules = sum(r['field_rules_extracted'] for r in all_results)

    print(f"\nDocuments processed: {total_docs}")
    print(f"Total sections: {total_sections}")
    print(f"Total field rules extracted: {total_rules}")

    # Rule type breakdown
    rule_type_counts = {}
    for result in all_results:
        for rule in result['unstructured_field_rules']:
            rule_type = rule['rule_type']
            rule_type_counts[rule_type] = rule_type_counts.get(rule_type, 0) + 1

    if rule_type_counts:
        print(f"\nRules by category:")
        for rule_type, count in sorted(rule_type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {rule_type}: {count}")

    # Per-document breakdown
    print(f"\nPer-document breakdown:")
    for result in all_results:
        print(f"  - {result['document_name']}: {result['field_rules_extracted']} rules")


def main():
    """Main entry point."""
    # Setup
    documents_dir = Path('documents')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_dir = Path('documents') / 'rule_info_output' / timestamp

    # Find all .docx files
    docx_files = list(documents_dir.glob('*.docx'))
    docx_files = [f for f in docx_files if not f.name.startswith('.~')]  # Exclude lock files

    if not docx_files:
        print("No .docx files found in documents/ directory")
        return

    print(f"Found {len(docx_files)} BUD documents")
    print(f"Output directory: {output_dir}")

    # Process each document
    all_results = []

    for doc_path in docx_files:
        try:
            result = process_document(str(doc_path), str(output_dir))
            all_results.append(result)
        except Exception as e:
            print(f"Error processing {doc_path.name}: {e}")
            continue

    # Generate summary
    if all_results:
        generate_summary(all_results)


if __name__ == '__main__':
    main()
