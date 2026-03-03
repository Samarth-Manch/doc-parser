# Issue 3: Inter-Panel Agent + EDV/Validate EDV Rule Defects (Block/Unblock BUD, Run 3)

## BUD Document
`documents/Pidilite Vendor block-unblock BUD .docx`

## Run Location
`output/block_unblock/runs/3/`

---

## Part A: Inter-Panel Agent Issues

### A1. Duplicate Rule Explosion — 16 Rules on One Field

**Affected Field:** `Which function you would like to Update?` (`_whichfunctionyouwouldliketoupdatevendordetails_`)

The inter-panel dispatcher groups refs by `referenced_panel` (target panel), not by source field. Since the 6 sub-panels all reference the same source field in Vendor Details, the dispatcher makes **7 separate agent calls**, each creating its own visibility + clearing rules on the same field.

**Result:** 16 rules on a single field (1 EDV + 15 cross-panel Expression rules) when it should have ~4 rules (1 EDV + 1 visibility + 1 mandatory + 1 clearing).

**Root cause:** `group_complex_refs_by_source_panel()` in `inter_panel_utils.py:45` groups by `ref.get('referenced_panel')`. All 6 panel groups create separate rules on the same source field, and the merge deduplication only catches exact matches.

**Fix needed:** Group by source field (the field where rules will be placed), not by target panel. One agent call should produce one comprehensive rule covering all 6 panels.

---

### A2. Inconsistent Visibility Rules — Panel-Only vs. Comprehensive

Phase 2 agents produce inconsistent visibility rules on the same type of input:

| Agent (Phase 2 order) | Panel | mvi/minvi targets | Log |
|---|---|---|---|
| Agent 1 (Vendor Details) | 4 panels combined | Panel variable only | Detailed |
| Agent 2 (posting all) | posting all | Panel variable only | **Empty** |
| **Agent 3 (payment all)** | payment all | **Panel variable only** | **Empty** |
| **Agent 4 (purchase org all)** | purchase org all | **Panel variable only** | **Empty** |
| Agent 5 (posting selected) | posting selected | Panel + all 6 child fields | Detailed |
| Agent 6 (payment selected) | payment selected | Panel + all 7 child fields | Detailed |
| Agent 7 (purchase org selected) | purchase org selected | Panel variable only | **Empty** |

**Bad output (agents 2, 3, 4, 7):**
```
mvi(vo("_whichfunction...")=="..", "_blockunblockpaymentallcompanycode_")
```
Only targets the PANEL variable — child fields NOT included.

**Good output (agents 5, 6):**
```
mvi(vo("_whichfunction...")=="..", "_blockunblockpostingselectedcompanycode_",
    "_postingblockselectedcompanycodedetails..._", "_companycode..._",
    "_postingblockold..._", "_postingblocknew..._", "_reasonforblock..._",
    "_requesterremark..._")
```
Panel + ALL child fields included.

**Correlation:** Agents with empty log files (just the header line, ~100 bytes) produce panel-only rules. Agents with detailed step-by-step logs (~750-900 bytes) produce comprehensive rules. The LLM skipped intermediate reasoning and missed the child field enumeration step.

**Root cause:** LLM non-determinism in the expression rule agent. The agent prompt does not explicitly instruct to include all child fields when making a panel visible/invisible.

**Fix needed:** Add explicit instruction to `expression_rule_agent.md`: "When using mvi/minvi on a PANEL variable, ALWAYS include ALL child fields of that panel in the same mvi/minvi call."

---

### A3. Phase 1 Detection Format Mismatch — "posting all company code" Lost

The Phase 1 detection agent for `Block / Unblock posting all company code` returned a **different JSON format** (nested `source_field`/`referenced_field` objects):

```json
{
  "source_field": { "field_name": "...", "variableName": "...", "panel": "..." },
  "referenced_field": { "field_name": "...", "variableName": "...", "panel": "..." },
  "reference_type": "visibility"
}
```

The `normalize_detection_output()` function in `inter_panel_dispatcher.py:123` does NOT handle this nested format. The `_normalize_single_ref()` function looks for flat keys like `referenced_panel`, `field_variableName` etc., which don't exist in the nested format. All 3 refs returned `None`.

**Result:** Master log reports "Block / Unblock posting all company code — 0 refs detected" despite the output file having 3 valid refs.

