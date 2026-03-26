import json

# Read input
with open("output/vendor_extension/runs/18/inter_panel/temp/Basic_Details_fields_input.json") as f:
    fields = json.load(f)

log_lines = []

# ================================================================
# PRE-SCAN: Identify EDV derivation relationships
# ================================================================

# Group 1: Vendor Name and Code -> VC_BASIC_DETAILS
vc_basic_destinations = {
    2: "_addressnumberbasicdetails_",
    3: "_namefirstnameoftheorganizationbasicdetails_",
    4: "_citybasicdetails_",
    5: "_postalcodebasicdetails_",
    6: "_regionbasicdetails_",
    9: "_streetbasicdetails_",
    14: "_mobilenumbertelephone2basicdetails_",
    16: "_groupkeycorporategroupbasicdetails_",
    19: "_choosethegroupofcompanybasicdetails_",
    20: "_accountgroupvendortypebasicdetails_",
}

# Group 2: Address Number -> VC_ADDRESS_DETAILS
vc_address_destinations = {
    8: "_namemiddlenameoftheorganizationbasicdetails_",
    9: "_namelastnameoftheorganizationbasicdetails_",
    10: "_name4alternatenamebasicdetails_",
    14: "_districtbasicdetails_",
    43: "_street1basicdetails_",
    44: "_street2basicdetails_",
    45: "_street3basicdetails_",
    56: "_searchtermreferencenumberbasicdetails_",
    97: "_countrybasicdetails_",
}

# Group 3: Address Number -> VC_EMAIL_DETAILS
vc_email_destinations = {
    9: "_emailbasicdetails_",
}

log_lines.append("Pre-scan complete: Identified 3 potential Validate EDV rules.")
log_lines.append("Source fields: [Vendor Name and Code (_vendornameandcodebasicdetails_), Address Number (_addressnumberbasicdetails_)]")
log_lines.append("Grouped destinations:")
log_lines.append("  VC_BASIC_DETAILS (source: Vendor Name and Code): %d destination fields" % len(vc_basic_destinations))
log_lines.append("  VC_ADDRESS_DETAILS (source: Address Number): %d destination fields" % len(vc_address_destinations))
log_lines.append("  VC_EMAIL_DETAILS (source: Address Number): %d destination fields" % len(vc_email_destinations))
log_lines.append("Skipped VC_CIN_DETAILS: No source field specified in logic, derived column is a1 (lookup key).")
log_lines.append("")


def build_dest_array(max_col, mapping):
    """Build destination_fields array from a2 to a{max_col}."""
    result = []
    for col in range(2, max_col + 1):
        if col in mapping:
            result.append(mapping[col])
        else:
            result.append("-1")
    return result


# Rule 1: VC_BASIC_DETAILS - 20 columns, dest has 19 entries (a2-a20)
dest_basic = build_dest_array(20, vc_basic_destinations)
log_lines.append("Step 1: Field Vendor Name and Code is source field: yes")
log_lines.append("Step 2: Source field Vendor Name and Code has %d destination fields" % len(vc_basic_destinations))
log_lines.append("Step 3: Field Vendor Name and Code dropdown classification: Independent (no parent dependency)")
log_lines.append("Step 4: Field Vendor Name and Code needs Validate EDV: yes. Reason: Multiple fields derive values from VC_BASIC_DETAILS using this field as lookup key.")
log_lines.append("Step 5: EDV table for Vendor Name and Code: VC_BASIC_DETAILS")
log_lines.append("Step 6: Source fields for Vendor Name and Code: [_vendornameandcodebasicdetails_]")
log_lines.append("Step 7: Destination fields for Vendor Name and Code: %d entries (a2-a20, skipped a1 lookup key)" % len(dest_basic))
log_lines.append("Step 8: Params for Vendor Name and Code: VC_BASIC_DETAILS (simple lookup, single source)")
log_lines.append("Step 9: Placed Validate EDV rule on source field Vendor Name and Code with 1 source fields, %d destination fields" % len(dest_basic))
log_lines.append("")

# Rule 2: VC_ADDRESS_DETAILS - 97 columns, dest has 96 entries (a2-a97)
dest_address = build_dest_array(97, vc_address_destinations)
log_lines.append("Step 1: Field Address Number is source field: yes (for VC_ADDRESS_DETAILS)")
log_lines.append("Step 2: Source field Address Number has %d destination fields for VC_ADDRESS_DETAILS" % len(vc_address_destinations))
log_lines.append("Step 3: Field Address Number is TEXT type, not a dropdown - N/A")
log_lines.append("Step 4: Field Address Number needs Validate EDV: yes. Reason: Multiple fields derive values from VC_ADDRESS_DETAILS using Address Number as lookup key.")
log_lines.append("Step 5: EDV table for Address Number (1): VC_ADDRESS_DETAILS")
log_lines.append("Step 6: Source fields for Address Number (VC_ADDRESS_DETAILS): [_addressnumberbasicdetails_]")
log_lines.append("Step 7: Destination fields for Address Number (VC_ADDRESS_DETAILS): %d entries (a2-a97, skipped a1 lookup key)" % len(dest_address))
log_lines.append("Step 8: Params for Address Number (VC_ADDRESS_DETAILS): VC_ADDRESS_DETAILS (simple lookup, single source)")
log_lines.append("Step 9: Placed Validate EDV rule on source field Address Number with 1 source fields, %d destination fields" % len(dest_address))
log_lines.append("")

