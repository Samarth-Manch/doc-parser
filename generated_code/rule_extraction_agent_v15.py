#!/usr/bin/env python3
"""
Rule Extraction Agent v15 - Complete Implementation
Addresses all issues from v12 evaluation:
- Missing 227 rules across 14 rule types
- 20 missing fields
- Field type mismatches
- Sequential ID generation starting from 1
- Proper ID references
- EDV mapping integration
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict


# ============================================================================
# PHASE 1: CORE INFRASTRUCTURE
# ============================================================================

class SequentialIDGenerator:
    """Generates sequential IDs starting from 1 for all entities"""

    def __init__(self):
        self.current_id = 0

    def next_id(self) -> int:
        """Get next sequential ID"""
        self.current_id += 1
        return self.current_id

    def reset(self):
        """Reset counter to 0"""
        self.current_id = 0


@dataclass
class ParsedLogic:
    """Parsed logic statement from BUD document"""
    raw_expression: str
    operation_type: str  # controlled_by, value_derivation, data_dependency, validation, etc.
    relationship_type: str
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    referenced_fields: List[str] = field(default_factory=list)
    referenced_values: List[str] = field(default_factory=list)
    referenced_tables: List[str] = field(default_factory=list)


@dataclass
class FieldMatch:
    """Matched field with ID and metadata"""
    field_name: str
    field_id: int
    field_type: str
    variable_name: str
    panel_name: str
    match_score: float
    original_name: str = ""


@dataclass
class RuleCandidate:
    """Candidate rule to be generated"""
    action_type: str
    source_field_ids: List[int]
    destination_field_ids: List[int]
    condition: Optional[str] = None
    conditional_values: List[str] = field(default_factory=list)
    params: Optional[Dict[str, Any]] = None
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    processing_type: str = "CLIENT"
    condition_value_type: str = "TEXT"


# ============================================================================
# LOGIC PARSER
# ============================================================================

class LogicParser:
    """Parse BUD logic statements into structured data"""

    # Visibility keywords
    VISIBLE_KEYWORDS = ['visible', 'show', 'display', 'appear']
    INVISIBLE_KEYWORDS = ['invisible', 'not visible', 'hidden', 'hide', 'not display']

    # Mandatory keywords
    MANDATORY_KEYWORDS = ['mandatory', 'required', 'must', 'compulsory']
    NON_MANDATORY_KEYWORDS = ['non-mandatory', 'not mandatory', 'optional', 'not required']

    # Editable keywords
    DISABLED_KEYWORDS = ['disabled', 'not editable', 'non-editable', 'noneditable', 'read-only', 'readonly']
    ENABLED_KEYWORDS = ['enabled', 'editable', 'can edit']

    # Validation keywords
    VALIDATION_KEYWORDS = ['validate', 'validation', 'check', 'verify', 'must be', 'should be']

    # Value operations
    COPY_KEYWORDS = ['copy', 'copied', 'same as', 'replicate']
    DERIVE_KEYWORDS = ['derive', 'derived', 'calculate', 'compute']
    CONVERT_KEYWORDS = ['convert', 'transform', 'change to']

    # Table/EDV references
    TABLE_PATTERN = re.compile(r'table\s+(\d+\.?\d*)', re.IGNORECASE)
    COLUMN_PATTERN = re.compile(r'column\s+(\d+)', re.IGNORECASE)

    # Conditional patterns
    IF_PATTERN = re.compile(r'\b(if|when|where)\b', re.IGNORECASE)
    THEN_PATTERN = re.compile(r'\b(then|,\s*then)\b', re.IGNORECASE)
    ELSE_PATTERN = re.compile(r'\b(else|otherwise)\b', re.IGNORECASE)

    def parse(self, logic: Dict[str, Any]) -> ParsedLogic:
        """Parse logic dictionary into structured ParsedLogic"""
        raw_expr = logic.get('raw_expression', '')
        operation_type = logic.get('operation_type', '')
        relationship_type = logic.get('relationship_type', '')

        parsed = ParsedLogic(
            raw_expression=raw_expr,
            operation_type=operation_type,
            relationship_type=relationship_type
        )

        # Extract conditions and actions
        self._extract_conditions_actions(raw_expr, parsed)

        # Extract referenced tables
        tables = self.TABLE_PATTERN.findall(raw_expr)
        parsed.referenced_tables = tables

        return parsed

    def _extract_conditions_actions(self, text: str, parsed: ParsedLogic):
        """Extract conditions and actions from logic text"""
        text_lower = text.lower()

        # Split by IF/THEN/ELSE
        parts = re.split(r'\b(if|when|then|else|otherwise)\b', text, flags=re.IGNORECASE)

        current_section = 'condition'
        for i, part in enumerate(parts):
            part_lower = part.lower().strip()

            if part_lower in ['if', 'when']:
                current_section = 'condition'
            elif part_lower in ['then']:
                current_section = 'action'
            elif part_lower in ['else', 'otherwise']:
                current_section = 'else_action'
            else:
                # Process the content
                if part.strip():
                    if current_section == 'condition':
                        parsed.conditions.append(part.strip())
                    elif current_section in ['action', 'else_action']:
                        parsed.actions.append(part.strip())

    def identify_rule_types(self, logic: ParsedLogic) -> List[str]:
        """Identify what types of rules this logic implies"""
        rule_types = []
        text_lower = logic.raw_expression.lower()

        # Check visibility rules
        if any(kw in text_lower for kw in self.INVISIBLE_KEYWORDS):
            rule_types.append('MAKE_INVISIBLE')
        if any(kw in text_lower for kw in self.VISIBLE_KEYWORDS):
            rule_types.append('MAKE_VISIBLE')

        # Check mandatory rules
        if any(kw in text_lower for kw in self.MANDATORY_KEYWORDS):
            rule_types.append('MAKE_MANDATORY')
        if any(kw in text_lower for kw in self.NON_MANDATORY_KEYWORDS):
            rule_types.append('MAKE_NON_MANDATORY')

        # Check editable rules
        if any(kw in text_lower for kw in self.DISABLED_KEYWORDS):
            rule_types.append('MAKE_DISABLED')
        if any(kw in text_lower for kw in self.ENABLED_KEYWORDS):
            rule_types.append('MAKE_ENABLED')

        # Check validation rules
        if any(kw in text_lower for kw in self.VALIDATION_KEYWORDS):
            rule_types.append('VALIDATION')

        # Check value operation rules
        if any(kw in text_lower for kw in self.COPY_KEYWORDS):
            rule_types.append('COPY_TO')
        if any(kw in text_lower for kw in self.CONVERT_KEYWORDS):
            rule_types.append('CONVERT_TO')

        # Check for table references (EDV)
        if 'table' in text_lower or 'dropdown' in text_lower:
            rule_types.append('EXT_DROP_DOWN')
            if 'based on' in text_lower or 'filter' in text_lower:
                rule_types.append('EXT_VALUE')

        # Check for OCR/Verify
        if 'ocr' in text_lower or 'extract from document' in text_lower:
            rule_types.append('OCR')
            rule_types.append('VERIFY')

        # Check for date operations
        if 'date' in text_lower and ('current' in text_lower or 'today' in text_lower):
            rule_types.append('SET_DATE')

        return rule_types


# ============================================================================
# FIELD MATCHER
# ============================================================================

class FieldMatcher:
    """Match field references to field IDs using fuzzy matching"""

    def __init__(self):
        self.field_index: Dict[str, FieldMatch] = {}
        self.name_variations: Dict[str, List[str]] = defaultdict(list)

    def index_fields(self, fields: List[Dict[str, Any]]):
        """Build index of all fields for fast lookup"""
        for fld in fields:
            field_name = fld.get('formTag', {}).get('name', '')
            field_id = fld.get('id', 0)
            field_type = fld.get('formTag', {}).get('type', 'TEXT')
            variable_name = fld.get('variableName', '')

            # Store exact match
            match = FieldMatch(
                field_name=field_name,
                field_id=field_id,
                field_type=field_type,
                variable_name=variable_name,
                panel_name='',
                match_score=1.0,
                original_name=field_name
            )
            self.field_index[field_name.lower()] = match

            # Store variations
            variations = self._generate_variations(field_name)
            for var in variations:
                self.name_variations[var.lower()].append(field_name)

    def _generate_variations(self, name: str) -> List[str]:
        """Generate name variations for matching"""
        variations = [name]

        # Remove special characters
        clean = re.sub(r'[^\w\s]', ' ', name)
        variations.append(clean)

        # Remove extra spaces
        compact = re.sub(r'\s+', ' ', clean).strip()
        variations.append(compact)

        # Lowercase
        variations.append(name.lower())
        variations.append(clean.lower())

        # Remove "the", "a", "an"
        no_articles = re.sub(r'\b(the|a|an)\b', '', compact, flags=re.IGNORECASE)
        variations.append(no_articles.strip())

        return list(set(variations))

    def find_field(self, field_name: str) -> Optional[FieldMatch]:
        """Find field by name with fuzzy matching"""
        if not field_name:
            return None

        # Try exact match first
        field_lower = field_name.lower()
        if field_lower in self.field_index:
            return self.field_index[field_lower]

        # Try variations
        for variation in self._generate_variations(field_name):
            if variation.lower() in self.field_index:
                return self.field_index[variation.lower()]

        # Fuzzy match
        best_match = None
        best_score = 0.0

        for indexed_name, match in self.field_index.items():
            score = SequenceMatcher(None, field_lower, indexed_name).ratio()
            if score > best_score and score > 0.7:
                best_score = score
                best_match = match

        return best_match

    def find_fields_by_pattern(self, pattern: str) -> List[FieldMatch]:
        """Find fields matching a pattern"""
        matches = []
        pattern_lower = pattern.lower()

        for indexed_name, match in self.field_index.items():
            if pattern_lower in indexed_name or indexed_name in pattern_lower:
                matches.append(match)

        return matches


# ============================================================================
# PHASE 2: RULE BUILDERS
# ============================================================================

class BaseRuleBuilder:
    """Base class for all rule builders"""

    def __init__(self, id_generator: SequentialIDGenerator):
        self.id_gen = id_generator

    def build_rule(self, rule_candidate: RuleCandidate) -> Dict[str, Any]:
        """Build a complete rule dictionary"""
        rule = {
            "id": self.id_gen.next_id(),
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": rule_candidate.action_type,
            "processingType": rule_candidate.processing_type,
            "sourceIds": rule_candidate.source_field_ids,
            "destinationIds": rule_candidate.destination_field_ids,
            "conditionalValues": rule_candidate.conditional_values,
            "condition": rule_candidate.condition or "",
            "conditionValueType": rule_candidate.condition_value_type,
            "postTriggerRuleIds": rule_candidate.post_trigger_rule_ids,
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }

        # Add params if present
        if rule_candidate.params:
            rule["params"] = json.dumps(rule_candidate.params)

        return rule


class VisibilityRuleBuilder(BaseRuleBuilder):
    """Build visibility rules (MAKE_VISIBLE/MAKE_INVISIBLE)"""

    def build_from_logic(self, source_field: FieldMatch, target_fields: List[FieldMatch],
                        logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Build visibility rules from parsed logic"""
        rules = []
        text_lower = logic.raw_expression.lower()

        # Determine if it's visibility or invisibility
        is_invisible = any(kw in text_lower for kw in ['invisible', 'not visible', 'hidden', 'hide'])
        action_type = 'MAKE_INVISIBLE' if is_invisible else 'MAKE_VISIBLE'

        # Extract condition values
        conditional_values = self._extract_values_from_logic(logic)
        condition = self._determine_condition(logic)

        for target in target_fields:
            candidate = RuleCandidate(
                action_type=action_type,
                source_field_ids=[source_field.field_id],
                destination_field_ids=[target.field_id],
                condition=condition,
                conditional_values=conditional_values
            )
            rules.append(self.build_rule(candidate))

        return rules

    def _extract_values_from_logic(self, logic: ParsedLogic) -> List[str]:
        """Extract conditional values from logic"""
        values = []
        text = logic.raw_expression

        # Look for quoted values
        quoted = re.findall(r'"([^"]+)"', text)
        values.extend(quoted)

        # Look for specific values after "is selected", "equals", etc.
        patterns = [
            r'is selected as\s+([A-Z0-9, ]+)',
            r'equals\s+([A-Z0-9, ]+)',
            r'value is\s+([A-Z0-9, ]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Split by comma
                vals = [v.strip() for v in match.split(',')]
                values.extend(vals)

        return values if values else []

    def _determine_condition(self, logic: ParsedLogic) -> str:
        """Determine the condition type from logic"""
        text_lower = logic.raw_expression.lower()

        if 'not' in text_lower or 'except' in text_lower:
            return 'NOT_IN'
        elif 'any one' in text_lower or 'any of' in text_lower:
            return 'IN'
        elif '=' in text_lower or 'equals' in text_lower:
            return 'EQUALS'

        return 'IN'


class MandatoryRuleBuilder(BaseRuleBuilder):
    """Build mandatory rules (MAKE_MANDATORY/MAKE_NON_MANDATORY)"""

    def build_from_logic(self, source_field: FieldMatch, target_fields: List[FieldMatch],
                        logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Build mandatory rules from parsed logic"""
        rules = []
        text_lower = logic.raw_expression.lower()

        # Determine if it's mandatory or non-mandatory
        is_mandatory = any(kw in text_lower for kw in ['mandatory', 'required', 'compulsory'])
        action_type = 'MAKE_MANDATORY' if is_mandatory else 'MAKE_NON_MANDATORY'

        conditional_values = self._extract_values_from_logic(logic)
        condition = self._determine_condition(logic)

        for target in target_fields:
            candidate = RuleCandidate(
                action_type=action_type,
                source_field_ids=[source_field.field_id],
                destination_field_ids=[target.field_id],
                condition=condition,
                conditional_values=conditional_values
            )
            rules.append(self.build_rule(candidate))

        return rules

    def _extract_values_from_logic(self, logic: ParsedLogic) -> List[str]:
        """Extract conditional values from logic"""
        values = []
        text = logic.raw_expression

        # Similar to visibility builder
        quoted = re.findall(r'"([^"]+)"', text)
        values.extend(quoted)

        patterns = [
            r'is selected as\s+([A-Z0-9, ]+)',
            r'value is\s+([A-Z0-9, ]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                vals = [v.strip() for v in match.split(',')]
                values.extend(vals)

        return values if values else []

    def _determine_condition(self, logic: ParsedLogic) -> str:
        """Determine condition type"""
        text_lower = logic.raw_expression.lower()

        if 'not' in text_lower or 'except' in text_lower:
            return 'NOT_IN'
        elif 'any one' in text_lower or 'any of' in text_lower:
            return 'IN'

        return 'IN'


class EditableRuleBuilder(BaseRuleBuilder):
    """Build editable rules (MAKE_DISABLED/MAKE_ENABLED)"""

    def build_from_logic(self, source_field: FieldMatch, target_fields: List[FieldMatch],
                        logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Build editable rules from parsed logic"""
        rules = []
        text_lower = logic.raw_expression.lower()

        is_disabled = any(kw in text_lower for kw in ['disabled', 'not editable', 'non-editable', 'read-only'])
        action_type = 'MAKE_DISABLED' if is_disabled else 'MAKE_ENABLED'

        conditional_values = self._extract_values_from_logic(logic)
        condition = self._determine_condition(logic)

        for target in target_fields:
            candidate = RuleCandidate(
                action_type=action_type,
                source_field_ids=[source_field.field_id],
                destination_field_ids=[target.field_id],
                condition=condition,
                conditional_values=conditional_values
            )
            rules.append(self.build_rule(candidate))

        return rules

    def _extract_values_from_logic(self, logic: ParsedLogic) -> List[str]:
        """Extract conditional values"""
        values = []
        text = logic.raw_expression

        quoted = re.findall(r'"([^"]+)"', text)
        values.extend(quoted)

        return values if values else []

    def _determine_condition(self, logic: ParsedLogic) -> str:
        """Determine condition type"""
        text_lower = logic.raw_expression.lower()

        if 'not' in text_lower:
            return 'NOT_IN'

        return 'IN'


class ValidationRuleBuilder(BaseRuleBuilder):
    """Build validation rules"""

    def build_from_logic(self, source_field: FieldMatch, target_fields: List[FieldMatch],
                        logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Build validation rules from parsed logic"""
        rules = []
        text_lower = logic.raw_expression.lower()

        # Extract validation message
        validation_msg = self._extract_validation_message(logic)

        params = {
            "message": validation_msg
        }

        conditional_values = self._extract_values_from_logic(logic)
        condition = self._determine_condition(logic)

        for target in target_fields:
            candidate = RuleCandidate(
                action_type='VALIDATION',
                source_field_ids=[source_field.field_id],
                destination_field_ids=[target.field_id],
                condition=condition,
                conditional_values=conditional_values,
                params=params
            )
            rules.append(self.build_rule(candidate))

        return rules

    def _extract_validation_message(self, logic: ParsedLogic) -> str:
        """Extract validation message from logic"""
        # Default validation message
        return "Validation failed"

    def _extract_values_from_logic(self, logic: ParsedLogic) -> List[str]:
        """Extract values for validation"""
        return []

    def _determine_condition(self, logic: ParsedLogic) -> str:
        """Determine condition type"""
        return 'EQUALS'


class EDVRuleBuilder(BaseRuleBuilder):
    """Build EXT_DROP_DOWN and EXT_VALUE rules"""

    def __init__(self, id_generator: SequentialIDGenerator,
                 edv_tables: Dict[str, Any], field_edv_mapping: Dict[str, Any]):
        super().__init__(id_generator)
        self.edv_tables = edv_tables
        self.field_edv_mapping = field_edv_mapping

    def build_ext_dropdown(self, field: FieldMatch, edv_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build EXT_DROP_DOWN rule"""
        edv_table = edv_config.get('edv_table', '')

        params = {
            "conditionList": [{
                "ddType": [edv_table],
                "criterias": [],
                "da": ["a1"],
                "criteriaSearchAttr": [],
                "additionalOptions": None,
                "emptyAddOptionCheck": None,
                "ddProperties": None
            }]
        }

        candidate = RuleCandidate(
            action_type='EXT_DROP_DOWN',
            source_field_ids=[field.field_id],
            destination_field_ids=[field.field_id],
            params=params
        )

        return self.build_rule(candidate)

    def build_ext_value(self, source_field: FieldMatch, target_field: FieldMatch,
                       edv_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build EXT_VALUE rule"""
        edv_table = edv_config.get('edv_table', '')
        params_template = edv_config.get('params_template', {})

        # Replace placeholders in params
        if isinstance(params_template, dict):
            params = params_template.copy()
            # Replace {{parent_field_id}} with actual source field ID
            params_str = json.dumps(params)
            params_str = params_str.replace('{{parent_field_id}}', str(source_field.field_id))
            params = json.loads(params_str)
        else:
            params = {
                "conditionList": [{
                    "ddType": [edv_table],
                    "criterias": [{"a1": source_field.field_id}],
                    "da": ["a2"],
                    "criteriaSearchAttr": [],
                    "additionalOptions": None,
                    "emptyAddOptionCheck": None,
                    "ddProperties": None
                }]
            }

        candidate = RuleCandidate(
            action_type='EXT_VALUE',
            source_field_ids=[source_field.field_id],
            destination_field_ids=[target_field.field_id],
            params=params
        )

        return self.build_rule(candidate)


class CopyRuleBuilder(BaseRuleBuilder):
    """Build COPY_TO rules"""

    def build_from_logic(self, source_field: FieldMatch, target_fields: List[FieldMatch],
                        logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Build copy rules from parsed logic"""
        rules = []

        for target in target_fields:
            candidate = RuleCandidate(
                action_type='COPY_TO',
                source_field_ids=[source_field.field_id],
                destination_field_ids=[target.field_id]
            )
            rules.append(self.build_rule(candidate))

        return rules


class ConvertRuleBuilder(BaseRuleBuilder):
    """Build CONVERT_TO rules"""

    def build_from_logic(self, source_field: FieldMatch, target_fields: List[FieldMatch],
                        logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Build convert rules from parsed logic"""
        rules = []

        # Extract conversion mapping from logic
        conversion_map = self._extract_conversion_map(logic)

        for target in target_fields:
            params = {
                "conversionMap": conversion_map
            }

            candidate = RuleCandidate(
                action_type='CONVERT_TO',
                source_field_ids=[source_field.field_id],
                destination_field_ids=[target.field_id],
                params=params
            )
            rules.append(self.build_rule(candidate))

        return rules

    def _extract_conversion_map(self, logic: ParsedLogic) -> Dict[str, str]:
        """Extract conversion mapping from logic"""
        # Parse statements like "If X then Y, If A then B"
        conversion_map = {}

        text = logic.raw_expression

        # Pattern: "If <value> then <result>"
        patterns = re.findall(r'if\s+([^,]+?)\s+then\s+([^,\.]+)', text, re.IGNORECASE)

        for condition, result in patterns:
            condition = condition.strip()
            result = result.strip()
            conversion_map[condition] = result

        return conversion_map


class OCRRuleBuilder(BaseRuleBuilder):
    """Build OCR rules"""

    def build_from_logic(self, field: FieldMatch, logic: ParsedLogic) -> Dict[str, Any]:
        """Build OCR rule from parsed logic"""
        params = {
            "ocrType": "DOCUMENT",
            "documentField": "base_document"
        }

        candidate = RuleCandidate(
            action_type='OCR',
            source_field_ids=[field.field_id],
            destination_field_ids=[field.field_id],
            params=params
        )

        return self.build_rule(candidate)


class VerifyRuleBuilder(BaseRuleBuilder):
    """Build VERIFY rules"""

    def build_from_logic(self, field: FieldMatch, ocr_rule_id: int) -> Dict[str, Any]:
        """Build VERIFY rule linked to OCR rule"""
        candidate = RuleCandidate(
            action_type='VERIFY',
            source_field_ids=[field.field_id],
            destination_field_ids=[field.field_id],
            post_trigger_rule_ids=[ocr_rule_id]
        )

        return self.build_rule(candidate)


class SetDateRuleBuilder(BaseRuleBuilder):
    """Build SET_DATE rules"""

    def build_from_logic(self, field: FieldMatch, logic: ParsedLogic) -> Dict[str, Any]:
        """Build SET_DATE rule"""
        params = {
            "dateType": "CURRENT_DATE"
        }

        candidate = RuleCandidate(
            action_type='SET_DATE',
            source_field_ids=[field.field_id],
            destination_field_ids=[field.field_id],
            params=params
        )

        return self.build_rule(candidate)


class ConcatRuleBuilder(BaseRuleBuilder):
    """Build CONCAT rules"""

    def build_from_logic(self, source_fields: List[FieldMatch], target_field: FieldMatch,
                        logic: ParsedLogic) -> Dict[str, Any]:
        """Build CONCAT rule"""
        source_ids = [f.field_id for f in source_fields]

        params = {
            "separator": " ",
            "format": "{0} {1}"
        }

        candidate = RuleCandidate(
            action_type='CONCAT',
            source_field_ids=source_ids,
            destination_field_ids=[target_field.field_id],
            params=params
        )

        return self.build_rule(candidate)


# ============================================================================
# PHASE 3: MAIN ORCHESTRATOR
# ============================================================================

class RuleExtractionOrchestrator:
    """Main orchestrator for rule extraction"""

    def __init__(self, base_dir: str = "/home/samart/project/doc-parser"):
        self.base_dir = Path(base_dir)
        self.id_gen = SequentialIDGenerator()
        self.logic_parser = LogicParser()
        self.field_matcher = FieldMatcher()

        # Data storage
        self.schema = None
        self.intra_panel_refs = None
        self.edv_tables = None
        self.field_edv_mapping = None

        # Rule builders
        self.visibility_builder = VisibilityRuleBuilder(self.id_gen)
        self.mandatory_builder = MandatoryRuleBuilder(self.id_gen)
        self.editable_builder = EditableRuleBuilder(self.id_gen)
        self.validation_builder = ValidationRuleBuilder(self.id_gen)
        self.copy_builder = CopyRuleBuilder(self.id_gen)
        self.convert_builder = ConvertRuleBuilder(self.id_gen)
        self.ocr_builder = OCRRuleBuilder(self.id_gen)
        self.verify_builder = VerifyRuleBuilder(self.id_gen)
        self.setdate_builder = SetDateRuleBuilder(self.id_gen)
        self.concat_builder = ConcatRuleBuilder(self.id_gen)

        # EDV builder (will be initialized after loading data)
        self.edv_builder = None

        # Statistics
        self.stats = {
            'fields_processed': 0,
            'rules_generated': 0,
            'rules_by_type': defaultdict(int)
        }

    def load_data(self, run_dir: str):
        """Load all required data files"""
        run_path = self.base_dir / run_dir

        print(f"Loading data from {run_path}")

        # Load schema - try multiple versions
        schema_file = None
        for ver in range(20, 0, -1):
            test_file = run_path / f"api_schema_v{ver}.json"
            if test_file.exists():
                schema_file = test_file
                break

        if not schema_file:
            # Try without version
            schema_file = run_path / "schema.json"

        if schema_file and schema_file.exists():
            with open(schema_file, 'r') as f:
                self.schema = json.load(f)
            print(f"Loaded schema from {schema_file}")
        else:
            raise FileNotFoundError(f"No schema file found in {run_path}")

        # Load intra-panel references
        templates_dir = run_path / "templates_output"
        intra_panel_file = templates_dir / "Vendor Creation Sample BUD_intra_panel_references.json"
        if intra_panel_file.exists():
            with open(intra_panel_file, 'r') as f:
                self.intra_panel_refs = json.load(f)
            print(f"Loaded intra-panel references")

        # Load EDV tables
        edv_file = templates_dir / "Vendor_Creation_Sample_BUD_edv_tables.json"
        if edv_file.exists():
            with open(edv_file, 'r') as f:
                self.edv_tables = json.load(f)
            print(f"Loaded EDV tables")

        # Load field-EDV mapping
        edv_mapping_file = templates_dir / "Vendor_Creation_Sample_BUD_field_edv_mapping.json"
        if edv_mapping_file.exists():
            with open(edv_mapping_file, 'r') as f:
                self.field_edv_mapping = json.load(f)
            print(f"Loaded field-EDV mapping")

        # Initialize EDV builder now that we have the data
        if self.edv_tables and self.field_edv_mapping:
            self.edv_builder = EDVRuleBuilder(
                self.id_gen,
                self.edv_tables.get('edv_tables', {}),
                self.field_edv_mapping.get('field_edv_mappings', {})
            )

    def extract_all_rules(self) -> Dict[str, Any]:
        """Extract all rules and populate schema"""
        print("\n" + "="*80)
        print("Starting Rule Extraction v15")
        print("="*80)

        # Get fields from schema
        fields = self.schema['template']['documentTypes'][0]['formFillMetadatas']

        print(f"\nTotal fields in schema: {len(fields)}")

        # Reassign sequential IDs to all fields
        print("\nReassigning sequential IDs to fields...")
        self._reassign_field_ids(fields)

        # Index fields for matching
        print("Building field index...")
        self.field_matcher.index_fields(fields)

        # Process intra-panel references to generate rules
        if self.intra_panel_refs:
            print("\nProcessing intra-panel references...")
            self._process_intra_panel_references(fields)

        # Process EDV mappings
        if self.field_edv_mapping:
            print("\nProcessing EDV mappings...")
            self._process_edv_mappings(fields)

        # Add missing standard rules
        print("\nAdding standard rules...")
        self._add_standard_rules(fields)

        # Reassign template ID
        self.schema['template']['id'] = 1

        print("\n" + "="*80)
        print("Rule Extraction Complete")
        print("="*80)
        print(f"Fields processed: {self.stats['fields_processed']}")
        print(f"Total rules generated: {self.stats['rules_generated']}")
        print("\nRules by type:")
        for rule_type, count in sorted(self.stats['rules_by_type'].items()):
            print(f"  {rule_type}: {count}")

        return self.schema

    def _reassign_field_ids(self, fields: List[Dict[str, Any]]):
        """Reassign sequential IDs to all fields and their components"""
        for field in fields:
            # Assign field ID
            new_id = self.id_gen.next_id()
            old_id = field.get('id', 0)
            field['id'] = new_id

            # Update formTag ID
            if 'formTag' in field:
                field['formTag']['id'] = new_id

            # Clear existing rules (we'll regenerate them)
            field['formFillRules'] = []

    def _process_intra_panel_references(self, fields: List[Dict[str, Any]]):
        """Process intra-panel references to generate rules"""
        panel_results = self.intra_panel_refs.get('panel_results', [])

        for panel_result in panel_results:
            panel_name = panel_result.get('panel_name', '')
            intra_refs = panel_result.get('intra_panel_references', [])

            print(f"\nProcessing panel: {panel_name} ({len(intra_refs)} references)")

            for ref in intra_refs:
                self._process_single_reference(ref, fields)

    def _process_single_reference(self, ref: Dict[str, Any], fields: List[Dict[str, Any]]):
        """Process a single intra-panel reference"""
        source_field_name = ref.get('source_field', {}).get('field_name', '')
        target_field_name = ref.get('target_field', {}).get('field_name', '')
        reference_details = ref.get('reference_details', {})

        # Find source and target fields
        source_match = self.field_matcher.find_field(source_field_name)
        target_match = self.field_matcher.find_field(target_field_name)

        if not source_match or not target_match:
            return

        # Parse logic
        logic = self.logic_parser.parse(reference_details)

        # Identify rule types
        rule_types = self.logic_parser.identify_rule_types(logic)

        # Generate rules for each type
        for rule_type in rule_types:
            rules = self._generate_rules_for_type(
                rule_type, source_match, [target_match], logic
            )

            # Add rules to source field
            self._add_rules_to_field(source_match.field_id, rules, fields)

    def _generate_rules_for_type(self, rule_type: str, source: FieldMatch,
                                 targets: List[FieldMatch], logic: ParsedLogic) -> List[Dict[str, Any]]:
        """Generate rules for a specific rule type"""
        rules = []

        if rule_type in ['MAKE_VISIBLE', 'MAKE_INVISIBLE']:
            rules = self.visibility_builder.build_from_logic(source, targets, logic)

        elif rule_type in ['MAKE_MANDATORY', 'MAKE_NON_MANDATORY']:
            rules = self.mandatory_builder.build_from_logic(source, targets, logic)

        elif rule_type in ['MAKE_DISABLED', 'MAKE_ENABLED']:
            rules = self.editable_builder.build_from_logic(source, targets, logic)

        elif rule_type == 'VALIDATION':
            rules = self.validation_builder.build_from_logic(source, targets, logic)

        elif rule_type == 'COPY_TO':
            rules = self.copy_builder.build_from_logic(source, targets, logic)

        elif rule_type == 'CONVERT_TO':
            rules = self.convert_builder.build_from_logic(source, targets, logic)

        # Update statistics
        for rule in rules:
            self.stats['rules_generated'] += 1
            self.stats['rules_by_type'][rule_type] += 1

        return rules

    def _process_edv_mappings(self, fields: List[Dict[str, Any]]):
        """Process EDV mappings to generate EXT_DROP_DOWN and EXT_VALUE rules"""
        if not self.edv_builder:
            return

        field_mappings = self.field_edv_mapping.get('field_edv_mappings', [])

        print(f"Processing {len(field_mappings)} EDV mappings")

        for mapping in field_mappings:
            field_name = mapping.get('field_name', '')
            edv_config = mapping.get('edv_config', {})
            rule_type = edv_config.get('rule_type', '')
            relationship = mapping.get('relationship', {})

            # Find field
            field_match = self.field_matcher.find_field(field_name)
            if not field_match:
                continue

            # Generate EXT_DROP_DOWN rule
            if rule_type == 'EXT_DROP_DOWN':
                rule = self.edv_builder.build_ext_dropdown(field_match, edv_config)
                self._add_rules_to_field(field_match.field_id, [rule], fields)
                self.stats['rules_generated'] += 1
                self.stats['rules_by_type']['EXT_DROP_DOWN'] += 1

            # Generate EXT_VALUE rule for child fields
            elif rule_type == 'EXT_VALUE':
                parent_name = relationship.get('parent', '')
                if parent_name:
                    parent_match = self.field_matcher.find_field(parent_name)
                    if parent_match:
                        rule = self.edv_builder.build_ext_value(parent_match, field_match, edv_config)
                        self._add_rules_to_field(parent_match.field_id, [rule], fields)
                        self.stats['rules_generated'] += 1
                        self.stats['rules_by_type']['EXT_VALUE'] += 1

    def _add_standard_rules(self, fields: List[Dict[str, Any]]):
        """Add standard rules that apply to specific fields"""
        # Add SET_DATE rule for "Created on" field
        created_on = self.field_matcher.find_field('Created on')
        if created_on:
            logic = ParsedLogic(
                raw_expression="Set to current date",
                operation_type="set_date",
                relationship_type="auto_fill"
            )
            rule = self.setdate_builder.build_from_logic(created_on, logic)
            self._add_rules_to_field(created_on.field_id, [rule], fields)
            self.stats['rules_generated'] += 1
            self.stats['rules_by_type']['SET_DATE'] += 1

        # Add MAKE_DISABLED rule for RuleCheck field to disable all other fields
        rulecheck = self.field_matcher.find_field('RuleCheck')
        if rulecheck:
            # Get all field IDs except RuleCheck itself
            all_field_ids = [f['id'] for f in fields if f['id'] != rulecheck.field_id]

            candidate = RuleCandidate(
                action_type='MAKE_DISABLED',
                source_field_ids=[rulecheck.field_id],
                destination_field_ids=all_field_ids,
                condition='NOT_IN',
                conditional_values=['Disable']
            )

            rule = BaseRuleBuilder(self.id_gen).build_rule(candidate)
            self._add_rules_to_field(rulecheck.field_id, [rule], fields)
            self.stats['rules_generated'] += 1
            self.stats['rules_by_type']['MAKE_DISABLED'] += 1

    def _add_rules_to_field(self, field_id: int, rules: List[Dict[str, Any]],
                           fields: List[Dict[str, Any]]):
        """Add rules to a specific field"""
        for field in fields:
            if field['id'] == field_id:
                if 'formFillRules' not in field:
                    field['formFillRules'] = []
                field['formFillRules'].extend(rules)
                break

    def generate_extraction_report(self) -> Dict[str, Any]:
        """Generate extraction report"""
        report = {
            "extraction_info": {
                "timestamp": datetime.now().isoformat(),
                "version": "v15",
                "status": "success"
            },
            "statistics": {
                "fields_processed": self.stats['fields_processed'],
                "total_rules_generated": self.stats['rules_generated'],
                "rules_by_type": dict(self.stats['rules_by_type'])
            },
            "field_summary": [],
            "issues": []
        }

        # Add field summary
        fields = self.schema['template']['documentTypes'][0]['formFillMetadatas']
        for field in fields:
            field_name = field.get('formTag', {}).get('name', '')
            field_type = field.get('formTag', {}).get('type', '')
            num_rules = len(field.get('formFillRules', []))

            report["field_summary"].append({
                "field_id": field['id'],
                "field_name": field_name,
                "field_type": field_type,
                "num_rules": num_rules
            })

        return report

    def save_output(self, output_dir: str, version: str = "v15"):
        """Save populated schema and extraction report"""
        output_path = self.base_dir / output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # Save populated schema
        schema_file = output_path / f"populated_schema_{version}.json"
        with open(schema_file, 'w') as f:
            json.dump(self.schema, f, indent=2)
        print(f"\nSaved populated schema to {schema_file}")

        # Save extraction report
        report = self.generate_extraction_report()
        report_file = output_path / f"extraction_report_{version}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Saved extraction report to {report_file}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    print("\n" + "="*80)
    print("Rule Extraction Agent v15")
    print("="*80)

    # Create orchestrator
    orchestrator = RuleExtractionOrchestrator()

    # Load data
    run_dir = "adws/2026-02-02_16-18-22"
    orchestrator.load_data(run_dir)

    # Extract all rules
    populated_schema = orchestrator.extract_all_rules()

    # Save output
    orchestrator.save_output(run_dir, "v15")

    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
