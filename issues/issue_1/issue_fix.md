# Inter-Panel Dispatcher — Issue Fix Verification (Run 6)

## Summary

The three issues documented in `issue.md` — alternate key names, nested `references` sub-arrays, and garbage refs — have been **fixed and verified** in run 6 (`output/vendor/runs/6/inter_panel/`). The dispatcher was also rewritten from v2 (two-pass global architecture) to v3 (panel-by-panel parallel architecture).

---

## Fix Verification: Issue by Issue

### Issue 1: Alternate Key Names Not Recognized — FIXED

**Evidence:**
- Run 6 detection outputs use varying key names across panels:
  - Bank Details uses `classification` (e.g., `"classification": "visibility/state"`)
  - Vendor Basic Details uses `type` + `classification` (e.g., `"type": "complex"`, `"classification": "derivation"`)
  - Address Details uses `reference_type` (e.g., `"reference_type": "visibility_state"`)
- All 14 Address Details refs and all 8 Vendor Basic Details refs were normalized correctly — no empty `field_variableName` or `"unknown"` referenced fields in the Phase 2 input.

**Code change:** `_normalize_single_ref()` now checks `destination_variableName`, `referenced_variableName`, `destination_field`, `referenced_field`, `reference_type`, `complexity`, and maps `visibility_state` -> `visibility`.

### Issue 2: Nested `references` Sub-Array Format — FIXED

**Evidence:**
- Address Details detection output (run 6) uses the nested format:
  ```json
  {
    "field_name": "Street",
    "field_variableName": "_streetaddressdetails_",
    "references": [
      {"referenced_panel": "PAN and GST Details", "reference_type": "visibility_state", ...},
      {"referenced_panel": "PAN and GST Details", "reference_type": "derivation", ...}
    ]
  }
  ```
- The normalizer flattened these into individual refs: Street got 2 refs (visibility + derivation from Building Number), Street 1 got 2 refs, etc.
- **Result: Address Details — 14 refs detected** (vs. 0 in the broken state).

**Code change:** `normalize_detection_output()` checks for `'references' in ref` and iterates sub-refs, merging parent `field_variableName`/`field_name` into each sub-ref via `setdefault`.

### Issue 3: Garbage Refs Polluting Phase 2 — FIXED

**Evidence:**
- Run 6 master log shows no filtering messages, meaning normalization produced clean refs upstream — the garbage filter had nothing to catch.
- All 39 Phase 1 refs passed to Phase 2 had valid `field_variableName` values (verified in `complex_*_refs.json` files).
- The PAN and GST Details group had 19 clean refs (including all 14 Address Details refs grouped under PAN as source panel), and the expression agent produced 10 rules covering visibility, derivation, mandatory, and clearing.

**Code change:** Post-Phase-1 filter removes any refs with empty `field_variableName` before Phase 2 grouping.

---

## Run 6 vs Run 5 Comparison

| Metric | Run 5 (v2, before) | Run 6 (v3, after) |
|--------|--------------------|--------------------|
| Architecture | Two-pass global (single LLM call per pass) | Panel-by-panel parallel (6 workers) |
| Phase 1 refs detected | 20 (global analysis) | 39 (per-panel detection) |
| Address Details refs | Included (as complex refs 5-7) | 14 refs (nested format handled) |
| Bank Details refs | Not separately tracked | 6 refs |
| Vendor Basic Details refs | Not separately tracked | 8 refs |
| Inter-panel rules created | 20 | 18 |
| Total rules in output | 125 | 119 |
| Runtime | 21m 37s | 26m 36s |

### Rules Present in Both Runs (8 shared patterns)
- `Account Group/Vendor Type` -> Service-Based Invoice Verification derivation
- `Select the process type` -> CIN/MSME/Withholding Tax visibility
- `PAN` -> Title derivation, Recipient Type derivation, CIN mandatory, clear derived fields
- `Please select GST option` -> Address visibility, GST address derivation, clearing

### New in Run 6 (5 new rule patterns)
- `Name/ First Name of the Organization` -> Vendor Basic Details 4-field name split derivation
- `Process Type` -> Bank Details visibility + Bank Country/Currency derivation
- `Vendor Domestic or Import` -> Title/Withholding Tax visibility
- `Minority Indicator` <-> `Terms of Payment` cross-validation error rules (bidirectional)
- `Please select GST option` -> Street/Postal Code mandatory rules
- `ID Type` -> FDA Registration Number mandatory (upgraded from visibility)

### Missing from Run 6 (7 rules lost vs run 5)
- `Company Code` -> Copy To Purchase Org (ref detected but agent merged into simpler handling)
- `Company Code` -> House Bank derivation (mapping table: 1000->CIT01, etc.)
- `Company Code` -> House Bank clearing
- `Group key/Corporate Group` -> Minority Indicator derivation
- `Select the process type` -> Currency derivation (subsumed by Process Type derivation)
- `Select the process type` -> Currency/Bank Country clearing
- `ID Type` -> FDA visibility (replaced by mandatory rule in run 6)

### Root Causes of Missing Rules
1. **Payment Details detection timed out** — no output file was produced, so Currency derivation from Payment Details perspective and House Bank/Minority Indicator derivation from that panel's detection were lost. Other panels' detections partially compensated (MSME detected 1 ref to Payment Details).
2. **Company Code copy_to ref detected but not fully expanded** — the ref `Company Code -> Purchase Org` was classified as `copy_to` (1 of the 39 refs). It was converted to a `ctfd` expression, but the agent treated it as a simple copy and didn't generate the House Bank derivation chain that run 5's global context captured.
3. **Different grouping strategy** — v3 groups by source panel, so `Basic Details` group had 19 refs from 7 destination panels. The agent consolidated some visibility rules (process type + vendor domestic/import) differently than v2's single global call.

---

## Architecture Changes (v2 -> v3)

| Aspect | v2 | v3 |
|--------|----|----|
| Phase 1 | Single global LLM call with all 158 fields | 11 parallel per-panel LLM calls (6 workers) |
| Phase 2 | Single LLM call for all 20 complex refs | 3 calls grouped by source panel (19+19+1 refs) |
| Parallelism | Sequential passes | ThreadPoolExecutor with configurable workers |
| Normalization | Assumed fixed output format | Handles 4+ output format variants |
| Thread safety | N/A | Added `_log_lock` for concurrent log writes |
| Context window | All panels in one context (~30K chars) | Per-panel context + compact index |

---

## Files Changed

- `dispatchers/agents/inter_panel_dispatcher.py` — Full rewrite from v2 to v3:
  - Added `build_all_panels_index()`, `normalize_detection_output()`, `_normalize_single_ref()`, `_build_normalized_ref()`
  - Added `ThreadPoolExecutor` for parallel Phase 1 detection
  - Added garbage ref filter between Phase 1 and Phase 2
  - Added Phase 2 grouping by source panel (`group_complex_refs_by_source_panel`)
- `dispatchers/agents/inter_panel_utils.py`:
  - Added `build_compact_single_panel_text()` for per-panel detection input
  - Added `group_complex_refs_by_source_panel()` for Phase 2 grouping

---

## Conclusion

All three normalizer issues are confirmed fixed. The v3 architecture successfully detects refs across all output format variants (flat, nested, alternate keys, array format). Address Details — the primary failure case — went from 0 refs to 14 refs. The garbage filter is in place as a safety net.

However, the new architecture introduced 2 detection timeouts (Vendor Duplicity Details, Payment Details) and the source-panel grouping strategy causes some rule coverage gaps compared to v2's global approach. These are separate issues from the normalizer bugs and represent trade-offs of the new architecture.
