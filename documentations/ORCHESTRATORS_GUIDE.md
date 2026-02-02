# Orchestrators Guide

This document explains the different orchestrators available in the Document Parser project and when to use each one.

## What is an Orchestrator?

An **orchestrator** is a high-level workflow automation script that combines multiple tools, skills, and agents to accomplish complex tasks end-to-end. Unlike simple dispatchers that just call a single Claude skill, orchestrators manage multi-step workflows with:

- Multiple tool invocations
- Conditional logic
- Iteration and self-healing
- Quality gates and validation
- Artifact management

## Available Orchestrators

### 1. Rule Extraction Workflow

**File:** `orchestrators/rule_extraction_workflow.py`

**Purpose:** Generate production-ready rule extraction code from BUD documents with automatic self-healing.

**What it does:**
1. Extracts intra-panel field dependencies
2. Generates rule extraction code using coding agent
3. Runs the generated code
4. Evaluates output (deterministic + AI-based)
5. Self-heals based on feedback
6. Iterates until success (max 3 iterations)

**When to use:**
- You need to generate formFillRules from a BUD document
- You want AI-generated code that improves itself
- You need high accuracy (90%+ match with reference)
- You want a complete end-to-end workflow

**Usage:**
```bash
python3 orchestrators/rule_extraction_workflow.py "documents/Your BUD.docx"
```

**Output:**
- Generated rule extraction code module
- Populated schema with formFillRules
- Evaluation reports
- Self-healing feedback

**Typical runtime:** 4-25 minutes (1-3 iterations)

---

## Comparison: Orchestrators vs Dispatchers vs Skills

| Feature | Orchestrator | Dispatcher | Skill |
|---------|-------------|-----------|-------|
| **Complexity** | High - multi-step workflows | Medium - single workflow step | Low - specific task |
| **Iterations** | Yes - self-healing loops | No - single execution | No - single execution |
| **Tools** | Multiple (Bash, Claude, Python) | 1-2 (Python parser + Claude) | 1 (Claude only) |
| **Validation** | Multi-phase with quality gates | Basic output validation | None |
| **Feedback Loop** | Yes - automatic self-healing | No | No |
| **Use Case** | End-to-end AI development | BUD analysis with Claude | Specific analysis task |

### Examples

**Skill:** `/intra_panel_rule_field_references`
- Takes: Pre-extracted field data
- Returns: Intra-panel dependencies
- Time: 1-3 minutes

**Dispatcher:** `dispatchers/intra_panel_rule_field_references.py`
- Parses BUD document
- Calls `/intra_panel_rule_field_references` skill
- Returns: Consolidated JSON output
- Time: 2-5 minutes

**Orchestrator:** `orchestrators/rule_extraction_workflow.py`
- Runs dispatcher for intra-panel refs
- Generates code with coding agent
- Executes code
- Evaluates output
- Self-heals and retries
- Returns: Production-ready code + populated schema
- Time: 4-25 minutes

---

## When to Use Each Approach

### Use a Skill (/command) When:
- ✅ You have pre-extracted data ready
- ✅ You need a quick one-time analysis
- ✅ You're experimenting or debugging
- ✅ You want to call it from other tools

### Use a Dispatcher When:
- ✅ You need to parse BUD + analyze in one step
- ✅ You want automated data extraction before analysis
- ✅ You need consolidated output from multiple panels
- ✅ You're building a simple pipeline

### Use an Orchestrator When:
- ✅ You need end-to-end automation
- ✅ You want code generation with validation
- ✅ You need self-healing capabilities
- ✅ Quality matters more than speed
- ✅ You're building production workflows

---

## Future Orchestrators (Planned)

### 2. Form Builder Validation Workflow

**Purpose:** Automated QA validation of generated form builders

**Planned Steps:**
1. Parse BUD document
2. Extract expected fields and panels
3. Navigate to QA form builder
4. Compare against BUD (visual)
5. Generate discrepancy report
6. Auto-fix mismatches (if possible)

**Status:** Planned (dispatcher exists: `compare_form_builders.py`)

### 3. Complete Document Processing Workflow

**Purpose:** End-to-end BUD processing from DOCX to deployed form

**Planned Steps:**
1. Parse BUD
2. Extract all fields and metadata
3. Generate formFillRules (via rule extraction orchestrator)
4. Create form builder JSON
5. Deploy to environment
6. Validate deployment
7. Run smoke tests

**Status:** Concept

### 4. Multi-BUD Batch Processing Workflow

**Purpose:** Process multiple BUD documents in parallel

**Planned Steps:**
1. Scan directory for BUD documents
2. Launch parallel orchestrators
3. Aggregate results
4. Generate comparison report
5. Identify common patterns

**Status:** Concept

---

## Architecture Patterns

### Pattern 1: Linear Workflow

```
Step 1 → Step 2 → Step 3 → Done
```

