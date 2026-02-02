---
name: Eval Panel Rules
allowed-tools: Read, Write, Bash
description: Panel-by-panel evaluation of generated formFillRules against reference output. Checks field matching and rule correctness within each panel.
---

# Eval Panel Rules - Detailed Panel-by-Panel Comparison

## Objective

Perform **granular panel-by-panel evaluation** of generated rule extraction output against human-made reference. For each panel, check:
1. All expected fields are present
2. Each field has correct formFillRules
3. Rules have correct actionType, sourceIds, destinationIds, and conditions

This provides detailed feedback for self-healing iterations.

---

## Input

You will be provided with:
1. **Generated Output Path**: Path to populated schema JSON from rule extraction agent
2. **Reference Output Path**: Path to human-made reference (e.g., vendor_creation_sample_bud.json)
3. **Eval Report Output Path**: Where to save the detailed evaluation report

**First action**: Read both JSON files.

---

## Evaluation Strategy

### Panel-by-Panel Approach

For EACH panel in the document:

1. **Extract panel fields from both outputs**
   - Generated panel fields
   - Reference panel fields

2. **Match fields by name/ID**
   - Use fuzzy matching (80% similarity)
   - Handle variations like "PAN" vs "PAN Number"

3. **For each matched field, compare rules:**
   - Rule count (generated vs reference)
   - Rule types (actionType distribution)
   - Source/destination field IDs
   - Conditional values and logic
   - Execution flags (executeOnFill, etc.)

4. **Identify discrepancies:**
   - Missing rules (in reference but not in generated)
   - Extra rules (in generated but not in reference)
   - Incorrect rules (wrong sourceIds, destinationIds, conditions)
   - Semantically equivalent but structurally different rules

5. **Generate panel-specific feedback**

---

## Panel Comparison Algorithm

```python
for each panel in document:
    reference_fields = get_panel_fields(reference, panel_name)
    generated_fields = get_panel_fields(generated, panel_name)

    # Match fields
    common_fields = match_fields(reference_fields, generated_fields)
    missing_fields = reference_fields - common_fields
    extra_fields = generated_fields - common_fields

    for each field in common_fields:
        reference_rules = get_rules(reference, field)
        generated_rules = get_rules(generated, field)

        # Compare rules
        for ref_rule in reference_rules:
            matching_generated = find_matching_rule(generated_rules, ref_rule)

            if not matching_generated:
                mark_as_missing_rule(field, ref_rule)
            elif not exact_match(matching_generated, ref_rule):
                if semantic_match(matching_generated, ref_rule):
                    mark_as_semantic_equivalent(field, ref_rule, matching_generated)
                else:
                    mark_as_incorrect_rule(field, ref_rule, matching_generated)

        # Check for extra rules in generated
        for gen_rule in generated_rules:
            if not find_matching_rule(reference_rules, gen_rule):
                mark_as_extra_rule(field, gen_rule)
```

---

## Rule Matching Criteria

### Exact Match

Two rules match exactly if ALL properties are identical:
- actionType
- sourceIds (same IDs, same order)
- destinationIds (same IDs, same order)
- conditionalValues (same values, same order)
- condition (e.g., "IN", "NOT_IN", "EQUALS")
- processingType (CLIENT or SERVER)

### Semantic Match

Two rules are semantically equivalent if they produce the same behavior even if structure differs slightly:

