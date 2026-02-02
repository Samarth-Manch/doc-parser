# Rules Extraction System - Complete Guide

## Overview

The Rules Extraction System uses OpenAI to automatically convert natural language field logic from BUD documents into structured JSON rules that match your Rule-Schemas.json format.

## Features

✅ **Automatic Rule Detection**
- Identifies rule types (EXPRESSION vs STANDARD)
- Extracts conditions and expressions
- Detects source/destination information

✅ **Expression Rules Support**
- `makeVisible/makeInvisible` - Visibility control
- `makeMandatory/makeNonMandatory` - Mandatory field control
- `enable/disable` - Field enablement
- `copyToFillData` - Value copying
- `clearField` - Field clearing

✅ **Standard Rules Support**
- OCR rules (PAN, Aadhaar, etc.)
- Validation rules
- Compare rules
- Copy rules

✅ **Source/Destination Extraction**
- Automatically identifies data sources from logic
- Detects non-editable fields
- Extracts validation sources (PAN validation, Aadhaar OCR, etc.)

## Installation

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure OpenAI API Key

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

### Option 1: Command Line Demo

Process fields and extract rules interactively:

```bash
source venv/bin/activate
python run_rules_extraction_demo.py
```

**Features:**
- Choose how many fields to process
- See extraction progress
- View summary statistics
- Export to JSON
- Optional detailed output

**Example Session:**

```
Document Parser - Rules Extraction Demo
================================================================================

1️⃣  Parsing document: documents/Vendor Creation Sample BUD(1).docx
   ✓ Found 350 fields

2️⃣  Rules Extraction
   Total fields available: 350
   Processing all fields may take several minutes and API calls.

   How many fields to process? (default: 10): 20

3️⃣  Initializing Rules Extractor...
   ✓ Loaded 182 rule schemas

4️⃣  Extracting rules from 20 fields...
   [1/20] Processing: Basic Details → 0 rule(s) ✓
   [2/20] Processing: Search term / Reference Number → 1 rule(s) ✓
   [3/20] Processing: Created on → 1 rule(s) ✓
   ...

📊 SUMMARY
================================================================================
Total fields processed:      20
Fields with rules:           15
Total rules extracted:       23
Average confidence:          87%

Rule Types:
  Expression rules:          18
  Standard rules:            5

5️⃣  Exporting to JSON: extracted_rules.json
   ✓ Exported successfully

✅ Done! Check extracted_rules.json for full JSON output.
```

### Option 2: Python API

Use the rules extractor programmatically:

```python
from rules_extractor import RulesExtractor, FieldWithRules
from doc_parser.parser import DocumentParser

# Parse document
parser = DocumentParser()
parsed_doc = parser.parse("document.docx")

# Extract rules
extractor = RulesExtractor()
fields_with_rules = extractor.process_parsed_document(parsed_doc)

# Export to JSON
extractor.export_to_json(fields_with_rules, "output.json")

# Access rules programmatically
for field_with_rules in fields_with_rules:
    print(f"Field: {field_with_rules.field_name}")
    for rule in field_with_rules.extracted_rules:
        print(f"  Rule: {rule.rule_name}")
        print(f"  Action: {rule.action}")
        print(f"  Confidence: {rule.confidence}")
```

### Option 3: GUI (Coming Soon)

Enhanced GUI with Rules tab showing extracted rules.

## How It Works

### 1. Rule Type Identification

The system first identifies whether the logic requires an **EXPRESSION** or **STANDARD** rule:

**Expression Rules** (action: EXECUTE):
- Conditional logic with keywords: "if", "when", "make", "set"
- Visibility/mandatory/enable operations
- Example: "Make field visible if PAN is verified"

**Standard Rules**:
- OCR operations: "extract", "scan", "OCR"
- Validation operations: "validate", "verify", "check"
- Example: "Get PAN from OCR rule"

### 2. Source/Destination Extraction

Extracts metadata from natural language:

```
Logic: "Data will come from PAN validation. Non-Editable"

Extracted:
- source: "PAN validation"
- is_editable: false
- validation_source: "PAN validation"
```

### 3. OpenAI-Powered Extraction

Uses GPT-4o-mini to convert logic to structured JSON:

**Input (Natural Language):**
```
"If SSI indicator is 1 or 2 then default value should be 1"
```

**Output (Structured JSON):**
```json
{
  "rule_name": "Set Minority Indicator Based on SSI",
  "action": "EXECUTE",
  "expression": "mm(vo(ssiIndicator)==1 || vo(ssiIndicator)==2, minorityIndicator)",
  "conditions": "SSI indicator equals 1 or 2",
  "confidence": 0.9,
  "rule_type": "EXPRESSION"
}
```

### 4. Knowledge Base Integration

References Rule-Schemas.json to match standard rules:

