#!/usr/bin/env python3
"""
Process PAN and GST Details panel and add conditional logic to rules.
Performs comprehensive cross-field analysis to populate source_fields and destination_fields.
"""

import json
from typing import List, Dict, Any
from datetime import datetime
import os

def log_message(log_file, message):
    """Write a timestamped message to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def build_field_dependency_map(fields: List[Dict[str, Any]], log_file: str) -> Dict[str, Dict[str, Any]]:
    """Build field dependency map through cross-field analysis."""
    log_message(log_file, "\n" + "="*80)
    log_message(log_file, "STEP 1: Building field dependency map")
    log_message(log_file, "="*80)

    field_map = {}
    
    # Create map
    for field in fields:
        var_name = field.get("variableName", "")
        field_name = field.get("field_name", "")
        logic = field.get("logic", "")
        
        field_map[var_name] = {
            "field_name": field_name,
            "logic": logic,
            "mentioned_by": [],
            "mentions": []
        }
    
    # Analyze dependencies
    for var_name, info in field_map.items():
        field_name_lower = info["field_name"].lower()
        
        for other_var, other_info in field_map.items():
            if other_var == var_name:
                continue
                
            other_logic_lower = other_info["logic"].lower()
            
            # Check if other field mentions this field
            if f'"{field_name_lower}"' in other_logic_lower or f" {field_name_lower} " in other_logic_lower:
                info["mentioned_by"].append(other_var)
                field_map[other_var]["mentions"].append(var_name)
                log_message(log_file, f"  Dependency: {other_info[\'field_name\']} mentions {info[\'field_name\']}")
    
    return field_map

def extract_conditional_values(logic: str) -> List[str]:
    """Extract conditional values from logic."""
    logic_lower = logic.lower()
    
    if "yes then" in logic_lower or "is yes" in logic_lower or "values is yes" in logic_lower:
        return ["Yes"]
    if "no then" in logic_lower or "is no" in logic_lower or "values is no" in logic_lower:
        return ["No"]
    if "always invisible" in logic_lower:
        return ["Invisible"]
    if "non-editable" in logic_lower or "non editable" in logic_lower:
        return ["Disable"]
    
    return []

def process_field(field: Dict[str, Any], field_map: Dict[str, Dict[str, Any]], log_file: str) -> Dict[str, Any]:
    """Process field and add conditional logic."""
    field_name = field.get("field_name", "")
    var_name = field.get("variableName", "")
    logic = field.get("logic", "")
    rules = field.get("rules", [])
    
    log_message(log_file, f"\n{'='*80}")
    log_message(log_file, f"Field: {field_name}")
    log_message(log_file, f"Logic: {logic}")
    
    for rule in rules:
        rule_name = rule.get("rule_name", "")
        log_message(log_file, f"\n  Rule: {rule_name}")
        
        # Check if visibility/mandatory rule
        is_conditional_rule = any(kw in rule_name for kw in 
            ["Make Visible", "Make Invisible", "Make Mandatory", "Make Non Mandatory", "Disable Field"])
        
        if is_conditional_rule:
            conditional_values = extract_conditional_values(logic)
            
            if conditional_values:
                # Determine condition
                if "Make Invisible" in rule_name or "Make Non Mandatory" in rule_name:
                    condition = "NOT_IN"
                elif "always" in logic.lower():
                    condition = "NOT_IN"
                else:
                    condition = "IN"
                
                # Find source and destination
                logic_lower = logic.lower()
                source_fields = []
                destination_fields = [var_name]
                
                if "please select gst option" in logic_lower:
                    source_fields = ["__please_select_gst_option__"]
                    # Find all fields affected by GST option
                    gst_option_mentions = field_map.get("__please_select_gst_option__", {}).get("mentioned_by", [])
                    if var_name in gst_option_mentions:
                        destination_fields = [var_name]
                
                # Add conditional logic
                rule["conditionalValues"] = conditional_values
                rule["condition"] = condition
                rule["conditionValueType"] = "TEXT"
                
                # Update source/dest for visibility rules
                if any(kw in rule_name for kw in ["Make Visible", "Make Invisible", "Make Mandatory", "Make Non Mandatory"]):
                    rule["source_fields"] = source_fields
                    rule["destination_fields"] = destination_fields
                
                # Update reasoning
                old_reasoning = rule.get("_reasoning", "")
                rule["_reasoning"] = f"{old_reasoning} | Conditional: src={source_fields}, dst={destination_fields}, {condition} {conditional_values}."
                
                log_message(log_file, f"    Added: conditionalValues={conditional_values}, condition={condition}")
                log_message(log_file, f"    source_fields={source_fields}, destination_fields={destination_fields}")
    
    return field

def main():
    os.makedirs("output/conditional_logic/temp", exist_ok=True)
    
    input_file = "output/conditional_logic/temp/PAN_and_GST_Details_fields_input.json"
    output_file = "output/conditional_logic/temp/PAN_and_GST_Details_conditional_logic_output.json"
    log_file = "output/conditional_logic/temp/PAN_and_GST_Details_conditional_logic_log.txt"
    
    with open(log_file, "w") as f:
        f.write(f"PAN and GST Details - Conditional Logic Processing\n")
        f.write(f"Started: {datetime.now()}\n")
        f.write("="*80 + "\n")
    
    with open(input_file, "r") as f:
        fields = json.load(f)
    
    log_message(log_file, f"Processing {len(fields)} fields")
    
    # Build dependency map
    field_map = build_field_dependency_map(fields, log_file)
    
    # Process fields
    log_message(log_file, "\n" + "="*80)
    log_message(log_file, "STEP 2: Processing fields")
    log_message(log_file, "="*80)
    
    processed_fields = []
    for field in fields:
        processed_field = process_field(field, field_map, log_file)
        processed_fields.append(processed_field)
    
    with open(output_file, "w") as f:
        json.dump(processed_fields, f, indent=2)
    
    log_message(log_file, f"\nComplete! Output: {output_file}")
    print(f"Done! Output: {output_file}")
    print(f"Log: {log_file}")

if __name__ == "__main__":
    main()
