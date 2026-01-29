# Section Iterator for BUD Documents

A Python utility for iterating through Business Understanding Documents (BUD) section by section, designed to reduce context load when processing large documents with Claude Code skills.

## Overview

The section iterator solves the problem of processing large BUD documents by allowing you to access individual sections by index, rather than processing the entire document at once. This is particularly useful for:

- Reducing API context size when using Claude
- Processing documents incrementally
- Better error recovery (if one section fails, others can continue)
- Progress tracking and monitoring

## Files Created

### 1. `get_section_by_index.py`

**Main utility script** that parses BUD documents and allows access to sections by index.

**Features:**
- Parses DOCX documents using the existing `doc_parser` package
- Flattens hierarchical section structure into a linear sequence
- Provides three modes: count, list, and get-by-index
- Outputs clean JSON (parsing progress goes to stderr)

**Usage:**

```bash
# Get total section count
python3 get_section_by_index.py "documents/sample.docx" --count

# List all sections with metadata
python3 get_section_by_index.py "documents/sample.docx" --list

# Get specific section by index
python3 get_section_by_index.py "documents/sample.docx" 13
```

**Key Classes:**
- `SectionIterator`: Main class for document iteration
  - `parse()`: Parse document and flatten sections
  - `get_section_count()`: Get total section count
  - `get_section_by_index(index)`: Get section data by index
  - `list_sections()`: Get overview of all sections

### 2. `example_section_iteration.py`

**Example implementation** showing how to use the section iterator for rule extraction.

**Features:**
- Demonstrates efficient single-parse approach
- Extracts implementation notes from sections
- Shows progress during processing
- Can save results to JSON

**Usage:**

```bash
# Process and display results
python3 example_section_iteration.py "documents/Vendor Creation Sample BUD(1).docx"

# Process and save to file
python3 example_section_iteration.py "documents/sample.docx" output/notes.json
```

**Sample Output:**
```
Processing document: documents/Vendor Creation Sample BUD(1).docx
----------------------------------------------------------------------

Step 1: Parsing document...
Found 35 sections (including subsections)

Step 2: Getting section overview...
Document structure:
   0. 1. Executive Summary
   1.   1.1 Purpose
   ...

Step 3: Processing sections...
  [1/35] ○ 1. Executive Summary: No notes
  [14/35] ✓ 4.4 Field-Level Information: Found 3 note(s)
  ...

Extraction complete!
Total sections processed: 35
Total notes extracted: 9
```

### 3. `SECTION_ITERATOR_USAGE.md`

**Comprehensive documentation** covering:
- All usage modes and examples
- Section data structure reference
- Integration patterns for Claude Code skills
- Error handling
- Best practices

### 4. `README_SECTION_ITERATOR.md` (this file)

High-level overview and quick start guide.

## Quick Start

### Installation

No additional dependencies needed beyond the existing `doc_parser` package.

### Basic Example

```python
from get_section_by_index import SectionIterator

# Initialize and parse document
iterator = SectionIterator("documents/sample.docx")
iterator.parse()

# Get total sections
total = iterator.get_section_count()
print(f"Document has {total} sections")

# Iterate through all sections
for i in range(total):
    section = iterator.get_section_by_index(i)
    print(f"{i}. {section['heading']}")

    # Process section content
    for paragraph in section['content']:
        print(f"   {paragraph[:50]}...")
```

## Section Data Structure

Each section returned contains:

```python
{
    "heading": str,              # Section title
    "level": int,                # Heading level (1-4)
    "content": [str],            # List of paragraphs
    "tables": [dict],            # Tables in this section
    "fields": [dict],            # Field definitions
    "workflow_steps": [dict],    # Workflow steps
    "parent_path": str,          # Breadcrumb path
    "has_subsections": bool,     # Has child sections
    "subsection_count": int,     # Number of children
    "index": int,                # Current index
    "total_sections": int        # Total in document
}
```

## How Sections are Flattened