```python
# Find matching OCR rule
extractor.knowledge_base.find_rule_by_keyword('PAN')
# Returns: "PAN OCR" rule with proper structure

# Get all OCR rules
extractor.knowledge_base.get_ocr_rules()
# Returns: List of 20+ OCR rules (Aadhaar, PAN, GST, etc.)
```

## Output Format

### Extracted Rule Structure

```json
{
  "rule_name": "Descriptive name",
  "action": "EXECUTE | OCR | VALIDATION | COPY_TO | etc.",
  "source": "Source field/system",
  "source_field_id": 123,
  "destination_fields": ["field1", "field2"],
  "destination_field_ids": [124, 125],
  "conditions": "Plain English conditions",
  "expression": "Expression eval syntax",
  "processing_type": "CLIENT | SERVER",
  "rule_type": "EXPRESSION | STANDARD",
  "confidence": 0.85,
  "original_logic": "Original text from BUD"
}
```

### Field with Rules Structure

```json
{
  "field_name": "Mobile Number",
  "field_type": "MOBILE",
  "is_mandatory": true,
  "original_logic": "Validation based on...",
  "source_info": "PAN validation",
  "has_validation": true,
  "has_visibility_rules": false,
  "has_mandatory_rules": true,
  "rules": [
    {
      "rule_name": "Mobile Validation",
      "action": "VALIDATION",
      ...
    }
  ]
}
```

## Expression Syntax Reference

Based on `expr-eval` library and custom functions from the PDF.

### Common Functions

```javascript
// Value access
vo(fieldId)  // Get value of field by ID

// Visibility
makeVisible(condition, ...destIds)
makeInvisible(condition, ...destIds)

// Mandatory
makeMandatory(condition, ...destIds)
makeNonMandatory(condition, ...destIds)

// Enable/Disable
enable(condition, ...destIds)
disable(condition, ...destIds)

// Copy data
copyToFillData(condition, srcValue, ...destIds)

// Clear fields
clearField(condition, ...destIds)

// Concatenate
concat(...values)
concatWithDelimiter(delimiter, ...values)
```

### Example Expressions

**Make field visible based on condition:**
```javascript
makeVisible(vo(121)=='Yes', 124, 125)
```

**Set mandatory if another field has value:**
```javascript
makeMandatory(vo(panField)!='', aadhaarField)
```

**Copy value conditionally:**
```javascript
copyToFillData(vo(sameAsAbove)=='Yes', vo(addressField), mailingAddress)
```

**Disable field (non-editable):**
```javascript
disable(true, transactionId)
```

## Rule Categories

### 1. Validation Rules
- **Purpose**: Validate field values
- **Actions**: `VALIDATION`, `OCR`, `COMPARE`
- **Example**: "PAN validation", "Aadhaar OCR"

### 2. Visibility Rules
- **Purpose**: Show/hide fields conditionally
- **Actions**: `EXECUTE` with `makeVisible/makeInvisible`
- **Example**: "Show GST fields if registered"

### 3. Mandatory Rules
- **Purpose**: Make fields required conditionally
- **Actions**: `EXECUTE` with `makeMandatory/makeNonMandatory`
- **Example**: "Make Aadhaar mandatory if PAN not provided"

### 4. Copy/Auto-fill Rules
- **Purpose**: Auto-populate field values
- **Actions**: `EXECUTE` with `copyToFillData`, `COPY_TO`
- **Example**: "Copy name from PAN to form"

### 5. Enable/Disable Rules
- **Purpose**: Make fields editable/non-editable
- **Actions**: `EXECUTE` with `enable/disable`
- **Example**: "Make transaction ID non-editable"

## Confidence Scores

The system provides confidence scores for extracted rules:

| Score | Meaning | Action |
|-------|---------|--------|
| 0.9-1.0 | Very High | Rule is clear and unambiguous |
| 0.7-0.9 | High | Rule is clear with minor interpretation |
| 0.5-0.7 | Medium | Rule requires some assumptions |
| 0.3-0.5 | Low | Rule is ambiguous, manual review needed |
| 0.0-0.3 | Very Low | Fallback rule, needs review |

**Recommendations:**
- **≥ 0.8**: Use directly
- **0.5-0.8**: Review and adjust
- **< 0.5**: Manual review required

## Performance & Costs

### Processing Time

- **Per Field**: ~1-2 seconds (OpenAI API call)
- **10 Fields**: ~15-20 seconds
- **50 Fields**: ~1-2 minutes
- **350 Fields**: ~8-10 minutes

### API Costs (GPT-4o-mini)

- **Input**: ~500 tokens/field
- **Output**: ~150 tokens/field
- **Cost**: ~$0.0003/field
- **350 Fields**: ~$0.10 total

*Costs may vary based on logic complexity*

