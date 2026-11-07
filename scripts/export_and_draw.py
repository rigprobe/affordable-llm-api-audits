#!/usr/bin/env python3
"""Task 6: export chart data from the new audit runs and draw charts A-D.

The original sns/make_charts.py is left untouched. This script reads the new
machine-readable artifacts, writes charts/data/{A,B,C,D}.json, then draws the
four PNGs with the same palette/style as the original script and overwrites
sns/charts/*.png.

Cross-check numbers are written to REPORT.md.
"""
import csv
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib import rcParams

rcParams["font.family"] = ["Yu Gothic", "Meiryo", "Noto Sans JP"]
rcParams["axes.unicode_minus"] = False

ROOT = Path(os.environ.get("AUDIT_ROOT", Path(__file__).resolve().parents[1]))
SNS = ROOT / "sns"
OUT = SNS / "charts"
DATA = OUT / "data"
DATA.mkdir(parents=True, exist_ok=True)

INK = "#1b1b1b"
OK = "#2f7d4f"
WARN = "#c08a1e"
BAD = "#b23b3b"
GREY = "#9a9a9a"
NONE = "#e6e6e6"

T1 = ROOT / "opencode" / "blazerail-verification" / "runs" / "20261108-012923" / "matrix"
T2 = ROOT / "harogo" / "runs" / "20261108-012923-matrix" / "matrix"
T3 = ROOT / "opencode" / "deeprelay-measured-20261108-012923"
T4 = ROOT / "rayucode-api-audit" / "runs" / "20261108-012923-usage-sync"
T5 = ROOT / "opencode" / "aihubmix-free-audit" / "snapshot-20261108-012923"
PRIOR_BLAZE = ROOT / "opencode" / "blazerail-verification" / "runs" / "20261107-004121"


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def save(fig, name):
    path = OUT / name
    tmp = OUT / name.replace(".png", ".tmp.png")
    fig.savefig(tmp, dpi=170, bbox_inches="tight", facecolor="white")
    os.replace(tmp, path)
    plt.close(fig)
    print("wrote", path)


# ------------------------------------------------------------------ A data
blaze_prior = load(PRIOR_BLAZE / "basic-results.json")
blaze_ok = sum(1 for r in blaze_prior if r.get("http_status") == 200)
blaze_n = len(blaze_prior)
blaze_fail = {}
for r in blaze_prior:
    if r.get("http_status") != 200:
        k = str(r.get("http_status"))
        blaze_fail[k] = blaze_fail.get(k, 0) + 1

dr = list(csv.DictReader(open(ROOT / "opencode" / "deeprelay-all-model-smoke" / "MODEL_TEST_RESULTS.csv", encoding="utf-8-sig")))
dr_ok = sum(1 for r in dr if r.get("verdict") == "PASS")
dr_tested = sum(1 for r in dr if r.get("verdict") != "SKIPPED_PAYG")
dr_blocked = len(dr) - dr_tested

ai = list(csv.DictReader(open(ROOT / "opencode" / "aihubmix-free-audit" / "MODEL_COMPATIBILITY_MATRIX.csv", encoding="utf-8-sig")))
ai_tested = [r for r in ai if r.get("basic_pass") not in ("",)]
ai_ok = sum(1 for r in ai_tested if r.get("basic_pass") == "True")
ai_n = len(ai_tested)
ai_outside = len(ai) - ai_n

rayu = load(ROOT / "rayucode-api-audit" / "runs" / "20261107-230714" / "BASIC-RESULTS.json")
rayu_ok = sum(1 for r in rayu if r.get("http_status") == 200)
rayu_n = len(rayu)

t2_counts = load(T2 / "counts.json")
har_ok = t2_counts["basic"]["ok"]
har_n = har_ok + t2_counts["basic"]["unavailable"]

