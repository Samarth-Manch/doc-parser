#!/usr/bin/env python3
"""
Post Trigger Rule IDs Linker

Deterministic script that populates postTriggerRuleIds on every SERVER-side rule
in the API-format JSON.

Logic:
  If a SERVER-side rule on field F writes to destination field D, and D has its
  own SERVER-side rule(s), those rule IDs are appended to F's rule's
  postTriggerRuleIds.  CLIENT-side rules are never added.

Usage:
  python3 dispatchers/agents/post_trigger_linker.py \\
      --json /tmp/test_merged.json \\
      --output /tmp/test_post_trigger.json

  # In-place update (overwrites input file):
  python3 dispatchers/agents/post_trigger_linker.py \\
      --json /tmp/test_merged.json
"""

import argparse
import json
import sys


def link_post_triggers(json_path: str, output_path: str) -> None:
    print(f"Loading JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_types = data.get('template', {}).get('documentTypes', [])
    if not doc_types:
        print("ERROR: No documentTypes found in JSON.")
        sys.exit(1)

    all_metadatas = doc_types[0].get('formFillMetadatas', [])
    print(f"  Fields (formFillMetadatas): {len(all_metadatas)}")

    # Step 1: Build id → field_meta map
    id_to_field = {m['id']: m for m in all_metadatas if 'id' in m}

    # Step 2: Count SERVER rules for reporting
    total_server_rules = sum(
        1 for m in all_metadatas
        for r in m.get('formFillRules', [])
        if r.get('processingType') == 'SERVER'
    )
    print(f"  SERVER rules to scan: {total_server_rules}")

    # Step 3: Link postTriggerRuleIds
    populated = []   # rules that received at least one postTriggerRuleId
    no_trigger = []  # SERVER rules with no triggers found
    skipped_self = []  # self-references skipped

    for meta in all_metadatas:
        field_name = meta.get('formTag', {}).get('name', f"id={meta.get('id')}")

        for rule in meta.get('formFillRules', []):
            if rule.get('processingType') != 'SERVER':
                continue

            rule_id = rule.get('id')
            dest_ids = [d for d in rule.get('destinationIds', []) if d != -1]
            added_ids = []

            source_field_id = meta.get('id')

            for dest_id in dest_ids:
                # Skip if destination is the same field — post triggers
                # should only chain to rules on different fields
                if dest_id == source_field_id:
                    skipped_self.append({
                        'field': field_name,
                        'rule_id': rule_id,
                        'action': rule.get('actionType'),
                        'reason': 'destination is same field',
                    })
                    continue

                dest_field = id_to_field.get(dest_id)
                if dest_field is None:
                    continue

                for dest_rule in dest_field.get('formFillRules', []):
                    if dest_rule.get('processingType') != 'SERVER':
                        continue
                    triggered_id = dest_rule.get('id')
                    if triggered_id is None:
                        continue
                    existing = rule.setdefault('postTriggerRuleIds', [])
                    if triggered_id not in existing:
                        existing.append(triggered_id)
                        added_ids.append(triggered_id)

            if added_ids:
                populated.append({
                    'field': field_name,
                    'rule_id': rule_id,
                    'action': rule.get('actionType'),
                    'added': added_ids,
                })
            else:
                no_trigger.append({
                    'field': field_name,
                    'rule_id': rule_id,
                    'action': rule.get('actionType'),
                    'dest_ids': dest_ids,
                })

    # Step 4: Detect and remove circular references
    # Build a graph: rule_id → list of postTriggerRuleIds
    rule_id_to_rule = {}
    for meta in all_metadatas:
        for rule in meta.get('formFillRules', []):
            rid = rule.get('id')
            if rid is not None:
                rule_id_to_rule[rid] = rule

    def _has_cycle_from(start_id, graph):
        """Check if following postTriggerRuleIds from start_id leads back to it."""
        visited = set()
        stack = list(graph.get(start_id, []))
        while stack:
            nid = stack.pop()
            if nid == start_id:
                return True
            if nid in visited:
                continue
            visited.add(nid)
            stack.extend(graph.get(nid, []))
        return False

    # Build adjacency from current state
    graph = {}
    for rid, rule in rule_id_to_rule.items():
        pts = rule.get('postTriggerRuleIds', [])
        if pts:
            graph[rid] = list(pts)

    circular_removed = []
    # For each rule, check if any of its postTriggerRuleIds creates a cycle
    for rid in list(graph.keys()):
        rule = rule_id_to_rule[rid]
        pts = rule.get('postTriggerRuleIds', [])
        if not pts:
            continue
        clean = []
        for tid in pts:
            # Temporarily set postTriggerRuleIds to clean + [tid] and check
            graph[rid] = clean + [tid]
            if _has_cycle_from(rid, graph):
                field_name = 'unknown'
                for m in all_metadatas:
                    if any(r.get('id') == rid for r in m.get('formFillRules', [])):
                        field_name = m.get('formTag', {}).get('name', f"id={m.get('id')}")
                        break
                circular_removed.append({
                    'rule_id': rid,
                    'removed_trigger': tid,
                    'field': field_name,
                })
            else:
                clean.append(tid)
        # Update the rule with the cycle-free list
        if clean:
            rule['postTriggerRuleIds'] = clean
            graph[rid] = clean
        else:
            rule.pop('postTriggerRuleIds', None)
            graph.pop(rid, None)

    # Report
    print(f"\n--- Results ---")
    print(f"Total SERVER rules scanned : {total_server_rules}")
    print(f"Rules with triggers linked : {len(populated)}")
    print(f"Rules with no triggers     : {len(no_trigger)}")
    print(f"Self-references skipped    : {len(skipped_self)}")
    print(f"Circular references removed: {len(circular_removed)}")

    if populated:
        print("\nLinked rules:")
        for p in populated:
            print(f"  Rule {p['rule_id']} ({p['action']}) on {p['field']!r}"
                  f" → postTriggerRuleIds: {p['added']}")

    if skipped_self:
        print("\nSame-field references skipped (would cause infinite loop):")
        for s in skipped_self:
            print(f"  Rule {s['rule_id']} ({s['action']}) on {s['field']!r}"
                  f" — destination is same field")

    if circular_removed:
        print("\nCircular references removed (would cause infinite loop):")
        for c in circular_removed:
            print(f"  Rule {c['rule_id']} on {c['field']!r}"
                  f" — removed trigger to rule {c['removed_trigger']}")

    if no_trigger:
        print("\nNo triggers found for:")
        for n in no_trigger:
            dest_str = f" (destIds={n['dest_ids']})" if n['dest_ids'] else " (no dest ids)"
            print(f"  Rule {n['rule_id']} ({n['action']}) on {n['field']!r}{dest_str}")

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Populate postTriggerRuleIds on SERVER-side rules in API-format JSON."
    )
    parser.add_argument('--json',   required=True,
                        help='Path to API-format JSON file')
    parser.add_argument('--output', default=None,
                        help='Output path (default: overwrites --json in-place)')
    args = parser.parse_args()

    output_path = args.output if args.output else args.json
    link_post_triggers(args.json, output_path)


if __name__ == '__main__':
    main()
