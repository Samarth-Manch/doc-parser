#!/usr/bin/env bash
#
# run_pipeline.sh - Run the full rule extraction pipeline
#
# Runs all 10 dispatcher stages sequentially, each building on the previous output.
# See README_PIPELINE.md for details.
#

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Defaults ────────────────────────────────────────────────────────────────
BUD_DOC=""
API_SCHEMA=""
KEYWORD_TREE="rule_extractor/static/keyword_tree.json"
RULE_SCHEMAS="rules/Rule-Schemas.json"
OUTPUT_DIR="output"
FINAL_OUTPUT="documents/json_output/vendor_creation_generated.json"
BUD_NAME="Vendor Creation"
START_STAGE=1
END_STAGE=10
PRETTY_FLAG=""

# ── Usage ───────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
${BOLD}Usage:${NC}
  $0 --bud <path-to-bud.docx> [options]

${BOLD}Required:${NC}
  --bud <path>              Path to the BUD document (.docx)

${BOLD}Options:${NC}
  --schema <path>           API schema JSON for injection mode (stage 7)
  --keyword-tree <path>     Keyword tree JSON (default: rule_extractor/static/keyword_tree.json)
  --rule-schemas <path>     Rule schemas JSON (default: rules/Rule-Schemas.json)
  --output-dir <path>       Base output directory (default: output)
  --final-output <path>     Final API JSON output path
                            (default: documents/json_output/vendor_creation_generated.json)
  --bud-name <name>         BUD name for legacy mode (default: "Vendor Creation")
  --start-stage <1-10>      Start from this stage (default: 1)
  --end-stage <1-10>        Stop after this stage (default: 10)
  --pretty                  Pretty print final API JSON
  -h, --help                Show this help

${BOLD}Stages:${NC}
  1  Rule Placement        Assign rule names to fields       (needs: --bud, --keyword-tree, --rule-schemas)
  2  Source/Destination     Determine source/dest fields      (needs: stage 1 output, --rule-schemas)
  3  EDV Rules             Populate EDV dropdown params       (needs: --bud, stage 2 output)
  4  Validate EDV          Place Validate EDV rules           (needs: --bud, stage 3 output)
  5  Conditional Logic     Add visibility/state rules         (needs: stage 4 output)
  6  Derivation Logic      Add Expression rules for derivation (needs: stage 5 output)
  7  Clear Child Fields    Clear child fields on parent change (needs: stage 6 output)
  8  Inter-Panel Rules     Handle cross-panel field references (needs: --bud, stage 7 output)
  9  Session Based         Inject RuleCheck session rules     (needs: --bud, stage 8 output)
  10 Convert to API        Convert to final API format        (needs: stage 9 output, --schema optional)

${BOLD}Examples:${NC}
  # Vendor Creation Sample BUD (full pipeline with schema injection)
  $0 --bud "documents/Vendor Creation Sample BUD.docx" \\
     --schema "documents/json_output/vendor_creation.json" --pretty

  # Run only stages 3-5
  $0 --bud "documents/Vendor Creation Sample BUD.docx" --start-stage 3 --end-stage 5

  # Custom output directory
  $0 --bud "documents/Vendor Creation Sample BUD.docx" --output-dir output/run1
EOF
    exit 0
}

# ── Parse Args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bud)           BUD_DOC="$2"; shift 2 ;;
        --schema)        API_SCHEMA="$2"; shift 2 ;;
        --keyword-tree)  KEYWORD_TREE="$2"; shift 2 ;;
        --rule-schemas)  RULE_SCHEMAS="$2"; shift 2 ;;
        --output-dir)    OUTPUT_DIR="$2"; shift 2 ;;
        --final-output)  FINAL_OUTPUT="$2"; shift 2 ;;
        --bud-name)      BUD_NAME="$2"; shift 2 ;;
        --start-stage)   START_STAGE="$2"; shift 2 ;;
        --end-stage)     END_STAGE="$2"; shift 2 ;;
        --pretty)        PRETTY_FLAG="--pretty"; shift ;;
        -h|--help)       usage ;;
        *)               echo -e "${RED}Unknown option: $1${NC}"; usage ;;
    esac
done

if [[ -z "$BUD_DOC" ]]; then
    echo -e "${RED}Error: --bud is required${NC}"
    usage
fi

if [[ ! -f "$BUD_DOC" ]]; then
    echo -e "${RED}Error: BUD document not found: $BUD_DOC${NC}"
    exit 1
fi

