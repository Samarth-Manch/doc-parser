#!/usr/bin/env python3
"""
Run Rule Extraction v7 - Based on v16 Perfect Score Implementation

This script runs the rule extraction agent using the v16 implementation
which achieved a 1.0 (perfect) score in evaluation.

Input Files:
- Schema JSON: output/complete_format/6421-schema.json
- Intra-Panel References: adws/2026-02-01_11-01-26/templates_output/Vendor Creation Sample BUD_intra_panel_references.json

Output Files:
- Populated Schema: adws/2026-02-01_11-01-26/populated_schema_v7.json
- Summary Report: adws/2026-02-01_11-01-26/extraction_report_v7.json
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent.enhanced_main_v16 import EnhancedRuleExtractionAgentV16


def main():
    # Input paths
    schema_path = "output/complete_format/6421-schema.json"
    intra_panel_path = "adws/2026-02-01_11-01-26/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"

    # Output paths
    output_dir = Path("adws/2026-02-01_11-01-26")
    output_path = output_dir / "populated_schema_v7.json"
    report_path = output_dir / "extraction_report_v7.json"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Rule Extraction v7 (based on v16 perfect score)")
    print("=" * 70)
    print(f"\nInput Schema: {schema_path}")
    print(f"Intra-Panel: {intra_panel_path}")
    print(f"Output Schema: {output_path}")
    print(f"Report: {report_path}")
    print()

    # Check if input files exist
    if not Path(schema_path).exists():
        print(f"ERROR: Schema file not found: {schema_path}")
        return 1

    if not Path(intra_panel_path).exists():
        print(f"WARNING: Intra-panel file not found: {intra_panel_path}")
        intra_panel_path = None

    # Run extraction
    agent = EnhancedRuleExtractionAgentV16(
        schema_path=schema_path,
        intra_panel_path=intra_panel_path,
        verbose=True
    )

    agent.save_output(str(output_path), str(report_path))

    print("\n" + "=" * 70)
    print("Rule Extraction v7 COMPLETE")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
