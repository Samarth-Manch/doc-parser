# Rule Extraction Orchestrator - Quick Start Guide

Get started with the self-healing rule extraction workflow in 5 minutes.

## Prerequisites

1. **Python 3.8+** installed
2. **Claude CLI** installed and configured
   ```bash
   claude --version
   ```
3. **Dependencies** installed
   ```bash
   pip install -r requirements.txt
   ```
4. **OpenAI API Key** (optional, for LLM fallback)
   ```bash
   export OPENAI_API_KEY=your-key-here
   ```

## Quick Start

### Step 1: Run the Orchestrator

```bash
python3 orchestrators/rule_extraction_workflow.py \
    "documents/Vendor Creation Sample BUD.docx"
```

This will:
1. Extract field dependencies
2. Generate rule extraction code
3. Run the code
4. Evaluate output
5. Self-heal if needed (up to 3 iterations)

### Step 2: Monitor Progress

Watch console output for each step:

```
============================================================
RULE EXTRACTION AI DEVELOPER WORKFLOW (ADWs)
============================================================

STEP 1: EXTRACT INTRA-PANEL FIELD REFERENCES
✓ Intra-panel references extracted
  Panels analyzed: 8

ITERATION 1 / 3
STEP 2: GENERATE RULE EXTRACTION CODE
✓ Code generated successfully

STEP 3: RUN GENERATED CODE
✓ Code executed successfully

STEP 4: EVALUATE OUTPUT
Phase 1: Deterministic Validation ✓
Phase 2: AI-Based Evaluation
  Exact match rate: 75%
  Semantic match rate: 85%
  Overall score: 82%
  Result: FAIL

STEP 5: GENERATE SELF-HEALING FEEDBACK
✓ Self-healing feedback generated

ITERATION 2 / 3
... (with improvements)
```

### Step 3: Check Results

Output directory: `adws/YYYY-MM-DD_HH-MM-SS/`

**If successful:**
- ✅ `populated_schema.json` - Your generated output
- ✅ `eval_report.json` - Shows 90%+ score
- ✅ `generated_code/` - Production-ready code

**If failed after 3 iterations:**
- ❌ Review `eval_report.json` for issues
- ❌ Check `self_heal_feedback.txt` for what went wrong
- ❌ Manually inspect `generated_code/` for bugs

## Understanding the Output

### populated_schema.json

This is your main output - the BUD schema with `formFillRules` arrays populated:

```json
{
  "all_fields": [
    {
      "name": "GSTIN",
      "field_type": "TEXT",
      "formFillRules": [
        {
          "actionType": "MAKE_VISIBLE",
          "sourceIds": [275491],
          "destinationIds": [275493],
          "conditionalValues": ["yes"],
          "condition": "IN"
        },
        {
          "actionType": "VERIFY",
          "sourceIds": [275493],
          "processingType": "SERVER"
        }
      ]
    }
  ]
}
```

### eval_report.json

Detailed evaluation metrics:

```json
{
  "evaluation_summary": {
    "overall_score": 0.92,
    "evaluation_passed": true
  },
  "coverage_metrics": {
    "field_coverage": 0.95,
    "rule_coverage": 0.90
  },
  "accuracy_metrics": {
    "exact_match_rate": 0.85,
    "semantic_match_rate": 0.92
  }
}
```

## Common Issues & Solutions

### Issue: Code Generation Fails

```
✗ Step 2 failed: Claude command not found
```

**Solution:**
```bash
# Verify Claude CLI is installed
claude --version

# If not, install it
npm install -g @anthropic-ai/claude-cli
# or
brew install claude-cli
```

### Issue: Code Execution Fails

```
✗ Step 3 failed: ModuleNotFoundError: No module named 'rapidfuzz'
```

**Solution:**
```bash
pip install rapidfuzz openai python-dotenv
```

### Issue: Low Evaluation Score

```
Overall Score: 75% (Threshold: 90%) - FAILED
```

**Solution:**
- Let it self-heal (it will retry automatically)
- After 3 iterations, check `self_heal_feedback.txt`
- Common issues:
  - Missing VERIFY rules → Add to logic parser
  - Wrong sourceIds → Improve field matching
  - Missing OCR rules → Add OCR pattern keywords

### Issue: Same Issues Every Iteration

```
Iteration 1: 75%
Iteration 2: 76%
Iteration 3: 75%
```

