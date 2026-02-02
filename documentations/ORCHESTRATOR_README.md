# Rule Extraction Orchestrator

Comprehensive orchestration system for extracting rules from BUD documents and populating formFillRules arrays.

## Overview

The orchestrator automates the complete rule extraction pipeline:

```
BUD Document → Intra-Panel Extraction → Rule Extraction Agent → Populated Schema
```

## Architecture

### Components

1. **Claude Coding Agent** (`.claude/agents/rule_extraction_coding_agent.md`)
   - ADW (Agent Definition Wrapper) for implementing the rule extraction system
   - Follows the detailed plan in `.claude/plans/plan.md`
   - Implements hybrid pattern-based + LLM approach

2. **Dispatcher** (`dispatchers/rule_extraction_coding_agent.py`)
   - Validates input files (schema JSON, intra-panel references JSON)
   - Calls the Claude coding agent with proper configuration
   - Manages output files and error handling

3. **Orchestrator** (`orchestrator_rule_extraction.py`)
   - Coordinates the complete pipeline
   - Creates timestamped workspace in `adws/`
   - Saves outputs in `templates_output/` subdirectory
   - Passes outputs between pipeline stages

### Directory Structure

```
project-root/
├── .claude/
│   ├── agents/
│   │   └── rule_extraction_coding_agent.md    # Coding agent ADW
│   └── plans/
│       └── plan.md                             # Implementation plan
├── dispatchers/
│   ├── intra_panel_rule_field_references.py   # Intra-panel dispatcher
│   └── rule_extraction_coding_agent.py        # Rule extraction dispatcher
├── adws/                                       # Workspace outputs
│   └── <timestamp>/
│       ├── templates_output/
│       │   └── <doc>_intra_panel_references.json
│       ├── populated_schema.json
│       └── extraction_report.json
└── orchestrator_rule_extraction.py            # Main orchestrator
```

## Usage

### Basic Usage

```bash
python3 orchestrator_rule_extraction.py \
  "documents/Vendor Creation Sample BUD.docx" \
  --schema output/complete_format/2581-schema.json
```

### With Options

