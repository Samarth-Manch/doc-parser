import json

f = open("output/vendor_extension/runs/4/validate_edv/temp/Basic_Details_validate_edv_output.json")
data = json.load(f)
f.close()

print("Total fields:", len(data))
print()
for field in data:
    rules = field.get("rules", [])
    for rule in rules:
        rn = rule.get("rule_name", "")
        if "Validate EDV" in rn:
            dest = rule["destination_fields"]
            mapped = [d for d in dest if d != "-1"]
            print("Field:", field["field_name"])
            print("  id:", rule["id"])
            print("  source:", rule["source_fields"])
            print("  params:", rule["params"])
            print("  dest_count:", len(dest), "mapped:", len(mapped))
            print("  mapped_to:", mapped)
            print()
