# Rule Extraction Agent - Quick Start Guide

## Installation

No additional installation required. All core dependencies are already installed.

Optional: Set up OpenAI API key for LLM fallback (complex cases):
```bash
echo "OPENAI_API_KEY=your-key-here" >> .env
```

## Basic Usage

### 1. Run Demonstration

See the agent in action with a working example:
```bash
python3 demo_rule_extraction.py
```

This will:
- Parse Vendor Creation Sample BUD (148 fields with logic)
- Extract rules from sample fields
- Show detailed rule generation
- Display summary statistics

### 2. Command Line - Simple

Process a schema and generate rules:
```bash
python rule_extraction_agent.py \
  --schema output/complete_format/2581-schema.json \
  --output output/rules_populated/2581-schema.json
```

### 3. Command Line - Full Options

With validation, reporting, and verbose output:
```bash
python rule_extraction_agent.py \
  --schema output/complete_format/2581-schema.json \
  --output output/rules_populated/2581-schema.json \
  --verbose \
  --validate \
  --report summary_report.json
```

### 4. Test Without Saving (Dry Run)

```bash
python rule_extraction_agent.py \
  --schema output/complete_format/2581-schema.json \
  --dry-run \
  --verbose
```

## Python API

### Quick Example

```python
from rule_extraction_agent.main import RuleExtractionAgent

# Initialize and process
agent = RuleExtractionAgent(
    schema_path="output/complete_format/2581-schema.json",
    verbose=True
)
result = agent.process()

# Save output
agent.save_schema("output/rules_populated/2581-schema.json")

# Print summary
print(result.summary())
```

### Parse Individual Logic Statements

```python
from rule_extraction_agent.logic_parser import LogicParser

parser = LogicParser()

# Parse logic
logic = "if field 'GST option' is yes then visible and mandatory"
parsed = parser.parse(logic)

# View results
print(f"Keywords: {parsed.keywords}")
print(f"Actions: {parsed.actions}")
print(f"Conditions: {parsed.conditions}")
print(f"Confidence: {parsed.confidence}")
```

### Match Field References

```python
from rule_extraction_agent.field_matcher import FieldMatcher
import json

# Load schema
with open('output/complete_format/2581-schema.json') as f:
    schema = json.load(f)

# Create matcher
matcher = FieldMatcher(schema)

# Match field
field = matcher.match_field("Please select GST option")
if field:
    print(f"Matched: {field.name} (ID: {field.id})")
```

### Generate Rules

```python
from rule_extraction_agent.logic_parser import LogicParser
from rule_extraction_agent.rule_tree import RuleSelectionTree
from rule_extraction_agent.rule_builders import StandardRuleBuilder
from rule_extraction_agent.models import FieldInfo

# Parse logic
parser = LogicParser()
parsed = parser.parse("if field 'X' is yes then visible")

# Select rules
tree = RuleSelectionTree()
selections = tree.select_rules(parsed)

# Create field info
source = FieldInfo(id=100, name="X", variable_name="_x_", field_type="TEXT")
dest = FieldInfo(id=101, name="Y", variable_name="_y_", field_type="TEXT")

# Build rules
builder = StandardRuleBuilder()
for selection in selections:
    rules = builder.build(parsed, selection, source, [dest])
    for rule in rules:
        print(rule.to_dict())
```

## Common Logic Patterns

### 1. Conditional Visibility

**Logic:** "if field 'GST option' is yes then visible and mandatory"

**Generated Rules:**
- MAKE_VISIBLE (when GST option = yes)
- MAKE_MANDATORY (when GST option = yes)

### 2. Editability Control

**Logic:** "Non-Editable"

**Generated Rules:**
- MAKE_DISABLED (unconditional)

### 3. Data Derivation

**Logic:** "Data will come from PAN validation. Non-Editable"

**Generated Rules:**
- VALIDATION rule (PAN)
- MAKE_DISABLED (unconditional)

### 4. OCR Extraction

**Logic:** "OCR extract from GSTIN document"

**Generated Rules:**
- OCR_EXTRACTION rule (GSTIN)

### 5. Dropdown Control

**Logic:** "Dropdown values are India, International"

**Handled by:** Field type + values (not a rule)

## Command Line Options Reference

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--schema` | Yes | Path to schema JSON | - |
| `--output` | No | Output path for populated schema | Auto-generated |
| `--intra-panel` | No | Path to intra-panel references JSON | None |
| `--rule-schemas` | No | Path to Rule-Schemas.json | rules/Rule-Schemas.json |
| `--llm-threshold` | No | Confidence threshold for LLM fallback | 0.7 |
| `--report` | No | Path to save summary report | None |
| `--verbose` | No | Enable verbose logging | False |
| `--validate` | No | Validate generated rules | False |
| `--dry-run` | No | Run without saving output | False |

## Output Format

### Summary Report
```json
{
  "total_fields": 168,
  "fields_with_logic": 148,
  "rules_generated": 256,
  "deterministic_rules": 240,
  "llm_fallback_rules": 16,
  "unmatched_fields": [],
  "errors": [],
  "warnings": [],
  "processing_time": 1.23
}
```

### Generated Rule
```json
{
  "id": 100000,
  "createUser": "FIRST_PARTY",
  "updateUser": "FIRST_PARTY",
  "actionType": "MAKE_VISIBLE",
  "processingType": "CLIENT",
  "sourceIds": [275491],
  "destinationIds": [275492],
  "conditionalValues": ["yes"],
  "condition": "IN",
  "conditionValueType": "TEXT",
  "executeOnFill": true,
  "executeOnRead": false
}
```

## Troubleshooting

### Issue: "Schema file not found"
**Solution:** Check the path to schema JSON file
```bash
ls -la output/complete_format/2581-schema.json
```

### Issue: "No fields with logic found"
**Solution:** The schema from extract_fields_complete.py doesn't preserve logic text. Use demo_rule_extraction.py to work with parsed BUD document directly.

### Issue: "Unmatched field references"
**Solution:** This is normal for fuzzy matching. Check the report to see which fields couldn't be matched. Adjust fuzzy threshold if needed.

### Issue: "Low confidence rules"
**Solution:** Enable LLM fallback by setting OPENAI_API_KEY in .env file. This will handle complex logic statements.

## Performance Tips

1. **Use dry-run first** to test without saving:
   ```bash
   python rule_extraction_agent.py --schema input.json --dry-run --verbose
   ```

2. **Enable validation** to catch issues early:
   ```bash
   python rule_extraction_agent.py --schema input.json --validate
   ```

3. **Generate report** for analysis:
   ```bash
   python rule_extraction_agent.py --schema input.json --report report.json
   ```

4. **Adjust LLM threshold** based on your needs:
   ```bash
   # More aggressive LLM use (lower threshold)
   python rule_extraction_agent.py --schema input.json --llm-threshold 0.5

   # Less LLM use (higher threshold)
   python rule_extraction_agent.py --schema input.json --llm-threshold 0.9
   ```

## Next Steps

1. Read the full documentation: `rule_extraction_agent/README.md`
2. Review implementation summary: `RULE_EXTRACTION_IMPLEMENTATION_SUMMARY.md`
3. Check the plan: `.claude/plans/plan.md`
4. Explore the code: `rule_extraction_agent/` directory

## Support

For questions or issues:
1. Check the documentation in `rule_extraction_agent/README.md`
2. Review the demonstration in `demo_rule_extraction.py`
3. Inspect the implementation in `rule_extraction_agent/` modules
