#!/usr/bin/env python3
"""
Fix Mandatory + Editable Fields

Deterministic script that sets mandatory and editable on every field in the
API-format JSON based on the BUD tables in sections 4.5.1 (Initiator) and
4.5.2 (Vendor/SPOC).

Rules (from BUD):
  Field only in 4.5.1 (Initiator):
    mandatory=Yes  →  mandatory=true,  editable=false
    mandatory=No   →  mandatory=false, editable=false

  Field only in 4.5.2 (Vendor/SPOC):
    mandatory=Yes  →  mandatory=true,  editable=true
    mandatory=No   →  mandatory=false, editable=true

  Field in BOTH tables:
    Only 4.5.1 mandatory  →  mandatory=true,  editable=false  (4.5.1 wins)
    Only 4.5.2 mandatory  →  mandatory=true,  editable=true   (4.5.2 wins)
    Both mandatory        →  mandatory=true,  editable=true   (4.5.2 wins)
    Neither mandatory     →  mandatory=false, editable=true   (4.5.2 wins)

  Additionally: if the logic/rules column in 4.5.2 says "Disable",
  editable is forced to false regardless of the above.

Fields not found in either table are skipped (kept as-is).

Matching strategy:
  Reads the 4.5.1 and 4.5.2 tables directly from the .docx, tracking the
  current PANEL row as section context.
  Matches JSON fields by (normalize(formTag.name), normalize(current_panel)).

Usage:
  python3 dispatchers/agents/fix_mandatory_fields.py \\
      --bud "documents/Vendor Creation Sample BUD 2.docx" \\
      --json /tmp/test_merged_6.json \\
      --output /tmp/test_merged_6_fixed.json

  # In-place update (overwrites input file):
  python3 dispatchers/agents/fix_mandatory_fields.py \\
      --bud "documents/Vendor Creation Sample BUD 2.docx" \\
      --json /tmp/test_merged_6.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table


def normalize(s: str) -> str:
    """Lowercase and strip all non-alphanumeric characters."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def parse_mandatory(value: str) -> bool:
    """Parse 'Yes'/'No'/'True'/'False'/'' → bool."""
    v = value.strip().lower()
    return v in ('yes', 'true', 'y', '1', 'mandatory')


def read_behaviour_table(tbl: Table) -> dict:
    """
    Parse a 4.5.x behaviour table into a lookup:
      (normalize(field_name), normalize(panel)) -> {'mandatory': bool, 'disabled': bool}

    'disabled' is True when the logic/rules column contains 'disable'.

    Table format:
      Row 0  : headers — ['Field Name', 'Field Type', 'Mandatory', 'Logic/Rules', ...]
      PANEL rows: field_type column == 'PANEL'  (track current panel)
      Data rows: normal field rows
    """
    lookup = {}
    current_panel = ''

    rows = tbl.rows
    if not rows:
        return lookup

    # Find column indices from the header row
    headers = [c.text.strip().lower() for c in rows[0].cells]
    name_idx      = next((i for i, h in enumerate(headers) if 'field name' in h or h == 'field'), 0)
    type_idx      = next((i for i, h in enumerate(headers) if 'field type' in h or h == 'type'), 1)
    mandatory_idx = next((i for i, h in enumerate(headers) if 'mandatory' in h), 2)
    logic_idx     = next((i for i, h in enumerate(headers) if 'logic' in h or 'rule' in h), -1)

    for row in rows[1:]:
        cells = [c.text.strip() for c in row.cells]
        if len(cells) <= max(name_idx, type_idx, mandatory_idx):
            continue

        field_name  = cells[name_idx]
        field_type  = cells[type_idx].upper()
        mandatory_v = cells[mandatory_idx]
        logic_v     = cells[logic_idx].lower() if logic_idx != -1 and logic_idx < len(cells) else ''

        if not field_name:
            continue

        # PANEL row — update current panel context
        if field_type == 'PANEL':
            current_panel = field_name
            continue

        key = (normalize(field_name), normalize(current_panel))
        is_mandatory = parse_mandatory(mandatory_v)
        is_disabled  = 'disable' in logic_v

        # If duplicate key, mandatory=True wins
        if key not in lookup or is_mandatory:
            lookup[key] = {'mandatory': is_mandatory, 'disabled': is_disabled}

    return lookup


