# Inter-Panel Dispatcher — Normalizer Issues & Fixes

## Problem Summary

The Phase 1 detection agents produce correct cross-panel references, but the normalizer (`normalize_detection_output` / `_normalize_single_ref`) fails to parse them because the detection agent uses **different key names and output structures** across runs. This causes valid refs to be silently discarded, resulting in 0 rules for panels like Address Details.

---

## Issue 1: Alternate Key Names Not Recognized

### Symptom
All Address Details refs had empty `field_variableName`, empty `field_name`, `referenced_field_variableName: "unknown"` after normalization — even though the raw detection output contained all the correct data.

### Root Cause
The detection agent uses different key names than the normalizer expected:

| Detection agent output key | Normalizer looked for |
|---|---|
| `destination_variableName` | `field_variableName`, `variable_name`, `field_variable_name`, `variableName` |
| `destination_field` | `field_name` |
| `referenced_variableName` | `referenced_field_variableName`, `target_field`, `source_field` |
| `referenced_field` | `referenced_field_name`, `target_field` |
| `reference_type` | `classification`, `reference_classification` |
| `complexity` | `type` |
| `visibility_state` | (not mapped to any valid classification) |

Since none of the alternate keys matched, the normalizer returned empty strings for all field identifiers.

### Fix
Added the missing key lookups to `_normalize_single_ref()`:

```python
# classification now checks: classification, reference_classification, reference_type
# field_variableName now checks: ..., destination_variableName
# referenced_field_variableName now checks: ..., referenced_variableName
# field_name now checks: field_name, destination_field
# referenced_field_name now checks: referenced_field_name, referenced_field, target_field
# type now checks: type, complexity
# visibility_state mapped to 'visibility'
```

---

## Issue 2: Nested `references` Sub-Array Format Not Handled

### Symptom
Address Details detection returned `"cross_panel_references": [...]` with correct key — but normalizer returned 0 refs. The `_normalize_single_ref()` check `if not referenced_panel` returned `None` for every entry.

### Root Cause
The detection agent sometimes outputs a **nested format** where each entry in `cross_panel_references` groups multiple sub-references under a single field:

```json
{
  "cross_panel_references": [
    {
      "field_name": "Street",
      "variableName": "_streetaddressdetails_",
      "references": [
        {
          "referenced_panel": "PAN and GST Details",
          "referenced_variableName": "_streetpanandgstdetails_",
          "reference_type": "derivation",
          ...
        },
        {
          "referenced_panel": "PAN and GST Details",
          "referenced_variableName": "_gstinimagepanandgstdetails_",
          "reference_type": "state",
          ...
        }
      ]
    }
  ]
}
```

The normalizer iterated over `cross_panel_references`, treating each entry as a flat ref. But these entries don't have `referenced_panel` at the top level — it's nested inside `references`. So `_normalize_single_ref()` couldn't find `referenced_panel` and returned `None` for every entry.

### Fix
Added nested format handling in the normalization loop:

```python
for ref in refs_raw:
    if 'references' in ref and isinstance(ref['references'], list):
        # Nested format: flatten by merging parent field info into each sub-ref
        parent_var = ref.get('variableName') or ref.get('field_variableName') or ''
        parent_name = ref.get('field_name') or ref.get('destination_field') or ''
        for sub_ref in ref['references']:
            merged = dict(sub_ref)
            merged.setdefault('field_variableName', parent_var)
            merged.setdefault('destination_variableName', parent_var)
            merged.setdefault('field_name', parent_name)
            merged.setdefault('destination_field', parent_name)
            norm = _normalize_single_ref(merged, valid_panel_set)
            if norm:
                normalized_refs.append(norm)
    else:
        # Flat format: normalize directly
        norm = _normalize_single_ref(ref, valid_panel_set)
        ...
```

---

## Issue 3: Garbage Refs Polluting Phase 2 Agent Context

### Symptom
Phase 2 "PAN and GST Details" group had 13 refs, but 12 were garbage (empty `field_variableName`, empty `logic_snippet`, `referenced_field_variableName: "unknown"`). The expression agent was overwhelmed and only handled the 1 good ref (Title derivation), ignoring address copy rules entirely.

### Root Cause
When normalization failed (Issues 1 & 2 above), refs were created with empty fields but still passed through to Phase 2 because the normalizer didn't filter them — it just returned refs with empty strings.

### Fix
Added a post-Phase-1 filter that removes refs with empty `field_variableName` before Phase 2:

```python
pre_filter = len(all_refs)
simple_refs = [r for r in simple_refs if r.get('field_variableName')]
complex_refs = [r for r in complex_refs if r.get('field_variableName')]
all_refs = [r for r in all_refs if r.get('field_variableName')]
filtered_out = pre_filter - len(all_refs)
if filtered_out:
    log(f"  Filtered out {filtered_out} refs with empty field_variableName (kept {len(all_refs)})")
```

---

## Impact

### Before fixes (run at 17:34)
- Address Details: **0 refs detected** (nested format discarded all 9)
- PAN and GST Details group: 5 refs (only Title + CIN/TDS, no address copies)
- Total rules created: **5**

### After fixes (expected)
- Address Details: **15 refs detected** (9 fields, some with multiple sub-refs)
- PAN and GST Details group: ~20 refs (Title + CIN/TDS + all address copies)
- Garbage refs filtered before Phase 2
- Expression agent gets clean, well-identified refs with proper field names and variableNames

---

## Why Detection Output Format Varies

The detection agent (`inter_panel_detect_refs.md`) specifies a strict output format, but the LLM doesn't always follow it exactly. Across runs, we've observed **4 different output structures**:

1. **Expected flat format**: `{panel_name, cross_panel_references: [{field_variableName, referenced_panel, ...}]}`
2. **Array format**: `[{field_name, variableName, detected_references: [{target_panel, ...}]}]`
3. **Alternate key names**: Same structure but `destination_variableName` instead of `field_variableName`, `reference_type` instead of `classification`, etc.
4. **Nested sub-refs**: `{panel_name, cross_panel_references: [{field_name, variableName, references: [{referenced_panel, ...}]}]}`

The normalizer now handles all 4 formats. The garbage filter acts as a safety net for any future format variations the normalizer might miss.

---

## Files Changed

- `dispatchers/agents/inter_panel_dispatcher.py`
  - `_normalize_single_ref()`: Added `destination_variableName`, `referenced_variableName`, `destination_field`, `referenced_field`, `reference_type`, `complexity`, `visibility_state` key mappings
  - `normalize_detection_output()`: Added nested `references` sub-array flattening
  - `main()`: Added garbage ref filter (empty `field_variableName`) between Phase 1 and Phase 2