**Example:** Simple data extraction

**Use for:** Quick, deterministic tasks

### Pattern 2: Iterative Self-Healing

```
Step 1 → Step 2 → Eval → Pass? → Done
                     ↓ Fail
                  Feedback
                     ↓
                  Step 2 (retry with feedback)
```

**Example:** Rule extraction workflow

**Use for:** AI code generation, complex transformations

### Pattern 3: Parallel + Merge

```
Step 1 → [Step 2a, Step 2b, Step 2c] → Merge → Done
```

**Example:** Multi-panel analysis

**Use for:** Independent parallel tasks

### Pattern 4: Conditional Branching

```
Step 1 → Check? → Branch A → Done
            ↓
         Branch B → Done
```

**Example:** Different logic for different BUD types

**Use for:** Workflows with variants

---

## Best Practices for Orchestrators

### 1. Idempotency

Make steps re-runnable without side effects:

```python
# Good: Check if output exists first
if not output_file.exists():
    generate_output()

# Bad: Always regenerate
generate_output()
```

### 2. Artifact Management

Save intermediate outputs for debugging:

```python
# Save each step's output
step1_output = run_step1()
save_artifact("step1_output.json", step1_output)

step2_output = run_step2(step1_output)
save_artifact("step2_output.json", step2_output)
```

### 3. Clear Progress Reporting

Show user what's happening:

```python
print("="*70)
print(f"STEP {n}: {step_name}")
print("="*70)

# ... do work ...

print(f"✓ {step_name} completed")
```

### 4. Error Recovery

Handle failures gracefully:

```python
try:
    result = risky_operation()
except Exception as e:
    log_error(e)
    # Try alternative approach
    result = fallback_operation()
```

### 5. Timestamped Outputs

Never overwrite previous runs:

```python
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
output_dir = f"adws/{timestamp}"
```

---

## Creating Your Own Orchestrator

### Template Structure

```python
#!/usr/bin/env python3
"""
Your Orchestrator Name

Description of what this orchestrator does.
"""

import argparse
import json
import subprocess
from pathlib import Path
from datetime import datetime


class YourOrchestrator:
    """Main orchestrator class."""

    def __init__(self, input_path: str, output_dir: str = None):
        self.input_path = input_path
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.output_dir = Path(output_dir or "adws") / timestamp
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def step_1_your_first_step(self) -> bool:
        """Description of step 1."""
        print("\n" + "="*70)
        print("STEP 1: YOUR FIRST STEP")
        print("="*70)

        try:
            # Do the work
            result = do_something()

            print(f"✓ Step 1 completed")
            return True

        except Exception as e:
            print(f"✗ Step 1 failed: {e}")
            return False

    def run_workflow(self):
        """Run the complete workflow."""
        print("\n" + "="*70)
        print("YOUR ORCHESTRATOR WORKFLOW")
        print("="*70)

        if not self.step_1_your_first_step():
            print("\n✗ Workflow failed at Step 1")
            return False

        # ... more steps ...

        print("\n✓ WORKFLOW SUCCEEDED!")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Your orchestrator description"
    )
    parser.add_argument("input_path", help="Input file path")
    parser.add_argument("-o", "--output-dir", default="adws")

    args = parser.parse_args()

    orchestrator = YourOrchestrator(
        input_path=args.input_path,
        output_dir=args.output_dir
    )

    success = orchestrator.run_workflow()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

### Key Components

1. **Timestamped output directory**
2. **Step methods** returning bool for success/failure
3. **Progress printing** with visual separators
4. **Exception handling** in each step
5. **CLI argument parsing**
6. **Main workflow method** orchestrating all steps

---

## Integration with CI/CD

Orchestrators can be integrated into automated pipelines:

```yaml
# .github/workflows/rule-extraction.yml
name: Rule Extraction

on:
  push:
    paths:
      - 'documents/**/*.docx'

jobs:
  extract-rules:
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
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: workflow-output
          path: adws/

      - name: Check success
        run: |
          # Fail CI if orchestrator failed
          exit $?
```

---

## Summary

| Aspect | Skill | Dispatcher | Orchestrator |
|--------|-------|-----------|--------------|
| **Abstraction Level** | Low | Medium | High |
| **User Interaction** | Manual | Semi-automated | Fully automated |
| **Error Handling** | User fixes | Basic retry | Self-healing |
| **Typical Use** | One-off analysis | Batch processing | Production workflows |
| **Output Quality** | Varies | Good | Excellent (validated) |
| **Development Effort** | Low | Medium | High |

**Choose based on your needs:**
- Quick task? → Use skill
- Automate analysis? → Use dispatcher
- Production workflow? → Use orchestrator

---

For detailed documentation on the rule extraction orchestrator, see:
- `orchestrators/README.md` - Technical architecture
- `ORCHESTRATOR_QUICKSTART.md` - Getting started guide
