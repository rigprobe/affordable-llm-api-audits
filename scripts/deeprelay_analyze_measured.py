#!/usr/bin/env python3
"""Post-process the DeepRelay measured runs.

Adds cache-read accounting: the billing weighted-input delta equals
(tokens_input + tokens_cache_read) x plan factor in every run checked, i.e.
cached prompt tokens are counted at full weight. This explains why the measured
per-task weighted input is far above the 4,000-token theoretical assumption.
"""
import csv
import json
import math
from pathlib import Path

OUT = Path(r"opencode\deeprelay-measured-20261108-012923")
rows = list(csv.DictReader(open(OUT / "measured.csv", encoding="utf-8-sig")))

for r in rows:
    csvp = Path(r["run_dir"]) / "results.csv"
    cache = None
    if csvp.exists():
        rr = list(csv.DictReader(open(csvp, encoding="utf-8-sig")))[0]
        v = rr.get("tokens_cache_read")
        cache = int(v) if v not in (None, "", "None") else None
    r["raw_tokens_cache_read"] = cache
    ti = r.get("raw_tokens_input")
    factor = float(r["factor"])
    if ti not in (None, "") and cache is not None:
        expected = (int(ti) + cache) * factor
        r["weighted_input_from_components"] = round(expected, 1)
        actual = r.get("billing_weighted_input_delta")
        r["component_match"] = bool(actual not in (None, "") and abs(float(actual) - expected) <= max(50, expected * 0.01))
    else:
        r["weighted_input_from_components"] = None
        r["component_match"] = None

with open(OUT / "measured.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

measured = json.load(open(OUT / "measured.json", encoding="utf-8"))
measured["runs"] = rows


def pct(vals, p):
    vals = sorted(vals)
    i = (len(vals) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (i - lo), 2)


for mid in measured["per_model"]:
    sub = [r for r in rows if r["model"] == mid]
    cache = [r["raw_tokens_cache_read"] for r in sub if r["raw_tokens_cache_read"] is not None]
    ratios = []
    for r in sub:
        if r.get("billing_weighted_input_delta") and r.get("raw_tokens_input"):
            ratios.append(float(r["billing_weighted_input_delta"]) / float(r["raw_tokens_input"]))
    measured["per_model"][mid]["cache_read_median"] = pct(cache, 0.5)
    measured["per_model"][mid]["billing_over_raw_input_median"] = pct(ratios, 0.5)
    measured["per_model"][mid]["theory_gap_factor"] = (
        round((measured["per_model"][mid]["weighted_in_median"] or 0) / 4000, 2))

measured["analysis"] = {
    "note": "Billing weighted input = (input + cache_read) x factor. Cached prompt tokens are counted at full weight.",
    "all_components_match": all(r.get("component_match") for r in rows),
    "runs_checked": len(rows),
}
(OUT / "measured.json").write_text(json.dumps(measured, ensure_ascii=False, indent=2), encoding="utf-8")

res = json.load(open(OUT / "RESULT.json", encoding="utf-8"))
res["notes"] += (" Weighted input is measured as the billing subscription delta; it equals "
                 "(OpenCode input + cache_read) x plan factor, so cached prompt tokens are counted at full weight. "
                 "The 4,000-token theory understates one real task by roughly the reported theory_gap_factor.")
(OUT / "RESULT.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(measured["analysis"], ensure_ascii=False, indent=2))
print(json.dumps({k: v.get("theory_gap_factor") for k, v in measured["per_model"].items()}, ensure_ascii=False, indent=2))