**Fix needed:** Add handling for nested `source_field`/`referenced_field` format in `_normalize_single_ref()`, extracting `referenced_panel` from `ref['referenced_field']['panel']` and `field_variableName` from `ref['source_field']['variableName']`.

---

### A4. Missing Mandatory Rules for "posting all company code"

Because the posting all panel's Phase 1 detection was lost (A3), its mandatory rule was also lost. The Vendor Details agent (agent 1) covers mandatory for 4 panels but misses `_postingblocknewblockunblockpostingallcompanycode_`.

**BUD says:** "if field 'Which function you would like to Update?' value is 'Block / Unblock posting all company code' then [Posting block new] is mandatory, otherwise non-mandatory"

**Output:** No mandatory rule exists for this field.

---

## Part B: EDV Rule Issues

### B1. Wrong EDV Table for "block new" / "posting block new" Fields

**Affected fields:**
- `Posting block new` in "posting all company code" panel → uses `VC_COMPANY_DETAILS a7`
- `Posting block new` in "posting selected company code" panel → uses `VC_COMPANY_DETAILS a7`
- `Payment block New` in "payment selected company code" panel → uses `VC_PAYMENT_BLOCK a1` (fabricated table)

**BUD says:** "Dropdown Values - True False" for all three fields.

**Expected:** `TRUE_FALSE` table with `da=[a1]` (like `Payment block New` in payment all and `Purchase org new` fields which are correct).

**What went wrong:**
- Posting block new: The EDV agent incorrectly inferred the same table as `Posting block old` (VC_COMPANY_DETAILS) instead of recognizing "True False" as a standalone dropdown.
- Payment block New (payment selected): The EDV agent **hallucinated** a non-existent table name `VC_PAYMENT_BLOCK` that appears nowhere in the BUD.

**Root cause:** Agent issue — the EDV agent's reasoning treats "True False" as values from the same reference table as the "old" field rather than recognizing it as a standard TRUE_FALSE EDV table. Inconsistent across panels (payment all correctly uses TRUE_FALSE, but posting all/selected and payment selected do not).

---

### B2. Self-Referencing Get Data From EDV on TEXT Fields

**Affected fields (all in "all company code" panels):**
- `Company code` in "posting all company code" → `source=self, dest=self`
- `Company Code` in "payment all company code" → `source=self, dest=self`
- `Company code` in "purchase org all company code" → `source=self, dest=self`
- `Purchase Org` in "purchase org all company code" → `source=self, dest=self`

**BUD says:** These TEXT fields should be auto-derived from reference tables (VC_COMPANY_DETAILS or VC_PURCHASE_DETAILS) using `Vendor Number` from the Vendor Details panel as the lookup key.

**What went wrong:** The intra-panel EDV agent cannot handle cross-panel dependencies. It created `Get Data From EDV` rules with `source_fields = destination_fields = [self]`, which is meaningless at runtime. The inter-panel agent should have created cross-panel EDV derivation rules for these fields but only created visibility and clearing rules.

**Root cause:** Gap between agent stages — the EDV agent (stage 3) skips cross-panel dependencies, and the inter-panel agent (stage 6) only handled visibility/clearing/mandatory, not EDV derivation for these fields.

---

### B3. Missing Validate EDV on "Old Status" Fields

**Affected fields:**

| Panel | Field | BUD Logic | Has Validate EDV? |
|---|---|---|---|
| posting all | Posting block old | "derived automatically through Validation from VC_COMPANY_DETAILS a7" | **No** |
| posting selected | Posting block old | "derived automatically through Validation from VC_COMPANY_DETAILS a7" | **No** |
| payment all | Payment block old | "derived automatically through Validation from VC_COMPANY_DETAILS a15" | **No** |
| payment selected | Payment block old | "derived automatically through Validation from VC_COMPANY_DETAILS a15" | **No** |
| purchase org all | Purchase org old | "derived automatically through Validation from VC_PURCHASE_DETAILS a7" | **Yes** ✅ |
| purchase org selected | Purchase org old | BUD says a2 (likely BUD inconsistency, should be a7) | **No** |

5 of 6 "old" fields are missing Validate EDV rules. Only `Purchase org old` in "purchase org all company code" panel correctly has a Validate EDV rule.

**BUD says:** "Old Status should be derived automatically through Validation from reference table" — this means the field value is auto-populated via Validate EDV, not user-selected via dropdown.

