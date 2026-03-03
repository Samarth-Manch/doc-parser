# Issue 3 — TODO

Action items derived from the Block/Unblock BUD (Run 3) issue analysis.

---

## 1. Inter-Panel Dispatcher: Group Phase 2 Refs by Source Field, Not Source Panel

**Issue ref:** A1 — Duplicate Rule Explosion (16 rules on one field)

**Problem:** The inter-panel dispatcher groups complex refs by `referenced_panel` (the panel the source field lives in). In this BUD, 6 sub-panels all reference the same source field (`Which function you would like to Update?` in Vendor Details). The dispatcher creates 7 separate Phase 2 agent calls — one for the Vendor Details group and one for each of the 6 sub-panels. Each agent call independently creates its own visibility + clearing rules on the same source field, resulting in 16 rules where there should be ~4.

The merge deduplication only catches exact-match duplicates, so rules that express the same intent with slightly different expression strings all survive.

**What needs to change:** The Phase 2 grouping logic in `inter_panel_utils.py` (`group_complex_refs_by_source_panel`) should group by the **source field** (the field where rules will be placed) rather than by the target panel. When multiple refs from different target panels all point to the same source field, they should be combined into a single group so one agent call produces one comprehensive rule covering all target panels.

**Expected outcome:** One agent call handles all 6 target panels together, producing a single consolidated visibility rule and a single clearing rule on `Which function you would like to Update?`, instead of 15 redundant expression rules.

**Note:** This is a structural change to how Phase 2 work is divided. The grouping key changes from "which panel is the source field in" to "which specific field is the source field." This may affect how the Phase 2 agent prompt receives its context — instead of getting "all refs from panel X," it would get "all refs that place rules on field Y."

---

## 2. Expression Rule Agent: Include All Child Fields in Panel Visibility Rules

**Issue ref:** A2 — Inconsistent Visibility Rules

**Problem:** When the expression rule agent creates visibility rules (`mvi`/`minvi`) targeting a PANEL variable, it sometimes includes all child fields of that panel and sometimes only includes the panel variable itself. In Run 3, agents 5 and 6 correctly listed the panel variable plus all 6-7 child fields in the `mvi`/`minvi` call, while agents 2, 3, 4, and 7 only listed the panel variable. The agents that produced panel-only rules also had empty log files (just a header line), suggesting the LLM skipped the intermediate reasoning steps.

**What needs to change:** The expression rule agent prompt (`expression_rule_agent.md`) needs an explicit instruction: when creating `mvi`/`minvi` rules that target a PANEL-type field, always enumerate and include ALL child fields belonging to that panel in the same `mvi`/`minvi` call. The agent should look up which fields have variableNames containing the panel's variableName pattern (or are structurally children of the panel) and include every one of them.

Currently the agent prompt has no guidance on panel-level visibility at all. The agent sometimes figures out the child field inclusion on its own (agents 5, 6 did it correctly) and sometimes doesn't (agents 2, 3, 4, 7). Making this an explicit, mandatory step in the prompt will eliminate the inconsistency.

**Expected outcome:** Every `mvi`/`minvi` call that targets a PANEL variable also targets all fields belonging to that panel, ensuring the panel and its contents are shown/hidden together consistently.

---

## 3. Inter-Panel Dispatcher: Handle Nested `source_field`/`referenced_field` Detection Format

**Issue ref:** A3 — Phase 1 Detection Format Mismatch

**Problem:** The Phase 1 detection agent for the `Block / Unblock posting all company code` panel returned a different JSON structure than expected. Instead of flat keys (`referenced_panel`, `field_variableName`), it returned nested objects:

```
{
  "source_field": { "field_name": "...", "variableName": "...", "panel": "..." },
  "referenced_field": { "field_name": "...", "variableName": "...", "panel": "..." }
}
```

The normalizer (`_normalize_single_ref`) only looks for flat keys and does not handle this nested object format. All 3 valid refs from this panel were silently discarded, showing "0 refs detected" in the master log despite the output file containing valid data.

