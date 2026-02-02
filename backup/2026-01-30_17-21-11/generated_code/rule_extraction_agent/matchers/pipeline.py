"""
Multi-stage matching pipeline for rule extraction.

Coordinates deterministic pattern matching with LLM fallback.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..models import ParsedLogic, RuleMatch, GeneratedRule, FieldInfo, ExtractionResult
from ..logic_parser import LogicParser
from ..schema_lookup import RuleSchemaLookup
from ..field_matcher import FieldMatcher, PanelFieldMatcher
from ..rule_tree import RuleSelectionTree
from ..rule_builders import StandardRuleBuilder, VerifyRuleBuilder, OcrRuleBuilder
from .deterministic import DeterministicMatcher
from .llm_fallback import LLMFallback, MockLLMFallback

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the matching pipeline."""
    llm_threshold: float = 0.7  # Use LLM if confidence below this
    fuzzy_match_threshold: float = 0.8  # For field name matching
    use_llm: bool = True  # Enable/disable LLM fallback
    llm_model: str = "gpt-4o-mini"
    verbose: bool = False


@dataclass
class PipelineResult:
    """Result from the matching pipeline."""
    field_id: int
    field_name: str
    logic_text: str
    parsed_logic: ParsedLogic
    rule_matches: List[RuleMatch] = field(default_factory=list)
    generated_rules: List[GeneratedRule] = field(default_factory=list)
    confidence: float = 0.0
    used_llm: bool = False
    errors: List[str] = field(default_factory=list)


