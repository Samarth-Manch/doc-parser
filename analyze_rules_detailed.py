"""Detailed analysis of specific rule types"""
import json

with open('rules/Rule-Schemas.json') as f:
    data = json.load(f)

# Find specific rule types
execute_rules = []
visibility_rules = []
mandatory_rules = []
copy_rules = []

for r in data['content']:
    action = r.get('action', '')
    if action == 'EXECUTE':
        execute_rules.append(r)
    elif 'VISIBLE' in action or 'INVISIBLE' in action:
        visibility_rules.append(r)
    elif 'MANDATORY' in action:
        mandatory_rules.append(r)
    elif 'COPY' in action:
        copy_rules.append(r)

print("="*100)
print("EXECUTE RULES (Expression-based)")
print("="*100)
for r in execute_rules[:3]:
    print(f"\nName: {r.get('name')}")
    print(f"Processing: {r.get('processingType')}")
    print(f"Source: {r.get('source')}")
    print(f"Params schema:")
    if 'params' in r and 'jsonSchema' in r['params']:
        schema = r['params']['jsonSchema']
        print(json.dumps(schema, indent=2)[:500])
    print(f"\nFull rule structure:")
    print(json.dumps(r, indent=2)[:1500])

print("\n" + "="*100)
print("VISIBILITY RULES (MAKE_VISIBLE / MAKE_INVISIBLE)")
print("="*100)
for r in visibility_rules[:3]:
    print(f"\nName: {r.get('name')}")
    print(f"Action: {r.get('action')}")
    print(f"Processing: {r.get('processingType')}")
    print(f"Destination Fields: {r.get('destinationFields', {}).get('numberOfItems', 0)}")
    print(f"\nFull rule structure:")
    print(json.dumps(r, indent=2)[:1000])

print("\n" + "="*100)
print("MANDATORY RULES")
print("="*100)
for r in mandatory_rules[:3]:
    print(f"\nName: {r.get('name')}")
    print(f"Action: {r.get('action')}")
    print(f"Processing: {r.get('processingType')}")
    print(f"\nFull rule structure:")
    print(json.dumps(r, indent=2)[:1000])

print("\n" + "="*100)
print("COPY_TO RULES")
print("="*100)
for r in copy_rules[:3]:
    print(f"\nName: {r.get('name')}")
    print(f"Action: {r.get('action')}")
    print(f"Source: {r.get('source')}")
    print(f"\nFull rule structure:")
    print(json.dumps(r, indent=2)[:1000])
