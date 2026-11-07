#!/usr/bin/env python3
"""DeepRelay measured benchmark: 3 tasks x 3 repeats x 2 models = 18 runs.

Uses the existing benchmark.py (OpenCode 1.18.18, v1 config) and the
BILLING_CHECK.json method: GET /v1/billing/subscription before/after each run,
then the weighted-token delta is the measured consumption. No key is written.
"""
import csv
import json
import math
import os
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"opencode")
BENCH = ROOT / "deeprelay_opencode_benchmark_2026-11-03" / "deeprelay_opencode_benchmark"
OUT = ROOT / "deeprelay-measured-20261108-012923"
RUNS = OUT / "runs"
RAW = OUT / "raw"
BASE = "https://api.deeprelay.ai/v1"

MODELS = [
    ("deepseek-v4.1-flash", "deeprelay/deeprelay/deepseek-v4.1-flash", 1.0),
    ("glm-5.3-flash", "deeprelay/deeprelay/glm-5.3-flash", 1.75),
]
CASES = ["invoice", "rate_limiter", "config_merge"]
REPEATS = 3


def key():
    return os.environ["DEEPRELAY_API_KEY"]


def billing():
    req = urllib.request.Request(BASE + "/billing/subscription")
    req.add_header("Authorization", "Bearer " + key())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def snapshot():
    j = billing()
    u = j.get("usage") or {}
    return {
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "subscribed": j.get("subscribed"),
        "status": j.get("status"),
        "plan": (j.get("plan") or {}).get("key"),
        "weighted_input_tokens": u.get("weighted_input_tokens"),
        "weighted_output_tokens": u.get("weighted_output_tokens"),
        "weekly_weighted_input_tokens": u.get("weekly_weighted_input_tokens"),
        "weekly_weighted_output_tokens": u.get("weekly_weighted_output_tokens"),
        "cost_micro_cents": u.get("cost_micro_cents"),
        "recent_payg_calls_24h": u.get("recent_payg_calls_24h"),
    }


def percentile(vals, pct):
    if not vals:
        return None
    vals = sorted(vals)
    i = (len(vals) - 1) * pct
    lo, hi = math.floor(i), math.ceil(i)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (i - lo), 2)


before_all = snapshot()
(RAW / "billing_before_all.json").write_text(json.dumps(before_all, indent=2), encoding="utf-8")

rows = []
for mid, ocid, factor in MODELS:
    for case in CASES:
        for rep in range(1, REPEATS + 1):
            tag = f"{mid}_{case}_rep{rep}"
            outdir = RUNS / tag
            b0 = snapshot()
            (RAW / f"{tag}_billing_before.json").write_text(json.dumps(b0, indent=2), encoding="utf-8")
            cmd = [sys.executable, str(BENCH / "benchmark.py"), "--mode", "v1",
                   "--cases", case, "--repeats", "1", "--max-runs", "1",
                   "--models", ocid, "--output", str(outdir), "--timeout", "240"]
            t0 = time.time()
            print(f"[{len(rows)+1}/18] {tag} ...", flush=True)
            p = subprocess.run(cmd, cwd=BENCH, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=900)
            wall = round(time.time() - t0, 1)
            (RAW / f"{tag}_benchmark.log").write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8")
            b1 = snapshot()
            if (b1["weighted_input_tokens"] or 0) == (b0["weighted_input_tokens"] or 0):
                time.sleep(5)
                b1 = snapshot()
            (RAW / f"{tag}_billing_after.json").write_text(json.dumps(b1, indent=2), encoding="utf-8")
            rc = p.returncode
            result = None
            csvp = outdir / "results.csv"
            if csvp.exists():
                result = list(csv.DictReader(open(csvp, encoding="utf-8-sig")))[0]
            wi = (b1["weighted_input_tokens"] or 0) - (b0["weighted_input_tokens"] or 0)
            wo = (b1["weighted_output_tokens"] or 0) - (b0["weighted_output_tokens"] or 0)
            raw_in = int(result["tokens_input"]) if result and result.get("tokens_input") not in (None, "", "None") else None
            raw_out = int(result["tokens_output"]) if result and result.get("tokens_output") not in (None, "", "None") else None
            rows.append({
                "model": mid,
                "task": case,
                "rep": rep,
                "benchmark_exit": rc,
                "passed": (result or {}).get("passed"),
                "elapsed_s": (result or {}).get("elapsed_s"),
                "wall_s": wall,
                "tests_run": (result or {}).get("tests_run"),
                "raw_tokens_input": raw_in,
                "raw_tokens_output": raw_out,
                "billing_weighted_input_before": b0["weighted_input_tokens"],
                "billing_weighted_input_after": b1["weighted_input_tokens"],
                "billing_weighted_input_delta": wi,
                "billing_weighted_output_delta": wo,
                "billing_cost_micro_cents_delta": (b1["cost_micro_cents"] or 0) - (b0["cost_micro_cents"] or 0),
                "payg_calls_24h_after": b1["recent_payg_calls_24h"],
                "factor": factor,
                "weighted_input_estimated": round(raw_in * factor, 1) if raw_in is not None else None,
                "run_dir": str(outdir),
            })
            with open(OUT / "measured.csv", "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            print(f"    exit={rc} pass={rows[-1]['passed']} elapsed={rows[-1]['elapsed_s']} "
                  f"raw_in={raw_in} weighted_delta={wi}", flush=True)

