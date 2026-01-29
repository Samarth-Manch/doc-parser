"""Analyze natural language logic/rules from parsed documents"""
from doc_parser.parser import DocumentParser

parser = DocumentParser()

# Parse the Vendor Creation document
result = parser.parse("documents/Vendor Creation Sample BUD(1).docx")

print("="*100)
print("NATURAL LANGUAGE LOGIC/RULES FROM DOCUMENT")
print("="*100)
print()

# Analyze field logic
fields_with_logic = [f for f in result.all_fields if f.logic and len(f.logic.strip()) > 5]

print(f"Total fields: {len(result.all_fields)}")
print(f"Fields with logic/rules: {len(fields_with_logic)}")
print()

# Categorize logic patterns
visibility_patterns = []
mandatory_patterns = []
copy_patterns = []
validation_patterns = []
conditional_patterns = []
other_patterns = []

for field in fields_with_logic:
    logic_lower = field.logic.lower()

    if 'visible' in logic_lower or 'show' in logic_lower or 'hide' in logic_lower or 'invisible' in logic_lower:
        visibility_patterns.append(field)
    elif 'mandatory' in logic_lower or 'required' in logic_lower:
        mandatory_patterns.append(field)
    elif 'copy' in logic_lower or 'auto-populate' in logic_lower or 'auto populate' in logic_lower or 'prefill' in logic_lower:
        copy_patterns.append(field)
    elif 'validate' in logic_lower or 'must be' in logic_lower or 'should be' in logic_lower or 'cannot' in logic_lower:
        validation_patterns.append(field)
    elif 'if ' in logic_lower or 'when ' in logic_lower or 'based on' in logic_lower:
        conditional_patterns.append(field)
    else:
        other_patterns.append(field)

print("LOGIC PATTERN CATEGORIES:")
print("-"*100)
print(f"  Visibility rules (show/hide): {len(visibility_patterns)}")
print(f"  Mandatory rules: {len(mandatory_patterns)}")
print(f"  Copy/Auto-populate rules: {len(copy_patterns)}")
print(f"  Validation rules: {len(validation_patterns)}")
print(f"  Conditional rules: {len(conditional_patterns)}")
print(f"  Other/Uncategorized: {len(other_patterns)}")
print()

# Show examples of each category
print("="*100)
print("VISIBILITY RULES EXAMPLES")
print("="*100)
for f in visibility_patterns[:5]:
    print(f"\nField: {f.name}")
    print(f"Type: {f.field_type.value}")
    print(f"Logic: {f.logic[:300]}...")
    print("-"*50)

print()
print("="*100)
print("MANDATORY RULES EXAMPLES")
print("="*100)
for f in mandatory_patterns[:5]:
    print(f"\nField: {f.name}")
    print(f"Type: {f.field_type.value}")
    print(f"Logic: {f.logic[:300]}...")
    print("-"*50)

print()
print("="*100)
print("COPY/AUTO-POPULATE RULES EXAMPLES")
print("="*100)
for f in copy_patterns[:5]:
    print(f"\nField: {f.name}")
    print(f"Type: {f.field_type.value}")
    print(f"Logic: {f.logic[:300]}...")
    print("-"*50)

print()
print("="*100)
print("CONDITIONAL RULES EXAMPLES")
print("="*100)
for f in conditional_patterns[:5]:
    print(f"\nField: {f.name}")
    print(f"Type: {f.field_type.value}")
    print(f"Logic: {f.logic[:300]}...")
    print("-"*50)

print()
print("="*100)
print("VALIDATION RULES EXAMPLES")
print("="*100)
for f in validation_patterns[:5]:
    print(f"\nField: {f.name}")
    print(f"Type: {f.field_type.value}")
    print(f"Logic: {f.logic[:300]}...")
    print("-"*50)