**What needs to change:** The normalizer needs to recognize and flatten this nested format. When a ref contains `source_field` or `referenced_field` as objects (dictionaries), the normalizer should extract:
- `field_variableName` from `source_field.variableName`
- `field_name` from `source_field.field_name`
- `referenced_panel` from `referenced_field.panel`
- `referenced_field_variableName` from `referenced_field.variableName`

This is similar to the nested `references` sub-array format that was already fixed (documented in issue_1), but it's a different nesting pattern that the current normalizer still does not handle.

**Expected outcome:** Refs in the nested `source_field`/`referenced_field` format are correctly normalized and passed to Phase 2, recovering the 3 lost refs from `posting all company code`.

---

## 4. Recover Mandatory Rules for "posting all company code"

**Issue ref:** A4 — Missing Mandatory Rules

**Problem:** Because the posting all panel's Phase 1 detection was lost (due to the format mismatch in TODO #3), its mandatory rule for `Posting block new` was also lost. The BUD states: "if 'Which function you would like to Update?' value is 'Block / Unblock posting all company code' then [Posting block new] is mandatory, otherwise non-mandatory."

No mandatory rule exists for this field in the Run 3 output.

**What needs to change:** This is a cascading failure from TODO #3. Once the nested format is handled and the posting all panel's refs are recovered, the mandatory rule should be naturally generated by the Phase 2 agent.

**Expected outcome:** After fixing TODO #3, re-running should produce a mandatory rule on `Posting block new` in the posting all panel.

**Verification:** After re-run, check that an `mm`/`mnm` rule exists for `_postingblocknewblockunblockpostingallcompanycode_` driven by the "Which function" field.

---

## 5. BUD Issue: "True False" Dropdowns Missing Reference Table Name

**Issue ref:** B1 — Wrong EDV Table for "block new" / "posting block new" Fields

**Problem:** All 6 "block new" fields across the sub-panels have identical BUD logic: `"Dropdown Values - True False"`. The logic does not mention any reference table name. The agent has no way of knowing that a `TRUE_FALSE` EDV table exists on the platform — it is not in the embedded reference tables, not mentioned in any field logic, and not documented anywhere in the BUD. The agent is forced to guess, and the results are inconsistent:
- 3 fields got `TRUE_FALSE` (lucky guess)
- 2 fields got `VC_COMPANY_DETAILS a7` (copied from the neighboring "old" field)
- 1 field got `VC_PAYMENT_BLOCK` (hallucinated a non-existent table)

This is not an agent prompt issue. The agent cannot be expected to infer a platform-specific table name that appears nowhere in its input.

**What needs to change:** The BUD should explicitly state the reference table name, the same way it does for other EDV fields (e.g., "derived from VC_COMPANY_DETAILS a7"). The logic for these fields should read something like:

> `"Dropdown values from TRUE_FALSE reference table, attribute 1"`

This follows the same pattern the BUD already uses for every other EDV-backed field and removes all ambiguity.

**Action:** Flag to the BUD author — all 6 "block new" fields need their logic updated to include the explicit reference table name.

**Expected outcome:** Once the BUD specifies `TRUE_FALSE` explicitly, the EDV agent will map it correctly with no prompt changes needed.

---

## 6. Inter-Panel Stage: Handle Cross-Panel EDV Derivation for TEXT Fields

**Issue ref:** B2 — Self-Referencing Get Data From EDV on TEXT Fields

**Problem:** Four TEXT fields in the "all company code" panels (Company code, Company Code, Company code, Purchase Org) should be auto-derived from reference tables using `Vendor Number` from the Vendor Details panel as the lookup key. The intra-panel EDV agent (stage 3) recognized the dependency but created self-referencing rules (`source_fields = destination_fields = [self]`) because it cannot handle cross-panel lookups. The inter-panel agent (stage 6) only created visibility and clearing rules for these panels, not EDV derivation rules.

**What needs to change:** There are two possible approaches:

**Option A — Extend the inter-panel agent:** The inter-panel agent currently handles expression rules (visibility, mandatory, derivation via `ctfd`, clearing). It does not handle EDV-type derivation where the lookup requires a cross-panel source field in `criterias`. The agent (or a dedicated sub-step) needs to detect when an EDV rule has a self-referencing source and the BUD logic mentions a field from another panel, then populate the correct `criterias` with the cross-panel field's variableName.