# ── Intermediate file paths ────────────────────────────────────────────────
STAGE1_OUT="${OUTPUT_DIR}/rule_placement/all_panels_rules.json"
STAGE2_OUT="${OUTPUT_DIR}/source_destination/all_panels_source_dest.json"
STAGE3_OUT="${OUTPUT_DIR}/edv_rules/all_panels_edv.json"
STAGE4_OUT="${OUTPUT_DIR}/validate_edv/all_panels_validate_edv.json"
STAGE5_OUT="${OUTPUT_DIR}/conditional_logic/all_panels_conditional_logic.json"
STAGE6_OUT="${OUTPUT_DIR}/derivation_logic/all_panels_derivation.json"
STAGE7_OUT="${OUTPUT_DIR}/clear_child_fields/all_panels_clear_child.json"
STAGE8_OUT="${OUTPUT_DIR}/inter_panel/all_panels_inter_panel.json"
STAGE9_OUT="${OUTPUT_DIR}/session_based/all_panels_session_based.json"
STAGE10_OUT="${FINAL_OUTPUT}"

# ── Helper ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISPATCHERS="${SCRIPT_DIR}/dispatchers/agents"
PASS=0
FAIL=0
SKIP=0

run_stage() {
    local stage_num="$1"
    local stage_name="$2"
    shift 2

    if [[ $stage_num -lt $START_STAGE || $stage_num -gt $END_STAGE ]]; then
        echo -e "${YELLOW}[Stage $stage_num] $stage_name — SKIPPED (outside range)${NC}"
        ((SKIP++))
        return 0
    fi

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  ${BOLD}Stage $stage_num: $stage_name${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    local start_time=$SECONDS

    if "$@"; then
        local elapsed=$((SECONDS - start_time))
        echo ""
        echo -e "${GREEN}[Stage $stage_num] $stage_name — PASSED (${elapsed}s)${NC}"
        ((PASS++))
    else
        local elapsed=$((SECONDS - start_time))
        echo ""
        echo -e "${RED}[Stage $stage_num] $stage_name — FAILED (${elapsed}s)${NC}"
        ((FAIL++))
        echo -e "${RED}Pipeline stopped at stage $stage_num.${NC}"
        echo -e "${YELLOW}Fix the issue and re-run with --start-stage $stage_num${NC}"
        exit 1
    fi
}

# ── Print config ────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Rule Extraction Pipeline${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "  BUD Document  : ${CYAN}${BUD_DOC}${NC}"
echo -e "  Keyword Tree  : ${CYAN}${KEYWORD_TREE}${NC}"
echo -e "  Rule Schemas  : ${CYAN}${RULE_SCHEMAS}${NC}"
echo -e "  Output Dir    : ${CYAN}${OUTPUT_DIR}${NC}"
echo -e "  Stages        : ${CYAN}${START_STAGE} → ${END_STAGE}${NC}"
[[ -n "$API_SCHEMA" ]] && echo -e "  API Schema    : ${CYAN}${API_SCHEMA}${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"

PIPELINE_START=$SECONDS

# ── Stage 1: Rule Placement ────────────────────────────────────────────────
run_stage 1 "Rule Placement" \
    python3 "${DISPATCHERS}/rule_placement_dispatcher.py" \
        --bud "$BUD_DOC" \
        --keyword-tree "$KEYWORD_TREE" \
        --rule-schemas "$RULE_SCHEMAS" \
        --output "$STAGE1_OUT"

# ── Stage 2: Source / Destination ──────────────────────────────────────────
run_stage 2 "Source / Destination" \
    python3 "${DISPATCHERS}/source_destination_dispatcher.py" \
        --input "$STAGE1_OUT" \
        --rule-schemas "$RULE_SCHEMAS" \
        --output "$STAGE2_OUT"

# ── Stage 3: EDV Rules ────────────────────────────────────────────────────
run_stage 3 "EDV Rules" \
    python3 "${DISPATCHERS}/edv_rule_dispatcher.py" \
        --bud "$BUD_DOC" \
        --source-dest-output "$STAGE2_OUT" \
        --output "$STAGE3_OUT"

# ── Stage 4: Validate EDV ─────────────────────────────────────────────────
run_stage 4 "Validate EDV" \
    python3 "${DISPATCHERS}/validate_edv_dispatcher.py" \
        --bud "$BUD_DOC" \
        --edv-output "$STAGE3_OUT" \
        --output "$STAGE4_OUT"

# ── Stage 5: Conditional Logic ─────────────────────────────────────────────
run_stage 5 "Conditional Logic" \
    python3 "${DISPATCHERS}/conditional_logic_dispatcher.py" \
        --validate-edv-output "$STAGE4_OUT" \
        --output "$STAGE5_OUT"

# ── Stage 6: Derivation Logic ──────────────────────────────────────────────
run_stage 6 "Derivation Logic" \
    python3 "${DISPATCHERS}/derivation_logic_dispatcher.py" \
        --conditional-logic-output "$STAGE5_OUT" \
        --output "$STAGE6_OUT"

# ── Stage 7: Clear Child Fields ───────────────────────────────────────────
run_stage 7 "Clear Child Fields" \
    python3 "${DISPATCHERS}/clear_child_fields_dispatcher.py" \
        --derivation-output "$STAGE6_OUT" \
        --output "$STAGE7_OUT"

# ── Stage 8: Inter-Panel Rules ─────────────────────────────────────────────
run_stage 8 "Inter-Panel Rules" \
    python3 "${DISPATCHERS}/inter_panel_dispatcher.py" \
        --clear-child-output "$STAGE7_OUT" \
        --bud "$BUD_DOC" \
        --output "$STAGE8_OUT"

# ── Stage 9: Session Based ────────────────────────────────────────────────
run_stage 9 "Session Based" \
    python3 "${DISPATCHERS}/session_based_dispatcher.py" \
        --clear-child-output "$STAGE8_OUT" \
        --bud "$BUD_DOC" \
        --output "$STAGE9_OUT"

# ── Stage 10: Convert to API Format ───────────────────────────────────────
STAGE10_ARGS=(
    python3 "${DISPATCHERS}/convert_to_api_format.py"
    --input "$STAGE9_OUT"
    --output "$STAGE10_OUT"
    --bud-name "$BUD_NAME"
)
[[ -n "$API_SCHEMA" ]] && STAGE10_ARGS+=(--schema "$API_SCHEMA")
[[ -n "$PRETTY_FLAG" ]] && STAGE10_ARGS+=($PRETTY_FLAG)

run_stage 10 "Convert to API Format" "${STAGE10_ARGS[@]}"

# ── Summary ─────────────────────────────────────────────────────────────────
PIPELINE_ELAPSED=$((SECONDS - PIPELINE_START))
echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Pipeline Complete${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"
echo -e "  Passed  : ${GREEN}${PASS}${NC}"
echo -e "  Failed  : ${RED}${FAIL}${NC}"
echo -e "  Skipped : ${YELLOW}${SKIP}${NC}"
echo -e "  Time    : ${CYAN}${PIPELINE_ELAPSED}s${NC}"
echo ""
echo -e "  ${BOLD}Outputs:${NC}"
[[ $START_STAGE -le 1 && $END_STAGE -ge 1 ]] && echo -e "    Stage 1: ${CYAN}${STAGE1_OUT}${NC}"
[[ $START_STAGE -le 2 && $END_STAGE -ge 2 ]] && echo -e "    Stage 2: ${CYAN}${STAGE2_OUT}${NC}"
[[ $START_STAGE -le 3 && $END_STAGE -ge 3 ]] && echo -e "    Stage 3: ${CYAN}${STAGE3_OUT}${NC}"
[[ $START_STAGE -le 4 && $END_STAGE -ge 4 ]] && echo -e "    Stage 4: ${CYAN}${STAGE4_OUT}${NC}"
[[ $START_STAGE -le 5 && $END_STAGE -ge 5 ]] && echo -e "    Stage 5: ${CYAN}${STAGE5_OUT}${NC}"
[[ $START_STAGE -le 6 && $END_STAGE -ge 6 ]] && echo -e "    Stage 6: ${CYAN}${STAGE6_OUT}${NC}"
[[ $START_STAGE -le 7 && $END_STAGE -ge 7 ]] && echo -e "    Stage 7: ${CYAN}${STAGE7_OUT}${NC}"
[[ $START_STAGE -le 8 && $END_STAGE -ge 8 ]] && echo -e "    Stage 8: ${CYAN}${STAGE8_OUT}${NC}"
[[ $START_STAGE -le 9 && $END_STAGE -ge 9 ]] && echo -e "    Stage 9: ${CYAN}${STAGE9_OUT}${NC}"
[[ $START_STAGE -le 10 && $END_STAGE -ge 10 ]] && echo -e "    Stage 10: ${CYAN}${STAGE10_OUT}${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════════════════════${NC}"
