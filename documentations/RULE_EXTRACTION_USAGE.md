# Rule Extraction Agent - Usage Guide

## Quick Start

```bash
# Run with enhanced agent (recommended)
python run_rule_extraction.py \
    --schema output/complete_format/6421-schema.json \
    --intra-panel "adws/2026-02-02_16-18-22/templates_output/Vendor Creation Sample BUD_intra_panel_references.json" \
    --edv-tables "adws/2026-02-02_16-18-22/templates_output/Vendor_Creation_Sample_BUD_edv_tables.json" \
    --field-edv-mapping "adws/2026-02-02_16-18-22/templates_output/Vendor_Creation_Sample_BUD_field_edv_mapping.json" \
    --output /tmp/populated_schema.json \
    --report /tmp/extraction_report.json \
    --verbose
```

## Python API - EnhancedRuleExtractionAgent

```python
from rule_extraction_agent import EnhancedRuleExtractionAgent

agent = EnhancedRuleExtractionAgent(
    edv_tables_path="edv_tables.json",
    field_edv_mapping_path="field_edv_mapping.json",
    llm_threshold=0.7,
    verbose=True
)

result = agent.process(
    schema_json_path="6421-schema.json",
    intra_panel_path="intra_panel_references.json",
    output_path="populated_schema.json"
)

print(f"Generated {result['stats']['total_rules_generated']} rules")
```

## Enhanced Features

1. **Missing Control Fields**: Adds 20 control fields (RuleCheck, Transaction ID, etc.)
2. **Comprehensive Visibility Rules**: 4-6 rules per controlling field
3. **VALIDATION Rules**: From EDV mappings
4. **COPY_TO Rules**: Common copy patterns
5. **OCR → VERIFY Chains**: Automatic linking

See IMPLEMENTATION_SUMMARY.md for full details.
