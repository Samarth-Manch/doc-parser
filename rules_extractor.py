"""
Rules Extractor - Converts natural language logic to JSON rules using OpenAI.
"""

import json
import os
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

from doc_parser.models import FieldDefinition, ParsedDocument
from doc_parser.parser import DocumentParser


@dataclass
class ExtractedRule:
    """Represents an extracted rule from field logic."""
    rule_name: str
    action: str
    source: Optional[str] = None
    source_variable_name: Optional[str] = None  # Variable name like __pan__
    destination_fields: List[str] = None
    destination_variable_names: List[str] = None  # Variable names like [__gst__, __mobile__]
    conditions: Optional[str] = None  # Expression syntax conditions
    expression: Optional[str] = None  # Full expression with variable names
    processing_type: str = "CLIENT"
    rule_type: str = "EXPRESSION"  # EXPRESSION or STANDARD
    confidence: float = 0.0
    original_logic: str = ""

    def __post_init__(self):
        if self.destination_fields is None:
            self.destination_fields = []
        if self.destination_variable_names is None:
            self.destination_variable_names = []


@dataclass
class FieldWithRules:
    """Field with extracted rules."""
    field_name: str
    field_type: str
    variable_name: str  # Like __pan__, __gst__, etc.
    is_mandatory: bool
    original_logic: str
    extracted_rules: List[ExtractedRule]
    source_info: Optional[str] = None  # e.g., "Data from PAN validation. Non-Editable"
    has_validation: bool = False
    has_visibility_rules: bool = False
    has_mandatory_rules: bool = False


class RulesKnowledgeBase:
    """Knowledge base of available rules from Rule-Schemas.json."""

    def __init__(self, schemas_path: str = "rules/Rule-Schemas.json"):
        self.rules = []
        self.rules_by_name = {}
        self.rules_by_action = {}
        self.load_schemas(schemas_path)

    def load_schemas(self, schemas_path: str):
        """Load rule schemas from JSON file."""
        with open(schemas_path, 'r') as f:
            data = json.load(f)
            self.rules = data.get('content', [])

        # Index by name and action
        for rule in self.rules:
            name = rule.get('name', '').lower()
            action = rule.get('action', '')

            self.rules_by_name[name] = rule

            if action not in self.rules_by_action:
                self.rules_by_action[action] = []
            self.rules_by_action[action].append(rule)

    def find_rule_by_keyword(self, keyword: str) -> Optional[Dict]:
        """Find rule by keyword in name."""
        keyword_lower = keyword.lower()

        # Exact match
        if keyword_lower in self.rules_by_name:
            return self.rules_by_name[keyword_lower]

        # Partial match
        for name, rule in self.rules_by_name.items():
            if keyword_lower in name:
                return rule

        return None

    def get_ocr_rules(self) -> List[Dict]:
        """Get all OCR rules."""
        return self.rules_by_action.get('OCR', [])

    def get_validation_rules(self) -> List[Dict]:
        """Get all VALIDATION rules."""
        return self.rules_by_action.get('VALIDATION', [])

    def get_rule_summary(self, rule: Dict) -> str:
        """Get a summary of a rule for LLM context."""
        summary = f"Rule: {rule.get('name', 'Unknown')}\n"
        summary += f"Action: {rule.get('action', 'N/A')}\n"
        summary += f"Source: {rule.get('source', 'N/A')}\n"

        dest_fields = rule.get('destinationFields', {})
        if dest_fields:
            fields = dest_fields.get('fields', [])
            field_names = [f['name'] for f in fields[:5]]
            summary += f"Destinations: {', '.join(field_names)}"
            if len(fields) > 5:
                summary += f" (and {len(fields) - 5} more)"
            summary += "\n"

        return summary

    def get_all_rules_compact(self) -> str:
        """Get a compact listing of all 182 rules for LLM context."""
        rules_text = "Available Standard Rules (182 total):\n\n"

        # Group by action
        for action, rules_list in sorted(self.rules_by_action.items()):
            rules_text += f"\n{action} Rules ({len(rules_list)}):\n"
            for rule in rules_list[:30]:  # Limit to first 30 per category to save tokens
                name = rule.get('name', 'Unknown')
                source = rule.get('source', 'N/A')
                rules_text += f"  - {name} (source: {source})\n"
            if len(rules_list) > 30:
                rules_text += f"  ... and {len(rules_list) - 30} more {action} rules\n"

        return rules_text


