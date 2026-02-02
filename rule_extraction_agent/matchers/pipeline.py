"""Multi-stage matching pipeline."""

import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .deterministic import DeterministicMatcher, MatchResult
from ..schema_lookup import RuleSchemaLookup
from ..field_matcher import FieldMatcher
from ..models import FieldInfo


@dataclass
class PipelineResult:
    """Result from matching pipeline."""
    matches: List[MatchResult] = field(default_factory=list)
    confidence: float = 0.0
    used_llm: bool = False
    source_field_id: Optional[int] = None
    destination_field_ids: List[int] = field(default_factory=list)
    controlling_field: Optional[str] = None
    conditional_values: List[str] = field(default_factory=list)


class MatchingPipeline:
    """Two-stage matching: deterministic patterns → LLM fallback."""

    def __init__(
        self,
        schema_lookup: RuleSchemaLookup = None,
        field_matcher: FieldMatcher = None,
        llm_threshold: float = 0.7
    ):
        self.deterministic = DeterministicMatcher()
        self.schema_lookup = schema_lookup or RuleSchemaLookup()
        self.field_matcher = field_matcher or FieldMatcher()
        self.llm_threshold = llm_threshold

    def match(
        self,
        logic_text: str,
        field_info: Dict,
        all_fields: List[Dict] = None
    ) -> PipelineResult:
        """
        Match logic text to rules using multi-stage approach.

        Args:
            logic_text: Natural language logic statement
            field_info: Current field's metadata
            all_fields: All fields for reference resolution

        Returns:
            PipelineResult with matches and metadata
        """
        if not logic_text:
            return PipelineResult()

        field_name = field_info.get('formTag', {}).get('name', '')

        # Stage 1: Deterministic pattern matching
        matches = self.deterministic.match(logic_text, field_name)

        result = PipelineResult(
            matches=matches,
            confidence=self.deterministic.get_confidence(matches),
            used_llm=False,
        )

        # Extract controlling field for visibility rules
        controlling = self._extract_controlling_field(logic_text)
        if controlling:
            result.controlling_field = controlling

            # Resolve to field ID if field matcher is loaded
            if self.field_matcher.fields:
                ctrl_field = self.field_matcher.match_field(controlling)
                if ctrl_field:
                    result.source_field_id = ctrl_field.id

        # Extract conditional values
        cond_values = self._extract_conditional_values(logic_text)
        if cond_values:
            result.conditional_values = cond_values

        # Stage 2: LLM fallback if needed
        if self.deterministic.needs_llm(matches, self.llm_threshold):
            result.used_llm = True
            # LLM fallback would be called here
            # For now, we just mark that it was needed

        return result

    def _extract_controlling_field(self, text: str) -> Optional[str]:
        """Extract the controlling field name from logic text."""
        patterns = [
            r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]",
            r"when\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]",
            r"based\s+on\s+(?:the\s+)?['\"]([^'\"]+)['\"]",
            r"depending\s+on\s+['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_conditional_values(self, text: str) -> List[str]:
        """Extract conditional values from logic text."""
        values = []

        # Pattern: "is X then" or "values is X then"
        patterns = [
            r"(?:value[s]?\s+is|is)\s+['\"]?([^'\"]+?)['\"]?\s+then",
            r"(?:equal[s]?\s+to|==)\s+['\"]?([^'\"]+?)['\"]?",
            r"select(?:ed|ion)?\s+['\"]?([^'\"]+?)['\"]?",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            values.extend([m.strip() for m in matches if m.strip()])

        return list(set(values))

    def process_field_logic(
        self,
        field: Dict,
        all_fields: List[Dict],
        intra_refs: List[Dict] = None
    ) -> List[Dict]:
        """
        Process a field's logic and return rule specifications.

        Args:
            field: Field metadata from schema
            all_fields: All fields for reference resolution
            intra_refs: Intra-panel references for additional context

        Returns:
            List of rule specification dicts
        """
        form_tag = field.get('formTag', {})
        field_name = form_tag.get('name', '')
        field_type = form_tag.get('type', 'TEXT')
        field_id = field.get('id', 0)

        # Get logic from helpText, rules field, or intra-panel refs
        logic_text = self._get_field_logic(field, field_name, intra_refs)

        if not logic_text:
            return []

        # Match patterns
        result = self.match(logic_text, field, all_fields)

        # Convert matches to rule specs
        rule_specs = []

        for match in result.matches:
            spec = {
                'action_type': match.action_type,
                'source_type': match.source_type,
                'confidence': match.confidence,
                'field_id': field_id,
                'field_name': field_name,
                'logic_text': logic_text,
            }

            # Add conditional info
            if result.conditional_values:
                spec['conditional_values'] = result.conditional_values
            if match.conditional_values:
                spec['conditional_values'] = match.conditional_values
            if match.condition:
                spec['condition'] = match.condition

            # Add controlling field
            if result.controlling_field:
                spec['controlling_field'] = result.controlling_field
                spec['source_field_id'] = result.source_field_id

            rule_specs.append(spec)

        return rule_specs

    def _get_field_logic(
        self,
        field: Dict,
        field_name: str,
        intra_refs: List[Dict] = None
    ) -> str:
        """Get logic text for a field from various sources."""
        logic_parts = []

        # From helpText
        help_text = field.get('helpText', '')
        if help_text:
            logic_parts.append(help_text)

        # From intra-panel references
        if intra_refs:
            for ref in intra_refs:
                if ref.get('dependent_field', '').lower() == field_name.lower():
                    desc = ref.get('rule_description', '')
                    if desc:
                        logic_parts.append(desc)

                if ref.get('target_field', '').lower() == field_name.lower():
                    desc = ref.get('dependency_description', '')
                    if desc:
                        logic_parts.append(desc)

        return ' '.join(logic_parts)


class VisibilityRuleGrouper:
    """Groups visibility rules by controlling field."""

    def __init__(self, field_matcher: FieldMatcher):
        self.field_matcher = field_matcher
        self.groups: Dict[str, Dict] = {}  # controlling_field_name -> group data

    def add_rule_spec(self, spec: Dict):
        """Add a rule spec to the appropriate group."""
        if spec.get('action_type') not in ['MAKE_VISIBLE', 'MAKE_INVISIBLE', 'MAKE_MANDATORY', 'MAKE_NON_MANDATORY']:
            return

        controlling_field = spec.get('controlling_field')
        if not controlling_field:
            return

        normalized = controlling_field.lower().strip()

        if normalized not in self.groups:
            # Find controlling field ID
            ctrl_field = self.field_matcher.match_field(controlling_field)
            self.groups[normalized] = {
                'controlling_field_name': controlling_field,
                'controlling_field_id': ctrl_field.id if ctrl_field else None,
                'conditional_values': set(),
                'destinations': {},  # action_type -> list of dest field ids
            }

        group = self.groups[normalized]

        # Add conditional values
        if spec.get('conditional_values'):
            group['conditional_values'].update(spec['conditional_values'])

        # Add destination
        action = spec['action_type']
        if action not in group['destinations']:
            group['destinations'][action] = []

        dest_id = spec.get('field_id')
        if dest_id and dest_id not in group['destinations'][action]:
            group['destinations'][action].append(dest_id)

    def get_consolidated_rules(self) -> List[Dict]:
        """Get consolidated visibility rules."""
        rules = []

        for group_name, group in self.groups.items():
            source_id = group.get('controlling_field_id')
            if not source_id:
                continue

            cond_values = list(group['conditional_values'])

            for action_type, dest_ids in group['destinations'].items():
                if not dest_ids:
                    continue

                rule = {
                    'action_type': action_type,
                    'source_ids': [source_id],
                    'destination_ids': sorted(dest_ids),
                    'conditional_values': cond_values,
                    'condition': 'IN' if action_type in ['MAKE_VISIBLE', 'MAKE_MANDATORY'] else 'NOT_IN',
                }
                rules.append(rule)

        return rules
