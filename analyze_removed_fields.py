"""
Script to identify fields that were removed due to UNKNOWN field type filtering.
"""

from pathlib import Path
from doc_parser.parser import DocumentParser
from doc_parser.models import FieldType
from docx import Document

class RemovedFieldsAnalyzer:
    """Analyzes which fields were removed due to UNKNOWN type filtering."""

    def __init__(self):
        self.parser = DocumentParser()
        self.removed_fields = {}

    def analyze_document(self, doc_path):
        """Analyze a document to find fields with UNKNOWN types."""
        doc = Document(doc_path)
        doc_name = Path(doc_path).stem
        removed = []

        # Parse document
        result = self.parser.parse(doc_path)

        # Now we need to check the raw tables for fields that were skipped
        for table_data in result.raw_tables:
            if "field" in table_data.table_type:
                headers_lower = [h.lower() for h in table_data.headers]

                # Find column indices
                name_idx = self.parser._find_column_index_flexible(
                    headers_lower,
                    ["field name", "filed name", "name", "field", "label", "attribute", "column name"]
                )

                type_idx = self.parser._find_column_index_flexible(
                    headers_lower,
                    ["field type", "type", "data type", "datatype", "field-type"]
                )

                logic_idx = self.parser._find_column_index_flexible(
                    headers_lower,
                    ["logic", "rules", "rule", "validation", "description", "notes", "logic and rules"]
                )

                mandatory_idx = self.parser._find_column_index_flexible(
                    headers_lower,
                    ["mandatory", "required", "is mandatory", "is required"]
                )

                if name_idx == -1 or type_idx == -1:
                    continue

                # Check each row
                for row in table_data.rows:
                    if not row or not any(row):
                        continue

                    name = row[name_idx] if name_idx < len(row) else ""
                    field_type_raw = row[type_idx] if type_idx < len(row) else ""

                    if not name or not name.strip():
                        continue

                    # Check if this field would be UNKNOWN
                    field_type = FieldType.from_string(field_type_raw)

                    if field_type == FieldType.UNKNOWN:
                        # This field was removed!
                        logic_value = row[logic_idx] if logic_idx != -1 and logic_idx < len(row) else ""
                        mandatory_value = row[mandatory_idx] if mandatory_idx != -1 and mandatory_idx < len(row) else ""

                        removed.append({
                            'name': name.strip(),
                            'field_type_raw': field_type_raw,
                            'mandatory': mandatory_value,
                            'logic': logic_value,
                            'table_type': table_data.table_type,
                            'context': table_data.context
                        })

        self.removed_fields[doc_name] = removed
        return removed

    def generate_html_report(self, output_path):
        """Generate HTML report of removed fields."""

        total_removed = sum(len(fields) for fields in self.removed_fields.values())

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Removed Fields Report - UNKNOWN Type Filter</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }}

        .header p {{
            font-size: 1.2em;
            opacity: 0.95;
        }}

        .summary {{
            background: #f8f9fa;
            padding: 30px;
            border-bottom: 3px solid #667eea;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            border-left: 4px solid #667eea;
        }}

        .summary-card h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}

        .summary-card .value {{
            font-size: 2.5em;
            font-weight: 700;
            color: #333;
        }}

        .content {{
            padding: 40px;
        }}

        .document-section {{
            margin-bottom: 50px;
        }}

        .document-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .document-header h2 {{
            font-size: 1.5em;
            font-weight: 600;
        }}

        .badge {{
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }}

        .no-fields {{
            background: #d4edda;
            color: #155724;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            margin-bottom: 20px;
        }}

        .field-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        }}

        .field-table thead {{
            background: #667eea;
            color: white;
        }}

        .field-table th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }}

        .field-table td {{
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
        }}

        .field-table tbody tr:hover {{
            background: #f8f9fa;
        }}

        .field-name {{
            font-weight: 600;
            color: #667eea;
            font-size: 1.05em;
        }}

        .type-badge {{
            background: #ffc107;
            color: #333;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            display: inline-block;
        }}

        .empty-type {{
            background: #dc3545;
            color: white;
        }}

        .mandatory-yes {{
            color: #dc3545;
            font-weight: 600;
        }}

        .mandatory-no {{
            color: #6c757d;
        }}

        .logic-text {{
            font-size: 0.9em;
            color: #666;
            max-width: 400px;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .table-context {{
            background: #e7f3ff;
            color: #004085;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            display: inline-block;
        }}

        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            border-top: 3px solid #667eea;
            color: #6c757d;
        }}

        .info-box {{
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
        }}

        .info-box h3 {{
            color: #2196F3;
            margin-bottom: 10px;
        }}

        .info-box ul {{
            margin-left: 20px;
            margin-top: 10px;
        }}

        .info-box li {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗑️ Removed Fields Report</h1>
            <p>Fields Skipped Due to UNKNOWN Type Filter</p>
        </div>

        <div class="summary">
            <h2 style="margin-bottom: 15px;">📊 Summary</h2>
            <div class="summary-grid">
                <div class="summary-card">
                    <h3>Total Removed</h3>
                    <div class="value">{total_removed}</div>
                </div>
                <div class="summary-card">
                    <h3>Documents Analyzed</h3>
                    <div class="value">{len(self.removed_fields)}</div>
                </div>
                <div class="summary-card">
                    <h3>Documents with Removals</h3>
                    <div class="value">{sum(1 for fields in self.removed_fields.values() if len(fields) > 0)}</div>
                </div>
            </div>
        </div>

        <div class="content">
            <div class="info-box">
                <h3>ℹ️ About This Report</h3>
                <p>This report shows all fields that were <strong>removed from the parsed output</strong> because they had UNKNOWN field types. Fields are removed when:</p>
                <ul>
                    <li>The field type column is empty</li>
                    <li>The field type is not recognized (not in FieldType enum)</li>
                    <li>The field type contains invalid or custom values</li>
                </ul>
                <p style="margin-top: 10px;"><strong>Parser Version:</strong> v1.2 (Skip UNKNOWN Fields)</p>
            </div>
"""

        # Add document sections
        for doc_name, fields in self.removed_fields.items():
            html += f"""
            <div class="document-section">
                <div class="document-header">
                    <h2>📄 {doc_name}</h2>
                    <span class="badge">{len(fields)} field{'s' if len(fields) != 1 else ''} removed</span>
                </div>
"""

            if not fields:
                html += """
                <div class="no-fields">
                    ✅ <strong>No fields removed</strong> - All fields in this document have valid types
                </div>
"""
            else:
                html += """
                <table class="field-table">
                    <thead>
                        <tr>
                            <th style="width: 5%">#</th>
                            <th style="width: 25%">Field Name</th>
                            <th style="width: 15%">Raw Type</th>
                            <th style="width: 15%">Table Context</th>
                            <th style="width: 10%">Mandatory</th>
                            <th style="width: 30%">Logic/Rules</th>
                        </tr>
                    </thead>
                    <tbody>
"""

                for i, field in enumerate(fields, 1):
                    type_badge_class = "empty-type" if not field['field_type_raw'].strip() else ""
                    mandatory_class = "mandatory-yes" if field['mandatory'].lower() in ['yes', 'true', 'mandatory'] else "mandatory-no"
                    mandatory_display = field['mandatory'] if field['mandatory'] else "—"
                    logic_display = field['logic'][:200] + "..." if len(field['logic']) > 200 else field['logic']
                    logic_display = logic_display if logic_display else "—"

                    # Extract table context (initiator, spoc, approver)
                    context = field['table_type'].replace('_fields', '').replace('_', ' ').title()

                    html += f"""
                        <tr>
                            <td>{i}</td>
                            <td class="field-name">{field['name']}</td>
                            <td><span class="type-badge {type_badge_class}">{field['field_type_raw'] if field['field_type_raw'] else '(empty)'}</span></td>
                            <td><span class="table-context">{context}</span></td>
                            <td class="{mandatory_class}">{mandatory_display}</td>
                            <td class="logic-text">{logic_display}</td>
                        </tr>
"""

                html += """
                    </tbody>
                </table>
"""

            html += """
            </div>
"""

        html += f"""
        </div>

        <div class="footer">
            <p><strong>Document Parser</strong> - Generated on {Path(__file__).parent.name}</p>
            <p>Total fields removed: <strong>{total_removed}</strong></p>
        </div>
    </div>
</body>
</html>
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"HTML report generated: {output_path}")
        return output_path


def main():
    analyzer = RemovedFieldsAnalyzer()

    documents = [
        'documents/Vendor Creation Sample BUD(1).docx',
        'documents/Change Beneficiary - UB 3526.docx',
        'documents/Complaint KYC - UB - 3803.docx',
        'documents/KYC Master - UB 3625, 3626, 3630.docx',
        'documents/Outlet_KYC _UB_3334.docx'
    ]

    print("Analyzing documents for removed fields...")
    print("=" * 70)

    for doc_path in documents:
        if Path(doc_path).exists():
            doc_name = Path(doc_path).stem
            removed = analyzer.analyze_document(doc_path)
            print(f"{doc_name:40} {len(removed):3} fields removed")
        else:
            print(f"⚠️  Document not found: {doc_path}")

    print("=" * 70)

    # Generate HTML report
    output_path = "removed_fields_report.html"
    analyzer.generate_html_report(output_path)

    total = sum(len(fields) for fields in analyzer.removed_fields.values())
    print(f"\n✅ Analysis complete!")
    print(f"📊 Total fields removed: {total}")
    print(f"📄 Report saved to: {output_path}")


if __name__ == "__main__":
    main()
