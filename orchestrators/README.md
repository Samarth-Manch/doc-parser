---
# Rule Extraction AI Developer Workflow (ADWs) Orchestrator

Automated self-healing workflow for generating rule extraction code from BUD documents.

## Overview

This orchestrator implements a complete AI Developer Workflow that:
1. Extracts intra-panel field dependencies from BUD
2. Generates rule extraction code using Claude coding agent
3. Runs the generated code
4. Evaluates output against reference (deterministic + AI-based)
5. Self-heals based on evaluation feedback
6. Iterates until success (max 3 iterations)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Workflow                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Extract Intra-Panel Field References                │
│   ├─ Run: dispatchers/intra_panel_rule_field_references.py  │
│   ├─ Skill: /intra_panel_rule_field_references              │
│   └─ Output: intra_panel_references.json                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ ITERATION LOOP (max 3 iterations)                           │
└─────────────────────────────────────────────────────────────┘
    │
    ├─► ┌────────────────────────────────────────────────────┐
    │   │ STEP 2: Generate Rule Extraction Code              │
    │   │   ├─ Skill: /rule_extraction_coding_agent          │
    │   │   ├─ Input: BUD + Intra-panel refs + Feedback      │
    │   │   └─ Output: generated_code/                       │
    │   └────────────────────────────────────────────────────┘
    │                       │
    │                       ▼
    ├─► ┌────────────────────────────────────────────────────┐
    │   │ STEP 3: Run Generated Code                         │
    │   │   ├─ Execute: rule_extraction_agent.py             │
    │   │   └─ Output: populated_schema.json                 │
    │   └────────────────────────────────────────────────────┘
    │                       │
    │                       ▼
    ├─► ┌────────────────────────────────────────────────────┐
    │   │ STEP 4: Evaluate Output                            │
    │   │   ├─ Phase 1: Deterministic checks                 │
    │   │   │   ├─ Valid JSON structure                      │
    │   │   │   ├─ Required fields present                   │
    │   │   │   └─ Rule properties complete                  │
    │   │   ├─ Phase 2: AI-based evaluation                  │
    │   │   │   ├─ Skill: /eval_rule_extraction              │
    │   │   │   ├─ Panel-by-panel comparison                 │
    │   │   │   ├─ Semantic matching                         │
    │   │   │   └─ Discrepancy detection                     │
    │   │   └─ Output: eval_report.json                      │
    │   └────────────────────────────────────────────────────┘
    │                       │
    │               ┌───────┴────────┐
    │               │   Evaluation   │
    │               │     Passed?    │
    │               └───────┬────────┘
    │                 YES   │   NO
    │                   │   │
    │   ┌───────────────┘   └────────────────┐
    │   │                                     │
    │   ▼                                     ▼
    │ ┌───────────────┐         ┌────────────────────────────┐
    │ │   SUCCESS!    │         │ STEP 5: Generate Self-Heal │
    │ │  Exit with 0  │         │   ├─ Extract feedback      │
    │ └───────────────┘         │   └─ Pass to next iteration│
    │                           └────────────────────────────┘
    │                                     │
    └─────────────────────────────────────┘
                (Next Iteration)
```

## Usage

### Basic Usage

```bash
python3 orchestrators/rule_extraction_workflow.py "documents/Vendor Creation Sample BUD.docx"
```

### With Custom Output Directory

```bash
python3 orchestrators/rule_extraction_workflow.py \
    "documents/Vendor Creation Sample BUD.docx" \
    --output-dir "my_workflow_runs"
```

### With Custom Max Iterations

```bash
python3 orchestrators/rule_extraction_workflow.py \
    "documents/Vendor Creation Sample BUD.docx" \
    --max-iterations 5
