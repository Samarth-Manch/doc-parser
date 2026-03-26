log_path = "output/vendor_extension/runs/18/inter_panel/temp/complex_gst___tax_number_3___gsttaxnumber3gstpantaxdetails___log.txt"
lines = [
    "Step 1: Read expression_rules.md reference document",
    "Step 2: Read complex refs found 1 cross-panel reference",
    "Step 3: Read involved panels: Basic Details (23 fields), GST PAN TAX Details (9 fields)",
    "Step 4: Classification: clearing type, staging data derivation (VC_BASIC_DETAILS)",
    "Step 5: Built Expression (Client) clearing rule on _vendornameandcodebasicdetails_",
    "Step 6: Output written with 1 Expression (Client) rule placed across 2 panels",
]
with open(log_path, "w") as f:
    for line in lines:
        f.write(line + "\n")
print("Log written successfully")
