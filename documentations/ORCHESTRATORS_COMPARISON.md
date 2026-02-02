# Orchestrators Comparison

Two orchestrators are available for rule extraction: **Basic** and **Self-Healing**.

## Quick Comparison

| Feature | Basic Orchestrator | Self-Healing Orchestrator |
|---------|-------------------|---------------------------|
| **File** | `orchestrator_rule_extraction.py` | `orchestrator_self_healing.py` |
| **Purpose** | Generate code and run once | Generate, evaluate, and self-heal |
| **Stages** | 2 (Extract → Generate) | 3 (Extract → Generate → Eval) |
| **Self-Healing** | ✗ No | ✓ Yes (up to N iterations) |
| **Evaluation** | ✗ No | ✓ Yes (Claude intelligence) |
| **Reference Required** | ✗ No | ✓ Yes (human-made JSON) |
| **Quality Gate** | ✗ No | ✓ Yes (pass/fail) |
| **Exit Code** | Always 0 | 0 = pass, 1 = fail |
| **Use Case** | Development, prototyping | Production, CI/CD |
| **Speed** | Fast (1 run) | Slower (multiple iterations) |
| **Accuracy** | Unknown | Measured & improved |

## Visual Comparison

### Basic Orchestrator
```
Input → Intra-Panel → Code Generation → Output
         (Stage 1)        (Stage 2)        (Done)
```

### Self-Healing Orchestrator
```
Input → Intra-Panel → Code Generation → Evaluation → Pass? → Output
         (Stage 1)        (Stage 2)       (Stage 3)     ↓
                                                        Fail
                                                         ↓
                           Code Fix ← Self-Heal ← Feedback
                             (Stage 2)  Instructions
                                 ↓
                              Repeat (max N times)
```

## Usage Examples

### Basic Orchestrator

```bash
# Simple run - no evaluation
python3 orchestrator_rule_extraction.py \
  "documents/Vendor Creation Sample BUD.docx" \
  --schema output/complete_format/2581-schema.json
```

**Output**:
- `adws/<timestamp>/populated_schema.json`
- `adws/<timestamp>/templates_output/*.json`

**Best for**:
- Quick testing
- Development iteration
- When reference output unavailable
- Manual review preferred

### Self-Healing Orchestrator

```bash
# Self-healing run with evaluation
python3 orchestrator_self_healing.py \
  "documents/Vendor Creation Sample BUD.docx" \
  --schema output/complete_format/2581-schema.json \
  --reference documents/json_output/vendor_creation_sample_bud.json
```

**Output**:
- `adws/<timestamp>/populated_schema_vN.json` (final version)
- `adws/<timestamp>/eval_report_v*.json` (all iterations)
- `adws/<timestamp>/self_heal_instructions_v*.json`
- Exit code: 0 (pass) or 1 (fail)

**Best for**:
- Production deployment
- CI/CD pipelines
- High accuracy requirements
- Automated quality gates
- Continuous improvement

## Decision Guide

### Choose Basic Orchestrator If:

✓ You're in active development
✓ You want fast iteration cycles
✓ You don't have reference output yet
✓ You prefer manual review
✓ You're prototyping or experimenting

### Choose Self-Healing Orchestrator If:

✓ You have human-made reference output
✓ You need measurable accuracy
✓ You want automated quality control
✓ You're deploying to production
✓ You want CI/CD integration
✓ You need pass/fail gates
✓ You want continuous improvement

## Performance Comparison

| Metric | Basic | Self-Healing |
|--------|-------|--------------|
| **Time to Complete** | 30-60s | 2-5 min (3 iterations) |
| **Accuracy** | Unknown | 90-95% (measured) |
| **Manual Review Needed** | Yes | Minimal |
| **Iterations** | 1 | 1-N (typically 2-3) |
| **Feedback Loop** | Manual | Automatic |
| **Quality Assurance** | Manual | Automatic |

## File Outputs

### Basic Orchestrator

```
adws/<timestamp>/
├── templates_output/
│   └── <doc>_intra_panel_references.json
├── populated_schema.json              # Single output
└── extraction_report.json
```