```

## Output Structure

Each workflow run creates a timestamped directory in `adws/`:

```
adws/
└── 2026-01-30_14-30-45/
    ├── intra_panel_temp/                  # Temp intra-panel extraction
    │   └── Vendor_Creation_Sample_BUD_intra_panel_references.json
    ├── intra_panel_references.json        # Consolidated intra-panel refs
    ├── schema.json                        # Parsed BUD schema
    ├── generated_code/                    # Generated rule extraction code
    │   ├── rule_extraction_agent.py       # Main entry point
    │   ├── rule_extraction_agent/         # Module directory
    │   │   ├── __init__.py
    │   │   ├── models.py
    │   │   ├── logic_parser.py
    │   │   ├── field_matcher.py
    │   │   ├── rule_tree.py
    │   │   ├── rule_builders/
    │   │   │   ├── __init__.py
    │   │   │   ├── base_builder.py
    │   │   │   ├── standard_builder.py
    │   │   │   └── validation_builder.py
    │   │   ├── llm_fallback.py
    │   │   ├── validators.py
    │   │   └── utils.py
    │   └── README.md                      # Generated code documentation
    ├── populated_schema.json              # Final output with formFillRules
    ├── eval_report.json                   # Evaluation report
    └── self_heal_feedback.txt             # Feedback for next iteration
```

## Workflow Steps Explained

### Step 1: Extract Intra-Panel Field References

Uses the intra-panel dispatcher to analyze field dependencies within each panel.

**Purpose:** Identify which fields control other fields (e.g., "GST Option" controls "GSTIN" visibility)

**Output:** JSON with field relationships, controlling fields, and dependency types

### Step 2: Generate Rule Extraction Code

Calls Claude with the `/rule_extraction_coding_agent` skill to generate production-ready code.

**Inputs:**
- BUD document path
- Intra-panel references
- Reference output (vendor_creation_sample_bud.json)
- Self-healing feedback (if retry)

**Output:** Complete Python module implementing rule extraction system

**Key Context Provided:**
- How formFillRules are structured (from reference JSON)
- Rule types and action types (from RULES_REFERENCE.md)
- Field matching strategies
- Logic parsing patterns

### Step 3: Run Generated Code

Executes the generated `rule_extraction_agent.py` script.

**Command:**
```bash
python3 generated_code/rule_extraction_agent.py \
    --schema schema.json \
    --intra-panel intra_panel_references.json \
    --output populated_schema.json \
    --verbose