**Root cause:** The Validate EDV agent (stage 4) did not pick up these fields. The keyword "Validation" in the logic should have triggered Validate EDV placement.

---

### B4. Missing Cascading Criteria on "Selected Company Code" Dropdowns

**Affected fields (EXTERNAL_DROP_DOWN_VALUE fields dependent on Vendor Number):**
- `Company code` in "posting selected company code" → `criterias=[]`
- `Company code` in "payment selected company code" → `criterias=[]`
- `Company code` in "purchase org selected company code" → `criterias=[]`

**BUD says:** "Derive company code from VC_COMPANY_DETAILS/VC_PURCHASE_DETAILS, dependent on field value of 'Vendor Number' (from Vendor Details panel)."

These dropdowns should be cascading — filtered by Vendor Number (attribute 1 of the same reference table). But `criterias` is empty because Vendor Number is a cross-panel field. The EDV agent notes this in its reasoning: "since that field is cross-panel, no criterias are applied."

**Root cause:** The EDV agent (stage 3) correctly identifies the cross-panel dependency but leaves `criterias=[]`. The inter-panel agent (stage 6) does not add the cascading criteria either — it only handles visibility/clearing/mandatory expression rules, not EDV params.

**Expected:**
```json
"criterias": [{ "a1": "_vendornumbervendordetails_" }]
```

---

## Part C: Approver Setup — Missing Rules (BUD Issue)

### C1. Approver Setup — 9 Fields with Zero Rules

**Affected fields:**
- Approver 2 Vertical Head Name / Email / Mobile (3 fields)
- Country Head Name / Email / Phone Number (3 fields)
- Approver 3 MDC Team Name / Email / Phone Number (3 fields)

**BUD says:** These fields should fetch values from `VEN_EXT_APPROVAL_MATRIX` reference table (columns 3-11), conditional on `"Choose the Group of Company"` being `PIL`, `Domestic Subsidiaries`, or `International Subsidiaries`.

**Problem:** The field `"Choose the Group of Company"` does **not exist** in this BUD document. It is likely defined in a parent/related process. No agent can resolve this dependency because the source field is undefined.

**Root cause:** BUD issue — the BUD references a field that doesn't exist in its own field definitions. The pipeline has no way to create EDV/Validate EDV rules without knowing the source field's variableName.

**Fix needed:** The BUD should either:
1. Define "Choose the Group of Company" as a field in this form, or
2. Specify the exact variableName of the field from the parent process

---

## Part D: BUD Inconsistency Flagged

### D1. Purchase org old — Attribute Mismatch Between Panels

- `Purchase org old` in "purchase org **all** company code": BUD says `VC_PURCHASE_DETAILS attribute 7` (block status) ✅
- `Purchase org old` in "purchase org **selected** company code": BUD says `VC_PURCHASE_DETAILS attribute 2` (Purchase Org value) ⚠️

Attribute 2 is the Purchase Org value, attribute 7 is the block status. The "old" field should show the current block status, so the "selected" variant likely should reference attribute 7, not attribute 2. This appears to be a documentation error in the BUD.

---

## Summary Table

| Issue | Category | Fix Location | Severity |
|---|---|---|---|
| A1. 16 duplicate rules on one field | Inter-panel dispatcher | `inter_panel_utils.py` — group by source field | High |
| A2. Panel-only visibility (agents 3,4) | Expression rule agent | `expression_rule_agent.md` — add child field instruction | High |
| A3. Phase 1 format mismatch | Inter-panel dispatcher | `inter_panel_dispatcher.py` — normalize nested format | Medium |
| A4. Missing mandatory for posting all | Cascading from A3 | Fix A3 first | Medium |
| B1. Wrong EDV table (True/False fields) | EDV agent | `03_edv_rule_agent_v2.md` — recognize "True False" pattern | High |
| B2. Self-referencing Get Data From EDV | EDV + inter-panel agent | Cross-panel EDV derivation stage needed | High |
| B3. Missing Validate EDV on "old" fields | Validate EDV agent | `04_validate_edv_agent_v2.md` — match "Validation" keyword | High |
| B4. Missing cascading on Vendor Number | EDV + inter-panel agent | Inter-panel should populate cross-panel criterias | Medium |
| C1. Approver Setup — 9 fields no rules | BUD | Define "Choose the Group of Company" field | Medium |
| D1. Purchase org old attr mismatch | BUD | Correct attribute 2 → 7 in selected panel | Low |
