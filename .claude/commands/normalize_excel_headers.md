---
name: Normalize Excel Headers
allowed-tools: Bash, Read
description: Uppercase the header row of every .xlsx in a folder and replace spaces with underscores, preserving all other data.
argument-hint: <path-to-folder-or-xlsx>
---

# Normalize Excel Headers

## Input

`$ARGUMENTS` — path to a folder containing `.xlsx` files, or a single `.xlsx` file.

If `$ARGUMENTS` is empty, ask the user for the path and stop.

## Objective

For every `.xlsx` file at the input path (recurse one level into the folder, non-recursive into subfolders), transform **only the header row** (row 1) of every sheet:

1. Convert all text to **UPPERCASE**.
2. Replace **every whitespace run** (spaces, tabs) with a single underscore `_`.
3. Strip leading/trailing whitespace before replacement.

All non-header rows, formulas, formatting, merged cells, and sheet structure must be preserved. Files are modified **in place**.

## Hard Constraints

* Do **not** touch any row except row 1.
* Do **not** create new files or copies; overwrite the originals.
* Skip files that start with `~$` (Excel lockfiles).
* Do **not** process `.xls`, `.csv`, or any non-`.xlsx` file.
* If a cell in row 1 is empty or non-string, leave it as-is.

## Procedure

Run this one-shot Python via `Bash`. Do not write a persistent script.

```bash
python3 - "$ARGUMENTS" <<'PY'
import sys, os, re
from pathlib import Path
from openpyxl import load_workbook

target = Path(sys.argv[1]).expanduser()
if not target.exists():
    sys.exit(f"Path not found: {target}")

if target.is_file():
    files = [target] if target.suffix.lower() == ".xlsx" else []
else:
    files = sorted(p for p in target.iterdir()
                   if p.is_file() and p.suffix.lower() == ".xlsx"
                   and not p.name.startswith("~$"))

if not files:
    sys.exit("No .xlsx files found.")

ws_re = re.compile(r"\s+")
for f in files:
    wb = load_workbook(f)
    changed = 0
    for ws in wb.worksheets:
        for cell in ws[1]:
            v = cell.value
            if isinstance(v, str) and v.strip():
                new = ws_re.sub("_", v.strip()).upper()
                if new != v:
                    cell.value = new
                    changed += 1
    wb.save(f)
    print(f"{f.name}: {changed} header cell(s) updated")
PY
```

## Report

After the run, print a short summary: number of files processed and total header cells changed. Do not show full file contents.