```

**Expected Output:** JSON file with formFillRules arrays populated for each field

### Step 4: Evaluate Output

Two-phase evaluation:

#### Phase 1: Deterministic Checks

Fast validation of basic requirements:
- ✓ Valid JSON structure
- ✓ Has fields with formFillRules
- ✓ Rules have required properties (actionType, sourceIds, destinationIds)

#### Phase 2: AI-Based Evaluation

Calls Claude with `/eval_rule_extraction` skill for intelligent comparison:
- Panel-by-panel comparison
- Semantic rule matching (not just structural)
- Field ID mapping validation
- Missing/incorrect rule detection
- Generates detailed feedback

**Output:** eval_report.json with:
- Coverage metrics (field coverage, rule coverage)
- Accuracy metrics (exact match, semantic match rates)
- Discrepancies (missing rules, incorrect mappings)
- Self-heal instructions (priority fixes, code changes)

### Step 5: Self-Heal (If Needed)

If evaluation fails, generates feedback for the coding agent:

**Feedback Includes:**
- Priority fixes with affected fields
- Specific code changes needed (file + function + approach)
- High severity issues with recommendations
- Pattern detection improvements needed

**Passes to Step 2** for next iteration with enhanced context.

## Self-Healing Mechanism

The orchestrator implements automatic self-healing through feedback loops:

### Iteration 1: Initial Attempt

```
Generate code → Run → Evaluate (fails: 82%)
Issues: Missing VERIFY rules, wrong sourceIds
```

### Iteration 2: Self-Heal

```
Generate code (with feedback about VERIFY rules and sourceId matching)
→ Run → Evaluate (improves: 88%)
Issues: Still some OCR rules missing
```

### Iteration 3: Final Fix

```
Generate code (with cumulative feedback)
→ Run → Evaluate (passes: 92%)
Success!
```

## Evaluation Metrics

### Coverage Metrics

- **Field Coverage**: % of reference fields that have rules in generated output
- **Rule Coverage**: % of reference rules matched in generated output

### Accuracy Metrics

- **Exact Match Rate**: % of rules matching exactly (structure + values)
- **Semantic Match Rate**: % of rules achieving same behavior
- **False Positive Rate**: % of generated rules that are incorrect

### Quality Metrics

- **Source/Destination Correctness**: % rules with correct field mappings
- **Condition Correctness**: % rules with correct conditional logic
- **ActionType Correctness**: % rules with correct action types

### Pass Criteria

```python
overall_score >= 0.90 AND
critical_issues == 0 AND
high_severity_issues <= 5
```

## Reference Files Used

The orchestrator and coding agent use these reference files:

1. **documents/json_output/vendor_creation_sample_bud.json**
   - Gold standard for rule structure
   - 330+ real-world formFillRules examples
   - Shows how rules are applied to fields

2. **RULES_REFERENCE.md**
   - 182 predefined rule schemas
   - Rule types, action types, clusters
   - Logic patterns and keywords
   - Field matching strategies

3. **.claude/agents/rule_extraction_coding_agent.md**
   - Implementation guidelines
   - Module structure
   - Hard constraints
   - Success criteria

4. **.claude/commands/eval_rule_extraction.md**
   - Evaluation strategy
   - Metrics calculation
   - Severity classification
   - Self-heal instruction format

## Success Criteria

The workflow succeeds when:

1. **Code Compiles & Runs**: No syntax/runtime errors
2. **Valid Output**: JSON structure matches schema
3. **High Coverage**: 90%+ of fields have rules
4. **High Accuracy**: 90%+ of rules are correct or semantically equivalent
5. **No Critical Issues**: All field IDs valid, core rules present
6. **Pass Threshold**: Overall score >= 90%

## Troubleshooting

### Code Generation Fails

**Symptom:** Step 2 fails, no code generated

**Possible Causes:**
- Claude API unavailable
- Coding agent skill not found
- Insufficient context

**Solution:**
- Check claude CLI is working: `claude --version`
- Verify skill exists: `.claude/agents/rule_extraction_coding_agent.md`
- Check reference files are readable

### Code Execution Fails

**Symptom:** Step 3 fails, syntax or runtime errors

**Possible Causes:**
- Missing dependencies (rapidfuzz, openai)
- Import errors
- Incorrect file paths

**Solution:**
- Install dependencies: `pip install rapidfuzz openai python-dotenv`
- Check generated code structure
- Verify schema.json and intra_panel_references.json exist

### Evaluation Never Passes

**Symptom:** Score improves but never reaches 90%

**Possible Causes:**
- Reference output has different structure
- Field ID mapping issues
- Logic parsing gaps

**Solution:**
- Review eval_report.json for patterns
- Check if same issues repeat across iterations
- Manual inspection of top discrepancies
- Adjust pass threshold temporarily for debugging

### Self-Heal Not Improving

**Symptom:** Same issues in every iteration

**Possible Causes:**
- Feedback not specific enough
- Coding agent not applying feedback
- Structural mismatch in approach

**Solution:**
- Review self_heal_feedback.txt
- Check if priority_fixes are being addressed
- Manual code review to identify gaps
- Provide more specific code snippets in feedback

## Advanced Usage

### Custom Evaluation Threshold

Modify `step_4_evaluate_output()` to adjust pass threshold:

```python
# Default: 0.90 (90%)
pass_threshold = 0.85  # Lower for testing
```

### Skip Iterations (Direct Run)

For testing generated code without regeneration:

```python
orchestrator = RuleExtractionOrchestrator(bud_path)
orchestrator.step_1_extract_intra_panel_references()
# Manually place code in generated_code/
orchestrator.step_3_run_generated_code()
orchestrator.step_4_evaluate_output()
```

### Custom Reference Output

To use a different reference output:

```python
orchestrator.reference_output = Path("custom/reference.json")
```

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Rule Extraction Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run orchestrator
        run: |
          python3 orchestrators/rule_extraction_workflow.py \
            "documents/Vendor Creation Sample BUD.docx" \
            --max-iterations 3
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: workflow-output
          path: adws/
```

## Future Enhancements

- [ ] Parallel rule evaluation for faster feedback
- [ ] Rule confidence scoring
- [ ] Automated regression testing suite
- [ ] Web UI for monitoring workflow progress
- [ ] Support for multiple BUD formats
- [ ] Incremental rule generation (panel-by-panel)
- [ ] Rule diff visualization
- [ ] Performance benchmarking

## License

Part of the Document Parser project.

## Support

For issues or questions, check:
- Project README.md
- RULES_REFERENCE.md
- .claude/agents/rule_extraction_coding_agent.md

---

**Built with Claude Code** 🚀