class MatchingPipeline:
    """
    Two-stage matching pipeline: deterministic patterns + LLM fallback.

    Pipeline stages:
    1. Parse logic text to extract keywords, conditions, references
    2. Deterministic pattern matching with confidence scoring
    3. If confidence < threshold, use LLM fallback with schema context
    4. Match field references to actual field IDs
    5. Build rules using appropriate builders
    """

    def __init__(
        self,
        schema_lookup: Optional[RuleSchemaLookup] = None,
        config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize the matching pipeline.

        Args:
            schema_lookup: RuleSchemaLookup for schema queries
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        self.schema_lookup = schema_lookup or RuleSchemaLookup()

        # Initialize components
        self.logic_parser = LogicParser()
        self.deterministic = DeterministicMatcher()
        self.rule_tree = RuleSelectionTree(self.schema_lookup)
        self.field_matcher: Optional[FieldMatcher] = None

        # Rule builders
        from ..id_mapper import DestinationIdMapper
        self.id_mapper = DestinationIdMapper(self.schema_lookup)
        self.standard_builder = StandardRuleBuilder()
        self.verify_builder = VerifyRuleBuilder(self.schema_lookup, self.id_mapper)
        self.ocr_builder = OcrRuleBuilder(self.schema_lookup, self.id_mapper)

        # LLM fallback (initialized lazily)
        self._llm_fallback: Optional[LLMFallback] = None

    def set_fields(self, fields: List[FieldInfo]) -> None:
        """Set available fields for matching."""
        self.field_matcher = PanelFieldMatcher(fields)

    def _get_llm_fallback(self) -> Optional[LLMFallback]:
        """Lazy initialization of LLM fallback."""
        if self._llm_fallback is None and self.config.use_llm:
            try:
                self._llm_fallback = LLMFallback(
                    self.schema_lookup,
                    model=self.config.llm_model,
                )
            except Exception as e:
                logger.warning(f"Could not initialize LLM fallback: {e}")
                self._llm_fallback = MockLLMFallback(self.schema_lookup)
        return self._llm_fallback

    def process(
        self,
        logic_text: str,
        field_info: FieldInfo,
    ) -> PipelineResult:
        """
        Process a single logic statement through the pipeline.

        Args:
            logic_text: Raw logic/rules text
            field_info: Information about the current field

        Returns:
            PipelineResult with matches and generated rules
        """
        result = PipelineResult(
            field_id=field_info.id,
            field_name=field_info.name,
            logic_text=logic_text,
            parsed_logic=ParsedLogic(original_text=logic_text),
        )

        # Stage 1: Parse logic
        parsed = self.logic_parser.parse(logic_text)
        result.parsed_logic = parsed

        if parsed.skip_reason:
            result.errors.append(f"Skipped: {parsed.skip_reason}")
            return result

        # Stage 2: Deterministic matching
        det_matches = self.deterministic.match(logic_text)
        tree_matches = self.rule_tree.select_rules(parsed)

        # Combine matches and get highest confidence
        all_matches = det_matches + tree_matches
        if all_matches:
            # Deduplicate by action_type, keeping highest confidence
            match_map = {}
            for m in all_matches:
                if m.action_type not in match_map or m.confidence > match_map[m.action_type].confidence:
                    match_map[m.action_type] = m
            result.rule_matches = list(match_map.values())
            result.confidence = max(m.confidence for m in result.rule_matches)

        # Stage 3: LLM fallback if needed
        if result.confidence < self.config.llm_threshold and self.config.use_llm:
            llm = self._get_llm_fallback()
            if llm:
                available_fields = self.field_matcher.fields if self.field_matcher else []
                llm_match = llm.match(
                    logic_text,
                    field_info.to_dict(),
                    available_fields=available_fields,
                )
                if llm_match:
                    result.rule_matches.append(llm_match)
                    result.confidence = max(result.confidence, llm_match.confidence)
                    result.used_llm = True

        # Stage 4: Build rules
        if result.rule_matches:
            rules = self._build_rules(parsed, field_info, result.rule_matches)
            result.generated_rules = rules

        return result

    def _build_rules(
        self,
        parsed: ParsedLogic,
        field_info: FieldInfo,
        matches: List[RuleMatch],
    ) -> List[GeneratedRule]:
        """Build rules from matches."""
        rules = []

        # Find source field if conditions reference other fields
        source_field_id = self._find_source_field(parsed, field_info)
        destination_field_id = field_info.id

        # Extract conditional values
        conditional_values = self._extract_conditional_values(parsed)

        for match in matches:
            action_type = match.action_type

            if action_type in ["MAKE_VISIBLE", "MAKE_INVISIBLE", "MAKE_MANDATORY",
                              "MAKE_NON_MANDATORY", "MAKE_DISABLED", "MAKE_ENABLED"]:
                # Standard visibility/mandatory/disable rules
                if parsed.has_else_branch and action_type in ["MAKE_VISIBLE", "MAKE_MANDATORY"]:
                    # Generate rule pairs for conditionals
                    rule_set = self.standard_builder.build_from_parsed_logic(
                        parsed,
                        source_field_id,
                        destination_field_id,
                    )
                    rules.extend(rule_set)
                else:
                    rule = self.standard_builder.build(
                        action_type=action_type,
                        source_field_id=source_field_id,
                        destination_field_id=destination_field_id,
                        conditional_values=conditional_values,
                        condition="IN",
                    )
                    rules.append(rule)

            elif action_type == "VERIFY":
                # VERIFY rules
                if match.schema_id:
                    try:
                        rule = self.verify_builder.build(
                            schema_id=match.schema_id,
                            source_field_id=field_info.id,
                            field_mappings=None,  # Would need field mapping logic
                        )
                        rules.append(rule)
                    except Exception as e:
                        logger.warning(f"Failed to build VERIFY rule: {e}")

            elif action_type == "OCR":
                # OCR rules
                if match.schema_id:
                    try:
                        rule = self.ocr_builder.build(
                            schema_id=match.schema_id,
                            upload_field_id=field_info.id,
                            output_field_ids=[destination_field_id],
                        )
                        rules.append(rule)
                    except Exception as e:
                        logger.warning(f"Failed to build OCR rule: {e}")

        return rules

    def _find_source_field(self, parsed: ParsedLogic, current_field: FieldInfo) -> int:
        """Find the source field for conditional rules."""
        if not self.field_matcher:
            return current_field.id

        # Check conditions for field references
        for condition in parsed.conditions:
            if condition.field_name:
                match = self.field_matcher.match(condition.field_name)
                if match.field_info:
                    return match.field_info.id

        # Check field references
        for ref in parsed.field_references:
            match = self.field_matcher.match(ref)
            if match.field_info:
                return match.field_info.id

        # Default to current field
        return current_field.id

    def _extract_conditional_values(self, parsed: ParsedLogic) -> List[str]:
        """Extract conditional values from parsed logic."""
        values = []
        for condition in parsed.conditions:
            if condition.value:
                values.append(condition.value)

        # Default to 'yes' for simple conditionals
        if not values and parsed.is_conditional:
            values = ["yes"]

        return values

    def process_batch(
        self,
        logic_entries: List[Dict[str, Any]],
    ) -> List[PipelineResult]:
        """
        Process multiple logic entries.

        Args:
            logic_entries: List of dicts with 'logic_text' and 'field_info'

        Returns:
            List of PipelineResult objects
        """
        results = []
        for entry in logic_entries:
            logic_text = entry.get('logic_text', '')
            field_info = entry.get('field_info')
            if isinstance(field_info, dict):
                field_info = FieldInfo(**field_info)
            if logic_text and field_info:
                result = self.process(logic_text, field_info)
                results.append(result)
        return results


class SimplifiedPipeline:
    """
    Simplified pipeline for basic rule extraction without full schema context.

    Useful for quick extractions or when Rule-Schemas.json is not available.
    """

    def __init__(self):
        self.logic_parser = LogicParser()
        self.deterministic = DeterministicMatcher()
        self.standard_builder = StandardRuleBuilder()

    def _extract_conditional_values(self, logic_text: str, parsed: ParsedLogic) -> List[str]:
        """
        Extract proper conditional values from logic text.

        Args:
            logic_text: Raw logic text
            parsed: ParsedLogic object

        Returns:
            List of conditional values like ['yes'], ['no'], etc.
        """
        from ..logic_parser import KeywordExtractor

        # First try from parsed conditions
        values = []
        for c in parsed.conditions:
            if c.value and c.value.lower() not in {
                'visible', 'invisible', 'mandatory', 'non-mandatory',
                'then', 'otherwise', 'else', 'in', 'the', 'field'
            }:
                values.append(c.value.lower())

        # If no values from conditions, use KeywordExtractor
        if not values:
            values = KeywordExtractor.extract_conditional_values(logic_text)

        # Filter out invalid values
        filtered = []
        invalid_values = {
            'visible', 'invisible', 'mandatory', 'non-mandatory', 'editable',
            'then', 'otherwise', 'else', 'in', 'the', 'field', 'if', 'when',
            'is', 'selected', 'chosen', 'make', 'hidden', 'and', 'or'
        }
        for v in values:
            v_lower = v.lower()
            if v_lower not in invalid_values:
                filtered.append(v_lower)

        # Default to 'yes' if conditional but no values found
        if not filtered and parsed.is_conditional:
            filtered = ["yes"]

        return filtered

    def extract_rules(
        self,
        logic_text: str,
        source_field_id: int,
        destination_field_id: int,
    ) -> List[GeneratedRule]:
        """
        Extract rules from logic text.

        Args:
            logic_text: Raw logic text
            source_field_id: Controlling field ID
            destination_field_id: Controlled field ID

        Returns:
            List of GeneratedRule objects
        """
        parsed = self.logic_parser.parse(logic_text)
        if parsed.skip_reason:
            return []

        matches = self.deterministic.match(logic_text)
        if not matches:
            return []

        rules = []

        # Extract proper conditional values
        conditional_values = self._extract_conditional_values(logic_text, parsed)

        # Track which action types we've processed to avoid duplicates
        processed_actions = set()

        for match in matches:
            if match.action_type.startswith("MAKE_"):
                # Skip if we already processed this action type
                if match.action_type in processed_actions:
                    continue

                if parsed.has_else_branch:
                    # Use build_from_parsed_logic which handles all visibility/mandatory rules at once
                    # Only call once to avoid duplicates
                    has_visibility = any(
                        a in ["MAKE_VISIBLE", "MAKE_INVISIBLE"]
                        for a in parsed.action_types
                    )
                    has_mandatory = any(
                        a in ["MAKE_MANDATORY", "MAKE_NON_MANDATORY"]
                        for a in parsed.action_types
                    )

                    if has_visibility and has_mandatory and not processed_actions:
                        # Generate visibility + mandatory set (4 rules)
                        rule_set = self.standard_builder.build_visibility_mandatory_set(
                            source_field_id=source_field_id,
                            destination_field_id=destination_field_id,
                            conditional_values=conditional_values,
                            visible_when_true="MAKE_VISIBLE" in parsed.action_types,
                            mandatory_when_true="MAKE_MANDATORY" in parsed.action_types,
                        )
                        rules.extend(rule_set)
                        # Mark all visibility/mandatory actions as processed
                        processed_actions.update([
                            "MAKE_VISIBLE", "MAKE_INVISIBLE",
                            "MAKE_MANDATORY", "MAKE_NON_MANDATORY"
                        ])
                    elif match.action_type not in processed_actions:
                        # Generate conditional pair for single action type
                        pos, neg = self.standard_builder.build_conditional_pair(
                            match.action_type,
                            source_field_id,
                            destination_field_id,
                            conditional_values
                        )
                        rules.extend([pos, neg])
                        # Mark both positive and negative actions as processed
                        processed_actions.add(match.action_type)
                        inverse = self.standard_builder.INVERSE_ACTIONS.get(match.action_type)
                        if inverse:
                            processed_actions.add(inverse)
                else:
                    # Non-conditional rule - for disable rules, use NOT_IN with sentinel value
                    if match.action_type == "MAKE_DISABLED":
                        rule = self.standard_builder.build_disable_rule(
                            source_field_id=source_field_id,
                            destination_field_id=destination_field_id,
                            always_disabled=True,
                            conditional_values=["Disable"],
                        )
                    else:
                        rule = self.standard_builder.build(
                            action_type=match.action_type,
                            source_field_id=source_field_id,
                            destination_field_id=destination_field_id,
                            conditional_values=conditional_values if conditional_values else None,
                            condition="IN" if conditional_values else None,
                        )
                    rules.append(rule)
                    processed_actions.add(match.action_type)

        return rules
