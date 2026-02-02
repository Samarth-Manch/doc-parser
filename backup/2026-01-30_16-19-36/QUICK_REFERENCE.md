# Quick Reference - Rule Extraction

## ✅ Status: Self-Healing Complete

All issues fixed. 103 rules generated across 40 fields. Output validated.

---

## Run Rule Extraction

```bash
./adws/2026-01-30_16-19-36/run_corrected_extraction.sh
```

---

## Verify Output

```bash
# Check formFillRules count
grep -c "formFillRules" adws/2026-01-30_16-19-36/populated_schema.json
# Expected: 40

# Validate structure
python3 adws/2026-01-30_16-19-36/validate_structure.py
# Expected: 6/6 checks passed

# View statistics
cat adws/2026-01-30_16-19-36/extraction_report.json
```

---

## Key Files

| File | Purpose |
|------|---------|
| `populated_schema.json` | ✅ Final output with formFillRules |
| `extraction_report.json` | Statistics (103 rules, 0 unmatched) |
| `run_corrected_extraction.sh` | Execute rule extraction |
| `validate_structure.py` | Validate output structure |
| `FINAL_SUMMARY.md` | Complete details |
| `generated_code/` | Rule extraction agent code |

---

## Results Summary

```
✓ 103 rules generated
✓ 40 fields with formFillRules
✓ 100% field matching (0 unmatched)
✓ 32 high confidence rules (>80%)
✓ 71 medium confidence rules (50-80%)
✓ 0 low confidence rules (<50%)
✓ 6/6 validation checks passed
```

---

## What Was Fixed

1. **Schema File**: Now uses `vendor_creation_schema.json` (template) instead of parsed BUD
2. **formFillRules**: Properly populated in schema structure
3. **Field IDs**: Correctly mapped (22110xxx format)
4. **Output Format**: Matches reference structure exactly

---

## Input Files

- BUD Document: `documents/Vendor Creation Sample BUD.docx`
- Intra-Panel Refs: `adws/2026-01-30_16-19-36/intra_panel_references.json`
- Schema Template: `documents/json_output/vendor_creation_schema.json`
- Reference Output: `documents/json_output/vendor_creation_sample_bud.json`

---

## Output Files

- Populated Schema: `adws/2026-01-30_16-19-36/populated_schema.json`
- Extraction Report: `adws/2026-01-30_16-19-36/extraction_report.json`
- Generated Code: `adws/2026-01-30_16-19-36/generated_code/`

---

## Next Steps

### Evaluate Output
```bash
python3 dispatchers/eval_rule_extraction.py \
  --generated adws/2026-01-30_16-19-36/populated_schema.json \
  --reference documents/json_output/vendor_creation_sample_bud.json
```

### Review Generated Rules
```bash
# Open populated_schema.json and inspect formFillRules arrays
# Compare with reference: documents/json_output/vendor_creation_sample_bud.json
```

---

## Documentation

- **Quick Reference**: This file
- **Final Summary**: `FINAL_SUMMARY.md` - Complete details
- **Fix Summary**: `generated_code/FIX_SUMMARY.md` - What was fixed
- **README**: `generated_code/README.md` - Agent documentation

---

## Support

If you encounter issues:

1. Check extraction logs: `adws/2026-01-30_16-19-36/extraction_log.txt`
2. Review statistics: `extraction_report.json`
3. Validate structure: `python3 validate_structure.py`
4. See detailed docs: `FINAL_SUMMARY.md`
