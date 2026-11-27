#!/usr/bin/env python3
"""Measure every case: run run.py on it and save what it expects, what it got, and the numbers behind it.

Usage, from the repo root:
    python measure.py                     # all cases, in case order
    python measure.py blur.sharpness      # sorted by a column (highest first)

Prints a table and saves it twice: measurements.txt and measurements.csv
bb conform says pass/fail; this shows *why*, for choosing thresholds.
"""
import csv
import glob
import json
import os
import subprocess
import sys
from datetime import datetime

# Which policy threshold belongs to which measured number, shown side by side.
# When a new check is added (e.g. dark/bright), add its number and threshold here.
THRESHOLDS = {
    "blur.sharpness": "blur_min_sharpness",
    "glare.largest_blob_share": "glare_min_blob_share",
}

OUT = "measurements.csv"
OUT_TXT = "measurements.txt"


def flatten(args, prefix=""):
    """{"blur": {"sharpness": 5}} -> {"blur.sharpness": 5}"""
    flat = {}
    for key, value in args.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, name + "."))
        else:
            flat[name] = value
    return flat


def run_case(case, policy):
    request = json.dumps({"input": case["input"], "policy": policy})
    result = subprocess.run([sys.executable, "run.py"], input=request,
                            capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr.strip().splitlines()[-1]
    return json.loads(result.stdout), None


def main():
    with open("policy.json", encoding="utf-8") as f:
        policy = json.load(f)

    rows = []
    for path in sorted(glob.glob(os.path.join("cases", "*.json"))):
        with open(path, encoding="utf-8") as f:
            case = json.load(f)
        answer, error = run_case(case, policy)
        expected = case["expect"].get("code")
        row = {"case": case["name"], "expected": expected or "ok"}
        if error:
            row.update({"got": "ERROR", "match": "ERROR", "error": error})
        else:
            got = answer["code"]
            row.update({"got": got or "ok", "match": "yes" if got == expected else "NO"})
            for name, value in flatten(answer["args"]).items():
                row[name] = value
                if name in THRESHOLDS:
                    row[f"{name} limit"] = policy.get(THRESHOLDS[name])
        rows.append(row)

    if len(sys.argv) > 1:
        col = sys.argv[1]
        rows.sort(key=lambda r: r.get(col, float("-inf")), reverse=True)

    # Every column that appears in any row, in first-seen order
    columns = []
    for row in rows:
        columns += [c for c in row if c not in columns]

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    # Same data as an aligned table: text left-aligned, numbers right-aligned, easy to read in an editor
    # Numbers in one column get the same number of decimals, so the decimal points line up
    def decimals(value):
        text = str(value)
        return len(text.split(".")[1]) if isinstance(value, float) and "." in text else 0

    places = {c: max(decimals(r.get(c)) for r in rows) for c in columns}

    def text(value, c):
        if isinstance(value, float):
            return f"{value:.{places[c]}f}"
        return "" if value is None else str(value)

    widths = {c: max(len(c), *(len(text(r.get(c), c)) for r in rows)) for c in columns}
    lines = ["  ".join(c.ljust(widths[c]) for c in columns),
             "  ".join("-" * widths[c] for c in columns)]
    for row in rows:
        cells = []
        for c in columns:
            value = row.get(c)
            is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
            cells.append(text(value, c).rjust(widths[c]) if is_number else text(value, c).ljust(widths[c]))
        lines.append("  ".join(cells).rstrip())

    wrong = sum(r["match"] != "yes" for r in rows)
    summary = f"{len(rows)} cases, {len(rows) - wrong} as expected, {wrong} not."
    # Header: when this was measured and with which settings, so an outdated file is easy to spot
    header = [f"Measured {datetime.now():%Y-%m-%d %H:%M} with policy.json:",
              *(f"  {key} = {json.dumps(value)}" for key, value in policy.items()),
              "If cases, policy.json or run.py change, run measure.py again to update this file.",
              ""]
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(header + lines) + "\n\n" + summary + "\n")

    print("\n".join(lines))
    print(f"\n{summary} Saved to {OUT_TXT} (to read) and {OUT} (for Excel)")


if __name__ == "__main__":
    main()