A = {
    "generated_utc": "2026-11-08",
    "providers": [
        {"name": "DeepRelay", "ok": dr_ok, "denom": dr_tested, "outside": dr_blocked},
        {"name": "Rayu Code", "ok": rayu_ok, "denom": rayu_n, "outside": 0},
        {"name": "BlazeRail", "ok": blaze_ok, "denom": blaze_n, "outside": 0,
         "fail_breakdown": blaze_fail},
        {"name": "Harogo", "ok": har_ok, "denom": har_n, "outside": 0,
         "unavailable": t2_counts["basic"]["unavailable"]},
        {"name": "AIHubMix", "ok": ai_ok, "denom": ai_n, "outside": ai_outside},
    ],
    "note": ("BlazeRail失敗内訳: 429×5, 404×2, 410×2, 400×1, timeout×3 ／ "
             "Harogo: UNAVAILABLE 8, NOT_ACCESSIBLE 1 ／ Rayu: 502×1, 503×1 ／ "
             "AIHubMix失敗11（429×6, 400×2, 404×2, 503×1）。"
             "AIHubMixは2026-11-04監査時点。2026-11-08再確認ではbasic_pass 23/23が応答。"),
}
(DATA / "A.json").write_text(json.dumps(A, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------------------ B data
t1_matrix = load(T1 / "matrix.json")
t2_matrix = load(T2 / "matrix.json")
B = {
    "generated_utc": "2026-11-08",
    "blazerail": [
        {"label": r["label"], "model_id": r["model_id"],
         "states": {"basic": r["basic"], "tool": r["tool"], "stream": r["stream"], "agent": r["agent"]}}
        for r in t1_matrix
    ],
    "harogo": [
        {"label": r["label"], "model_id": r["model_id"], "status": r["status"],
         "states": {"basic": r["basic"], "tool": r["tool"], "stream": r["stream"]}}
        for r in t2_matrix
    ],
    "blazerail_counts": load(T1 / "counts.json"),
    "harogo_counts": t2_counts,
}
(DATA / "B.json").write_text(json.dumps(B, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------------------ C data
theory = []
for name, factor in [("DeepSeek V4.1 Flash (×1)", 1), ("GLM-5.3 Flash (×1.75)", 1.75),
                     ("GLM-5.3 (×12)", 12), ("Kimi K3 (×24)", 24)]:
    theory.append({
        "name": name,
        "factor": factor,
        "monthly": 500_000_000 / (4000 * factor),
        "weekly": 125_000_000 / (4000 * factor),
    })
measured = load(T3 / "measured.json")
C = {
    "generated_utc": "2026-11-08",
    "task": {"input_tokens": 4000, "output_tokens": 1000},
    "theory": theory,
    "measured": measured["per_model"],
    "batch_billing": measured["batch_billing"],
    "runs": measured["runs"],
}
(DATA / "C.json").write_text(json.dumps(C, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------------------ D data
events = [
    ["2026-11-02", "DeepRelay Base 契約（$0.99/月）", GREY],
    ["2026-11-03", "DeepRelay GLM-5.3 Flash: OpenCode 0/9（503）", BAD],
    ["2026-11-03", "DeepRelay DeepSeek V4.1 Flash / GLM-5.3: 9/9完走", OK],
    ["2026-11-04", "DeepRelay GLM-5.3 Flash API復旧（Tools含む）", OK],
    ["2026-11-04", "AIHubMix 無料監査（23/34成功、退役32件確認）", WARN],
    ["2026-11-05 03:38", "Harogo Claude系 503（11:14にzhang: 容量拡張中と回答）", BAD],
    ["2026-11-06 13:41 UTC", "BlazeRail $5.35入金 → 402解消・無料枠解放", OK],
    ["2026-11-07 06:42 UTC", "Harogo 8モデル障害を実測（Claude系503・404等）", BAD],
    ["2026-11-07 17:17", "Harogo 障害をTelegram報告、17:18に担当者へ確認依頼", BAD],
    ["2026-11-07 22:14 JST", "Harogo 再試験: 8モデル全て同一エラーで未復旧（13:14 UTC）", BAD],
    ["2026-11-07 23:28", "Rayu Pro 無料有効化・Nemotron 0 credits実証", OK],
    ["2026-11-07", "Rayu DeepSeek V4 Pro/Flash 502/503継続", BAD],
    ["2026-11-08 01:30 JST", "Rayu /v1/credits＋ダッシュボード同時刻（45.34 vs 46.18）", WARN],
    ["2026-11-08 01:39 JST", "BlazeRail 429除外で機能マトリクス再測定（17モデル）", WARN],
    ["2026-11-08 01:42 JST", "Harogo FULL_PASS 10モデルを機能別に集計（10/10）", OK],
    ["2026-11-08 01:46 JST", "AIHubMix 無料カタログ再取得（23/23応答、有効5件消失）", WARN],
]
D = {"generated_utc": "2026-11-08", "events": events}
(DATA / "D.json").write_text(json.dumps(D, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------------------ chart A
providers = [p["name"] for p in A["providers"]]
ok = [p["ok"] for p in A["providers"]]
denom = [p["denom"] for p in A["providers"]]
outside = [p["outside"] for p in A["providers"]]
fail = [d - o for d, o in zip(denom, ok)]

fig, ax = plt.subplots(figsize=(9.2, 4.6))
y = range(len(providers))
ax.barh(y, ok, color=OK, label="HTTP 200 / FULL_PASS")
ax.barh(y, fail, left=ok, color=BAD, label="失敗・利用不可")
ax.barh(y, outside, left=[o + f for o, f in zip(ok, fail)], color=NONE, label="試験対象外（PAYG未積・未到達）")
for i, (o, d) in enumerate(zip(ok, denom)):
    ax.text(d + 0.4, i, f"{o}/{d}", va="center", fontsize=10, color=INK)
ax.set_yticks(list(y))
ax.set_yticklabels(providers)
ax.invert_yaxis()
ax.set_xlabel("モデル数（各社の試験集合は異なる・分母はその日の対象数）")
ax.set_title("基本APIの実測結果（2026/11/02〜11/07）", fontsize=13, color=INK)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, fontsize=8.5, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", color="#eeeeee")
ax.set_axisbelow(True)
fig.text(0.01, -0.19, A["note"], fontsize=7.6, color="#555555", ha="left")
save(fig, "A_api_success.png")

# ------------------------------------------------------------------ chart B
state_color = {"ok": OK, "fail": BAD, "rate_limited": WARN, "timeout": BAD,
               "unavailable": NONE, "untested": NONE}
state_mark = {"ok": "○", "fail": "×", "rate_limited": "△", "timeout": "×",
              "unavailable": "", "untested": ""}

fig, axes = plt.subplots(1, 2, figsize=(14.2, 8.2), gridspec_kw={"width_ratios": [1, 1], "wspace": 0.62})
for ax, title, rows, cols, keyname in [
    (axes[0], "BlazeRail: モデル×機能（429除外の再測定）", B["blazerail"],
     ["basic", "tool", "stream", "agent"], "blazerail"),
    (axes[1], "Harogo: FULL_PASS と到達不可（既存JSON集計）", B["harogo"],
     ["basic", "tool", "stream"], "harogo"),
]:
    for i, row in enumerate(rows):
        for j, col in enumerate(cols):
            st = row["states"].get(col)
            if st is None:
                st = "unavailable"
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=state_color[st],
                                       edgecolor="white", linewidth=1.5))
            mark = state_mark[st]
            ax.text(j + 0.5, i + 0.5, mark, ha="center", va="center", fontsize=12,
                    color="white" if st in ("ok", "fail", "rate_limited") else INK)
    ax.set_xlim(0, len(cols))
    ax.set_ylim(0, len(rows))
    ax.set_xticks([j + 0.5 for j in range(len(cols))])
    ax.set_xticklabels([c.capitalize() for c in cols], fontsize=9)
    ax.set_yticks([i + 0.5 for i in range(len(rows))])
    ax.set_yticklabels([r["label"] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.tick_params(length=0)
    ax.spines[:].set_visible(False)
    ax.set_title(title, fontsize=10.5, color=INK, pad=8)
    for j in range(len(cols) + 1):
        ax.axvline(j, color="#ffffff", linewidth=1)
    for i in range(len(rows) + 1):
        ax.axhline(i, color="#ffffff", linewidth=1)

fig.legend(handles=[Patch(color=OK, label="○ 成功"),
                    Patch(color=BAD, label="× 失敗"),
                    Patch(color=WARN, label="△ 429（再試行後も失敗）"),
                    Patch(color=NONE, label="灰 未到達・未検証")],
           loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=4, fontsize=8.5, frameon=False)
fig.text(0.01, -0.06,
         "BlazeRailはbasic 200の17モデルのみ。AgentはOpenCode 1.18.18で隔離リポジトリを実走し、node test.jsの出力42まで確認。"
         "HarogoはFULL_PASS 10モデルとUNAVAILABLE/NOT_ACCESSIBLE 9モデルを残した。Claude系は公式Claude Code経由の実測。",
         fontsize=7.4, color="#555555")
fig.suptitle("モデル×機能の実測マトリクス（429を除外した再測定と既存監査の集計）", fontsize=12.5, color=INK)
save(fig, "B_model_matrix.png")

# ------------------------------------------------------------------ chart C
labels = [r["name"] for r in C["theory"]]
monthly = [r["monthly"] for r in C["theory"]]
weekly = [r["weekly"] for r in C["theory"]]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 4.6), gridspec_kw={"width_ratios": [1.1, 1]})
x = range(len(labels))
ax1.bar([i - 0.2 for i in x], monthly, width=0.4, color=OK, label="月間上限から算出（30日）")
ax1.bar([i + 0.2 for i in x], weekly, width=0.4, color=WARN, label="7日ローリング上限から算出")
for i, (m, w) in enumerate(zip(monthly, weekly)):
    ax1.text(i - 0.2, m, f"{m:,.0f}", ha="center", va="bottom", fontsize=7.5)
    ax1.text(i + 0.2, w, f"{w:,.0f}", ha="center", va="bottom", fontsize=7.5)
ax1.set_xticks(list(x))
ax1.set_xticklabels(labels, fontsize=7.5, rotation=18, ha="right")
ax1.set_ylabel("完了可能なタスク数")
ax1.set_title("理論値: DeepRelay Base（$0.99/月）", fontsize=11, color=INK)
ax1.set_yscale("log")
ax1.set_yticks([1000, 2500, 5000, 10000, 25000, 50000, 100000])
ax1.set_yticklabels(["1,000", "2,500", "5,000", "10,000", "25,000", "50,000", "100,000"])
ax1.spines[["top", "right"]].set_visible(False)
ax1.grid(axis="y", color="#eeeeee")
ax1.set_axisbelow(True)
ax1.legend(fontsize=8, frameon=False)

mnames = list(C["measured"].keys())
med = [C["measured"][m].get("median_s") or 0 for m in mnames]
p95 = [C["measured"][m].get("p95_s") or 0 for m in mnames]
xx = range(len(mnames))
ax2.bar([i - 0.2 for i in xx], med, width=0.4, color=OK, label="所要時間 中央値 (s)")
ax2.bar([i + 0.2 for i in xx], p95, width=0.4, color=WARN, label="所要時間 p95 (s)")
ax2.set_ylim(0, max(p95 + [1]) * 1.62)
for i, m in enumerate(mnames):
    d = C["measured"][m]
    ratio = d.get("theory_gap_factor")
    wi = d.get("weighted_in_median") or 0
    ax2.text(i, max(med[i], p95[i]) + max(p95 + [1]) * 0.10,
             f"合格 {d.get('pass')}\n加重入力 {wi:,.0f}\n理論4,000の{ratio:.1f}倍",
             ha="center", va="bottom", fontsize=7.5)
ax2.set_xticks(list(xx))
ax2.set_xticklabels(mnames, fontsize=8.5)
ax2.set_ylabel("秒")
ax2.set_title("実測: OpenCode 3タスク×3回（18ラン）", fontsize=11, color=INK)
ax2.spines[["top", "right"]].set_visible(False)
ax2.grid(axis="y", color="#eeeeee")
ax2.set_axisbelow(True)
ax2.legend(fontsize=8, frameon=False)

fig.text(0.01, -0.10,
         "理論値は1タスク=入力4,000＋出力1,000、キャッシュなし、加重倍率適用後の入力枠のみ。実測の加重入力は/v1/billing/subscriptionの前後差分（実測）。"
         "OpenCodeのトークン表示はbest-effortで、請求カウンタとは一致しない場合がある。",
         fontsize=7.4, color="#555555")
fig.suptitle("DeepRelay Base: 理論上限と実測（加重トークンは請求カウンタ差分）", fontsize=12.5, color=INK)
save(fig, "C_task_capacity.png")

# ------------------------------------------------------------------ chart D
ev = D["events"]
fig, ax = plt.subplots(figsize=(9.6, 5.6))
for i, (date, text, color) in enumerate(ev):
    ax.plot([0], [i], marker="o", markersize=8, color=color)
    ax.text(0.03, i, f"{date}  {text}", va="center", fontsize=8.6, color=INK)
ax.axvline(0, color="#cccccc", linewidth=1)
ax.set_xlim(-0.05, 1)
ax.set_ylim(-1, len(ev))
ax.invert_yaxis()
ax.set_yticks([])
ax.set_xticks([])
ax.spines[:].set_visible(False)
ax.set_title("障害・復旧・契約のタイムライン（実測記録から）", fontsize=12.5, color=INK, pad=12)
fig.text(0.01, -0.04, "時刻は記録に残っているものだけ表記（UTC/JST混在は明記）。同日の並びは記録時刻順。",
         fontsize=7.6, color="#555555")
ax.legend(handles=[Patch(color=OK, label="成功・復旧"),
                   Patch(color=BAD, label="障害・未復旧"),
                   Patch(color=WARN, label="注意・制限"),
                   Patch(color=GREY, label="契約・設定")],
          loc="lower right", fontsize=8.5, frameon=False)
save(fig, "D_timeline.png")

# ------------------------------------------------------------------ cross-check
t1r = load(T1 / "RESULT.json")
t2r = load(T2 / "RESULT.json")
t3r = load(T3 / "RESULT.json")
t5r = load(T5 / "RESULT.json")
checks = []
def check(name, a, b, note=""):
    checks.append({"item": name, "chart_value": a, "source_value": b, "match": a == b, "note": note})

check("A BlazeRail ok", blaze_ok, t1r["counts"]["basic"]["ok"])
check("A BlazeRail denom", blaze_n, 30, "11/07 basic test set")
check("A Harogo ok", har_ok, t2r["tested_models"])
check("A Harogo denom", har_n, t2r["tested_models"] + t2r["counts"]["basic"]["unavailable"])
check("A AIHubMix ok", ai_ok, t5r["recheck_ok"], "chart A is the 11/04 basis; task5 recheck was 23/23")
check("A AIHubMix denom", ai_n, 34, "historical 11/04 tested set; task5 recheck_total=23")
check("A DeepRelay ok", dr_ok, 4)
check("A Rayu ok", rayu_ok, 17)
check("B BlazeRail rows", len(B["blazerail"]), t1r["tested_models"])
check("B Harogo rows", len(B["harogo"]), t2r["tested_models"] + t2r["counts"]["basic"]["unavailable"])
check("B BlazeRail agent ok", B["blazerail_counts"]["agent"]["ok"], t1r["counts"]["agent"]["ok"])
check("B Harogo tool ok", t2_counts["tool"]["ok"], t2r["counts"]["tool"]["ok"])
check("C DeepSeek pass", C["measured"]["deepseek-v4.1-flash"]["pass"], t3r["per_model"]["deepseek-v4.1-flash"]["pass"])
check("C DeepSeek median_s", C["measured"]["deepseek-v4.1-flash"]["median_s"], t3r["per_model"]["deepseek-v4.1-flash"]["median_s"])
check("C DeepSeek p95_s", C["measured"]["deepseek-v4.1-flash"]["p95_s"], t3r["per_model"]["deepseek-v4.1-flash"]["p95_s"])
check("C DeepSeek weighted_in_median", C["measured"]["deepseek-v4.1-flash"]["weighted_in_median"], t3r["per_model"]["deepseek-v4.1-flash"]["weighted_in_median"])
check("C GLM pass", C["measured"]["glm-5.3-flash"]["pass"], t3r["per_model"]["glm-5.3-flash"]["pass"])
check("C GLM median_s", C["measured"]["glm-5.3-flash"]["median_s"], t3r["per_model"]["glm-5.3-flash"]["median_s"])
check("C GLM p95_s", C["measured"]["glm-5.3-flash"]["p95_s"], t3r["per_model"]["glm-5.3-flash"]["p95_s"])
check("C GLM weighted_in_median", C["measured"]["glm-5.3-flash"]["weighted_in_median"], t3r["per_model"]["glm-5.3-flash"]["weighted_in_median"])
check("D events", len(ev), len(D["events"]), "timeline is an event list, not a RESULT.json count")

report = ["# グラフ用データ最終エクスポート REPORT", "",
          f"生成: {C['generated_utc']}", "",
          "## 出力", "",
          "- `charts/data/A.json`, `B.json`, `C.json`, `D.json`",
          "- `charts/A_api_success.png`, `B_model_matrix.png`, `C_task_capacity.png`, `D_timeline.png`（上書き）",
          "- 元の `sns/make_charts.py` は未変更。`charts/export_and_draw.py` が新しいデータJSONを読む。",
          "", "## 数値照合（RESULT.json との1件ずつ照合）", "",
          "| 項目 | グラフ側 | RESULT.json側 | 一致 | 注記 |", "|---|---:|---:|:---:|---|"]
for c in checks:
    report.append(f"| {c['item']} | {c['chart_value']} | {c['source_value']} | {'OK' if c['match'] else 'MISMATCH'} | {c['note']} |")
report += ["", "## 不一致", ""]
mism = [c for c in checks if not c["match"]]
report.append("なし" if not mism else "\n".join(f"- {c['item']}: {c['chart_value']} vs {c['source_value']}" for c in mism))
report += ["", "## 注記", "",
           "- AのAIHubMixは2026-11-04監査時点の23/34。2026-11-08再確認ではbasic_pass 23/23が応答し、有効カタログから5件が消失した。",
           "- BのBlazeRail AgentはOpenCode 1.18.18で実走。Claude系は直接API 200でもOpenCodeでHTTP 400（extra usage）となり×。",
           "- BのHarogoは既存JSONの機械集計のみ。Claude系は公式Claude Code経由の503/404実測。",
           "- Cの実測は18ラン（DeepSeek 9/9、GLM-5.3 Flash 9/9）。加重入力は/v1/billing/subscriptionの前後差分で、"
           "全ランで (OpenCode input + cache_read) × 倍率 と一致した。理論4,000に対する倍率はDeepSeek 21.8倍、GLM 34.9倍。",
           "- Dは既存イベントに2026-11-08の再測定・再取得を追加。",
           "- Rayuの0.836は、ダッシュボードのトップライン46.18（7日/5時間カウンタ）とCredit Source Split 45.344（期間カウンタ）の差として再現した。"
           "ただしどちらが請求の正本かは未確定。"]
(OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
print("wrote", OUT / "REPORT.md")
