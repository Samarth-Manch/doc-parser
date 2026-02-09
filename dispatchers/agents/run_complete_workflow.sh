#!/bin/bash
# run_complete_workflow.sh - Execute all three dispatchers in sequence
#
# This script runs the complete BUD processing pipeline:
# 1. Rule Placement Dispatcher - Identifies which rules apply to fields
# 2. Source-Destination Dispatcher - Determines source/dest field IDs
# 3. EDV Rule Dispatcher - Populates EDV params for dropdown rules

set -e  # Exit on error

# Configuration
BUD_FILE="documents/Vendor Creation Sample BUD.docx"
KEYWORD_TREE="rule_extractor/static/keyword_tree.json"
RULE_SCHEMAS="rules/Rule-Schemas.json"

# Output files
RULE_PLACEMENT_OUTPUT="output/rule_placement/all_panels_rules.json"
SOURCE_DEST_OUTPUT="output/source_destination/all_panels_source_dest.json"
EDV_OUTPUT="output/edv_rules/all_panels_edv.json"
API_OUTPUT="documents/json_output/vendor_creation_generated.json"

# Parse command line arguments
CLEAN_TEMP=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --bud)
      BUD_FILE="$2"
      shift 2
      ;;
    --clean-temp)
      CLEAN_TEMP=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --bud FILE        Path to BUD document (default: documents/Vendor Creation Sample BUD.docx)"
      echo "  --clean-temp      Remove temp files after completion"
      echo "  --verbose         Show detailed output"
      echo "  --help            Show this help message"
      echo ""
      echo "Output files:"
      echo "  1. $RULE_PLACEMENT_OUTPUT"
      echo "  2. $SOURCE_DEST_OUTPUT"
      echo "  3. $EDV_OUTPUT"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Validate input files
if [ ! -f "$BUD_FILE" ]; then
    echo "❌ Error: BUD file not found: $BUD_FILE"
    exit 1
fi

if [ ! -f "$KEYWORD_TREE" ]; then
    echo "❌ Error: Keyword tree not found: $KEYWORD_TREE"
    exit 1
fi

if [ ! -f "$RULE_SCHEMAS" ]; then
    echo "❌ Error: Rule schemas not found: $RULE_SCHEMAS"
    exit 1
fi

echo "========================================"
echo "Complete BUD Processing Workflow"
echo "========================================"
echo ""
echo "📁 Input Files:"
echo "  BUD Document:    $BUD_FILE"
echo "  Keyword Tree:    $KEYWORD_TREE"
echo "  Rule Schemas:    $RULE_SCHEMAS"
echo ""
echo "📝 Output Files:"
echo "  1. Rule Placement:     $RULE_PLACEMENT_OUTPUT"
echo "  2. Source-Destination: $SOURCE_DEST_OUTPUT"
echo "  3. EDV Rules:          $EDV_OUTPUT"
echo "  4. API Format (Final): $API_OUTPUT"
echo ""
echo "========================================"
echo ""

# Start timer
START_TIME=$(date +%s)

# Step 1: Rule Placement
echo "┌────────────────────────────────────────┐"
echo "│  Step 1/3: Rule Placement Dispatcher   │"
echo "└────────────────────────────────────────┘"
echo ""
STEP1_START=$(date +%s)

python3 dispatchers/agents/rule_placement_dispatcher.py \
  --bud "$BUD_FILE" \
  --keyword-tree "$KEYWORD_TREE" \
  --rule-schemas "$RULE_SCHEMAS" \
  --output "$RULE_PLACEMENT_OUTPUT"

STEP1_END=$(date +%s)
STEP1_TIME=$((STEP1_END - STEP1_START))

echo ""
echo "✓ Rule placement complete (${STEP1_TIME}s)"
echo ""

# Step 2: Source-Destination
echo "┌────────────────────────────────────────┐"
echo "│ Step 2/3: Source-Destination Dispatcher│"
echo "└────────────────────────────────────────┘"
echo ""
STEP2_START=$(date +%s)

python3 dispatchers/agents/source_destination_dispatcher.py \
  --bud "$BUD_FILE" \
  --rule-placement-output "$RULE_PLACEMENT_OUTPUT" \
  --rule-schemas "$RULE_SCHEMAS" \
  --output "$SOURCE_DEST_OUTPUT"

STEP2_END=$(date +%s)
STEP2_TIME=$((STEP2_END - STEP2_START))

echo ""
echo "✓ Source-destination complete (${STEP2_TIME}s)"
echo ""

# Step 3: EDV Rules
echo "┌────────────────────────────────────────┐"
echo "│      Step 3/4: EDV Rule Dispatcher     │"
echo "└────────────────────────────────────────┘"
echo ""
STEP3_START=$(date +%s)

