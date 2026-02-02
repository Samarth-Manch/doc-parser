# Quick Start Guide - Rule Extraction Agent v15

## Prerequisites

- Python 3.8+
- Required data files in run directory:
  - `api_schema_vX.json` (base schema)
  - `templates_output/Vendor Creation Sample BUD_intra_panel_references.json`
  - `templates_output/Vendor_Creation_Sample_BUD_edv_tables.json`
  - `templates_output/Vendor_Creation_Sample_BUD_field_edv_mapping.json`

## Quick Run

```bash
cd /home/samart/project/doc-parser
python3 generated_code/rule_extraction_agent_v15.py
```

## Output

Two files will be created in the run directory:
1. `populated_schema_v15.json` - Complete schema with all extracted rules
2. `extraction_report_v15.json` - Statistics and summary

## Customizing the Run

### Change Input Directory

Edit `main()` function in `rule_extraction_agent_v15.py`:

```python
def main():
    orchestrator = RuleExtractionOrchestrator()

    # Change this to your run directory
    run_dir = "adws/2026-02-02_16-18-22"

    orchestrator.load_data(run_dir)
    orchestrator.extract_all_rules()
    orchestrator.save_output(run_dir, "v15")
```

### Change Output Version

```python
# Save as v16 instead of v15
orchestrator.save_output(run_dir, "v16")
```

### Access Generated Data

```python
# Get the populated schema
populated_schema = orchestrator.extract_all_rules()

# Access fields
fields = populated_schema['template']['documentTypes'][0]['formFillMetadatas']

# Access rules for a specific field
field_1_rules = fields[0]['formFillRules']
```

## Understanding the Output

### Populated Schema Structure

```json
{
  "template": {
    "id": 1,
    "documentTypes": [{
      "formFillMetadatas": [
        {
          "id": 1,           // Sequential ID
          "formTag": {
            "id": 1,         // Matches field ID
            "name": "Field Name",
            "type": "TEXT"
          },
          "formFillRules": [  // Generated rules
            {
              "id": 100,
              "actionType": "MAKE_VISIBLE",
              "sourceIds": [1],
              "destinationIds": [2],
              "condition": "IN",
              "conditionalValues": ["value1", "value2"],
              ...
            }
          ]
        }
      ]
    }]
  }
}
```

### Extraction Report Structure

```json
{
  "extraction_info": {
    "timestamp": "2026-02-02T17:18:54",
    "version": "v15",
    "status": "success"
  },
  "statistics": {
    "fields_processed": 168,
    "total_rules_generated": 343,
    "rules_by_type": {
      "MAKE_VISIBLE": 5,
      "MAKE_MANDATORY": 76,
      ...
    }
  },
  "field_summary": [
    {
      "field_id": 1,
      "field_name": "Basic Details",
      "field_type": "PANEL",
      "num_rules": 0
    }
  ]
}
```

## Troubleshooting

### Error: "No schema file found"
- Ensure api_schema_vX.json exists in run directory
- Check file permissions
- Verify JSON is valid

### Error: FileNotFoundError for templates_output
- Run directory must contain `templates_output/` subdirectory
- Required files:
  - `*_intra_panel_references.json`
  - `*_edv_tables.json`
  - `*_field_edv_mapping.json`

### Few Rules Generated
- Check intra_panel_references has data
- Verify field names match between schema and references
- Review logic parser patterns in code

### ID Conflicts
- Ensure clean run (no partial state)
- ID generator resets to 0 at start
- All IDs assigned sequentially

## Advanced Usage

### Add Custom Rule Builder

```python
class MyCustomRuleBuilder(BaseRuleBuilder):
    """Build custom rules"""

    def build_from_logic(self, source, targets, logic):
        rules = []
        # Your logic here
        return rules

# Add to orchestrator
orchestrator.my_builder = MyCustomRuleBuilder(orchestrator.id_gen)
```

### Modify Logic Parser

Edit `LogicParser` class to add new patterns:

```python
class LogicParser:
    # Add new keywords
    MY_KEYWORDS = ['custom', 'special']

    # Add to identify_rule_types
    def identify_rule_types(self, logic):
        rule_types = []
        text_lower = logic.raw_expression.lower()

        if any(kw in text_lower for kw in self.MY_KEYWORDS):
            rule_types.append('MY_CUSTOM_RULE')

        return rule_types
```

### Filter Generated Rules

```python
def filter_rules(rules, min_confidence=0.8):
    """Filter rules by confidence score"""
    return [r for r in rules if r.get('confidence', 1.0) >= min_confidence]

# Use in orchestrator
rules = self._generate_rules_for_type(...)
rules = filter_rules(rules, 0.8)
```

## Common Use Cases

### 1. Extract Rules for Single Field

```python
orchestrator = RuleExtractionOrchestrator()
orchestrator.load_data("adws/2026-02-02_16-18-22")

# Find specific field
field_match = orchestrator.field_matcher.find_field("Account Group/Vendor Type")

# Get intra-panel references for this field
# ... (see code for details)
```

### 2. Generate Report Without Saving

```python
orchestrator = RuleExtractionOrchestrator()
orchestrator.load_data("adws/2026-02-02_16-18-22")
populated_schema = orchestrator.extract_all_rules()

# Generate report but don't save
report = orchestrator.generate_extraction_report()
print(json.dumps(report, indent=2))
```

### 3. Compare Two Versions

```python
# Run v15
orchestrator = RuleExtractionOrchestrator()
orchestrator.load_data("adws/2026-02-02_16-18-22")
orchestrator.extract_all_rules()
orchestrator.save_output("adws/2026-02-02_16-18-22", "v15")

# Modify logic parser...

# Run v16
orchestrator2 = RuleExtractionOrchestrator()
orchestrator2.load_data("adws/2026-02-02_16-18-22")
orchestrator2.extract_all_rules()
orchestrator2.save_output("adws/2026-02-02_16-18-22", "v16")

# Compare reports
```

## Performance

- **Typical Run Time**: 2-5 seconds
- **Memory Usage**: ~50MB
- **Scalability**: Linear with number of fields and references

## Support

For issues or questions:
1. Check the summary document: `RULE_EXTRACTION_V15_SUMMARY.md`
2. Review code comments in `rule_extraction_agent_v15.py`
3. Check extraction report for specific field issues
4. Verify input data is complete and valid

## Version History

- **v15** (2026-02-02): Complete implementation with all rule builders
- **v12** (2026-02-02): Previous version with issues
- **v1-v11**: Development iterations

## Next Steps

1. Review generated rules in `populated_schema_v15.json`
2. Check extraction report for statistics
3. Compare with reference if available
4. Iterate on logic parser patterns as needed
5. Add custom rule builders for specific requirements
