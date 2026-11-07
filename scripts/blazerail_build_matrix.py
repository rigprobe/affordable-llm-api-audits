#!/usr/bin/env python3
"""BlazeRail free-model feature matrix re-measurement (2026-11-08).

Scope: only models whose 2026-11-07 basic run returned HTTP 200.
Features: tool_calling (add 19+23 with continuation), streaming (>=2 content
deltas), agent (OpenCode 1.18.18 completes an isolated repo task).

429 handling: exponential backoff 2/4/8/16 s, max 4 retries; final 429 is
recorded as rate_limited and never mixed with fail. The API key is read from
opencode auth.json and is never written to artifacts.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.blazerail.com/v1"
RUN = Path(__file__).resolve().parent
RAW = RUN / "raw"
REPOS = RUN / "agent-repos"
PRIOR = Path(r"opencode\blazerail-verification\runs\20261107-004121")
OUT = RUN
BACKOFF = [2, 4, 8, 16]


def get_key():
    key = os.environ.get("BLAZERAIL_API_KEY")
    if key:
        return key
    auth = Path(os.environ["USERPROFILE"]) / ".local" / "share" / "opencode" / "auth.json"
    with open(auth, encoding="utf-8") as f:
        return json.load(f)["blazerail"]["key"]


KEY = get_key()


def post(payload, timeout=60, stream=False):
    req = urllib.request.Request(BASE + "/chat/completions",
                                 data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + KEY)
    req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if stream:
                lines = []
                for raw in r:
                    lines.append(raw.decode("utf-8", "replace"))
                return {"http": r.status, "lines": lines, "ms": round((time.time() - t0) * 1000, 1), "error": None}
            body = r.read().decode("utf-8", "replace")
            return {"http": r.status, "body": body, "ms": round((time.time() - t0) * 1000, 1), "error": None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return {"http": e.code, "body": body, "ms": round((time.time() - t0) * 1000, 1), "error": body[:800]}
    except Exception as e:
        return {"http": None, "body": None, "ms": round((time.time() - t0) * 1000, 1), "error": repr(e)}


def with_backoff(fn):
    """Run fn(); retry only on HTTP 429 or agent output containing 429."""
    attempts = 0
    delays = []
    while True:
        r = fn()
        status = r.get("http")
        agent_429 = r.get("agent_429", False)
        if status == 429 or agent_429:
            if attempts < len(BACKOFF):
                delay = BACKOFF[attempts]
                delays.append(delay)
                attempts += 1
                time.sleep(delay)
                continue
            r["rate_limited"] = True
            r["retry_delays_s"] = delays
            return r
        r["rate_limited"] = False
        r["retry_delays_s"] = delays
        return r


# ---- target list: previous basic HTTP 200 only ----
basic = json.load(open(PRIOR / "basic-results.json", encoding="utf-8"))
targets = [{"model": r["model"], "label": r.get("label")} for r in basic if r.get("http_status") == 200]
print(f"targets={len(targets)}")

# ---- OpenCode agent config for all targets ----
models_cfg = {}
for t in targets:
    models_cfg[t["model"]] = {
        "name": t["label"] + " (free)",
        "tool_call": True,
        "reasoning": False,
        "limit": {"context": 200000, "output": 32768},
    }
cfg = {
    "$schema": "https://opencode.ai/config.json",
    "model": f"blazerail/{targets[0]['model']}",
    "small_model": f"blazerail/{targets[0]['model']}",
    "autoupdate": False,
    "permission": {
        "edit": "allow", "bash": "allow", "read": "allow", "grep": "allow",
        "glob": "allow", "list": "allow", "webfetch": "deny",
        "external_directory": "deny",
    },
    "provider": {
        "blazerail": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "BlazeRail Free Audit",
            "options": {"baseURL": BASE},
            "models": models_cfg,
        }
    },
}
CFG_PATH = RUN / "opencode.agentmatrix.jsonc"
CFG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_integers",
        "description": "Add two integer numbers and return the arithmetic sum.",
        "parameters": {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    },
}


def test_tool(mid):
    def once():
        payload = {
            "model": mid,
            "messages": [{"role": "user", "content": "Use the add_integers tool to calculate 19 + 23. Then report the result."}],
            "tools": [TOOL_DEF],
            "tool_choice": "auto",
            "max_tokens": 256,
        }
        r = post(payload)
        out = {"http": r["http"], "ms": r["ms"], "error": r["error"]}
        if r["http"] != 200:
            return out
        try:
            msg = json.loads(r["body"])["choices"][0]["message"]
        except Exception as e:
            out.update({"ok": False, "reason": f"parse: {e}"})
            return out
        calls = msg.get("tool_calls") or []
        out["tool_call_count"] = len(calls)
        out["tool_name"] = calls[0]["function"]["name"] if calls else None
        out["arguments"] = calls[0]["function"]["arguments"] if calls else None
        args_ok = False
        if calls:
            try:
                a = json.loads(calls[0]["function"]["arguments"])
                args_ok = a.get("a") == 19 and a.get("b") == 23
            except Exception:
                args_ok = False
        out["args_ok"] = args_ok
        if not calls or not args_ok:
            out["ok"] = False
            return out
        # continuation with the tool result
        cont_msgs = [
            {"role": "user", "content": "Use the add_integers tool to calculate 19 + 23. Then report the result."},
            {"role": "assistant", "content": msg.get("content"), "tool_calls": calls},
            {"role": "tool", "tool_call_id": calls[0].get("id"), "content": "42"},
        ]
        r2 = post({"model": mid, "messages": cont_msgs, "max_tokens": 128})
        out["continuation_http"] = r2["http"]
        if r2["http"] != 200:
            out["ok"] = False
            return out
        try:
            cont = json.loads(r2["body"])["choices"][0]["message"].get("content") or ""
        except Exception:
            cont = ""
        out["continuation_excerpt"] = cont[:200]
        out["followup_ok"] = "42" in cont
        out["ok"] = bool(out["followup_ok"])
        return out
    return with_backoff(once)


def test_stream(mid):
    def once():
        payload = {
            "model": mid,
            "messages": [{"role": "user", "content": "Write one short sentence about the number 42."}],
            "max_tokens": 64,
            "stream": True,
        }
        r = post(payload, stream=True, timeout=60)
        out = {"http": r["http"], "ms": r["ms"], "error": r["error"]}
        if r["http"] != 200:
            return out
        deltas = 0
        excerpt = ""
        finish = None
        for line in r["lines"]:
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            try:
                ev = json.loads(data)
                ch = ev.get("choices") or []
                if ch:
                    d = ch[0].get("delta") or {}
                    c = d.get("content")
                    if isinstance(c, str) and c:
                        deltas += 1
                        excerpt += c
                    if ch[0].get("finish_reason"):
                        finish = ch[0]["finish_reason"]
            except Exception:
                pass
        out.update({"content_deltas": deltas, "content_excerpt": excerpt[:200], "finish_reason": finish})
        out["ok"] = deltas >= 2
        return out
    return with_backoff(once)


AGENT_PROMPT = (
    "In this repository, create math.js that exports a function add(a, b) returning a + b. "
    "Create test.js that requires ./math and prints add(19, 23). "
    "Run `node test.js` and report the printed result. Do not modify anything else."
)


def test_agent(mid):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", mid)
    repo = REPOS / safe

    def once():
        if repo.exists():
            shutil.rmtree(repo)
        repo.mkdir(parents=True)
        (repo / "README_TASK.md").write_text(
            "Create math.js exporting add(a,b) and test.js printing add(19,23). "
            "Run node test.js.\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=repo, capture_output=True)
        env = os.environ.copy()
        env["OPENCODE_CONFIG"] = str(CFG_PATH)
        env["OPENCODE_AUTO_SHARE"] = "false"
        cmd = ["opencode", "run", "--format", "json", "--model", f"blazerail/{mid}",
               "--auto", "--title", "blazerail-agent-matrix", AGENT_PROMPT]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
            code, stdout, stderr = p.returncode, p.stdout, p.stderr
            timed_out = False
        except subprocess.TimeoutExpired as e:
            code, stdout, stderr, timed_out = 124, (e.stdout or ""), (e.stderr or ""), True
        ms = round((time.time() - t0) * 1000, 1)
        (RAW / f"agent_{safe}.jsonl").write_text(stdout or "", encoding="utf-8")
        (RAW / f"agent_{safe}.stderr.txt").write_text(stderr or "", encoding="utf-8")
        node_out, node_ok = "", False
        if (repo / "test.js").exists():
            try:
                np = subprocess.run(["node", "test.js"], cwd=repo, capture_output=True, text=True,
                                    timeout=20, encoding="utf-8", errors="replace")
                node_out = (np.stdout or "").strip()
                node_ok = np.returncode == 0 and node_out.replace("\n", "").strip() == "42"
            except Exception as e:
                node_out = repr(e)
        agent_429 = ("429" in (stdout or "") or "429" in (stderr or "")) and code != 0
        out = {
            "http": 429 if agent_429 else 200,
            "agent_429": agent_429,
            "exit_code": code,
            "timed_out": timed_out,
            "ms": ms,
            "math_js": (repo / "math.js").exists(),
            "test_js": (repo / "test.js").exists(),
            "node_output": node_out,
            "ok": (code == 0) and (not timed_out) and node_ok,
            "error_excerpt": (stderr or "")[-400:] if code != 0 else None,
        }
        return out
    return with_backoff(once)


matrix = []
counts = {k: {"ok": 0, "fail": 0, "rate_limited": 0, "timeout": 0} for k in ("basic", "tool", "stream", "agent")}
counts["basic"]["ok"] = len(targets)

for idx, t in enumerate(targets):
    mid, label = t["model"], t["label"]
    print(f"[{idx+1}/{len(targets)}] {label} ({mid})")
    tool_r = test_tool(mid)
    stream_r = test_stream(mid)
    agent_r = test_agent(mid)

    def state(r):
        if r.get("rate_limited"):
            return "rate_limited"
        if r.get("timed_out") or r.get("http") is None:
            return "timeout"
        return "ok" if r.get("ok") else "fail"

    row = {
        "model_id": mid,
        "label": label,
        "basic": "ok",
        "tool": state(tool_r),
        "stream": state(stream_r),
        "agent": state(agent_r),
        "tool_detail": tool_r,
        "stream_detail": stream_r,
        "agent_detail": agent_r,
    }
    matrix.append(row)
    for k in ("tool", "stream", "agent"):
        counts[k][row[k]] += 1
    (OUT / "matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    tool={row['tool']} stream={row['stream']} agent={row['agent']}")
    if idx + 1 < len(targets):
        time.sleep(12)

result = {
    "task": "blazerail_matrix",
    "run_dir": str(RUN),
    "tested_models": len(matrix),
    "counts": counts,
    "unverified": [],
    "notes": ("429 backoff 2/4/8/16 s, max 4 retries; final 429 recorded as rate_limited. "
              "12 s between models. Agent = OpenCode 1.18.18, isolated git repo, verified with node test.js. "
              "Basic values reused from runs/20261107-004121/basic-results.json (HTTP 200 subset)."),
}
(OUT / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