```bash
python3 orchestrator_rule_extraction.py \
  "documents/Vendor Creation Sample BUD.docx" \
  --schema output/complete_format/2581-schema.json \
  --workspace adws/my-extraction \
  --verbose \
  --validate \
  --llm-threshold 0.7
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `document_path` | Yes | Path to BUD document (.docx) |
| `--schema` | Yes | Path to schema JSON from extract_fields_complete.py |
| `--workspace` | No | Custom workspace directory (default: adws/<timestamp>/) |
| `--verbose` | No | Enable verbose logging |
| `--validate` | No | Validate generated rules |
| `--llm-threshold` | No | Confidence threshold for LLM fallback (default: 0.7) |

## Pipeline Stages

### Stage 1: Intra-Panel Field References Extraction

**Purpose**: Extract within-panel field dependencies from BUD logic text

**Process**:
1. Parse BUD document using DocumentParser
2. Extract all fields organized by panel
3. Call Claude command for each panel separately
4. Detect field references in logic text
5. Consolidate results into single JSON

**Output**: `templates_output/<doc>_intra_panel_references.json`

**Output Format**:
```json
{
  "document_info": {...},
  "panels_analyzed": 12,
  "panel_results": [
    {
      "panel_name": "PAN and GST Details",
      "intra_panel_references": [
        {
          "source_field": {"field_name": "Please select GST option", ...},
          "target_field": {"field_name": "GSTIN", ...},
          "reference_details": {
            "relationship_type": "visibility_control",
            "operation_type": "controlled_by",
            "raw_expression": "if field 'GST option' is yes then visible"
          }
        }
      ]
    }
  ]
}
```

### Stage 2: Rule Extraction Coding Agent

**Purpose**: Implement complete rule extraction system to populate formFillRules

**Process**:
1. Read schema JSON (formFillMetadatas)
2. Read intra-panel references JSON
3. Implement logic parser, field matcher, rule tree, rule builders
4. Parse logic statements into structured data
5. Match field references to field IDs
6. Select rules using pattern matching (80%+ deterministic)
7. Fall back to LLM for complex cases (confidence < 70%)
8. Generate formFillRules JSON structures
9. Populate schema with generated rules

**Output**: `populated_schema.json`

**Output Format**:
```json
{
  "formFillMetadatas": [
    {
      "id": 275491,
      "name": "Please select GST option",
      "formFillRules": []
    },
    {
      "id": 275492,
      "name": "GSTIN",
      "formFillRules": [
        {
          "id": 119617,
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
      ]
    }
  ]
}
```

**Report**: `extraction_report.json`

```json
{
  "total_rules_generated": 330,
  "deterministic_coverage": 0.85,
  "llm_fallback_count": 45,
  "unmatched_fields": [],
  "rule_type_distribution": {
    "visibility_control": 120,
    "mandatory_control": 80,
    "validation": 50,
    "data_derivation": 40,
    "ocr_extraction": 25,
    "other": 15
  }
}
```

## Implementation Details

### Rule Extraction System Architecture

The coding agent implements the following architecture (see `.claude/plans/plan.md`):

```
Input → Logic Analysis → Rule Selection → Field Matching → Rule Generation → Output
  ↓          ↓                 ↓               ↓                ↓              ↓
Schema   Keywords/        Decision Tree    Fuzzy Match     Build JSON    Populated
+ Intra  Patterns         + LLM Fallback   Field IDs       Rules         Schema
Panel
```

### Key Components

1. **Logic Parser** (`logic_parser.py`)
   - Extracts keywords, conditions, field references from logic text
   - Handles patterns: visibility, mandatory, validation, OCR, derivation

2. **Rule Selection Tree** (`rule_tree.py`)
   - Deterministic rule selection based on keywords
   - Tree structure for visibility, mandatory, validation, OCR, etc.
   - 80%+ coverage without LLM

3. **Field Matcher** (`field_matcher.py`)
   - Fuzzy string matching using RapidFuzz
   - Exact match first, fuzzy match with 80% threshold
   - Handles variations in field names

4. **Rule Builders** (`rule_builders/`)
   - StandardRuleBuilder: actionType rules (MAKE_VISIBLE, etc.)
   - ValidationRuleBuilder: OCR/validation rules from Rule-Schemas.json

5. **LLM Fallback** (`llm_fallback.py`)
   - OpenAI integration for complex logic
   - Used when confidence < 70%
   - Handles nested conditions, multi-step logic

### Success Criteria

1. **Coverage**: Process 100% of logic statements
2. **Accuracy**: 95%+ correct rule selection
3. **Determinism**: 80%+ handled by pattern-based approach
4. **Performance**: < 5 seconds for Vendor Creation BUD
5. **Validation**: No unmatched field references

## Examples

### Example 1: Simple Conditional Visibility

**Logic**: "if the field 'Please select GST option' value is yes then visible and mandatory otherwise invisible and non-mandatory"

**Generated Rules**:
- MAKE_VISIBLE (condition: IN, value: "yes")
- MAKE_MANDATORY (condition: IN, value: "yes")
- MAKE_INVISIBLE (condition: NOT_IN, value: "yes")
- MAKE_NON_MANDATORY (condition: NOT_IN, value: "yes")

### Example 2: Validation + Editability

**Logic**: "Data will come from PAN validation. Non-Editable"

**Generated Rules**:
- VERIFY_PAN (STANDARD Rule #360)
- MAKE_DISABLED

## Troubleshooting

### Issue: Claude command not found
**Solution**: Ensure Claude CLI is installed and in PATH

### Issue: Output files not created
**Solution**: Check permissions on adws/ directory, verify input files are valid JSON

### Issue: Low deterministic coverage
**Solution**: Review logic patterns, add new patterns to rule tree, adjust LLM threshold

### Issue: Unmatched field references
**Solution**: Check field name variations, improve fuzzy matching threshold, verify intra-panel references

## Development

### Adding New Rule Patterns

1. Update `rule_tree.py` with new pattern keywords
2. Add rule builder in `rule_builders/`
3. Update tests in Phase 4

### Adding New Relationship Types

1. Update `RELATIONSHIP_TYPES` in logic parser
2. Add to decision tree traversal
3. Create corresponding rule builder

### Testing

```bash
# Test on Vendor Creation Sample BUD
python3 orchestrator_rule_extraction.py \
  "documents/Vendor Creation Sample BUD.docx" \
  --schema output/complete_format/2581-schema.json \
  --validate \
  --verbose

# Compare against expected output
diff adws/<timestamp>/populated_schema.json \
     documents/json_output/vendor_creation_sample_bud.json
```

## References

- Implementation Plan: `.claude/plans/plan.md`
- Coding Agent ADW: `.claude/agents/rule_extraction_coding_agent.md`
- Rule Schemas: `rules/Rule-Schemas.json` (182 rules)
- Rule Documentation: `RULES_REFERENCE.md`
- Intra-Panel Command: `.claude/commands/intra_panel_rule_field_references.md`

## License

Part of the Document Parser project for BUD document analysis.