| Reference | Generated | Verdict |
|-----------|-----------|---------|
| condition: "EQUALS", values: ["yes"] | condition: "IN", values: ["yes"] | SEMANTIC_MATCH (both check for "yes") |
| condition: "IN", values: ["yes", "no"] | condition: "IN", values: ["no", "yes"] | SEMANTIC_MATCH (order doesn't matter) |
| sourceIds: [A, B] | sourceIds: [B, A] | MISMATCH (order matters for sources) |
| destinationIds: [X, Y] | destinationIds: [Y, X] | SEMANTIC_MATCH (order doesn't matter for destinations if actionType is the same) |

### Field ID Matching

When comparing sourceIds/destinationIds:
1. **Exact match preferred**: Same field ID
2. **Name-based match**: If IDs differ but field names match
3. **Fuzzy match**: If names are 85%+ similar
4. **Positional match**: If fields are in same position within panel

---

## Output Format

### Panel Evaluation Report

```json
{
  "panel_name": "Basic Details",
  "panel_summary": {
    "reference_field_count": 10,
    "generated_field_count": 10,
    "common_fields": 10,
    "missing_fields": 0,
    "extra_fields": 0,
    "total_reference_rules": 45,
    "total_generated_rules": 42,
    "matched_rules": 38,
    "missing_rules": 7,
    "extra_rules": 4,
    "incorrect_rules": 3,
    "semantic_matches": 5
  },
  "field_evaluations": [
    {
      "field_name": "GSTIN",
      "field_id_reference": 275493,
      "field_id_generated": 275493,
      "match_status": "EXACT",
      "rule_comparison": {
        "reference_rule_count": 6,
        "generated_rule_count": 4,
        "exact_matches": 2,
        "semantic_matches": 1,
        "missing_rules": 3,
        "extra_rules": 0,
        "incorrect_rules": 1
      },
      "missing_rules": [
        {
          "actionType": "VERIFY",
          "severity": "high",
          "description": "GSTIN verification rule missing",
          "recommendation": "Add VERIFY rule with sourceIds: [275493], processingType: SERVER"
        }
      ],
      "incorrect_rules": [
        {
          "actionType": "MAKE_VISIBLE",
          "issue": "Wrong sourceId",
          "reference_sourceIds": [275491],
          "generated_sourceIds": [275490],
          "recommendation": "Update sourceIds to [275491] - should reference 'GST Option' field"
        }
      ],
      "semantic_matches": [
        {
          "actionType": "MAKE_MANDATORY",
          "reference": {
            "condition": "EQUALS",
            "conditionalValues": ["yes"]
          },
          "generated": {
            "condition": "IN",
            "conditionalValues": ["yes"]
          },
          "note": "Both achieve same behavior - minor structural difference"
        }
      ]
    }
  ],
  "missing_fields": [],
  "extra_fields": [],
  "panel_score": 0.85,
  "panel_passed": false,
  "critical_issues": [
    "GSTIN field missing VERIFY rule (high priority)",
    "3 fields have incorrect sourceIds"
  ]
}
```

### Complete Evaluation Report

```json
{
  "evaluation_metadata": {
    "generated_output": "adws/2026-01-30_14-30-45/populated_schema.json",
    "reference_output": "documents/json_output/vendor_creation_sample_bud.json",
    "evaluation_timestamp": "2026-01-30T14:35:00Z",
    "total_panels": 8
  },
  "overall_summary": {
    "total_fields_reference": 168,
    "total_fields_generated": 165,
    "common_fields": 160,
    "missing_fields": 8,
    "extra_fields": 5,
    "total_rules_reference": 330,
    "total_rules_generated": 285,
    "exact_matches": 210,
    "semantic_matches": 45,
    "missing_rules": 75,
    "extra_rules": 15,
    "incorrect_rules": 30,
    "overall_score": 0.82,
    "pass_threshold": 0.90,
    "evaluation_passed": false
  },
  "panel_evaluations": [
    /* Array of panel evaluation objects */
  ],
  "critical_issues_summary": {
    "high_severity": [
      "Basic Details panel: 3 fields missing VERIFY rules",
      "Bank Details panel: Incorrect sourceIds for 5 fields",
      "Address Details panel: 2 fields missing OCR rules"
    ],
    "medium_severity": [
      "12 fields have semantic equivalent but different structure",
      "5 fields have extra rules not in reference"
    ],
    "low_severity": [
      "15 condition types use IN instead of EQUALS for single values"
    ]
  },
  "self_heal_instructions": {
    "priority_fixes": [
      {
        "priority": "HIGH",
        "panel": "Basic Details",
        "issue": "Missing VERIFY rules for validation fields",
        "affected_fields": ["GSTIN", "PAN", "Bank Account"],
        "fix": "Add VERIFY action detection in logic parser - keywords: 'validate', 'verification', 'check against'",
        "file_to_modify": "rule_extraction_agent/logic_parser.py",
        "code_snippet": "Add to VALIDATION_KEYWORDS: ['validate', 'verification', 'verify against', 'check validity']"
      },
      {
        "priority": "HIGH",
        "panel": "Bank Details",
        "issue": "Incorrect sourceIds - referencing wrong control fields",
        "affected_fields": ["IFSC Code", "Branch", "Account Type", "Account Number", "Bank Name"],
        "fix": "Improve field matching in FieldMatcher - use intra-panel references to identify correct source fields",
        "file_to_modify": "rule_extraction_agent/field_matcher.py",
        "code_snippet": "Increase fuzzy match threshold to 85% for control fields, use dependency graph from intra_panel_references"
      }
    ],
    "medium_priority_fixes": [
      {
        "priority": "MEDIUM",
        "issue": "Semantic equivalents using different condition operators",
        "affected_count": 15,
        "fix": "Standardize condition operators - use EQUALS for single-value conditions instead of IN",
        "file_to_modify": "rule_extraction_agent/rule_builders/standard_builder.py"
      }
    ],
    "low_priority_fixes": [
      {
        "priority": "LOW",
        "issue": "Extra rules not in reference",
        "affected_count": 5,
        "fix": "Review rule generation logic to avoid generating redundant rules"
      }
    ]
  },
  "detailed_recommendations": [
    "1. Add VERIFY action detection for fields with validation logic - check Rule-Schemas.json for VERIFY rule patterns",
    "2. Fix field ID matching by cross-referencing intra-panel dependencies",
    "3. Implement OCR pattern detection for file upload fields",
    "4. Standardize condition operators (prefer EQUALS for single values)",
    "5. Add validation to check generated field IDs exist in schema"
  ]
}
```

---

## Scoring Algorithm

### Panel Score Calculation

```
panel_score = (
    0.4 * (exact_matches / total_reference_rules) +
    0.3 * (semantic_matches / total_reference_rules) +
    0.2 * (1 - (missing_rules / total_reference_rules)) +
    0.1 * (1 - (incorrect_rules / total_reference_rules))
)
```

### Overall Score Calculation

```
overall_score = average(panel_scores)
```

### Pass Criteria

- `overall_score >= 0.90`
- No HIGH severity issues > 5
- No CRITICAL severity issues

---

## Severity Classification

| Severity | Condition | Examples |
|----------|-----------|----------|
| **CRITICAL** | Core functionality broken | Invalid JSON, syntax errors, missing all rules |
| **HIGH** | Important rules missing | VERIFY rules, OCR rules, validation rules |
| **MEDIUM** | Incorrect but functional | Wrong sourceIds, suboptimal conditions |
| **LOW** | Semantic equivalents | EQUALS vs IN for single values |
| **INFO** | Suggestions only | Code style, optimization opportunities |

---

## Console Output

```
================================================================
PANEL-BY-PANEL RULE EXTRACTION EVALUATION
================================================================
Generated: adws/2026-01-30_14-30-45/populated_schema.json
Reference: documents/json_output/vendor_creation_sample_bud.json

Overall Score: 82% (Threshold: 90%) - FAILED
----------------------------------------------------------------

Panel Scores:
  ✓ Basic Details           : 88% (10/10 fields, 42/45 rules)
  ✗ Bank Details            : 72% (8/10 fields, 35/48 rules) - HIGH issues
  ✓ Address Details         : 90% (12/12 fields, 55/58 rules)
  ✓ Tax Details             : 85% (6/6 fields, 28/32 rules)
  ✗ Contact Details         : 75% (8/8 fields, 30/38 rules) - MEDIUM issues
  ✓ Attachment Details      : 92% (5/5 fields, 22/24 rules)
  ✓ Approval Workflow       : 95% (3/3 fields, 15/15 rules)
  ✓ Additional Information  : 88% (4/4 fields, 18/20 rules)

Critical Issues by Panel:
  Bank Details (5 issues):
    - 5 fields have incorrect sourceIds
    - 3 fields missing VERIFY rules

  Contact Details (3 issues):
    - 2 fields missing validation rules
    - 1 field has extra unnecessary rule

Top Recommendations:
  1. Fix sourceId mapping in Bank Details panel
  2. Add VERIFY rule detection for validation fields
  3. Add OCR pattern keywords for file upload fields

================================================================
Detailed report saved to: adws/2026-01-30_14-30-45/eval_report.json
================================================================
```

---

## Hard Constraints

* Compare panel-by-panel for granular feedback
* Use semantic matching - don't penalize equivalent rules
* Provide actionable fix instructions with file names and code snippets
* Calculate meaningful scores at panel and overall levels
* Generate self-heal instructions that coding agent can directly use
* Output JSON report in the specified detailed format
* Include panel scores in console summary
* Highlight which panels have critical issues

---

## Integration with Orchestrator

The orchestrator will:
1. Run this eval command after code execution
2. Parse the eval report JSON
3. Check if evaluation passed (overall_score >= 0.90)
4. If failed, extract self_heal_instructions
5. Pass feedback to coding agent for next iteration
6. Repeat until success or max iterations reached

---

This granular panel-by-panel evaluation ensures the rule extraction system achieves high accuracy by providing specific, actionable feedback for each panel and field.