### Self-Healing Orchestrator

```
adws/<timestamp>/
├── templates_output/
│   └── <doc>_intra_panel_references.json
├── populated_schema.json              # v1
├── populated_schema_v2.json           # v2 (if iter 2)
├── populated_schema_v3.json           # v3 (if iter 3) - FINAL
├── extraction_report_v1.json
├── extraction_report_v2.json
├── eval_report_v1.json                # Evaluation results
├── eval_report_v2.json
├── eval_report_v3.json
├── self_heal_instructions_v2.json     # Fix instructions
└── self_heal_instructions_v3.json
```

## Command-Line Options Comparison

### Common Options (Both)

| Option | Description |
|--------|-------------|
| `document_path` | BUD document path (required) |
| `--schema` | Schema JSON path (required) |
| `--workspace` | Custom workspace directory |
| `--verbose` | Enable verbose logging |
| `--validate` | Validate generated rules |
| `--llm-threshold` | LLM fallback threshold |

### Self-Healing Only

| Option | Description | Default |
|--------|-------------|---------|
| `--reference` | Reference JSON (required) | - |
| `--max-iterations` | Max self-heal iterations | 3 |
| `--threshold` | Evaluation pass threshold | 0.90 |

## Exit Codes

### Basic Orchestrator
- Always exits with `0` (success if code generated)
- No quality validation

### Self-Healing Orchestrator
- Exits `0` if evaluation **passes** (score >= threshold)
- Exits `1` if evaluation **fails** (score < threshold or max iterations)
- Useful for CI/CD pipelines

## CI/CD Integration

### Basic (Not Recommended)
```bash
# No quality gate
python3 orchestrator_rule_extraction.py input.docx --schema schema.json
# Always succeeds if runs
```

### Self-Healing (Recommended)
```bash
# With quality gate
python3 orchestrator_self_healing.py \
  input.docx \
  --schema schema.json \
  --reference expected.json \
  --threshold 0.95

# Fails CI if score < 95%
if [ $? -eq 0 ]; then
    echo "✓ Quality gate passed"
else
    echo "✗ Quality gate failed"
    exit 1
fi
```

## Evolution Path

```
Start Here                     Production Ready
    ↓                                ↓

Development                    Deployment
    │                                │
    ├─→ Basic Orchestrator          │
    │   • Fast iteration            │
    │   • Manual review             │
    │                                │
    └─→ Create reference ──→ Self-Healing Orchestrator
            output              • Automated QA
                                • Self-healing
                                • CI/CD ready
```

## Recommended Workflow

### Phase 1: Development (Use Basic)
1. Use basic orchestrator for rapid iteration
2. Manually review outputs
3. Create/refine reference output
4. Document expected behavior

### Phase 2: Testing (Switch to Self-Healing)
1. Switch to self-healing orchestrator
2. Use created reference output
3. Let system self-heal and improve
4. Review eval reports
5. Refine thresholds

### Phase 3: Production (Self-Healing Only)
1. Integrate into CI/CD
2. Set appropriate thresholds
3. Monitor eval scores
4. Update references as needed

## Summary

| Scenario | Recommended Orchestrator |
|----------|-------------------------|
| Active development | **Basic** |
| Quick prototyping | **Basic** |
| Manual testing | **Basic** |
| Regression testing | **Self-Healing** |
| Production deployment | **Self-Healing** |
| CI/CD pipeline | **Self-Healing** |
| Quality assurance | **Self-Healing** |
| Automated testing | **Self-Healing** |

## Documentation

- **Basic Orchestrator**: [ORCHESTRATOR_README.md](ORCHESTRATOR_README.md)
- **Self-Healing**: [SELF_HEALING_README.md](SELF_HEALING_README.md)
- **Quick Start**: [QUICKSTART_ORCHESTRATOR.md](QUICKSTART_ORCHESTRATOR.md)

---

**Start with Basic for speed, graduate to Self-Healing for quality.** 🎯