## Advanced Usage

### Custom Rule Detection

Add custom patterns for specific rule types:

```python
extractor = RulesExtractor()

# Add custom pattern
extractor.expression_patterns['custom_action'] = r'perform\s+custom\s+action'

# Extract with custom pattern
rules = extractor.extract_rules_with_llm(field)
```

### Batch Processing

Process multiple documents:

```python
import glob

extractor = RulesExtractor()
parser = DocumentParser()

for doc_path in glob.glob("documents/*.docx"):
    parsed = parser.parse(doc_path)
    fields_with_rules = extractor.process_parsed_document(parsed)

    output_name = f"rules_{Path(doc_path).stem}.json"
    extractor.export_to_json(fields_with_rules, output_name)
```

### Filter by Confidence

Process only high-confidence rules:

```python
high_confidence_fields = []

for field in fields_with_rules:
    high_conf_rules = [
        rule for rule in field.extracted_rules
        if rule.confidence >= 0.8
    ]

    if high_conf_rules:
        field.extracted_rules = high_conf_rules
        high_confidence_fields.append(field)
```

## Troubleshooting

### Issue: "OpenAI API key not found"

**Solution:**
```bash
# Check .env file exists
cat .env

# Verify key is set
grep OPENAI_API_KEY .env

# If missing, add it
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Issue: "Module 'openai' not found"

**Solution:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Issue: Low confidence scores

**Causes:**
- Ambiguous or complex logic
- Non-standard terminology
- Missing context

**Solutions:**
1. Check original logic text
2. Add more context to LLM prompt
3. Manually review and adjust
4. Split complex logic into multiple rules

### Issue: Wrong rule type detected

**Solution:**
```python
# Override rule type detection
if field.name == "Special Field":
    rule_type = "EXPRESSION"  # Force type
    rules = extractor.extract_rules_with_llm(field)
```

## Examples

### Example 1: Auto-derived Field

**BUD Logic:**
```
System-generated transaction ID from Manch (Non-Editable)
```

**Extracted Rule:**
```json
{
  "rule_name": "Transaction ID Non-Editable",
  "action": "EXECUTE",
  "expression": "disable(true, transactionId)",
  "conditions": "Always disabled",
  "processing_type": "CLIENT",
  "rule_type": "EXPRESSION",
  "confidence": 0.9
}
```

### Example 2: Conditional Visibility

**BUD Logic:**
```
Show GST fields only if organization is GST registered
```

**Extracted Rule:**
```json
{
  "rule_name": "Show GST Fields Conditionally",
  "action": "EXECUTE",
  "expression": "makeVisible(vo(gstRegistered)=='Yes', gstNumber, gstCertificate)",
  "conditions": "GST registered equals Yes",
  "destination_fields": ["gstNumber", "gstCertificate"],
  "rule_type": "EXPRESSION",
  "confidence": 0.95
}
```

### Example 3: Validation Rule

**BUD Logic:**
```
Validate PAN number format and verify with government database
```

**Extracted Rule:**
```json
{
  "rule_name": "PAN Validation",
  "action": "VALIDATION",
  "source": "PAN_VALIDATION",
  "destination_fields": ["panNumber"],
  "conditions": "Format validation and government verification",
  "processing_type": "SERVER",
  "rule_type": "STANDARD",
  "confidence": 0.88
}
```

## Best Practices

1. **Start Small**: Test with 10-20 fields first
2. **Review High-Impact Fields**: Manually review critical business rules
3. **Check Confidence**: Focus on rules with confidence < 0.7
4. **Validate Expressions**: Test generated expressions in your system
5. **Iterate**: Refine prompts based on results
6. **Document Custom Rules**: Add custom patterns for domain-specific rules
7. **Version Control**: Keep extracted rules in version control
8. **Track Changes**: Monitor extraction quality over time

## Future Enhancements

- [ ] GUI integration with Rules tab
- [ ] Field ID mapping from BUD metadata
- [ ] Batch export to Rule-Schemas.json format
- [ ] Rule validation against actual form metadata
- [ ] Confidence score tuning
- [ ] Custom rule templates
- [ ] Multi-language support
- [ ] Rule diff/comparison tools
- [ ] Integration with form builder systems

## Support

For issues or questions:
1. Check this guide
2. Review `sample_rules_extraction.json` for examples
3. Check OpenAI API status
4. Verify .env configuration

## Quick Reference

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env

# Run demo
python run_rules_extraction_demo.py

# Use in code
from rules_extractor import RulesExtractor
extractor = RulesExtractor()
rules = extractor.extract_rules_with_llm(field)

# Check output
cat extracted_rules.json | jq '.fields[0]'
```

---

**Last Updated:** 2026-01-16
**Version:** 1.0
**Status:** ✅ Production Ready