def build_bud_lookups(bud_path: str):
    """
    Read 4.5.1 and 4.5.2 tables directly from the .docx and return:
      init_lookup  — (norm_name, norm_panel) -> is_mandatory  (4.5.1 Initiator)
      spoc_lookup  — (norm_name, norm_panel) -> is_mandatory  (4.5.2 Vendor/SPOC)
    """
    print(f"Parsing BUD: {bud_path}")
    doc = Document(bud_path)

    init_lookup = {}
    spoc_lookup = {}

    # States: None, '4.5.1', '4.5.2'
    current_section = None

    for block in doc.element.body:
        tag = block.tag.split('}')[-1]

        if tag == 'p':
            text = ''.join(r.text for r in block.findall('.//' + qn('w:t'))).strip()
            if '4.5.1' in text:
                current_section = '4.5.1'
            elif '4.5.2' in text:
                current_section = '4.5.2'
            elif re.match(r'4\.5\.[3-9]', text) or re.match(r'4\.[6-9]', text) or re.match(r'[5-9]\.', text):
                current_section = None  # past 4.5.2

        elif tag == 'tbl' and current_section in ('4.5.1', '4.5.2'):
            tbl = Table(block, doc)
            # Only process the field behaviour table (has 'Field Name' + 'Mandatory' headers)
            if not tbl.rows:
                continue
            headers_lower = [c.text.strip().lower() for c in tbl.rows[0].cells]
            if not any('field name' in h or h == 'field' for h in headers_lower):
                continue
            if not any('mandatory' in h for h in headers_lower):
                continue

            result = read_behaviour_table(tbl)

            if current_section == '4.5.1':
                # Merge: mandatory=True wins on duplicates
                for k, v in result.items():
                    if k not in init_lookup or v['mandatory']:
                        init_lookup[k] = v
            else:
                for k, v in result.items():
                    if k not in spoc_lookup or v['mandatory']:
                        spoc_lookup[k] = v

    mandatory_init = sum(1 for v in init_lookup.values() if v['mandatory'])
    mandatory_spoc = sum(1 for v in spoc_lookup.values() if v['mandatory'])
    print(f"  4.5.1 Initiator : {len(init_lookup)} fields "
          f"({mandatory_init} mandatory, {len(init_lookup) - mandatory_init} non-mandatory)")
    print(f"  4.5.2 SPOC/Vendor: {len(spoc_lookup)} fields "
          f"({mandatory_spoc} mandatory, {len(spoc_lookup) - mandatory_spoc} non-mandatory)")

    only_init = len(set(init_lookup) - set(spoc_lookup))
    only_spoc = len(set(spoc_lookup) - set(init_lookup))
    both      = len(set(init_lookup) & set(spoc_lookup))
    print(f"  Overlap: {both} in both, {only_init} initiator-only, {only_spoc} spoc-only")

    return init_lookup, spoc_lookup


