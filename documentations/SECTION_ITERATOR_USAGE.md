# Section Iterator Usage Guide

This guide explains how to use `get_section_by_index.py` to iterate through BUD documents section by section.

## Overview

The `get_section_by_index.py` script allows you to:
- Parse a BUD document and access sections by index
- Handle nested subsections automatically
- Reduce context load when processing large documents
- Process documents incrementally instead of all at once

## Installation

No additional installation required. The script uses the existing `doc_parser` package.

## Usage

### 1. Get Total Section Count

```bash
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" --count
```

**Output:**
```json
{
  "document": "documents/Vendor Creation Sample BUD(1).docx",
  "total_sections": 35
}
```

### 2. List All Sections

```bash
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" --list
```

**Output:**
```json
{
  "document": "documents/Vendor Creation Sample BUD(1).docx",
  "total_sections": 35,
  "sections": [
    {
      "index": 0,
      "heading": "1. Executive Summary",
      "level": 1,
      "parent_path": "",
      "content_length": 33,
      "table_count": 0,
      "field_count": 0
    },
    ...
  ]
}
```

### 3. Get Specific Section by Index

```bash
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" 13
```

**Output:**
```json
{
  "document": "documents/Vendor Creation Sample BUD(1).docx",
  "section": {
    "heading": "4.4 Field-Level Information",
    "level": 2,
    "content": [
      "Below are the details of each field...",
      "Note – If there is any dependent dropdown..."
    ],
    "tables": [],
    "fields": [],
    "workflow_steps": [],
    "parent_path": "4. Vendor Creation Functional Requirements",
    "has_subsections": false,
    "subsection_count": 0,
    "index": 13,
    "total_sections": 35
  }
}
```

## Section Data Structure

Each section contains:

| Field | Type | Description |
|-------|------|-------------|
| `heading` | string | Section heading text |
| `level` | int | Heading level (1-4) |
| `content` | array | List of paragraph strings in this section |
| `tables` | array | Tables found in this section (as dict) |
| `fields` | array | Field definitions in this section (as dict) |
| `workflow_steps` | array | Workflow steps in this section (as dict) |
| `parent_path` | string | Breadcrumb path to parent (e.g., "Section A > Section B") |
| `has_subsections` | bool | Whether this section has child sections |
| `subsection_count` | int | Number of direct child sections |
| `index` | int | Zero-based index in flattened hierarchy |
| `total_sections` | int | Total number of sections in document |

## How Sections are Flattened

The script flattens the hierarchical section structure into a linear sequence:

```
Document Structure:          Flattened Index:
1. Executive Summary         0
  1.1 Purpose                1
  1.2 Audience               2
2. Project Description       3
  2.1 Background             4
  2.2 Objectives             5
3. Project Scope             6
  3.1 In Scope               7
  3.2 Out of Scope           8
```

## Integration with Claude Code Skills

### Example: Rule Extraction Skill

The `rule_info_extractor` skill can be updated to process sections incrementally:

```python
import subprocess
import json

def extract_rules_section_by_section(document_path: str):
    """Extract rules from a document, one section at a time."""

    # Step 1: Get total section count
    result = subprocess.run(
        ["python3", "get_section_by_index.py", document_path, "--count"],
        capture_output=True,
        text=True
    )
    data = json.loads(result.stdout)
    total_sections = data["total_sections"]

    all_rules = []

    # Step 2: Process each section
    for i in range(total_sections):
        print(f"Processing section {i+1}/{total_sections}...")

        # Get section data
        result = subprocess.run(
            ["python3", "get_section_by_index.py", document_path, str(i)],
            capture_output=True,
            text=True
        )
        section_data = json.loads(result.stdout)
        section = section_data["section"]

        # Extract rules from this section
        rules = extract_rules_from_section(section)
        all_rules.extend(rules)

    return all_rules

def extract_rules_from_section(section: dict) -> list:
    """Extract rules from a single section."""
    rules = []

    # Look for "Note" patterns in content
    for paragraph in section["content"]:
        if "Note" in paragraph or "note" in paragraph:
            rules.append({
                "section_name": section["heading"],
                "rule_type": "implementation_note",
                "text": paragraph,
                "level": section["level"],
                "parent_path": section["parent_path"]
            })

    return rules
```

### Benefits of Section-by-Section Processing

1. **Reduced Context Size**: Each API call processes only one section instead of the entire document
2. **Better Error Recovery**: If processing fails on one section, others can continue
3. **Progress Tracking**: Easy to show progress (e.g., "Processing 13/35 sections")
4. **Parallel Processing**: Multiple sections can be processed concurrently
5. **Incremental Results**: Start seeing results before the entire document is processed

## Example: Iterating Through All Sections

```bash
#!/bin/bash

DOC_PATH="documents/Vendor Creation Sample BUD(1).docx"

# Get total count
COUNT=$(python3 get_section_by_index.py "$DOC_PATH" --count | jq -r '.total_sections')

echo "Processing $COUNT sections..."

# Iterate through all sections
for i in $(seq 0 $((COUNT-1))); do
    echo "Section $i:"
    python3 get_section_by_index.py "$DOC_PATH" "$i" | jq -r '.section.heading'
done
```

## Error Handling

The script provides clear error messages:

```bash
# Invalid index
python3 get_section_by_index.py "doc.docx" 999
# Error: Section index 999 out of range (0-34)

# Document not found
python3 get_section_by_index.py "missing.docx" 0
# Error: Document not found: missing.docx

# Invalid command
python3 get_section_by_index.py "doc.docx" invalid
# Error: Invalid section index: invalid
```

## Notes

- Section indices are **zero-based** (0 to total_sections-1)
- Subsections are included in the flattened list
- Parent sections appear before their subsections
- Empty sections (headings with no content) are still included
- Tables and fields are included in their containing section
