#!/usr/bin/env python3
"""AIHubMix free-model re-snapshot (2026-11-08).

Reads the 2026-11-04 audit CSVs, fetches the live /v1/models catalog, then
rechecks only the models that previously had basic_pass=True.
Rate limit: one request per 6 s (10/min). 429/404 are recorded separately and
the 404 body is kept verbatim.
"""
import csv
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://aihubmix.com"
AUDIT = Path(r"opencode\aihubmix-free-audit")
OUT = Path(__file__).resolve().parent
RAW = OUT / "raw"


def get_key():
    key = os.environ.get("AIHUBMIX_API_KEY")
    if key:
        return key
    auth = Path(os.environ["USERPROFILE"]) / ".local" / "share" / "opencode" / "auth.json"
    with open(auth, encoding="utf-8") as f:
        return json.load(f)["aihubmix"]["key"]


KEY = get_key()


def request(path, payload=None, timeout=40):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return {"http": r.status, "body": body, "ms": round((time.time() - t0) * 1000, 1), "error": None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return {"http": e.code, "body": body, "ms": round((time.time() - t0) * 1000, 1), "error": body[:500]}
    except Exception as e:  # timeout, DNS, etc.
        return {"http": None, "body": None, "ms": round((time.time() - t0) * 1000, 1), "error": repr(e)}


# 1. live catalog
cat = request("/v1/models")
(RAW / "v1_models.json").write_text(cat["body"] or "", encoding="utf-8")
live_ids = set()
if cat["http"] == 200 and cat["body"]:
    try:
        live_ids = {m.get("id") for m in json.loads(cat["body"]).get("data", []) if m.get("id")}
    except ValueError:
        pass

old = list(csv.DictReader(open(AUDIT / "FREE_CATALOG_ALL.csv", encoding="utf-8-sig")))
old_ids = {r["model_id"] for r in old}
old_active = {r["model_id"] for r in old if r["catalog_status"].startswith("active")}
by_name_old = {r.get("display_name"): r["model_id"] for r in old if r.get("display_name")}

added = sorted(live_ids - old_ids)
removed_all = sorted(old_ids - live_ids)
removed_active = sorted(old_active - live_ids)
# name-based ID change candidates among ids that disappeared
renamed = []
live_names = {}
if cat["http"] == 200 and cat["body"]:
    try:
        for m in json.loads(cat["body"]).get("data", []):
            live_names[m.get("id")] = m.get("name") or m.get("id")
    except ValueError:
        pass
for mid in removed_active:
    nm = next((r.get("display_name") for r in old if r["model_id"] == mid), None)
    if nm:
        hit = next((lid for lid, ln in live_names.items() if ln == nm and lid not in old_ids), None)
        if hit:
            renamed.append({"old_id": mid, "new_id": hit, "display_name": nm})

catalog_diff = {
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "http_status": cat["http"],
    "live_model_count": len(live_ids),
    "old_catalog_rows": len(old),
    "old_active_rows": len(old_active),
    "added": added,
    "removed_vs_all_rows": removed_all,
    "removed_vs_active_rows": removed_active,
    "renamed_candidates": renamed,
}
(OUT / "catalog_diff.json").write_text(json.dumps(catalog_diff, ensure_ascii=False, indent=2), encoding="utf-8")

# 2. recheck only previous basic_pass=True models
matrix = list(csv.DictReader(open(AUDIT / "MODEL_COMPATIBILITY_MATRIX.csv", encoding="utf-8-sig")))
targets = [r["model_id"] for r in matrix if r.get("basic_pass") == "True"]
recheck = []
for i, mid in enumerate(targets):
    payload = {
        "model": mid,
        "messages": [{"role": "user", "content": "Reply with exactly OK."}],
        "max_tokens": 8,
        "stream": False,
    }
    r = request("/v1/chat/completions", payload)
    ok = r["http"] == 200
    content = None
    if ok:
        try:
            content = json.loads(r["body"])["choices"][0]["message"]["content"]
        except Exception:
            content = None
    row = {
        "model_id": mid,
        "http_status": r["http"],
        "ok": ok,
        "content": content,
        "error_body": None if ok else r["body"],
        "latency_ms": r["ms"],
        "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    recheck.append(row)
    (RAW / f"recheck_{mid.replace('/', '_')}.json").write_text(
        json.dumps({"request": payload, "response": r}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{i+1}/{len(targets)}] {mid} -> {r['http']}")
    if i + 1 < len(targets):
        time.sleep(6)

counts = {
    "recheck_total": len(recheck),
    "recheck_ok": sum(1 for r in recheck if r["ok"]),
    "recheck_404": sum(1 for r in recheck if r["http_status"] == 404),
    "recheck_429": sum(1 for r in recheck if r["http_status"] == 429),
    "recheck_other_error": sum(1 for r in recheck if not r["ok"] and r["http_status"] not in (404, 429)),
    "catalog_added": len(added),
    "catalog_removed_vs_all": len(removed_all),
    "catalog_removed_vs_active": len(removed_active),
}
(OUT / "recheck.json").write_text(json.dumps(recheck, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")

result = {
    "task": "aihubmix_snapshot",
    "run_dir": str(OUT),
    "catalog_added": len(added),
    "catalog_removed": len(removed_active),
    "recheck_ok": counts["recheck_ok"],
    "recheck_404": counts["recheck_404"],
    "recheck_429": counts["recheck_429"],
    "unverified": [],
    "notes": (
        "Diff base is the 2026-11-04 FREE_CATALOG_ALL.csv (72 rows; 32 already retired). "
        "catalog_removed counts only rows that were active on 11-04. "
        "Recheck targets were the 23 models with basic_pass=True; pace 6 s (10/min). "
        f"Live catalog HTTP {cat['http']}, {len(live_ids)} ids. "
        f"removed_vs_all={len(removed_all)}, removed_vs_active={len(removed_active)}, renamed_candidates={len(renamed)}."
    ),
}
(OUT / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