The hierarchical document structure is flattened into a linear sequence:

```
Original Document:          Flattened Indices:
├─ 1. Executive Summary     → 0
│  ├─ 1.1 Purpose           → 1
│  └─ 1.2 Audience          → 2
├─ 2. Project Description   → 3
│  ├─ 2.1 Background        → 4
│  └─ 2.2 Objectives        → 5
└─ 3. Project Scope         → 6
   ├─ 3.1 In Scope          → 7
   └─ 3.2 Out of Scope      → 8
```

## Integration with Claude Code Skills

### For the `rule_info_extractor` Skill

The rule extraction skill can be updated to process documents section by section:

**Current Approach (processes entire document at once):**
```python
# Single API call with full document context
extract_rules(full_document_content)  # Large context!
```

**New Approach (section by section):**
```python
from get_section_by_index import SectionIterator

iterator = SectionIterator(document_path)
iterator.parse()

all_rules = []
for i in range(iterator.get_section_count()):
    section = iterator.get_section_by_index(i)

    # Process only this section (reduced context)
    rules = extract_rules_from_section(section)
    all_rules.extend(rules)
```

### Benefits

1. **Reduced Context Size**: Each Claude API call processes only one section
2. **Better Progress Tracking**: Show "Processing section 15/35"
3. **Fault Tolerance**: If one section fails, others can continue
4. **Incremental Results**: See results before full completion
5. **Parallel Processing**: Can process multiple sections concurrently

## Command-Line Usage from Skills

If you prefer to call the script as a subprocess (for isolation):

```python
import subprocess
import json

# Get section count
result = subprocess.run(
    ["python3", "get_section_by_index.py", doc_path, "--count"],
    capture_output=True, text=True, stderr=subprocess.DEVNULL
)
data = json.loads(result.stdout)
total_sections = data["total_sections"]

# Get specific section
result = subprocess.run(
    ["python3", "get_section_by_index.py", doc_path, "13"],
    capture_output=True, text=True, stderr=subprocess.DEVNULL
)
section_data = json.loads(result.stdout)
section = section_data["section"]
```

**Note:** For efficiency, prefer using the `SectionIterator` class directly (as shown in `example_section_iteration.py`) to avoid re-parsing the document for each section.

## Example Output

Running the example on "Vendor Creation Sample BUD":

```json
{
  "document": "documents/Vendor Creation Sample BUD(1).docx",
  "total_sections": 35,
  "notes_extracted": 9,
  "notes": [
    {
      "section_name": "4.4 Field-Level Information",
      "section_level": 2,
      "parent_path": "4. Vendor Creation Functional Requirements",
      "rule_type": "implementation_note",
      "text": "Note – If there is any dependent dropdown, then it should be clear when the parent dropdown values are changed.",
      "index": 13
    },
    ...
  ]
}
```

## Testing

Test with the sample BUD document:

```bash
# Test the iterator
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" --count
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" --list
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" 13

# Test the example
python3 example_section_iteration.py "documents/Vendor Creation Sample BUD(1).docx"
```

## Performance

The "Vendor Creation Sample BUD" document:
- **Total sections**: 35 (including all subsections)
- **Parsing time**: ~5-10 seconds (one-time)
- **Per-section access**: Instant (no re-parsing)

## Notes

- Section indices are **zero-based** (0 to total_sections-1)
- Subsections are automatically included in the flattened list
- Parent sections always appear before their subsections
- Empty sections (headings with no content) are included
- Tables and fields are included in their containing section

## Future Enhancements

Potential improvements:
- Add section filtering (e.g., only level 2 headings)
- Support section ranges (e.g., sections 10-15)
- Add caching for frequently accessed documents
- Export to other formats (CSV, Markdown)

## See Also

- `SECTION_ITERATOR_USAGE.md` - Detailed usage documentation
- `CLAUDE.md` - Project overview and common commands
- `.claude/commands/rule_info_extractor.md` - Rule extraction skill definition