**Option B — Let the EDV agent reference cross-panel fields:** The EDV agent could be given a compact index of all panels' fields (similar to what the inter-panel Phase 1 agent receives) so it can look up cross-panel variableNames for cascading criteria. This would require changes to the EDV dispatcher to provide the cross-panel context.

Either way, the end result should be: these four fields get `Get Data From EDV` rules with `source_fields` pointing to `_vendornumbervendordetails_` (from Vendor Details panel) and correct `criterias` mapping.

**Expected outcome:** Company code / Purchase Org fields in the "all company code" panels have EDV derivation rules with `criterias: [{"a1": "_vendornumbervendordetails_"}]` instead of self-referencing source/destination.

---

## 7. Validate EDV Agent: Detect "Validation" Keyword for Auto-Populated Fields

**Issue ref:** B3 — Missing Validate EDV on "Old Status" Fields

**Problem:** 5 of 6 "old status" fields (Posting block old, Payment block old, Purchase org old) are missing Validate EDV rules. The BUD logic says "derived automatically through Validation from [table] [attribute]," but only one field (Purchase org old in the "all" panel) correctly received a Validate EDV rule.

The Validate EDV agent prompt (`04_validate_edv_agent_v2.md`) instructs the agent to look for keywords like "derive," "fetch," "auto-populate," "lookup," "validate against table," "on validation," "will be populated." The BUD uses the phrase "through Validation" which is close but may not be triggering the agent reliably — 5 out of 6 fields were missed.

**What needs to change:** The Validate EDV agent prompt should explicitly list "through Validation from" and "derived automatically through Validation" as trigger patterns in its keyword detection step (Step 1). The current keyword list is close but not matching this specific BUD phrasing consistently.

Additionally, the agent may be failing because these are TEXT/DISPLAY_ONLY fields rather than DROPDOWN fields. The current agent prompt says "Validate EDV rules are always placed on dropdown fields" (Rule 2). But in this BUD, the "old" fields are display-only text fields that get auto-populated from a reference table lookup triggered by a parent field — they are not dropdowns. The agent needs to broaden its scope to include non-dropdown fields that receive auto-populated values through EDV validation.

**Expected outcome:** All 6 "old status" fields have Validate EDV rules with the correct table name and attribute column mapping. The agent should not skip these fields just because they are not dropdowns.

---

## 8. EDV Agent + Inter-Panel: Populate Cross-Panel Cascading Criteria

**Issue ref:** B4 — Missing Cascading Criteria on "Selected Company Code" Dropdowns

**Problem:** Three `Company code` dropdown fields in the "selected company code" panels should be cascading dropdowns filtered by `Vendor Number` from the Vendor Details panel. The EDV agent correctly identifies the dependency in its reasoning ("since that field is cross-panel, no criterias are applied") but leaves `criterias: []` because it cannot reference cross-panel fields. The inter-panel agent does not fill in the missing cascading criteria either.

This is related to TODO #6 (same root cause: cross-panel EDV dependencies not handled) but specifically affects EXTERNAL_DROP_DOWN_VALUE fields rather than TEXT fields.

**What needs to change:** Same approaches as TODO #6 apply. The cascading criteria for these dropdowns need to be populated with the cross-panel parent field:
- `criterias: [{"a1": "_vendornumbervendordetails_"}]`

The EDV agent already does the analysis correctly and knows what the criteria should be — it just cannot express it because the source field is outside the current panel. Either the EDV agent needs cross-panel context, or a post-processing step (in the inter-panel stage or a new step) needs to fill in cross-panel cascading criteria that the EDV agent left empty.

**Expected outcome:** The three "selected company code" `Company code` dropdowns have `criterias: [{"a1": "_vendornumbervendordetails_"}]` and their source_fields include `_vendornumbervendordetails_`.

---

## 9. BUD Issue: Approver Setup — Undefined Source Field

**Issue ref:** C1 — 9 Fields with Zero Rules