class RulesExtractor:
    """Extracts and converts field logic to JSON rules using OpenAI."""

    def __init__(self, openai_api_key: Optional[str] = None):
        load_dotenv()
        self.api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY in .env file")

        self.client = OpenAI(api_key=self.api_key)
        self.knowledge_base = RulesKnowledgeBase()
        self.field_map = {}  # Maps field names to variable names

        # Expression rule patterns
        self.expression_patterns = {
            'make_invisible': r'(?:make|set).*?invisible|hide|hidden',
            'make_visible': r'(?:make|set).*?visible|show|display',
            'make_mandatory': r'(?:make|set).*?mandatory|required',
            'make_non_mandatory': r'(?:make|set).*?(?:non-mandatory|optional|not required)',
            'enable': r'enable|editable',
            'disable': r'disable|non-editable|read-only',
            'copy': r'copy|populate|fill|auto.?fill',
            'validate': r'validat(?:e|ion)|check|verify',
        }

    def set_field_map(self, fields: List[FieldDefinition]):
        """Build a map of field names to variable names for reference resolution."""
        self.field_map = {field.name.lower(): field.variable_name for field in fields if field.variable_name}

    def find_variable_name(self, field_reference: str) -> Optional[str]:
        """Find variable name for a field reference (handles partial matches)."""
        if not field_reference:
            return None

        field_ref_lower = field_reference.lower().strip()

        # Exact match
        if field_ref_lower in self.field_map:
            return self.field_map[field_ref_lower]

        # Partial match (e.g., "PAN" matches "PAN Number")
        for field_name, var_name in self.field_map.items():
            if field_ref_lower in field_name or field_name in field_ref_lower:
                return var_name

        return None

    def get_field_mapping_context(self) -> str:
        """Generate context string with field name to variable name mappings."""
        if not self.field_map:
            return ""

        context = "\nAvailable Fields (use these variable names in expressions):\n"
        for field_name, var_name in sorted(self.field_map.items())[:50]:  # Limit to first 50
            context += f"  - {field_name.title()}: {var_name}\n"

        if len(self.field_map) > 50:
            context += f"  ... and {len(self.field_map) - 50} more fields\n"

        return context

    def extract_source_destination_info(self, logic: str) -> Dict[str, Any]:
        """Extract source and destination information from logic text."""
        info = {
            'source': None,
            'destinations': [],
            'is_editable': True,
            'validation_source': None
        }

        # Extract source information
        source_patterns = [
            r'(?:data|value|come)(?:s)?\s+(?:from|will come from)\s+([^.]+)',
            r'(?:auto|automatically)\s+(?:derived|filled|populated)\s+from\s+([^.]+)',
            r'(?:fetched|retrieved)\s+from\s+([^.]+)',
        ]

        for pattern in source_patterns:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                info['source'] = match.group(1).strip()
                break

        # Check if non-editable
        if re.search(r'non-editable|not editable|read-only|readonly', logic, re.IGNORECASE):
            info['is_editable'] = False

        # Extract validation source (e.g., "PAN validation", "Aadhaar OCR")
        validation_match = re.search(r'(PAN|Aadhaar|GST|[A-Z]+)\s+(?:validation|OCR|verification)', logic, re.IGNORECASE)
        if validation_match:
            info['validation_source'] = validation_match.group(0)

        return info

    def identify_rule_type(self, logic: str) -> str:
        """
        Identify if logic requires EXPRESSION rule or STANDARD rule.
        NOTE: Visibility and mandatory rules MUST always be EXPRESSION (EXECUTE action).
        """
        logic_lower = logic.lower()

        # ALWAYS use EXPRESSION for visibility/mandatory/enable/disable
        visibility_keywords = ['invisible', 'visible', 'hide', 'show', 'display']
        mandatory_keywords = ['mandatory', 'required', 'optional']
        editable_keywords = ['enable', 'disable', 'editable', 'non-editable', 'read-only']

        for keyword in visibility_keywords + mandatory_keywords + editable_keywords:
            if keyword in logic_lower:
                return 'EXPRESSION'

        # Check for conditional logic (always EXPRESSION)
        if 'if' in logic_lower or 'when' in logic_lower or 'based on' in logic_lower:
            return 'EXPRESSION'

        # Check for standard rule keywords (OCR, VALIDATION)
        ocr_keywords = ['ocr', 'scan', 'extract from image', 'extract from document']
        for keyword in ocr_keywords:
            if keyword in logic_lower and 'if' not in logic_lower:  # Only if not conditional
                return 'STANDARD'

        # Default to EXPRESSION (safer)
        return 'EXPRESSION'

    def extract_rules_with_llm(self, field: FieldDefinition) -> List[ExtractedRule]:
        """Use OpenAI to extract rules from field logic."""
        if not field.logic or not field.logic.strip():
            return []

        # Split logic by bullet points if merged
        logic_parts = field.logic.split('\n•')
        all_rules = []

        for logic in logic_parts:
            logic = logic.strip()
            if not logic:
                continue

            # Extract source/destination info
            src_dest_info = self.extract_source_destination_info(logic)

            # Identify rule type
            rule_type = self.identify_rule_type(logic)

            # Prepare context for LLM
            context = self._prepare_llm_context(field, logic, rule_type)

            # Call OpenAI
            try:
                rules = self._call_openai_for_rules(field, logic, context, rule_type, src_dest_info)
                all_rules.extend(rules)
            except Exception as e:
                print(f"Error extracting rules for {field.name}: {e}")
                # Create a basic rule as fallback
                all_rules.append(ExtractedRule(
                    rule_name=f"{field.name} Logic",
                    action="EXECUTE",
                    expression=logic,
                    rule_type=rule_type,
                    original_logic=logic,
                    confidence=0.3
                ))

        return all_rules

    def _prepare_llm_context(self, field: FieldDefinition, logic: str, rule_type: str) -> str:
        """Prepare context for LLM with ALL available rules."""
        context = f"""You are extracting form field rules from business requirement documents.

Field Information:
- Name: {field.name}
- Variable Name: {field.variable_name}
- Type: {field.field_type.name}
- Mandatory: {field.is_mandatory}

Logic/Rules: {logic}

IMPORTANT: You MUST use variable names (like __pan__, __gst__) instead of numeric IDs in all expressions.

"""

        # Always include expression rules documentation
        context += """
EXPRESSION RULES (action: EXECUTE):
These rules control field behavior dynamically using expression syntax.

Available Expression Functions:
- makeVisible(condition, destVar1, destVar2, ...) - Makes fields visible
- makeInvisible(condition, destVar1, destVar2, ...) - Makes fields invisible
- makeMandatory(condition, destVar1, destVar2, ...) - Makes fields mandatory
- makeNonMandatory(condition, destVar1, destVar2, ...) - Makes fields optional
- enable(condition, destVar1, destVar2, ...) - Enables fields (editable)
- disable(condition, destVar1, destVar2, ...) - Disables fields (read-only)
- copyToFillData(condition, sourceVar, destVar1, destVar2, ...) - Copies value
- clearField(condition, destVar1, destVar2, ...) - Clears field values

Expression Syntax:
- Use vo(variableName) to reference field values
- Example: makeVisible(vo(__gst_reg__)=='Yes', __gst__, __gst_pin__)
- Example: disable(true, __transaction_id__)
- Conditions use JavaScript syntax: ==, !=, >, <, &&, ||

"""

        # Include field mappings for reference
        context += self.get_field_mapping_context()

        # Include ALL standard rules
        if rule_type == 'STANDARD' or 'ocr' in logic.lower() or 'validation' in logic.lower():
            context += "\n" + self.knowledge_base.get_all_rules_compact()

        return context

    def _call_openai_for_rules(
        self,
        field: FieldDefinition,
        logic: str,
        context: str,
        rule_type: str,
        src_dest_info: Dict
    ) -> List[ExtractedRule]:
        """Call OpenAI API to extract rules with variable names."""

        prompt = f"""{context}

Extract the rule(s) from the logic above. Return a JSON array of rules with this structure:
{{
  "rules": [
    {{
      "rule_name": "Descriptive name of the rule",
      "action": "EXECUTE for ALL visibility/mandatory/enable rules, or OCR/VALIDATION/etc for standard rules",
      "source": "Source field name if mentioned",
      "source_variable_name": "Variable name of source field (e.g., __pan__)",
      "destination_fields": ["list of destination field names"],
      "destination_variable_names": ["list of destination variable names like __gst__, __mobile__"],
      "conditions": "Expression syntax condition (e.g., vo(__gst_reg__)=='Yes')",
      "expression": "Full expression using variable names (e.g., makeVisible(vo(__gst_reg__)=='Yes', __gst__))",
      "processing_type": "SERVER or CLIENT",
      "confidence": 0.0-1.0 confidence score
    }}
  ]
}}

CRITICAL RULES:
1. ALL visibility rules (show/hide/visible/invisible) MUST use action "EXECUTE" with makeVisible/makeInvisible
2. ALL mandatory rules MUST use action "EXECUTE" with makeMandatory/makeNonMandatory
3. ALL enable/disable rules MUST use action "EXECUTE" with enable/disable
4. ALWAYS use variable names (like __pan__, __gst__) NOT numeric IDs
5. Extract source and destination variable names from the field mapping provided
6. Write conditions in expression syntax: vo(__field_var__) == 'value'
7. For OCR/VALIDATION rules from Rule-Schemas, use the appropriate standard action
8. Extract ALL rules mentioned in the logic
9. Confidence: 0.8-1.0 if clear, 0.5-0.8 if somewhat ambiguous, <0.5 if very unclear

Return ONLY valid JSON, no other text."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a business rules extraction expert. You MUST use variable names like __pan__, __gst__ instead of numeric IDs. ALL visibility/mandatory/enable rules use action EXECUTE with expression syntax."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        # Parse response
        result = json.loads(response.choices[0].message.content)
        rules_data = result.get('rules', [])

        # Convert to ExtractedRule objects
        rules = []
        for rule_data in rules_data:
            # Force EXECUTE action for visibility/mandatory/enable rules
            action = rule_data.get('action', 'EXECUTE')
            if rule_type == 'EXPRESSION':
                action = 'EXECUTE'

            rule = ExtractedRule(
                rule_name=rule_data.get('rule_name', f"{field.name} Rule"),
                action=action,
                source=rule_data.get('source') or src_dest_info.get('source'),
                source_variable_name=rule_data.get('source_variable_name'),
                destination_fields=rule_data.get('destination_fields', []),
                destination_variable_names=rule_data.get('destination_variable_names', []),
                conditions=rule_data.get('conditions'),
                expression=rule_data.get('expression'),
                processing_type=rule_data.get('processing_type', 'CLIENT'),
                rule_type=rule_type,
                confidence=rule_data.get('confidence', 0.5),
                original_logic=logic
            )
            rules.append(rule)

        return rules

    def process_parsed_document(self, parsed_doc: ParsedDocument) -> List[FieldWithRules]:
        """Process all fields in a parsed document and extract rules."""
        from variable_name_generator import generate_variable_names

        # Step 1: Generate variable names for all fields
        generate_variable_names(parsed_doc.all_fields)

        # Step 2: Build field map for reference resolution
        self.set_field_map(parsed_doc.all_fields)

        # Step 3: Extract rules for each field
        fields_with_rules = []

        for field in parsed_doc.all_fields:
            # Extract rules
            extracted_rules = self.extract_rules_with_llm(field)

            # Get source info
            src_dest_info = self.extract_source_destination_info(field.logic)

            # Check rule types
            has_validation = any(r.action in ['VALIDATION', 'OCR', 'COMPARE'] for r in extracted_rules)
            has_visibility = any('visible' in r.rule_name.lower() or 'visible' in str(r.expression).lower()
                               for r in extracted_rules)
            has_mandatory = any('mandatory' in r.rule_name.lower() or 'mandatory' in str(r.expression).lower()
                              for r in extracted_rules)

            field_with_rules = FieldWithRules(
                field_name=field.name,
                field_type=field.field_type.name,
                variable_name=field.variable_name,  # Include variable name
                is_mandatory=field.is_mandatory,
                original_logic=field.logic,
                extracted_rules=extracted_rules,
                source_info=src_dest_info.get('source'),
                has_validation=has_validation,
                has_visibility_rules=has_visibility,
                has_mandatory_rules=has_mandatory
            )

            fields_with_rules.append(field_with_rules)

        return fields_with_rules

    def export_to_json(self, fields_with_rules: List[FieldWithRules], output_path: str):
        """Export extracted rules to JSON file."""
        export_data = {
            'total_fields': len(fields_with_rules),
            'fields_with_rules': sum(1 for f in fields_with_rules if f.extracted_rules),
            'total_rules_extracted': sum(len(f.extracted_rules) for f in fields_with_rules),
            'fields': []
        }

        for field_with_rules in fields_with_rules:
            field_data = {
                'field_name': field_with_rules.field_name,
                'field_type': field_with_rules.field_type,
                'is_mandatory': field_with_rules.is_mandatory,
                'original_logic': field_with_rules.original_logic,
                'source_info': field_with_rules.source_info,
                'has_validation': field_with_rules.has_validation,
                'has_visibility_rules': field_with_rules.has_visibility_rules,
                'has_mandatory_rules': field_with_rules.has_mandatory_rules,
                'rules': []
            }

            for rule in field_with_rules.extracted_rules:
                rule_dict = asdict(rule)
                field_data['rules'].append(rule_dict)

            export_data['fields'].append(field_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return output_path


def main():
    """Main function to demonstrate rules extraction."""
    # Parse document
    parser = DocumentParser()
    doc_path = 'documents/Vendor Creation Sample BUD(1).docx'

    print("Parsing document...")
    parsed_doc = parser.parse(doc_path)
    print(f"Found {len(parsed_doc.all_fields)} fields")

    # Extract rules
    print("\nExtracting rules using OpenAI...")
    extractor = RulesExtractor()

    # Process first 10 fields as demo
    demo_fields = parsed_doc.all_fields[:10]
    fields_with_rules = []

    for i, field in enumerate(demo_fields, 1):
        print(f"\nProcessing field {i}/{len(demo_fields)}: {field.name}")
        if field.logic:
            print(f"  Logic: {field.logic[:100]}...")

        extracted_rules = extractor.extract_rules_with_llm(field)
        src_dest_info = extractor.extract_source_destination_info(field.logic)

        field_with_rules = FieldWithRules(
            field_name=field.name,
            field_type=field.field_type.name,
            is_mandatory=field.is_mandatory,
            original_logic=field.logic,
            extracted_rules=extracted_rules,
            source_info=src_dest_info.get('source')
        )

        fields_with_rules.append(field_with_rules)

        if extracted_rules:
            print(f"  Extracted {len(extracted_rules)} rule(s):")
            for rule in extracted_rules:
                print(f"    - {rule.rule_name} ({rule.action}) [confidence: {rule.confidence:.2f}]")

    # Export to JSON
    output_path = "extracted_rules_demo.json"
    extractor.export_to_json(fields_with_rules, output_path)
    print(f"\n✅ Rules exported to: {output_path}")


if __name__ == "__main__":
    main()
