# Integration Guide: Updating rule_info_extractor Skill

This guide shows how to update the `.claude/commands/rule_info_extractor.md` skill to use section-by-section processing.

## Problem

The current skill processes the entire document at once:
- Large context size sent to Claude API
- Risk of hitting context limits
- No progress tracking
- All-or-nothing approach (if processing fails, lose everything)

## Solution

Use the new section iterator to process documents section by section:
- Smaller context per API call
- Progress tracking (e.g., "Processing section 15/35")
- Fault tolerance (failed sections don't affect others)
- Incremental results

## Implementation Options

### Option 1: Use SectionIterator Class Directly (Recommended)

**Advantages:**
- Fastest (parses document only once)
- Most efficient memory usage
- Direct Python integration

**Example Implementation:**

```python
#!/usr/bin/env python3
"""
Updated rule extraction that processes section by section.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from get_section_by_index import SectionIterator


def extract_rules_from_section(section: dict) -> list:
    """
    Extract unstructured rules from a single section.

    In practice, this would call Claude API with just this section's content.
    """
    rules = []

    # Keywords that indicate important implementation notes
    rule_keywords = [
        "note", "Note", "NOTE",
        "important", "Important", "IMPORTANT",
        "rule", "Rule", "RULE",
        "must", "should", "shall",
        "requirement", "Requirement"
    ]

    for paragraph in section["content"]:
        # Check if paragraph contains rule-related keywords
        if any(keyword in paragraph for keyword in rule_keywords):
            # Determine rule type
            rule_type = "implementation_note"
            if "Note" in paragraph or "note" in paragraph:
                rule_type = "implementation_note"
            elif "Important" in paragraph or "important" in paragraph:
                rule_type = "important_rule"
            elif "must" in paragraph.lower() or "shall" in paragraph.lower():
                rule_type = "mandatory_rule"

            rules.append({
                "section_name": section["heading"],
                "section_level": section["level"],
                "parent_path": section["parent_path"],
                "rule_type": rule_type,
                "text": paragraph,
                "section_index": section["index"]
            })

    # Also check tables in this section for rule-related content
    for table in section["tables"]:
        # Look for tables with "logic", "rules", or "notes" in headers
        headers_lower = [h.lower() for h in table.get("headers", [])]
        if any(kw in " ".join(headers_lower) for kw in ["logic", "rule", "note", "validation"]):
            # Extract rules from table rows
            # This is simplified - in practice you'd parse the table structure
            rules.append({
                "section_name": section["heading"],
                "section_level": section["level"],
                "parent_path": section["parent_path"],
                "rule_type": "table_rule",
                "text": f"Table with headers: {', '.join(table.get('headers', []))}",
                "section_index": section["index"],
                "table_context": table.get("context", "")
            })

    return rules


def process_document(document_path: str, output_dir: str):
    """
    Process a BUD document section by section and extract rules.
    """
    print(f"\n{'='*70}")
    print(f"Processing: {Path(document_path).name}")
    print(f"{'='*70}\n")

    # Step 1: Parse document once
    print("Step 1: Parsing document...")
    iterator = SectionIterator(document_path)
    iterator.parse()
    total_sections = iterator.get_section_count()
    print(f"  ✓ Found {total_sections} sections\n")

    # Step 2: Process each section
    print("Step 2: Extracting rules section by section...")
    all_rules = []

    for i in range(total_sections):
        section = iterator.get_section_by_index(i)

        # Show progress
        progress = f"[{i+1}/{total_sections}]"
        heading = section['heading'][:50]
        print(f"  {progress} {heading}...", end="", flush=True)

        # Extract rules from this section
        # In practice, you would call Claude API here with section content
        rules = extract_rules_from_section(section)

        if rules:
            print(f" ✓ Found {len(rules)} rule(s)")
            all_rules.extend(rules)
        else:
            print(" ○ No rules")

    # Step 3: Save results
    print(f"\nStep 3: Saving results...")

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate output filename
    doc_name = Path(document_path).stem
    output_file = output_path / f"{doc_name}_meta_rules.json"

    # Prepare output data
    output_data = {
        "document_name": doc_name,
        "document_path": document_path,
        "total_sections": total_sections,
        "rules_extracted": len(all_rules),
        "extraction_date": datetime.now().isoformat(),
        "unstructured_rules": all_rules
    }

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved to: {output_file}")

    # Step 4: Display summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Document: {doc_name}")
    print(f"Sections processed: {total_sections}")
    print(f"Rules extracted: {len(all_rules)}")
    print(f"Output: {output_file}")
    print(f"{'='*70}\n")

    return all_rules


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 extract_rules_sectional.py <document_path> [output_dir]")
        sys.exit(1)

    document_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "documents/rule_info_output"

    # Add timestamp to output dir
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = f"{output_dir}/{timestamp}"

    # Validate document exists
    if not Path(document_path).exists():
        print(f"Error: Document not found: {document_path}", file=sys.stderr)
        sys.exit(1)

    # Process document
    process_document(document_path, output_dir)


if __name__ == "__main__":
    main()
```

### Option 2: Call as Subprocess (For Isolation)

**Advantages:**
- Process isolation
- Can be called from any language
- Good for distributed processing

**Example Implementation:**

```python
import subprocess
import json


def get_section_count(document_path: str) -> int:
    """Get total number of sections in document."""
    result = subprocess.run(
        ["python3", "get_section_by_index.py", document_path, "--count"],
        capture_output=True,
        text=True,
        stderr=subprocess.DEVNULL
    )
    data = json.loads(result.stdout)
    return data["total_sections"]


def get_section(document_path: str, index: int) -> dict:
    """Get section data by index."""
    result = subprocess.run(
        ["python3", "get_section_by_index.py", document_path, str(index)],
        capture_output=True,
        text=True,
        stderr=subprocess.DEVNULL
    )
    data = json.loads(result.stdout)
    return data["section"]


def process_document_subprocess(document_path: str):
    """Process document using subprocess calls."""
    total_sections = get_section_count(document_path)
    print(f"Processing {total_sections} sections...")

    all_rules = []
    for i in range(total_sections):
        section = get_section(document_path, i)

        # Process this section
        rules = extract_rules_from_section(section)
        all_rules.extend(rules)

        print(f"[{i+1}/{total_sections}] {section['heading']}: {len(rules)} rules")

    return all_rules
```

## Updated Skill Workflow

Update `.claude/commands/rule_info_extractor.md` to include:

```markdown
### Step 3: Extract Unstructured Rule Information (Section by Section)

Instead of processing the entire document at once, iterate through sections:

```python
from get_section_by_index import SectionIterator

iterator = SectionIterator(document_path)
iterator.parse()

all_rules = []
total_sections = iterator.get_section_count()

for i in range(total_sections):
    section = iterator.get_section_by_index(i)

    # Process only this section (reduced context)
    print(f"Processing [{i+1}/{total_sections}]: {section['heading']}")

    # Extract rules from section content, tables, fields
    rules = extract_rules_from_section(section)
    all_rules.extend(rules)

    # Show progress
    if rules:
        print(f"  ✓ Found {len(rules)} rule(s)")
```
```

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Context size per API call** | Entire document (~100KB+) | Single section (~5-10KB) |
| **Progress visibility** | None | "Processing 15/35 sections" |
| **Error recovery** | All-or-nothing | Continue after failed section |
| **Memory usage** | High (full document in memory) | Lower (section-by-section) |
| **Processing time** | Same for all docs | Faster for small docs |
| **Partial results** | No | Yes (can use partial results) |

## Testing the New Approach

Test with the sample document:

```bash
# Test the section iterator
python3 get_section_by_index.py "documents/Vendor Creation Sample BUD(1).docx" --count

# Test the example implementation
python3 example_section_iteration.py "documents/Vendor Creation Sample BUD(1).docx"
```

Expected output for the sample BUD:
- **Total sections**: 35
- **Processing time**: ~5-10 seconds
- **Memory usage**: Moderate
- **Rules found**: 9+ implementation notes

## Migration Checklist

- [ ] Review current `rule_info_extractor.md` skill
- [ ] Decide between Option 1 (class) or Option 2 (subprocess)
- [ ] Create new extraction script using section iterator
- [ ] Update skill markdown to use new script
- [ ] Test with sample documents
- [ ] Verify JSON output format matches expectations
- [ ] Update documentation
- [ ] Deploy to production

## Example Output

The output format remains the same, but now includes section metadata:

```json
{
  "document_name": "Vendor Creation Sample BUD",
  "total_sections": 35,
  "rules_extracted": 9,
  "unstructured_rules": [
    {
      "section_name": "4.4 Field-Level Information",
      "section_level": 2,
      "parent_path": "4. Vendor Creation Functional Requirements",
      "rule_type": "implementation_note",
      "text": "Note – If there is any dependent dropdown...",
      "section_index": 13
    }
  ]
}
```

## Next Steps

1. Copy `get_section_by_index.py` to your project
2. Choose implementation approach (Option 1 recommended)
3. Create your extraction script using the examples above
4. Update `.claude/commands/rule_info_extractor.md`
5. Test with multiple BUD documents
6. Monitor performance and adjust as needed
