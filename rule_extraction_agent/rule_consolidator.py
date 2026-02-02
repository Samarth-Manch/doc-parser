"""
Rule consolidation and cleanup module.

This module handles:
1. Consolidating MAKE_DISABLED rules into RuleCheck pattern
2. Deduplicating rules
3. Merging visibility/mandatory rules with same source
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict
from .models import id_generator


class RuleConsolidator:
    """Consolidates and deduplicates rules for optimal output."""

    # Actions that can be consolidated (same source -> merge destinations)
    CONSOLIDATABLE_ACTIONS = [
        'MAKE_DISABLED',
        'MAKE_VISIBLE',
        'MAKE_INVISIBLE',
        'MAKE_MANDATORY',
        'MAKE_NON_MANDATORY'
    ]

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.rulecheck_field_id = None

    def set_rulecheck_field_id(self, field_id: int):
        """Set the RuleCheck control field ID for MAKE_DISABLED consolidation."""
        self.rulecheck_field_id = field_id

    def consolidate(self, all_rules: List[Dict]) -> List[Dict]:
        """
        Consolidate and deduplicate rules.

        Key operations:
        1. Extract all MAKE_DISABLED rules and consolidate to RuleCheck
        2. Consolidate other groupable actions by (source, condition, values)
        3. Remove exact duplicates
        """
        if self.verbose:
            print(f"\n=== Consolidating {len(all_rules)} rules ===")

        # Step 1: Separate MAKE_DISABLED for special handling
        disabled_rules = []
        other_rules = []

        for rule in all_rules:
            if rule.get('actionType') == 'MAKE_DISABLED':
                disabled_rules.append(rule)
            else:
                other_rules.append(rule)

        if self.verbose:
            print(f"Found {len(disabled_rules)} MAKE_DISABLED rules to consolidate")

        # Step 2: Consolidate MAKE_DISABLED rules
        consolidated_disabled = self._consolidate_make_disabled(disabled_rules)

        if self.verbose:
            print(f"Consolidated to {len(consolidated_disabled)} MAKE_DISABLED rules")

        # Step 3: Consolidate other groupable actions
        consolidated_others = self._consolidate_groupable(other_rules)

        # Step 4: Combine and deduplicate
        all_consolidated = consolidated_disabled + consolidated_others
        deduplicated = self._deduplicate(all_consolidated)

        if self.verbose:
            print(f"Final rule count after consolidation: {len(deduplicated)}")

        return deduplicated

    def _consolidate_make_disabled(self, disabled_rules: List[Dict]) -> List[Dict]:
        """
        Consolidate MAKE_DISABLED rules following the reference pattern:

        1. Create ONE consolidated rule on RuleCheck field with all destinations
        2. Keep specific MAKE_DISABLED rules for OCR fields (GSTIN IMAGE, MSME Image, etc.)
        """
        if not disabled_rules:
            return []

        # Separate OCR-specific disabled rules from general ones
        ocr_disabled_fields = [
            'gstin image',
            'msme image',
            'msme registration number',
            'account group code'  # Also has specific rule
        ]

        general_disabled = []
        specific_disabled = []

        for rule in disabled_rules:
            source_ids = rule.get('sourceIds', [])
            dest_ids = rule.get('destinationIds', [])

            # Rules with empty destinations are OCR-specific (self-disabled after OCR)
            if len(dest_ids) == 0:
                specific_disabled.append(rule)
            # Rules where source is already the RuleCheck field should be kept as-is
            elif self.rulecheck_field_id and source_ids and source_ids[0] == self.rulecheck_field_id:
                specific_disabled.append(rule)
            # All other MAKE_DISABLED rules should be consolidated
            else:
                general_disabled.append(rule)

        result = []

        # Create consolidated RuleCheck rule if we have general disabled rules
        if general_disabled:
            # Collect all destination IDs
            all_dest_ids = set()
            for rule in general_disabled:
                all_dest_ids.update(rule.get('destinationIds', []))

            # Only create if we have a RuleCheck field
            if self.rulecheck_field_id:
                consolidated = {
                    "id": id_generator.next_id('rule'),
                    "createUser": "FIRST_PARTY",
                    "updateUser": "FIRST_PARTY",
                    "actionType": "MAKE_DISABLED",
                    "processingType": "CLIENT",
                    "sourceIds": [self.rulecheck_field_id],
                    "destinationIds": sorted(list(all_dest_ids)),
                    "conditionalValues": ["Disable"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "postTriggerRuleIds": [],
                    "button": "",
                    "searchable": False,
                    "executeOnFill": True,
                    "executeOnRead": False,
                    "executeOnEsign": False,
                    "executePostEsign": False,
                    "runPostConditionFail": False
                }
                result.append(consolidated)

                if self.verbose:
                    print(f"Created consolidated MAKE_DISABLED rule with {len(all_dest_ids)} destinations")
            else:
                if self.verbose:
                    print("WARNING: No RuleCheck field ID set, cannot consolidate MAKE_DISABLED")
                # Keep original rules if no RuleCheck
                result.extend(general_disabled[:5])  # Limit to avoid over-generation

        # Add specific disabled rules
        result.extend(specific_disabled)

        return result

    def _consolidate_groupable(self, rules: List[Dict]) -> List[Dict]:
        """
        Consolidate groupable actions by (actionType, sourceIds, condition, conditionalValues).

        Rules with same trigger criteria are merged into single rule with combined destinations.
        """
        groups = defaultdict(list)
        non_groupable = []

        for rule in rules:
            action = rule.get('actionType')
            if action in self.CONSOLIDATABLE_ACTIONS and action != 'MAKE_DISABLED':
                # Group by trigger criteria
                key = (
                    action,
                    tuple(sorted(rule.get('sourceIds', []))),
                    rule.get('condition'),
                    tuple(sorted(rule.get('conditionalValues', [])))
                )
                groups[key].append(rule)
            else:
                non_groupable.append(rule)

        # Merge grouped rules
        consolidated = []
        for key, group_rules in groups.items():
            if len(group_rules) == 1:
                consolidated.append(group_rules[0])
            else:
                # Merge: combine all destinationIds
                merged = group_rules[0].copy()
                all_dest_ids = set()
                for r in group_rules:
                    all_dest_ids.update(r.get('destinationIds', []))
                merged['destinationIds'] = sorted(list(all_dest_ids))

                # Merge postTriggerRuleIds
                all_post_trigger = set()
                for r in group_rules:
                    all_post_trigger.update(r.get('postTriggerRuleIds', []))
                merged['postTriggerRuleIds'] = sorted(list(all_post_trigger))

                consolidated.append(merged)

                if self.verbose:
                    print(f"Merged {len(group_rules)} {key[0]} rules into 1")

        consolidated.extend(non_groupable)
        return consolidated

    def _deduplicate(self, rules: List[Dict]) -> List[Dict]:
        """Remove exact duplicate rules."""
        seen = set()
        deduplicated = []

        for rule in rules:
            # Create unique key for this rule
            key = (
                rule.get('actionType'),
                tuple(sorted(rule.get('sourceIds', []))),
                tuple(sorted(rule.get('destinationIds', []))),
                rule.get('sourceType'),
                rule.get('condition'),
                tuple(sorted(rule.get('conditionalValues', []))),
                rule.get('params')
            )

            if key not in seen:
                seen.add(key)
                deduplicated.append(rule)
            else:
                if self.verbose:
                    print(f"Removed duplicate {rule.get('actionType')} rule")

        return deduplicated
