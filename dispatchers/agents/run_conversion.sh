#!/bin/bash
# Convert EDV output to API-compatible format
#
# Usage:
#   ./run_conversion.sh                    # Use defaults
#   ./run_conversion.sh --pretty           # Pretty print JSON
#   ./run_conversion.sh --bud-name "Custom Name"

set -e

# Default paths
INPUT="output/edv_rules/all_panels_edv.json"
OUTPUT="documents/json_output/vendor_creation_generated.json"
BUD_NAME="Vendor Creation"
PRETTY_FLAG=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --input)
      INPUT="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --bud-name)
      BUD_NAME="$2"
      shift 2
      ;;
    --pretty)
      PRETTY_FLAG="--pretty"
      shift
      ;;
    --help)
      echo "Convert EDV output to API format"
      echo ""
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --input FILE      Input EDV JSON (default: $INPUT)"
      echo "  --output FILE     Output API JSON (default: $OUTPUT)"
      echo "  --bud-name NAME   BUD name for template (default: $BUD_NAME)"
      echo "  --pretty          Pretty print JSON"
      echo "  --help            Show this help"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage"
      exit 1
      ;;
  esac
done

# Check input exists
if [ ! -f "$INPUT" ]; then
    echo "❌ Error: Input file not found: $INPUT"
    exit 1
fi

echo "========================================"
echo "EDV to API Format Converter"
echo "========================================"
echo ""
echo "📁 Input:  $INPUT"
echo "📝 Output: $OUTPUT"
echo "🏷️  Template: $BUD_NAME"
echo ""

# Run conversion
python3 dispatchers/agents/convert_to_api_format.py \
  --input "$INPUT" \
  --output "$OUTPUT" \
  --bud-name "$BUD_NAME" \
  $PRETTY_FLAG

echo ""
echo "✅ Conversion complete!"
echo ""
echo "Output file: $OUTPUT"
echo ""
echo "Next steps:"
echo "  - Review the generated JSON"
echo "  - Validate against API schema"
echo "  - Test with the API endpoint"
echo ""