python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "$BUD_FILE" \
  --source-dest-output "$SOURCE_DEST_OUTPUT" \
  --output "$EDV_OUTPUT"

STEP3_END=$(date +%s)
STEP3_TIME=$((STEP3_END - STEP3_START))

echo ""
echo "✓ EDV rules complete (${STEP3_TIME}s)"
echo ""

# Step 4: API Format Conversion
echo "┌────────────────────────────────────────┐"
echo "│   Step 4/4: API Format Converter       │"
echo "└────────────────────────────────────────┘"
echo ""
STEP4_START=$(date +%s)

python3 dispatchers/agents/convert_to_api_format.py \
  --input "$EDV_OUTPUT" \
  --output "$API_OUTPUT" \
  --bud-name "$BUD_FILE" \
  --pretty

STEP4_END=$(date +%s)
STEP4_TIME=$((STEP4_END - STEP4_START))

echo ""
echo "✓ API conversion complete (${STEP4_TIME}s)"
echo ""

# End timer
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

# Clean temp files if requested
if [ "$CLEAN_TEMP" = true ]; then
    echo "🧹 Cleaning temp files..."
    rm -rf output/rule_placement/temp/
    rm -rf output/source_destination/temp/
    rm -rf output/edv_rules/temp/
    echo "✓ Temp files removed"
    echo ""
fi

# Display summary
echo "========================================"
echo "✅ Complete Workflow Finished!"
echo "========================================"
echo ""
echo "⏱️  Timing Summary:"
echo "  Step 1 (Rule Placement):      ${STEP1_TIME}s"
echo "  Step 2 (Source-Destination):  ${STEP2_TIME}s"
echo "  Step 3 (EDV Rules):           ${STEP3_TIME}s"
echo "  Step 4 (API Conversion):      ${STEP4_TIME}s"
echo "  ────────────────────────────────────"
echo "  Total Time:                   ${TOTAL_TIME}s"
echo ""
echo "📄 Output Files:"
echo "  1. Rule Placement:      $RULE_PLACEMENT_OUTPUT"
echo "  2. Source-Destination:  $SOURCE_DEST_OUTPUT"
echo "  3. EDV Rules:           $EDV_OUTPUT"
echo "  4. API Format (Final):  $API_OUTPUT"
echo ""

# Show file sizes
if command -v du &> /dev/null; then
    echo "📊 File Sizes:"
    if [ -f "$RULE_PLACEMENT_OUTPUT" ]; then
        SIZE=$(du -h "$RULE_PLACEMENT_OUTPUT" | cut -f1)
        echo "  1. Rule Placement:      $SIZE"
    fi
    if [ -f "$SOURCE_DEST_OUTPUT" ]; then
        SIZE=$(du -h "$SOURCE_DEST_OUTPUT" | cut -f1)
        echo "  2. Source-Destination:  $SIZE"
    fi
    if [ -f "$EDV_OUTPUT" ]; then
        SIZE=$(du -h "$EDV_OUTPUT" | cut -f1)
        echo "  3. EDV Rules:           $SIZE"
    fi
    if [ -f "$API_OUTPUT" ]; then
        SIZE=$(du -h "$API_OUTPUT" | cut -f1)
        echo "  4. API Format (Final):  $SIZE"
    fi
    echo ""
fi

# Show quick stats
if command -v jq &> /dev/null; then
    echo "📈 Quick Stats:"
    if [ -f "$API_OUTPUT" ]; then
        TEMPLATE_NAME=$(jq -r '.template.templateName' "$API_OUTPUT" 2>/dev/null || echo "N/A")
        echo "  Template Name:          $TEMPLATE_NAME"

        TEMPLATE_ID=$(jq -r '.template.id' "$API_OUTPUT" 2>/dev/null || echo "N/A")
        echo "  Template ID:            $TEMPLATE_ID"

        METADATA_COUNT=$(jq '.template.documentTypes[0].formFillMetadatas | length' "$API_OUTPUT" 2>/dev/null || echo "N/A")
        echo "  Form Fill Metadatas:    $METADATA_COUNT"

        RULE_COUNT=$(jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[]] | length' "$API_OUTPUT" 2>/dev/null || echo "N/A")
        echo "  Total Rules:            $RULE_COUNT"

        EDV_PARAM_COUNT=$(jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[] | select(.params | contains("conditionList"))] | length' "$API_OUTPUT" 2>/dev/null || echo "N/A")
        echo "  EDV Rules w/ Params:    $EDV_PARAM_COUNT"
    fi
    echo ""
fi

echo "🎉 Workflow completed successfully!"
echo ""
echo "Next steps:"
echo "  - Review the API output: $API_OUTPUT"
echo "  - Validate against API schema"
echo "  - Test with API endpoint"
echo "  - Deploy to production"
echo ""
