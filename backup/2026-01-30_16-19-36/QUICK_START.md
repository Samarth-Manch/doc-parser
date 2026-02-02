# Rule Extraction Agent - Quick Start Guide

## What Was Built

A complete rule extraction system that automatically generates `formFillRules` from BUD document logic text.

## Directory Structure

```
/home/samart/project/doc-parser/adws/2026-01-30_16-19-36/
├── generated_code/                    # Main implementation
│   ├── models.py                      # Data models
│   ├── logic_parser.py                # Logic text parser
│   ├── field_matcher.py               # Fuzzy field matching
│   ├── rule_tree.py                   # Rule selection tree
│   ├── rule_builders/                 # Rule generators
│   ├── main.py                        # Main agent
│   ├── rule_extraction_agent.py       # CLI entry point
│   └── README.md                      # Full documentation
├── populated_schema.json              # OUTPUT: Schema with rules
├── extraction_report.json             # OUTPUT: Statistics
├── intra_panel_references.json        # INPUT: Field dependencies
└── IMPLEMENTATION_SUMMARY.md          # This summary
```

## Quick Run

```bash
cd /home/samart/project/doc-parser/adws/2026-01-30_16-19-36/generated_code

python3 rule_extraction_agent.py \
  --schema /home/samart/project/doc-parser/documents/json_output/vendor_creation_schema.json \
  --intra-panel ../intra_panel_references.json \
  --output ../populated_schema.json \
  --report ../extraction_report.json
```

## Results

**Input:**
- 168 fields in schema
- 55 field dependencies in intra_panel_references.json

**Output:**
- 103 formFillRules generated
- 40 fields populated with rules
- 100% field match rate
- 0% low confidence rules
- Processing time: < 2 seconds

## Generated Rule Types

| Action Type | Count | Description |
|------------|-------|-------------|
| COPY_TO | 25 | Copy value from source to destination |
| VERIFY_MSME | 22 | MSME validation |
| MAKE_DISABLED | 22 | Make field non-editable |
| MAKE_VISIBLE | 14 | Show field conditionally |
| MAKE_INVISIBLE | 12 | Hide field conditionally |
| MAKE_MANDATORY | 5 | Make field required |
| VERIFY_PINCODE | 3 | PIN code validation |

## Example Generated Rule

```json
{
  "id": 119617,
  "createUser": "FIRST_PARTY",
  "updateUser": "FIRST_PARTY",
  "actionType": "MAKE_VISIBLE",
  "processingType": "CLIENT",
  "sourceIds": [22110043],
  "destinationIds": [22110044],
  "conditionalValues": ["yes"],
  "condition": "IN",
  "conditionValueType": "TEXT",
  "executeOnFill": true,
  "executeOnRead": false,
  "executeOnEsign": false
}
```

## Key Features

1. **Natural Language Parsing** - Understands BUD logic text
2. **Fuzzy Field Matching** - 80% similarity threshold
3. **Decision Tree** - Deterministic rule selection
4. **If/Else Support** - Generates both true/false rules
5. **Confidence Scoring** - Tracks extraction confidence
6. **Deduplication** - Removes duplicate rules
7. **Comprehensive Logging** - Detailed processing logs

## Files to Check

1. **populated_schema.json** - Your main output (128 KB)
   - Contains all 168 fields
   - 40 fields have formFillRules arrays
   - 103 rules total

2. **extraction_report.json** - Statistics
   ```json
   {
     "statistics": {
       "total_references": 55,
       "rules_generated": 103,
       "high_confidence": 32,
       "medium_confidence": 71,
       "low_confidence": 0,
       "unmatched_fields": []
     }
   }
   ```

3. **generated_code/README.md** - Full documentation

## Verification

Run the verification script:

```bash
cd /home/samart/project/doc-parser/adws/2026-01-30_16-19-36
python3 verify_output.py
```

## Next Steps

### To Use This System on New BUDs

1. Parse BUD document to extract fields (use existing parser)
2. Generate intra_panel_references.json (use existing tools)
3. Run rule_extraction_agent.py with your schema
4. Review populated_schema.json output
5. Check extraction_report.json for statistics

### To Extend Functionality

1. **Add New Rule Types** - Update ActionType enum in models.py
2. **Add New Logic Patterns** - Update LogicParser keywords
3. **Customize Rule Selection** - Modify RuleTree handlers
4. **Add LLM Fallback** - Implement llm_fallback.py (planned)

## Support

- Full documentation: `/generated_code/README.md`
- Implementation details: `/IMPLEMENTATION_SUMMARY.md`
- Code is well-commented and type-hinted

## Dependencies

```bash
pip install rapidfuzz
```

## Success Metrics

- ✅ 100% field matching (0 unmatched fields)
- ✅ 103 rules generated from 55 references
- ✅ 0% low confidence rules
- ✅ < 2 seconds processing time
- ✅ Valid formFillRule JSON format
- ✅ Production-quality code with error handling

---

**Status**: ✅ Complete and Working
**Date**: January 30, 2026
**Total Lines of Code**: 2000+
**Files Created**: 14