**Problem:** 9 fields in the Approver Setup panel (Approver 2 Vertical Head, Country Head, Approver 3 MDC Team — Name/Email/Phone for each) have zero rules. The BUD says these fields should fetch values from the `VEN_EXT_APPROVAL_MATRIX` reference table, conditional on `"Choose the Group of Company"` field. However, this field does not exist anywhere in this BUD document.

**What needs to change:** This is a BUD issue, not a pipeline issue. No agent can resolve this because the source field is undefined. The BUD needs to either:
1. Define "Choose the Group of Company" as a field in this form, or
2. Specify the exact variableName of the field from a parent/related process

**Action:** Flag this to the BUD author / client for clarification. No pipeline fix can address this until the source field is defined.

---

## 10. BUD Issue: Purchase Org Old — Attribute Mismatch Between Panels

**Issue ref:** D1 — Attribute Mismatch

**Problem:**
- `Purchase org old` in "purchase org **all** company code": BUD says `VC_PURCHASE_DETAILS attribute 7` (block status)
- `Purchase org old` in "purchase org **selected** company code": BUD says `VC_PURCHASE_DETAILS attribute 2` (Purchase Org value)

The "old" field should show the current block status, so the "selected" variant should also reference attribute 7, not attribute 2. This appears to be a BUD documentation error.

**Action:** Flag this discrepancy to the BUD author for correction. If confirmed as an error, update the BUD to use attribute 7 for both panels.

---

## 11. Inter-Panel Dispatcher: Capture CLI Failure Output

**Problem:** When the `claude` CLI exits with a non-zero return code during Phase 1 or Phase 2, the dispatcher logs the exit code but discards stdout/stderr. There is no visibility into why the CLI failed. In Run 3, several Phase 2 agents produced empty log files (agents 2, 3, 4, 7) and poor output, but the logs contain no diagnostic information.

**What needs to change:** On non-zero exit code, the dispatcher should write the captured stdout/stderr to both the per-panel log file and the master log. This applies to both Phase 1 (subprocess.run) and Phase 2 (subprocess.Popen) workers.

**Expected outcome:** Future failures include diagnostic output (API error, rate limit, context overflow, etc.) in the log files, enabling root cause analysis for issues like A2 where some agents silently produced degraded output.

---

## 12. Inter-Panel Dispatcher: Recover Partial Output on CLI Failure

**Problem:** If the CLI exits with a non-zero return code, the dispatcher immediately returns empty results without checking whether the agent already wrote valid output to the output file before failing. This was documented in issue_1 for the Vendor Creation BUD (Vendor Duplicity Details had 7 valid refs discarded, MSME Details had a valid derivation rule discarded). The same pattern applies to this BUD.

**What needs to change:** The dispatcher should check for a valid output file on disk regardless of the CLI exit code. If the file exists and contains valid JSON, use it. Only return empty results when both the exit code is non-zero AND no output file exists (or the file contains invalid data). This applies to both Phase 1 and Phase 2 workers.

**Expected outcome:** Valid output from agents that crash partway through is recovered instead of silently discarded.

---

## Priority Order

| Priority | TODO | Severity | Dependencies |
|---|---|---|---|
| 1 | #1 — Group by source field | High | None |
| 2 | #2 — Child fields in panel visibility | High | None |
| 3 | #5 — TRUE_FALSE EDV table name missing in BUD | High | Needs BUD author |
| 4 | #7 — Validate EDV keyword + non-dropdown support | High | None |
| 5 | #3 — Nested format normalization | Medium | None |
| 6 | #4 — Recover mandatory rules | Medium | Depends on #3 |
| 7 | #6 — Cross-panel EDV derivation for TEXT | High | Design decision needed |
| 8 | #8 — Cross-panel cascading criteria | Medium | Related to #6 |
| 9 | #11 — Capture CLI failure output | Medium | None |
| 10 | #12 — Recover partial output | Medium | None |
| 11 | #9 — Approver Setup (BUD issue) | Medium | Needs BUD author |
| 12 | #10 — Purchase org old (BUD issue) | Low | Needs BUD author |

TODOs #1, #2, #5, #7 are independent and can be worked on in parallel.
TODOs #6 and #8 share the same root cause (cross-panel EDV gap) and should be designed together.
TODOs #9 and #10 are BUD issues requiring external action, not pipeline fixes.
