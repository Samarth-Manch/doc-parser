#!/usr/bin/env python3
"""
Rule Extraction System v1
Extracts rules from BUD logic/rules sections and populates formFillRules arrays.

Based on plan.md and lessons learned from self_heal_instructions_v100.json:
- Priority 1: Link OCR -> VERIFY chains via postTriggerRuleIds
- Priority 2: Add EXT_DROP_DOWN for external/cascading dropdowns
- Fix: Consolidate MAKE_DISABLED rules (single rule with multiple destinationIds)
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path


# ============================================================================
# ID Generator - Sequential IDs starting from 1
# ============================================================================

class IdGenerator:
    """Generate sequential IDs starting from 1 for each object type."""

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def next_id(self, id_type: str = 'rule') -> int:
        """Get next sequential ID for given type."""
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def reset(self, id_type: str = None):
        """Reset counter(s) to 0."""
        if id_type:
            self.counters[id_type] = 0
        else:
            self.counters = {}

    def get_current(self, id_type: str = 'rule') -> int:
        """Get current ID without incrementing."""
        return self.counters.get(id_type, 0)


# Global ID generator
id_generator = IdGenerator()


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class FieldInfo:
    """Information about a form field."""
    id: int
    name: str
    variable_name: str
    field_type: str
    mandatory: bool = False
    editable: bool = True
    visible: bool = True


@dataclass
class RuleInfo:
    """Information about a generated rule."""
    id: int
    action_type: str
    source_ids: List[int]
    destination_ids: List[int]
    source_type: Optional[str] = None
    conditional_values: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    processing_type: str = "CLIENT"
    button: str = ""
    params: Optional[str] = None


@dataclass
class ExtractionReport:
    """Report on rule extraction results."""
    total_fields: int = 0
    total_rules: int = 0
    rules_by_type: Dict[str, int] = field(default_factory=dict)
    ocr_verify_chains: int = 0
    visibility_rules: int = 0
    mandatory_rules: int = 0
    ext_dropdown_rules: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ============================================================================
# Rule Builder
# ============================================================================

class RuleBuilder:
    """Build formFillRules JSON structures."""

    @staticmethod
    def create_base_rule(
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int] = None,
        processing_type: str = "CLIENT"
    ) -> Dict:
        """Create base rule with all required fields and sequential ID."""
        return {
            "id": id_generator.next_id('rule'),
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": action_type,
            "processingType": processing_type,
            "sourceIds": source_ids,
            "destinationIds": destination_ids or [],
            "postTriggerRuleIds": [],
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }

    @staticmethod
    def create_conditional_rule(
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        conditional_values: List[str],
        condition: str = "IN"
    ) -> Dict:
        """Create conditional visibility/mandatory rule."""
        rule = RuleBuilder.create_base_rule(action_type, source_ids, destination_ids)
        rule.update({
            "conditionalValues": conditional_values,
            "condition": condition,
            "conditionValueType": "TEXT"
        })
        return rule

    @staticmethod
    def create_verify_rule(
        source_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        post_trigger_ids: List[int] = None,
        button: str = "Verify"
    ) -> Dict:
        """Create VERIFY rule for validation."""
        rule = RuleBuilder.create_base_rule("VERIFY", source_ids, destination_ids, "SERVER")
        rule.update({
            "sourceType": source_type,
            "button": button,
            "postTriggerRuleIds": post_trigger_ids or []
        })
        return rule

    @staticmethod
    def create_ocr_rule(
        source_type: str,
        source_ids: List[int],
        destination_ids: List[int],
        post_trigger_ids: List[int] = None
    ) -> Dict:
        """Create OCR rule for document extraction."""
        rule = RuleBuilder.create_base_rule("OCR", source_ids, destination_ids, "SERVER")
        rule.update({
            "sourceType": source_type,
            "postTriggerRuleIds": post_trigger_ids or []
        })
        return rule

    @staticmethod
    def create_ext_dropdown_rule(
        source_ids: List[int],
        destination_ids: List[int] = None,
        params: str = ""
    ) -> Dict:
        """Create external dropdown rule."""
        rule = RuleBuilder.create_base_rule("EXT_DROP_DOWN", source_ids, destination_ids or [], "SERVER")
        rule.update({
            "sourceType": "FORM_FILL_DROP_DOWN",
            "params": params,
            "searchable": True
        })
        return rule

    @staticmethod
    def create_ext_value_rule(
        source_ids: List[int],
        destination_ids: List[int] = None,
        params: str = ""
    ) -> Dict:
        """Create external value rule."""
        rule = RuleBuilder.create_base_rule("EXT_VALUE", source_ids, destination_ids or [], "SERVER")
        rule.update({
            "sourceType": "EXTERNAL_DATA_VALUE",
            "params": params
        })
        return rule

    @staticmethod
    def create_convert_to_rule(
        source_type: str,
        source_ids: List[int]
    ) -> Dict:
        """Create CONVERT_TO rule (e.g., UPPER_CASE)."""
        rule = RuleBuilder.create_base_rule("CONVERT_TO", source_ids, [])
        rule.update({
            "sourceType": source_type
        })
        return rule

    @staticmethod
    def create_gstin_with_pan_rule(
        pan_field_id: int,
        gstin_field_id: int
    ) -> Dict:
        """Create GSTIN with PAN cross-validation rule."""
        rule = RuleBuilder.create_base_rule("VERIFY", [pan_field_id, gstin_field_id], [], "SERVER")
        rule.update({
            "sourceType": "GSTIN_WITH_PAN",
            "params": '{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
            "onStatusFail": "CONTINUE"
        })
        return rule


# ============================================================================
# Field Index
# ============================================================================

class FieldIndex:
    """Index for looking up fields by name, ID, or variable name."""

    def __init__(self, schema: Dict):
        self.by_id: Dict[int, FieldInfo] = {}
        self.by_name: Dict[str, FieldInfo] = {}
        self.by_name_lower: Dict[str, FieldInfo] = {}
        self.by_variable: Dict[str, FieldInfo] = {}
        self._build_index(schema)

    def _build_index(self, schema: Dict):
        """Build indexes from schema."""
        document_types = schema.get('template', schema).get('documentTypes', [])

        for doc_type in document_types:
            for metadata in doc_type.get('formFillMetadatas', []):
                field_id = metadata.get('id')
                form_tag = metadata.get('formTag', {})
                field_name = form_tag.get('name', '')
                field_type = form_tag.get('type', 'TEXT')
                variable_name = metadata.get('variableName', '')

                field_info = FieldInfo(
                    id=field_id,
                    name=field_name,
                    variable_name=variable_name,
                    field_type=field_type,
                    mandatory=metadata.get('mandatory', False),
                    editable=metadata.get('editable', True),
                    visible=metadata.get('visible', True)
                )

                self.by_id[field_id] = field_info
                self.by_name[field_name] = field_info
                self.by_name_lower[field_name.lower()] = field_info
                self.by_variable[variable_name] = field_info

    def find_by_name(self, name: str) -> Optional[FieldInfo]:
        """Find field by exact or fuzzy name match."""
        # Exact match
        if name in self.by_name:
            return self.by_name[name]

        # Case-insensitive match
        name_lower = name.lower()
        if name_lower in self.by_name_lower:
            return self.by_name_lower[name_lower]

        # Fuzzy match - check for partial matches
        for field_name, field_info in self.by_name.items():
            if name_lower in field_name.lower() or field_name.lower() in name_lower:
                return field_info

        return None

    def find_by_variable(self, variable: str) -> Optional[FieldInfo]:
        """Find field by variable name."""
        # Normalize variable name
        normalized = variable.strip('_').lower().replace('_', '')

        for var_name, field_info in self.by_variable.items():
            var_normalized = var_name.strip('_').lower().replace('_', '')
            if normalized == var_normalized:
                return field_info

        return None

    def get_all_fields(self) -> List[FieldInfo]:
        """Get all fields in order."""
        return list(self.by_id.values())


# ============================================================================
# Intra-Panel Reference Processor
# ============================================================================

class IntraPanelProcessor:
    """Process intra-panel references to extract rule dependencies."""

    # Dependency type to rule type mapping
    DEPENDENCY_TO_RULE = {
        'visibility': ['MAKE_VISIBLE', 'MAKE_INVISIBLE'],
        'visibility_and_mandatory': ['MAKE_VISIBLE', 'MAKE_INVISIBLE', 'MAKE_MANDATORY', 'MAKE_NON_MANDATORY'],
        'visibility_condition': ['MAKE_VISIBLE', 'MAKE_INVISIBLE'],
        'mandatory': ['MAKE_MANDATORY', 'MAKE_NON_MANDATORY'],
        'data_source': ['OCR', 'VERIFY', 'COPY_TO'],
        'data_dependency': ['EXT_VALUE', 'EXT_DROP_DOWN'],
        'value_derivation': ['EXT_VALUE', 'COPY_TO'],
        'dropdown_cascade': ['EXT_DROP_DOWN'],
        'dropdown_filter': ['EXT_DROP_DOWN'],
        'validation': ['VERIFY', 'VALIDATION'],
        'conditional_behavior': ['MAKE_VISIBLE', 'MAKE_INVISIBLE', 'MAKE_DISABLED']
    }

    def __init__(self, intra_panel_data: Dict, field_index: FieldIndex):
        self.data = intra_panel_data
        self.field_index = field_index
        self.visibility_groups: Dict[str, List[Dict]] = defaultdict(list)
        self.mandatory_groups: Dict[str, List[Dict]] = defaultdict(list)
        self.ocr_sources: Dict[str, List[str]] = {}  # upload field -> destination fields
        self.verify_sources: Dict[str, List[str]] = {}  # source field -> destination fields
        self.ext_dropdown_fields: List[str] = []
        self.gstin_pan_pairs: List[Tuple[str, str]] = []

    def process(self) -> None:
        """Process all intra-panel references."""
        panel_results = self.data.get('panel_results', [])

        for panel in panel_results:
            refs = panel.get('intra_panel_references', [])
            for ref in refs:
                self._process_reference(ref)

            # Also process any alternative formats
            for ref in refs:
                self._process_alternative_formats(ref)

    def _process_alternative_formats(self, ref: Dict) -> None:
        """Handle alternative reference formats."""
        # Format with source_field and depends_on
        if 'source_field' in ref and 'depends_on' in ref:
            source_field = ref.get('source_field', '')
            depends_on = ref.get('depends_on', [])

            for dep in depends_on:
                target_field = dep.get('target_field', '')
                dep_type = dep.get('dependency_type', '')
                condition = dep.get('condition', '')
                logic_excerpt = dep.get('logic_excerpt', '')

                if dep_type == 'visibility':
                    cond_values = self._extract_conditional_values(condition + ' ' + logic_excerpt)
                    self.visibility_groups[target_field].append({
                        'destination_field': source_field,
                        'conditional_values': cond_values,
                        'dependency_type': dep_type,
                        'rule_description': logic_excerpt
                    })

                elif dep_type == 'data_source':
                    if 'OCR' in logic_excerpt.upper():
                        if target_field not in self.ocr_sources:
                            self.ocr_sources[target_field] = []
                        self.ocr_sources[target_field].append(source_field)

        # Format with field_name and referenced_by_within_panel
        if 'field_name' in ref and 'referenced_by_within_panel' in ref:
            source_field = ref.get('field_name', '')
            referenced_by = ref.get('referenced_by_within_panel', [])

            for ref_by in referenced_by:
                ref_field = ref_by.get('field_name', '')
                ref_type = ref_by.get('reference_type', '')
                ref_context = ref_by.get('reference_context', '')

                if ref_type == 'data_source' and 'copy' in ref_context.lower():
                    # This is a COPY_TO rule
                    pass  # Handled separately

        # Format with dependent_field dict and references list
        if 'dependent_field' in ref and isinstance(ref['dependent_field'], dict):
            dep_field = ref['dependent_field']
            field_name = dep_field.get('field_name', '')
            references = ref.get('references', [])

            for reference in references:
                ref_type = reference.get('dependency_type', reference.get('reference_type', ''))
                ref_field = reference.get('referenced_field_name', reference.get('target_field', ''))
                condition_desc = reference.get('condition_description', reference.get('dependency_description', ''))
                raw_logic = reference.get('raw_logic_excerpt', '')

                if ref_type == 'visibility':
                    cond_values = self._extract_conditional_values(condition_desc + ' ' + raw_logic)
                    self.visibility_groups[ref_field].append({
                        'destination_field': field_name,
                        'conditional_values': cond_values,
                        'dependency_type': ref_type,
                        'rule_description': condition_desc
                    })

                elif ref_type == 'value_derivation' and 'OCR' in condition_desc.upper():
                    if ref_field not in self.ocr_sources:
                        self.ocr_sources[ref_field] = []
                    self.ocr_sources[ref_field].append(field_name)

    def _process_reference(self, ref: Dict) -> None:
        """Process a single reference."""
        # Handle different reference formats
        if 'dependency_type' in ref:
            # Simple format
            self._process_simple_reference(ref)
        elif 'dependent_field' in ref and isinstance(ref['dependent_field'], dict):
            # Complex format with nested structure
            self._process_complex_reference(ref)

    def _process_simple_reference(self, ref: Dict) -> None:
        """Process simple format reference."""
        dep_type = ref.get('dependency_type', '')
        source_field = ref.get('source_field', '')
        dependent_field = ref.get('dependent_field', '')
        rule_desc = ref.get('rule_description', '')

        if dep_type in ['visibility', 'visibility_and_mandatory', 'visibility_condition']:
            # Extract conditional values from rule description
            conditional_values = self._extract_conditional_values(rule_desc)
            self.visibility_groups[source_field].append({
                'destination_field': dependent_field,
                'conditional_values': conditional_values,
                'dependency_type': dep_type,
                'rule_description': rule_desc
            })

            if dep_type == 'visibility_and_mandatory':
                self.mandatory_groups[source_field].append({
                    'destination_field': dependent_field,
                    'conditional_values': conditional_values,
                    'rule_description': rule_desc
                })

        elif dep_type == 'dropdown_cascade' or dep_type == 'dropdown_filter':
            self.ext_dropdown_fields.append(dependent_field)

        elif dep_type == 'value_derivation':
            # Could be EXT_VALUE or COPY_TO
            pass

    def _process_complex_reference(self, ref: Dict) -> None:
        """Process complex format reference with nested structure."""
        dep_field = ref.get('dependent_field', {})
        field_name = dep_field.get('field_name', '')
        logic_text = ref.get('logic_text', '')
        references = ref.get('references', [])

        for reference in references:
            ref_type = reference.get('reference_type', '')
            ref_field_name = reference.get('referenced_field_name', '')
            dep_desc = reference.get('dependency_description', '')

            if ref_type == 'visibility_condition':
                conditional_values = self._extract_conditional_values(dep_desc)
                self.visibility_groups[ref_field_name].append({
                    'destination_field': field_name,
                    'conditional_values': conditional_values,
                    'dependency_type': ref_type,
                    'rule_description': dep_desc
                })

            elif ref_type == 'data_source':
                # Check if it's OCR or VERIFY
                if 'OCR' in dep_desc.upper():
                    if ref_field_name not in self.ocr_sources:
                        self.ocr_sources[ref_field_name] = []
                    self.ocr_sources[ref_field_name].append(field_name)
                elif 'validation' in dep_desc.lower() or 'verification' in dep_desc.lower():
                    if ref_field_name not in self.verify_sources:
                        self.verify_sources[ref_field_name] = []
                    self.verify_sources[ref_field_name].append(field_name)

            elif ref_type == 'validation':
                # Cross-validation like GSTIN_WITH_PAN
                if 'PAN' in dep_desc and 'GST' in dep_desc:
                    self.gstin_pan_pairs.append((ref_field_name, field_name))

        # Check logic text for additional patterns
        if logic_text:
            self._extract_from_logic(field_name, logic_text)

    def _extract_from_logic(self, field_name: str, logic_text: str) -> None:
        """Extract rule information from logic text."""
        logic_lower = logic_text.lower()

        # Check for OCR rules
        if 'ocr' in logic_lower and 'get' in logic_lower:
            pass  # Already handled via references

        # Check for VERIFY rules
        if 'validation' in logic_lower or 'verify' in logic_lower:
            if 'perform' in logic_lower:
                # This field is a source of validation
                pass

    def _extract_conditional_values(self, text: str) -> List[str]:
        """Extract conditional values from rule description."""
        values = []

        # Pattern: "is 'Yes'" or 'is "Yes"'
        matches = re.findall(r"is\s+['\"]?([^'\"]+)['\"]?(?:\s+then|\s*,)", text, re.I)
        values.extend(matches)

        # Pattern: "value is yes" or "values is yes"
        matches = re.findall(r"values?\s+is\s+['\"]?(\w+)['\"]?", text, re.I)
        values.extend(matches)

        # Common values
        if 'yes' in text.lower():
            if 'Yes' not in values and 'yes' not in values:
                values.append('Yes')

        return list(set(values)) if values else ['Yes']


# ============================================================================
# Rule Extractor
# ============================================================================

class RuleExtractor:
    """Main rule extraction engine."""

    # VERIFY source type mappings
    VERIFY_SOURCE_TYPES = {
        'pan': 'PAN_NUMBER',
        'gstin': 'GSTIN',
        'gst': 'GSTIN',
        'bank': 'BANK_ACCOUNT_NUMBER',
        'ifsc': 'BANK_ACCOUNT_NUMBER',
        'msme': 'MSME_UDYAM_REG_NUMBER',
        'udyam': 'MSME_UDYAM_REG_NUMBER',
        'cin': 'CIN_ID',
        'tan': 'TAN_NUMBER',
        'fssai': 'FSSAI'
    }

    # OCR source type mappings
    OCR_SOURCE_TYPES = {
        'pan': 'PAN_IMAGE',
        'gstin': 'GSTIN_IMAGE',
        'gst': 'GSTIN_IMAGE',
        'aadhaar_front': 'AADHAR_IMAGE',
        'aadhaar_back': 'AADHAR_BACK_IMAGE',
        'aadhar_front': 'AADHAR_IMAGE',
        'aadhar_back': 'AADHAR_BACK_IMAGE',
        'cheque': 'CHEQUEE',
        'cancelled_cheque': 'CHEQUEE',
        'msme': 'MSME',
        'cin': 'CIN'
    }

    # Verify destination ordinals for common verification types
    VERIFY_ORDINALS = {
        'PAN_NUMBER': {
            'Pan Holder Name': 4,
            'PAN Holder Name': 4,
            'Fullname': 4,
            'Name': 4,
            'PAN Status': 6,
            'Pan Status': 6,
            'Status': 6,
            'PAN Type': 8,
            'Pan Type': 8,
            'Type': 8,
            'Aadhaar PAN List Status': 9,
            'Aadhaar Seeding Status': 9
        },
        'GSTIN': {
            'Trade Name': 1,
            'Legal Name': 2,
            'Reg Date': 3,
            'Registration Date': 3,
            'Type': 4,
            'Building Number': 5,
            'Street': 6,
            'City': 8,
            'District': 9,
            'State': 10,
            'Pin': 11,
            'Pincode': 11
        },
        'BANK_ACCOUNT_NUMBER': {
            'Bank Name': 1,
            'IFSC Code': 2,
            'IFSC': 2,
            'Beneficiary Name': 3,
            'Account Holder Name': 3
        }
    }

    def __init__(self, schema: Dict, intra_panel_data: Dict, verbose: bool = False):
        self.schema = schema
        self.intra_panel_data = intra_panel_data
        self.verbose = verbose
        self.field_index = FieldIndex(schema)
        self.intra_processor = IntraPanelProcessor(intra_panel_data, self.field_index)
        self.report = ExtractionReport()
        self.all_rules: List[Dict] = []
        self.rules_by_field: Dict[int, List[Dict]] = defaultdict(list)

        # OCR to VERIFY rule mapping for chaining
        self.verify_rules: Dict[int, Dict] = {}  # source_field_id -> verify_rule
        self.ocr_rules: List[Dict] = []

    def extract(self) -> Dict:
        """Run the full extraction pipeline."""
        # Reset ID generator
        id_generator.reset()

        # Process intra-panel references
        self.intra_processor.process()

        # Step 1: Generate visibility rules
        self._generate_visibility_rules()

        # Step 2: Generate mandatory rules
        self._generate_mandatory_rules()

        # Step 3: Generate VERIFY rules
        self._generate_verify_rules()

        # Step 4: Generate OCR rules
        self._generate_ocr_rules()

        # Step 5: Link OCR -> VERIFY chains
        self._link_ocr_verify_chains()

        # Step 6: Generate EXT_DROP_DOWN rules
        self._generate_ext_dropdown_rules()

        # Step 7: Generate other rules (CONVERT_TO, MAKE_DISABLED, etc.)
        self._generate_other_rules()

        # Step 8: Consolidate rules
        self._consolidate_rules()

        # Step 9: Populate schema with rules
        return self._populate_schema()

    def _generate_visibility_rules(self) -> None:
        """Generate visibility rules from intra-panel processor."""
        if self.verbose:
            print(f"Generating visibility rules from {len(self.intra_processor.visibility_groups)} source fields...")

        for source_field_name, destinations in self.intra_processor.visibility_groups.items():
            source_field = self.field_index.find_by_name(source_field_name)
            if not source_field:
                self.report.warnings.append(f"Source field not found: {source_field_name}")
                continue

            # Group destinations by conditional values
            by_condition: Dict[str, List[int]] = defaultdict(list)
            for dest in destinations:
                dest_field = self.field_index.find_by_name(dest['destination_field'])
                if dest_field:
                    cond_key = ','.join(sorted(dest['conditional_values']))
                    by_condition[cond_key].append(dest_field.id)

            # Create consolidated visibility rules
            for cond_key, dest_ids in by_condition.items():
                cond_values = cond_key.split(',') if cond_key else ['Yes']

                # MAKE_VISIBLE when condition matches
                visible_rule = RuleBuilder.create_conditional_rule(
                    'MAKE_VISIBLE',
                    [source_field.id],
                    dest_ids,
                    cond_values,
                    'IN'
                )
                self.rules_by_field[source_field.id].append(visible_rule)
                self.all_rules.append(visible_rule)
                self.report.visibility_rules += 1

                # MAKE_INVISIBLE when condition doesn't match
                invisible_rule = RuleBuilder.create_conditional_rule(
                    'MAKE_INVISIBLE',
                    [source_field.id],
                    dest_ids,
                    cond_values,
                    'NOT_IN'
                )
                self.rules_by_field[source_field.id].append(invisible_rule)
                self.all_rules.append(invisible_rule)
                self.report.visibility_rules += 1

    def _generate_mandatory_rules(self) -> None:
        """Generate mandatory rules from intra-panel processor."""
        if self.verbose:
            print(f"Generating mandatory rules from {len(self.intra_processor.mandatory_groups)} source fields...")

        for source_field_name, destinations in self.intra_processor.mandatory_groups.items():
            source_field = self.field_index.find_by_name(source_field_name)
            if not source_field:
                continue

            # Group destinations by conditional values
            by_condition: Dict[str, List[int]] = defaultdict(list)
            for dest in destinations:
                dest_field = self.field_index.find_by_name(dest['destination_field'])
                if dest_field:
                    cond_key = ','.join(sorted(dest['conditional_values']))
                    by_condition[cond_key].append(dest_field.id)

            # Create consolidated mandatory rules
            for cond_key, dest_ids in by_condition.items():
                cond_values = cond_key.split(',') if cond_key else ['Yes']

                # MAKE_MANDATORY when condition matches
                mandatory_rule = RuleBuilder.create_conditional_rule(
                    'MAKE_MANDATORY',
                    [source_field.id],
                    dest_ids,
                    cond_values,
                    'IN'
                )
                self.rules_by_field[source_field.id].append(mandatory_rule)
                self.all_rules.append(mandatory_rule)
                self.report.mandatory_rules += 1

                # MAKE_NON_MANDATORY when condition doesn't match
                non_mandatory_rule = RuleBuilder.create_conditional_rule(
                    'MAKE_NON_MANDATORY',
                    [source_field.id],
                    dest_ids,
                    cond_values,
                    'NOT_IN'
                )
                self.rules_by_field[source_field.id].append(non_mandatory_rule)
                self.all_rules.append(non_mandatory_rule)
                self.report.mandatory_rules += 1

    def _generate_verify_rules(self) -> None:
        """Generate VERIFY rules from intra-panel processor."""
        if self.verbose:
            print(f"Generating VERIFY rules from {len(self.intra_processor.verify_sources)} source fields...")

        for source_field_name, dest_field_names in self.intra_processor.verify_sources.items():
            source_field = self.field_index.find_by_name(source_field_name)
            if not source_field:
                self.report.warnings.append(f"VERIFY source field not found: {source_field_name}")
                continue

            # Determine source type
            source_type = self._detect_verify_source_type(source_field_name)
            if not source_type:
                self.report.warnings.append(f"Could not determine VERIFY source type for: {source_field_name}")
                continue

            # Build destination IDs with ordinal mapping
            destination_ids = self._build_verify_destination_ids(source_type, dest_field_names)

            # Create VERIFY rule
            verify_rule = RuleBuilder.create_verify_rule(
                source_type,
                [source_field.id],
                destination_ids,
                [],
                'Verify'
            )
            self.rules_by_field[source_field.id].append(verify_rule)
            self.all_rules.append(verify_rule)
            self.verify_rules[source_field.id] = verify_rule

        # Generate GSTIN_WITH_PAN cross-validation rules
        for pan_field_name, gstin_field_name in self.intra_processor.gstin_pan_pairs:
            pan_field = self.field_index.find_by_name(pan_field_name)
            gstin_field = self.field_index.find_by_name(gstin_field_name)
            if pan_field and gstin_field:
                cross_rule = RuleBuilder.create_gstin_with_pan_rule(
                    pan_field.id,
                    gstin_field.id
                )
                self.rules_by_field[gstin_field.id].append(cross_rule)
                self.all_rules.append(cross_rule)

    def _generate_ocr_rules(self) -> None:
        """Generate OCR rules from intra-panel processor."""
        if self.verbose:
            print(f"Generating OCR rules from {len(self.intra_processor.ocr_sources)} source fields...")

        for upload_field_name, dest_field_names in self.intra_processor.ocr_sources.items():
            upload_field = self.field_index.find_by_name(upload_field_name)
            if not upload_field:
                self.report.warnings.append(f"OCR upload field not found: {upload_field_name}")
                continue

            # Determine source type
            source_type = self._detect_ocr_source_type(upload_field_name)
            if not source_type:
                self.report.warnings.append(f"Could not determine OCR source type for: {upload_field_name}")
                continue

            # Get destination field(s)
            destination_ids = []
            for dest_name in dest_field_names:
                dest_field = self.field_index.find_by_name(dest_name)
                if dest_field:
                    destination_ids.append(dest_field.id)

            if not destination_ids:
                self.report.warnings.append(f"No destination fields found for OCR: {upload_field_name}")
                continue

            # Create OCR rule
            ocr_rule = RuleBuilder.create_ocr_rule(
                source_type,
                [upload_field.id],
                destination_ids,
                []  # Will be filled in during chain linking
            )
            self.rules_by_field[upload_field.id].append(ocr_rule)
            self.all_rules.append(ocr_rule)
            self.ocr_rules.append(ocr_rule)

    def _link_ocr_verify_chains(self) -> None:
        """Link OCR rules to corresponding VERIFY rules via postTriggerRuleIds."""
        if self.verbose:
            print(f"Linking {len(self.ocr_rules)} OCR rules to VERIFY rules...")

        # OCR source type to VERIFY source type mapping
        OCR_TO_VERIFY = {
            'PAN_IMAGE': 'PAN_NUMBER',
            'GSTIN_IMAGE': 'GSTIN',
            'CHEQUEE': 'BANK_ACCOUNT_NUMBER',
            'MSME': 'MSME_UDYAM_REG_NUMBER',
            'CIN': 'CIN_ID'
        }

        for ocr_rule in self.ocr_rules:
            ocr_source_type = ocr_rule.get('sourceType', '')
            verify_source_type = OCR_TO_VERIFY.get(ocr_source_type)

            if not verify_source_type:
                continue

            # Find the destination field of OCR
            dest_ids = ocr_rule.get('destinationIds', [])
            if not dest_ids:
                continue

            ocr_dest_field_id = dest_ids[0]

            # Find VERIFY rule that uses this field as source
            if ocr_dest_field_id in self.verify_rules:
                verify_rule = self.verify_rules[ocr_dest_field_id]
                if verify_rule.get('id') not in ocr_rule['postTriggerRuleIds']:
                    ocr_rule['postTriggerRuleIds'].append(verify_rule['id'])
                    self.report.ocr_verify_chains += 1
                    if self.verbose:
                        print(f"  Linked OCR {ocr_source_type} -> VERIFY {verify_source_type}")

    def _generate_ext_dropdown_rules(self) -> None:
        """Generate EXT_DROP_DOWN rules."""
        if self.verbose:
            print(f"Generating EXT_DROP_DOWN rules for {len(self.intra_processor.ext_dropdown_fields)} fields...")

        # Find fields with EXTERNAL_DROP_DOWN_VALUE type
        for field in self.field_index.get_all_fields():
            if field.field_type == 'EXTERNAL_DROP_DOWN_VALUE':
                ext_rule = RuleBuilder.create_ext_dropdown_rule(
                    [field.id],
                    [],
                    ''  # params would come from table references
                )
                self.rules_by_field[field.id].append(ext_rule)
                self.all_rules.append(ext_rule)
                self.report.ext_dropdown_rules += 1

    def _generate_other_rules(self) -> None:
        """Generate other rule types (CONVERT_TO, MAKE_DISABLED, etc.)."""
        if self.verbose:
            print("Generating other rules...")

        # Find fields that need CONVERT_TO UPPER_CASE
        upper_case_patterns = ['pan', 'gstin', 'gst', 'ifsc', 'cin', 'tan']

        for field in self.field_index.get_all_fields():
            field_name_lower = field.name.lower()

            # CONVERT_TO for specific fields
            for pattern in upper_case_patterns:
                if pattern in field_name_lower and field.field_type == 'TEXT':
                    # Check if this is a source field (not a destination of verification)
                    is_destination = False
                    for dest_fields in self.intra_processor.verify_sources.values():
                        if field.name in dest_fields:
                            is_destination = True
                            break

                    if not is_destination:
                        convert_rule = RuleBuilder.create_convert_to_rule(
                            'UPPER_CASE',
                            [field.id]
                        )
                        self.rules_by_field[field.id].append(convert_rule)
                        self.all_rules.append(convert_rule)
                    break

    def _consolidate_rules(self) -> None:
        """Consolidate and deduplicate rules."""
        if self.verbose:
            print("Consolidating rules...")

        # Group rules for consolidation
        groupable_actions = ['MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE',
                            'MAKE_MANDATORY', 'MAKE_NON_MANDATORY']

        rule_groups: Dict[tuple, List[Dict]] = defaultdict(list)
        non_groupable = []

        for rule in self.all_rules:
            action = rule.get('actionType')
            if action in groupable_actions:
                key = (
                    action,
                    tuple(sorted(rule.get('sourceIds', []))),
                    rule.get('condition'),
                    tuple(sorted(rule.get('conditionalValues', [])))
                )
                rule_groups[key].append(rule)
            else:
                non_groupable.append(rule)

        # Merge grouped rules
        consolidated = []
        for key, rules in rule_groups.items():
            if len(rules) == 1:
                consolidated.append(rules[0])
            else:
                # Merge: combine all destinationIds
                merged = rules[0].copy()
                all_dest_ids = set()
                for r in rules:
                    all_dest_ids.update(r.get('destinationIds', []))
                merged['destinationIds'] = sorted(list(all_dest_ids))
                consolidated.append(merged)

        consolidated.extend(non_groupable)
        self.all_rules = consolidated

    def _detect_verify_source_type(self, field_name: str) -> Optional[str]:
        """Detect VERIFY source type from field name."""
        field_name_lower = field_name.lower()
        for keyword, source_type in self.VERIFY_SOURCE_TYPES.items():
            if keyword in field_name_lower:
                return source_type
        return None

    def _detect_ocr_source_type(self, field_name: str) -> Optional[str]:
        """Detect OCR source type from field name."""
        field_name_lower = field_name.lower().replace(' ', '_')

        # Check for specific patterns
        if 'pan' in field_name_lower and ('upload' in field_name_lower or 'image' in field_name_lower):
            return 'PAN_IMAGE'
        if 'gstin' in field_name_lower and ('upload' in field_name_lower or 'image' in field_name_lower):
            return 'GSTIN_IMAGE'
        if 'gst' in field_name_lower and ('upload' in field_name_lower or 'image' in field_name_lower):
            return 'GSTIN_IMAGE'
        if 'aadhaar' in field_name_lower or 'aadhar' in field_name_lower:
            if 'back' in field_name_lower:
                return 'AADHAR_BACK_IMAGE'
            return 'AADHAR_IMAGE'
        if 'cheque' in field_name_lower:
            return 'CHEQUEE'
        if 'msme' in field_name_lower or 'udyam' in field_name_lower:
            return 'MSME'
        if 'cin' in field_name_lower:
            return 'CIN'

        # Check generic patterns
        for keyword, source_type in self.OCR_SOURCE_TYPES.items():
            if keyword in field_name_lower:
                return source_type

        return None

    def _build_verify_destination_ids(self, source_type: str, dest_field_names: List[str]) -> List[int]:
        """Build destination IDs array with ordinal mapping."""
        ordinals = self.VERIFY_ORDINALS.get(source_type, {})
        if not ordinals:
            # No ordinal mapping, just return field IDs
            return [self.field_index.find_by_name(name).id
                    for name in dest_field_names
                    if self.field_index.find_by_name(name)]

        # Determine max ordinal
        max_ordinal = max(ordinals.values()) if ordinals else 0

        # Initialize with -1 for all positions
        destination_ids = [-1] * max_ordinal

        # Map fields to ordinal positions
        for dest_name in dest_field_names:
            dest_field = self.field_index.find_by_name(dest_name)
            if dest_field:
                # Find ordinal for this field
                for ordinal_name, ordinal in ordinals.items():
                    if ordinal_name.lower() in dest_name.lower() or dest_name.lower() in ordinal_name.lower():
                        if ordinal <= max_ordinal:
                            destination_ids[ordinal - 1] = dest_field.id
                        break

        return destination_ids

    def _populate_schema(self) -> Dict:
        """Populate the schema with generated rules."""
        # Deep copy schema
        populated = json.loads(json.dumps(self.schema))

        # Get document types
        document_types = populated.get('template', populated).get('documentTypes', [])

        for doc_type in document_types:
            for metadata in doc_type.get('formFillMetadatas', []):
                field_id = metadata.get('id')
                if field_id in self.rules_by_field:
                    metadata['formFillRules'] = self.rules_by_field[field_id]

        # Update report
        self.report.total_fields = len(self.field_index.by_id)
        self.report.total_rules = len(self.all_rules)

        # Count rules by type
        for rule in self.all_rules:
            action = rule.get('actionType', 'UNKNOWN')
            self.report.rules_by_type[action] = self.report.rules_by_type.get(action, 0) + 1

        return populated

    def get_report(self) -> Dict:
        """Get extraction report as dictionary."""
        return {
            'total_fields': self.report.total_fields,
            'total_rules': self.report.total_rules,
            'rules_by_type': self.report.rules_by_type,
            'ocr_verify_chains': self.report.ocr_verify_chains,
            'visibility_rules': self.report.visibility_rules,
            'mandatory_rules': self.report.mandatory_rules,
            'ext_dropdown_rules': self.report.ext_dropdown_rules,
            'warnings': self.report.warnings,
            'errors': self.report.errors
        }


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Rule Extraction System')
    parser.add_argument('--schema', required=True, help='Path to input schema JSON')
    parser.add_argument('--intra-panel', required=True, help='Path to intra-panel references JSON')
    parser.add_argument('--output', required=True, help='Path for output populated schema')
    parser.add_argument('--report', help='Path for extraction report JSON')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()

    # Load input files
    print(f"Loading schema from: {args.schema}")
    with open(args.schema, 'r') as f:
        schema = json.load(f)

    print(f"Loading intra-panel references from: {args.intra_panel}")
    with open(args.intra_panel, 'r') as f:
        intra_panel_data = json.load(f)

    # Run extraction
    print("Running rule extraction...")
    extractor = RuleExtractor(schema, intra_panel_data, verbose=args.verbose)
    populated_schema = extractor.extract()

    # Save outputs
    print(f"Saving populated schema to: {args.output}")
    with open(args.output, 'w') as f:
        json.dump(populated_schema, f, indent=2)

    report = extractor.get_report()

    if args.report:
        print(f"Saving report to: {args.report}")
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)

    # Print summary
    print("\n=== Extraction Summary ===")
    print(f"Total fields: {report['total_fields']}")
    print(f"Total rules generated: {report['total_rules']}")
    print(f"OCR → VERIFY chains: {report['ocr_verify_chains']}")
    print(f"Visibility rules: {report['visibility_rules']}")
    print(f"Mandatory rules: {report['mandatory_rules']}")
    print(f"EXT_DROP_DOWN rules: {report['ext_dropdown_rules']}")
    print("\nRules by type:")
    for action_type, count in sorted(report['rules_by_type'].items()):
        print(f"  {action_type}: {count}")

    if report['warnings']:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report['warnings'][:10]:
            print(f"  - {warning}")
        if len(report['warnings']) > 10:
            print(f"  ... and {len(report['warnings']) - 10} more")

    if report['errors']:
        print(f"\nErrors ({len(report['errors'])}):")
        for error in report['errors']:
            print(f"  - {error}")

    print("\nDone!")


if __name__ == '__main__':
    main()