after_all = snapshot()
(RAW / "billing_after_all.json").write_text(json.dumps(after_all, indent=2), encoding="utf-8")

per_model = {}
for mid, _, factor in MODELS:
    sub = [r for r in rows if r["model"] == mid]
    passed = sum(1 for r in sub if str(r["passed"]).lower() == "true")
    elapsed = [float(r["elapsed_s"]) for r in sub if r["elapsed_s"] not in (None, "", "None")]
    # measured weighted input: prefer billing delta, fall back to raw x factor
    weighted = []
    for r in sub:
        if r["billing_weighted_input_delta"] and r["billing_weighted_input_delta"] > 0:
            weighted.append(float(r["billing_weighted_input_delta"]))
        elif r["weighted_input_estimated"]:
            weighted.append(float(r["weighted_input_estimated"]))
    raw_inputs = [r["raw_tokens_input"] for r in sub if r["raw_tokens_input"]]
    per_model[mid] = {
        "pass": f"{passed}/{len(sub)}",
        "median_s": percentile(elapsed, 0.5),
        "p95_s": percentile(elapsed, 0.95),
        "weighted_in_median": percentile(weighted, 0.5),
        "weighted_in_source": "billing delta per run" if all(
            r["billing_weighted_input_delta"] for r in sub) else "billing delta where >0, else raw x factor",
        "raw_in_median": percentile(raw_inputs, 0.5),
        "per_task_weighted_in": round(sum(weighted) / len(weighted), 1) if weighted else None,
        "factor": factor,
    }

batch_delta_in = (after_all["weighted_input_tokens"] or 0) - (before_all["weighted_input_tokens"] or 0)
batch_delta_out = (after_all["weighted_output_tokens"] or 0) - (before_all["weighted_output_tokens"] or 0)
batch_cost = (after_all["cost_micro_cents"] or 0) - (before_all["cost_micro_cents"] or 0)
payg = any((r["payg_calls_24h_after"] or 0) > 0 for r in rows)

measured = {
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "runs": rows,
    "per_model": per_model,
    "batch_billing": {
        "before": before_all,
        "after": after_all,
        "weighted_input_delta": batch_delta_in,
        "weighted_output_delta": batch_delta_out,
        "cost_micro_cents_delta": batch_cost,
    },
    "theory": {"task_input_tokens": 4000, "task_output_tokens": 1000},
}
(OUT / "measured.json").write_text(json.dumps(measured, ensure_ascii=False, indent=2), encoding="utf-8")

result = {
    "task": "deeprelay_measured",
    "run_dir": str(OUT),
    "per_model": per_model,
    "unverified": [] if not payg else ["PAYG calls detected; see measured.csv"],
    "notes": (
        f"18 runs (3 tasks x 3 repeats x 2 models). Billing delta over the batch: "
        f"weighted_input={batch_delta_in}, weighted_output={batch_delta_out}, "
        f"cost_micro_cents={batch_cost}, PAYG calls={payg}. "
        "Theory assumes 4,000 input / 1,000 output per task. "
        "OpenCode token counters are best-effort; billing counters are authoritative."
    ),
}
(OUT / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
