"""Analyze rules schema"""
import json

with open('rules/Rule-Schemas.json') as f:
    data = json.load(f)

print(f"Total rules: {len(data['content'])}")

# Get unique actions
actions = set()
sources = set()
processing_types = set()

for r in data['content']:
    actions.add(r.get('action', ''))
    sources.add(r.get('source', ''))
    processing_types.add(r.get('processingType', ''))

print(f"\nUnique Actions ({len(actions)}):")
for a in sorted(actions):
    print(f"  - {a}")

print(f"\nUnique Processing Types ({len(processing_types)}):")
for p in sorted(processing_types):
    print(f"  - {p}")

print(f"\nUnique Sources (sample of 20):")
for s in sorted(sources)[:20]:
    print(f"  - {s}")

# Sample a few different rule types
print("\n" + "="*80)
print("SAMPLE RULES BY ACTION TYPE:")
print("="*80)

# Get one example of each action type
seen_actions = set()
for r in data['content']:
    action = r.get('action', '')
    if action not in seen_actions and len(seen_actions) < 10:
        seen_actions.add(action)
        print(f"\n--- {action} Rule Example ---")
        print(f"Name: {r.get('name', '')}")
        print(f"Source: {r.get('source', '')}")
        print(f"ProcessingType: {r.get('processingType', '')}")
        if 'destinationFields' in r:
            dest = r['destinationFields']
            print(f"Destination Fields: {dest.get('numberOfItems', 0)} fields")
            if 'fields' in dest:
                for field in dest['fields'][:3]:
                    print(f"  - {field.get('name', '')}")
        if 'expression' in r:
            expr = r['expression'][:100] if len(r.get('expression', '')) > 100 else r.get('expression', '')
            print(f"Expression: {expr}...")
        print()