def fix_fields(json_path: str, init_lookup: dict, spoc_lookup: dict, output_path: str) -> None:
    """
    Load API-format JSON, update mandatory + editable per BUD lookups, write output.
    """
    print(f"\nLoading JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_types = data.get('template', {}).get('documentTypes', [])
    if not doc_types:
        print("ERROR: No documentTypes found in JSON.")
        sys.exit(1)

    all_metadatas = doc_types[0].get('formFillMetadatas', [])
    print(f"  JSON fields: {len(all_metadatas)} formFillMetadatas")

    current_panel = ''
    changed = []
    skipped_unmatched = []

    for meta in all_metadatas:
        form_tag   = meta.get('formTag', {})
        field_name = form_tag.get('name', '')
        field_type = form_tag.get('type', '')

        # Track current panel (PANEL entries themselves are never updated)
        if field_type == 'PANEL':
            current_panel = field_name
            continue

        key          = (normalize(field_name), normalize(current_panel))
        old_mandatory = meta.get('mandatory', False)
        old_editable  = meta.get('editable', True)

        # Resolution rules for mandatory + editable:
        #   Field in both tables:
        #     - Only 4.5.1 is mandatory  → 4.5.1 wins → mandatory=true,  editable=false
        #     - Only 4.5.2 is mandatory  → 4.5.2 wins → mandatory=true,  editable=true
        #     - Both mandatory           → 4.5.2 wins → mandatory=true,  editable=true
        #     - Neither mandatory        → 4.5.2 wins → mandatory=false, editable=true
        #   Field only in 4.5.1         → mandatory=4.5.1 value, editable=false
        #   Field only in 4.5.2         → mandatory=4.5.2 value, editable=true
        in_init = key in init_lookup
        in_spoc = key in spoc_lookup

        if in_init and in_spoc:
            init_mandatory = init_lookup[key]['mandatory']
            spoc_mandatory = spoc_lookup[key]['mandatory']
            spoc_disabled  = spoc_lookup[key]['disabled']
            if init_mandatory and not spoc_mandatory:
                # Only initiator is mandatory → initiator wins
                new_mandatory = True
                new_editable  = False
                source = '4.5.1 Initiator (mandatory only here)'
            else:
                # Both mandatory, only spoc mandatory, or neither → 4.5.2 wins
                # But if 4.5.2 logic says Disable, field is not editable
                new_mandatory = spoc_mandatory or init_mandatory
                new_editable  = not spoc_disabled
                source = '4.5.2 SPOC (disabled)' if spoc_disabled else '4.5.2 SPOC'
        elif in_spoc:
            new_mandatory = spoc_lookup[key]['mandatory']
            new_editable  = not spoc_lookup[key]['disabled']
            source = '4.5.2 SPOC (disabled)' if spoc_lookup[key]['disabled'] else '4.5.2 SPOC'
        elif in_init:
            new_mandatory = init_lookup[key]['mandatory']
            new_editable  = False
            source = '4.5.1 Initiator'
        else:
            skipped_unmatched.append({
                'id': meta.get('id'),
                'field': field_name,
                'panel': current_panel,
                'mandatory': old_mandatory,
                'editable': old_editable,
            })
            continue

        meta['mandatory'] = new_mandatory
        meta['editable']  = new_editable

        if old_mandatory != new_mandatory or old_editable != new_editable:
            changed.append({
                'id': meta.get('id'),
                'field': field_name,
                'panel': current_panel,
                'source': source,
                'old_mandatory': old_mandatory,
                'new_mandatory': new_mandatory,
                'old_editable': old_editable,
                'new_editable': new_editable,
            })

    # Report
    print(f"\n--- Results ---")
    if changed:
        print(f"Changed ({len(changed)} fields):")
        for c in changed:
            parts = []
            if c['old_mandatory'] != c['new_mandatory']:
                parts.append(f"mandatory: {c['old_mandatory']} → {c['new_mandatory']}")
            if c['old_editable'] != c['new_editable']:
                parts.append(f"editable: {c['old_editable']} → {c['new_editable']}")
            print(f"  [id={c['id']}] [{c['source']}] {c['field']!r} "
                  f"(panel={c['panel']!r}): {', '.join(parts)}")
    else:
        print("No changes needed — all mandatory/editable flags already match BUD.")

    if skipped_unmatched:
        print(f"\nSkipped {len(skipped_unmatched)} fields not in 4.5.1 or 4.5.2 (kept as-is):")
        for s in skipped_unmatched:
            print(f"  [id={s['id']}] {s['field']!r} (panel={s['panel']!r}) "
                  f"mandatory={s['mandatory']} editable={s['editable']}")

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Fix mandatory+editable in API JSON using BUD sections 4.5.1/4.5.2 as source of truth."
    )
    parser.add_argument('--bud',    required=True, help='Path to BUD .docx file')
    parser.add_argument('--json',   required=True, help='Path to API-format JSON file to fix')
    parser.add_argument('--output', default=None,
                        help='Output path (default: overwrites --json in-place)')
    args = parser.parse_args()

    output_path = args.output if args.output else args.json

    init_lookup, spoc_lookup = build_bud_lookups(args.bud)
    fix_fields(args.json, init_lookup, spoc_lookup, output_path)


if __name__ == '__main__':
    main()
