#!/usr/bin/env python3
"""
Resolve EDV Variable Names to Field IDs

Deterministic script that replaces variableName strings (e.g. "_processtypebasicdetails_")
in the params of EXT_VALUE, EXTERNAL_DROP_DOWN, and VALIDATE_EDV rules with the
corresponding numeric field ID.

These variable names appear in criterias inside params for cascading dropdowns, e.g.:
  "criterias": [{"a1": "_accountgroupvendortypebasicdetails_"}]
  →
  "criterias": [{"a1": 8}]

Usage:
  python3 dispatchers/agents/resolve_edv_varnames.py \\
      --json /tmp/test_merged.json \\
      --output /tmp/test_resolved.json

  # In-place update (overwrites input file):
  python3 dispatchers/agents/resolve_edv_varnames.py \\
      --json /tmp/test_merged.json
"""

import argparse
import json
import sys

TARGET_ACTIONS = {'ext_value', 'external_drop_down', 'validate_edv'}


def is_target_action(action_type: str) -> bool:
    return any(t in action_type.lower() for t in TARGET_ACTIONS)


def resolve_varnames(json_path: str, output_path: str) -> None:
    print(f"Loading JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_types = data.get('template', {}).get('documentTypes', [])
    if not doc_types:
        print("ERROR: No documentTypes found in JSON.")
        sys.exit(1)

    all_metadatas = doc_types[0].get('formFillMetadatas', [])
    print(f"  Fields (formFillMetadatas): {len(all_metadatas)}")

    # Build variableName -> id map (variableName is at top level of each metadata)
    varname_to_id = {}
    for meta in all_metadatas:
        vn = meta.get('variableName', '')
        if vn:
            varname_to_id[vn] = meta['id']

    print(f"  Variable names indexed: {len(varname_to_id)}")

    replaced = []    # (field_name, rule_id, action, old_val, new_val, path)
    no_match = []    # variable names found in params but not in index

    for meta in all_metadatas:
        field_name = meta.get('formTag', {}).get('name', f"id={meta.get('id')}")

        for rule in meta.get('formFillRules', []):
            action = rule.get('actionType', '')
            if not is_target_action(action):
                continue

            params_raw = rule.get('params')
            if not params_raw:
                continue

            # params is stored as a JSON string
            try:
                params = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
            except (json.JSONDecodeError, TypeError):
                print(f"  WARNING: Could not parse params for rule {rule.get('id')} "
                      f"on field {repr(field_name)}")
                continue

            changed = False

            for cond_wrapper in params:
                for cond in cond_wrapper.get('conditionList', []):
                    for criteria in cond.get('criterias', []):
                        for key, val in list(criteria.items()):
                            if not isinstance(val, str):
                                continue
                            if not (val.startswith('_') and val.endswith('_')):
                                continue

                            field_id = varname_to_id.get(val)
                            if field_id is not None:
                                criteria[key] = field_id
                                replaced.append({
                                    'field': field_name,
                                    'rule_id': rule.get('id'),
                                    'action': action,
                                    'criteria_key': key,
                                    'old': val,
                                    'new': field_id,
                                })
                                changed = True
                            else:
                                no_match.append({
                                    'field': field_name,
                                    'rule_id': rule.get('id'),
                                    'action': action,
                                    'varname': val,
                                })

            if changed:
                rule['params'] = json.dumps(params, ensure_ascii=False)

    # Report
    print(f"\n--- Results ---")
    print(f"Variable names resolved : {len(replaced)}")
    print(f"Unresolved (not found)  : {len(no_match)}")

    if replaced:
        print("\nResolved:")
        for r in replaced:
            print(f"  Rule {r['rule_id']} ({r['action']}) on {r['field']!r} "
                  f"[{r['criteria_key']}]: {r['old']!r} → {r['new']}")

    if no_match:
        print("\nUnresolved variable names (not found in field index):")
        for n in no_match:
            print(f"  Rule {n['rule_id']} ({n['action']}) on {n['field']!r}: {n['varname']!r}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Replace variableNames in EDV/EXT_VALUE params with numeric field IDs."
    )
    parser.add_argument('--json',   required=True,
                        help='Path to API-format JSON file')
    parser.add_argument('--output', default=None,
                        help='Output path (default: overwrites --json in-place)')
    args = parser.parse_args()

    output_path = args.output if args.output else args.json
    resolve_varnames(args.json, output_path)


if __name__ == '__main__':
    main()
