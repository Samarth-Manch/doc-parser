import json

with open("output/vendor_extension/12/validate_edv/temp/Basic_Details_validate_edv_output.json") as f:
    data = json.load(f)

print("Total fields:", len(data))
unmapped = str(-1)
for field in data:
    if field["rules"]:
        print("\nField:", field["field_name"])
        for r in field["rules"]:
            dest = r.get("destination_fields", [])
            mapped = [d for d in dest if d != unmapped]
            print("  Rule:", r["rule_name"], "| id:", r["id"])
            print("    src:", r.get("source_fields"))
            print("    dest total:", len(dest), "| mapped:", len(mapped))
            if r["rule_name"] == "Validate EDV (Server)":
                print("    params:", r["params"])
                for i, d in enumerate(dest):
                    if d != unmapped:
                        print("      a%d -> %s" % (i+2, d))