# Rule 3: VC_EMAIL_DETAILS - 9 columns, dest has 8 entries (a2-a9)
dest_email = build_dest_array(9, vc_email_destinations)
log_lines.append("Step 1: Field Address Number is source field: yes (for VC_EMAIL_DETAILS)")
log_lines.append("Step 2: Source field Address Number has %d destination fields for VC_EMAIL_DETAILS" % len(vc_email_destinations))
log_lines.append("Step 4: Field Address Number needs Validate EDV: yes. Reason: Email field derives value from VC_EMAIL_DETAILS using Address Number as lookup key.")
log_lines.append("Step 5: EDV table for Address Number (2): VC_EMAIL_DETAILS")
log_lines.append("Step 6: Source fields for Address Number (VC_EMAIL_DETAILS): [_addressnumberbasicdetails_]")
log_lines.append("Step 7: Destination fields for Address Number (VC_EMAIL_DETAILS): %d entries (a2-a9, skipped a1 lookup key)" % len(dest_email))
log_lines.append("Step 8: Params for Address Number (VC_EMAIL_DETAILS): VC_EMAIL_DETAILS (simple lookup, single source)")
log_lines.append("Step 9: Placed Validate EDV rule on source field Address Number with 1 source fields, %d destination fields" % len(dest_email))
log_lines.append("")

# ================================================================
# Build output JSON
# ================================================================

output = []
for field in fields:
    f = dict(field)
    vn = f["variableName"]

    if vn == "_vendornameandcodebasicdetails_":
        f["rules"] = list(f["rules"])
        f["rules"].append({
            "id": 296,
            "rule_name": "Validate EDV (Server)",
            "source_fields": ["_vendornameandcodebasicdetails_"],
            "destination_fields": dest_basic,
            "params": "VC_BASIC_DETAILS",
            "_reasoning": (
                "VC_BASIC_DETAILS has at least 20 columns. Source is Vendor Name and Code "
                "(a1 = lookup key, skipped in destinations). Destination fields map a2-a20: "
                "a2->Address Number, a3->Name/First Name, a4->City, a5->Postal Code, "
                "a6->Region, a9->Street, a14->Mobile Number, a16->Group key/Corporate Group, "
                "a19->Choose Group of Company, a20->Account Group/Vendor Type. "
                "Unmapped columns filled with -1. Total 19 destination entries."
            )
        })

    elif vn == "_addressnumberbasicdetails_":
        f["rules"] = list(f["rules"])
        f["rules"].append({
            "id": 297,
            "rule_name": "Validate EDV (Server)",
            "source_fields": ["_addressnumberbasicdetails_"],
            "destination_fields": dest_address,
            "params": "VC_ADDRESS_DETAILS",
            "_reasoning": (
                "VC_ADDRESS_DETAILS has at least 97 columns. Source is Address Number "
                "(a1 = lookup key, skipped in destinations). Destination fields map a2-a97: "
                "a8->Name/Middle Name, a9->Name/Last Name, a10->Name 4/Alternate Name, "
                "a14->District, a43->Street 1, a44->Street 2, a45->Street 3, "
                "a56->Search term/Reference Number, a97->Country. "
                "Unmapped columns filled with -1. Total 96 destination entries."
            )
        })
        f["rules"].append({
            "id": 298,
            "rule_name": "Validate EDV (Server)",
            "source_fields": ["_addressnumberbasicdetails_"],
            "destination_fields": dest_email,
            "params": "VC_EMAIL_DETAILS",
            "_reasoning": (
                "VC_EMAIL_DETAILS has at least 9 columns. Source is Address Number "
                "(a1 = lookup key, skipped in destinations). Destination fields map a2-a9: "
                "a9->Email. Unmapped columns a2-a8 filled with -1. Total 8 destination entries."
            )
        })

    output.append(f)

# Write output
with open("output/vendor_extension/runs/18/inter_panel/temp/Basic_Details_validate_edv_output.json", "w") as f:
    json.dump(output, f, indent=2)

# Write log
log_lines.append("Step 10 complete: Created output JSON with 3 Validate EDV rules placed on 2 source fields.")
log_lines.append("  - Vendor Name and Code: 1 Validate EDV rule (VC_BASIC_DETAILS)")
log_lines.append("  - Address Number: 2 Validate EDV rules (VC_ADDRESS_DETAILS, VC_EMAIL_DETAILS)")
log_lines.append("  - Skipped: Name of Representative / VC_CIN_DETAILS (no source field, a1 is lookup key)")

with open("output/vendor_extension/runs/18/inter_panel/temp/Basic_Details_validate_edv_log.txt", "w") as f:
    f.write("\n".join(log_lines) + "\n")

# Verify
print("Output: %d fields" % len(output))
vnc = [f for f in output if f["variableName"] == "_vendornameandcodebasicdetails_"][0]
adr = [f for f in output if f["variableName"] == "_addressnumberbasicdetails_"][0]
print("Vendor Name and Code rules: %d" % len(vnc["rules"]))
print("Address Number rules: %d" % len(adr["rules"]))
print("VC_BASIC_DETAILS dest count: %d" % len(dest_basic))
print("VC_ADDRESS_DETAILS dest count: %d" % len(dest_address))
print("VC_EMAIL_DETAILS dest count: %d" % len(dest_email))

# Sanity checks
assert len(dest_basic) == 19
assert len(dest_address) == 96
assert len(dest_email) == 8
assert dest_basic[0] == "_addressnumberbasicdetails_"  # a2
assert dest_basic[1] == "_namefirstnameoftheorganizationbasicdetails_"  # a3
assert dest_basic[7] == "_streetbasicdetails_"  # a9 (index 7)
assert dest_address[6] == "_namemiddlenameoftheorganizationbasicdetails_"  # a8 (index 6)
assert dest_address[95] == "_countrybasicdetails_"  # a97 (index 95)
assert dest_email[7] == "_emailbasicdetails_"  # a9 (index 7)
print("All assertions passed!")
