#!/bin/bash

# Corrected Rule Extraction Script
# Fixes: Uses vendor_creation_schema.json instead of parsed BUD document

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "==============================================="
echo "  Rule Extraction Agent - Corrected Run"
echo "==============================================="
echo ""
echo "Fixes Applied:"
echo "  ✓ Using vendor_creation_schema.json as template"
echo "  ✓ Correct schema path for formFillRules population"
echo "  ✓ Proper field ID mapping"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the rule extraction agent with corrected paths
python3 "$SCRIPT_DIR/generated_code/main.py" \
    --schema "documents/json_output/vendor_creation_schema.json" \
    --intra-panel "$SCRIPT_DIR/intra_panel_references.json" \
    --output "$SCRIPT_DIR/populated_schema.json" \
    --report "$SCRIPT_DIR/extraction_report.json" \
    --start-rule-id 119617 \
    --verbose

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "==============================================="
    echo "  ✓ Rule Extraction Completed Successfully"
    echo "==============================================="
    echo ""
    echo "Output Files:"
    echo "  - Populated Schema: $SCRIPT_DIR/populated_schema.json"
    echo "  - Extraction Report: $SCRIPT_DIR/extraction_report.json"
    echo ""

    # Count formFillRules in output
    RULE_COUNT=$(grep -o "formFillRules" "$SCRIPT_DIR/populated_schema.json" | wc -l)
    echo "  - formFillRules arrays found: $RULE_COUNT"
    echo ""

    # Verify output structure
    echo "Verifying output structure..."
    python3 "$SCRIPT_DIR/verify_output.py" "$SCRIPT_DIR/populated_schema.json"
else
    echo ""
    echo "==============================================="
    echo "  ✗ Rule Extraction Failed (Exit Code: $EXIT_CODE)"
    echo "==============================================="
    echo ""
    exit $EXIT_CODE
fi