**Solution:**
- Review `eval_report.json` discrepancies section
- Check if coding agent is applying feedback
- Manually edit generated code in `generated_code/`
- Adjust pass threshold for debugging (in orchestrator code)

## Advanced Options

### Custom Output Directory

```bash
python3 orchestrators/rule_extraction_workflow.py \
    "documents/Your BUD.docx" \
    --output-dir "my_runs"
```

### More Iterations

```bash
python3 orchestrators/rule_extraction_workflow.py \
    "documents/Your BUD.docx" \
    --max-iterations 5
```

### Debug Mode

Add verbose logging to orchestrator:

```python
# In orchestrators/rule_extraction_workflow.py
# Set at top of file
import logging
logging.basicConfig(level=logging.DEBUG)
```

## What Gets Generated

The orchestrator produces a complete rule extraction system:

```
generated_code/
├── rule_extraction_agent.py              # CLI entry point
└── rule_extraction_agent/
    ├── __init__.py
    ├── models.py                         # Data models
    ├── logic_parser.py                   # Parse field logic text
    ├── field_matcher.py                  # Match fields by name/ID
    ├── rule_tree.py                      # Rule selection decision tree
    ├── rule_builders/
    │   ├── __init__.py
    │   ├── base_builder.py              # Base rule builder
    │   ├── standard_builder.py          # Standard rules (OCR, VERIFY, etc.)
    │   └── validation_builder.py        # Validation rules
    ├── llm_fallback.py                  # OpenAI integration
    ├── validators.py                     # Rule validation
    └── utils.py                          # Utilities
```

This code can be:
- ✅ Used standalone: `python3 generated_code/rule_extraction_agent.py --help`
- ✅ Integrated into pipelines
- ✅ Extended with custom rules
- ✅ Tested independently

## Next Steps

### 1. Test with Your BUD

```bash
python3 orchestrators/rule_extraction_workflow.py "path/to/your-bud.docx"
```

### 2. Review Generated Code

```bash
cd adws/latest_run/generated_code/
cat rule_extraction_agent/logic_parser.py
```

### 3. Integrate into Pipeline

```python
from adws.latest_run.generated_code import rule_extraction_agent

# Use in your workflow
agent = rule_extraction_agent.RuleExtractionAgent(schema_path)
populated = agent.extract_rules(logic_text)
```

### 4. Customize Rules

Edit generated code to add custom rules:

```python
# In generated_code/rule_extraction_agent/rule_builders/standard_builder.py

def build_custom_rule(self, logic: str, field: Field) -> Optional[Rule]:
    """Add your custom rule logic here."""
    if "your pattern" in logic.lower():
        return Rule(
            actionType="YOUR_ACTION",
            # ... rule properties
        )
    return None
```

## Performance Benchmarks

Based on Vendor Creation BUD (168 fields, 330+ rules):

- **Step 1**: 30-60 seconds (intra-panel extraction)
- **Step 2**: 2-5 minutes (code generation)
- **Step 3**: 5-10 seconds (code execution)
- **Step 4**: 1-3 minutes (evaluation)
- **Total (1 iteration)**: 4-8 minutes
- **Total (3 iterations)**: 12-25 minutes

## Success Metrics

Good workflow runs achieve:

- ✅ Overall score: 90-95%
- ✅ Exact match rate: 80-85%
- ✅ Semantic match rate: 90-95%
- ✅ Field coverage: 95-100%
- ✅ Zero critical issues

## Getting Help

1. **Check logs**: Console output shows each step
2. **Review eval report**: `eval_report.json` has detailed feedback
3. **Read orchestrator README**: `orchestrators/README.md`
4. **Check reference docs**:
   - `RULES_REFERENCE.md` - Rule types and patterns
   - `.claude/agents/rule_extraction_coding_agent.md` - Coding agent guide
   - `.claude/commands/eval_rule_extraction.md` - Evaluation guide

## Best Practices

1. **Start with reference BUD**: Use Vendor Creation Sample BUD first
2. **Let it self-heal**: Don't intervene until max iterations reached
3. **Review patterns**: Look for systematic issues in eval reports
4. **Archive successful runs**: Keep for comparison and reference
5. **Iterate on feedback**: Use self-heal feedback to improve coding agent

---

**You're ready to go!** 🚀

Run the orchestrator and watch the AI generate production-ready rule extraction code with self-healing capabilities.

```bash
python3 orchestrators/rule_extraction_workflow.py "documents/Vendor Creation Sample BUD.docx"
```
