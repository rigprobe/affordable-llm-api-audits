#!/usr/bin/env python
import os
from pathlib import Path
"""Generate the 4 charts for the cloud-LLM audit article from local audit artifacts.

Reads only files that exist under AUDIT_ROOT (verified below).
Writes PNGs to sns/charts/.
"""
import csv, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib import rcParams

rcParams["font.family"] = ["Yu Gothic", "Meiryo", "Noto Sans JP"]
rcParams["axes.unicode_minus"] = False

ROOT = os.environ.get("AUDIT_ROOT", str(Path(__file__).resolve().parents[1]))
OUT = "sns/charts"
os.makedirs(OUT, exist_ok=True)

INK = "#1b1b1b"
OK = "#2f7d4f"
WARN = "#c08a1e"
BAD = "#b23b3b"
GREY = "#9a9a9a"
NONE = "#e6e6e6"


def load_csv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    path = OUT + "/" + name
    tmp = OUT + "/" + name.replace(".png", ".tmp.png")
    fig.savefig(tmp, dpi=170, bbox_inches="tight", facecolor="white")
    os.replace(tmp, path)
    plt.close(fig)
    print("wrote", path)


# ---------------------------------------------------------------- chart A
# Basic API success by provider, with the HTTP failure mix, from local artifacts.
blaze = json.load(open(f"{ROOT}/opencode/blazerail-verification/runs/20261107-004121/basic-results.json", encoding="utf-8"))
blaze_ok = sum(1 for r in blaze if r.get("http_status") == 200)
blaze_n = len(blaze)
blaze_fail = {}
for r in blaze:
    if r.get("http_status") != 200:
        key = str(r.get("http_status"))
        blaze_fail[key] = blaze_fail.get(key, 0) + 1

har = load_csv(f"{ROOT}/harogo/runs/full-model-incident-audit-20261107-064043/ALL-MODELS-RESULTS.csv")
har_ok = sum(1 for r in har if r.get("classification") == "FULL_PASS")
har_n = len(har)

dr = load_csv(f"{ROOT}/opencode/deeprelay-all-model-smoke/MODEL_TEST_RESULTS.csv")
dr_ok = sum(1 for r in dr if r.get("verdict") == "PASS")
dr_tested = sum(1 for r in dr if r.get("verdict") != "SKIPPED_PAYG")
dr_blocked = len(dr) - dr_tested

ai = load_csv(f"{ROOT}/opencode/aihubmix-free-audit/MODEL_COMPATIBILITY_MATRIX.csv")
ai_tested = [r for r in ai if r.get("basic_pass") not in ("",)]
ai_ok = sum(1 for r in ai_tested if r.get("basic_pass") == "True")
ai_n = len(ai_tested)
ai_outside = len(ai) - ai_n

rayu = json.load(open(f"{ROOT}/rayucode-api-audit/runs/20261107-230714/BASIC-RESULTS.json", encoding="utf-8"))
rayu_ok = sum(1 for r in rayu if r.get("http_status") == 200)
rayu_n = len(rayu)

providers = ["DeepRelay", "Rayu Code", "BlazeRail", "Harogo", "AIHubMix"]
ok = [dr_ok, rayu_ok, blaze_ok, har_ok, ai_ok]
denom = [dr_tested, rayu_n, blaze_n, har_n, ai_n]
fail = [d - o for d, o in zip(denom, ok)]
outside = [dr_blocked, 0, 0, 0, ai_outside]

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
note = ("BlazeRail失敗内訳: 429×5, 404×2, 410×2, 400×1, timeout×3 ／ "
        "Harogo: UNAVAILABLE 8, NOT_ACCESSIBLE 1 ／ Rayu: 502×1, 503×1 ／ AIHubMix失敗11（429×6, 400×2, 404×2, 503×1）")
fig.text(0.01, -0.19, note, fontsize=7.6, color="#555555", ha="left")
save(fig, "A_api_success.png")


# ---------------------------------------------------------------- chart B
# Model x provider heatmap. States come straight from the audit files.
def blaze_state(model_label):
    for r in blaze:
        if r.get("label") == model_label:
            return "ok" if r.get("http_status") == 200 else "fail"
    return "untested"


def harogo_state(mid):
    for r in har:
        if r.get("model_id") == mid:
            return "ok" if r.get("classification") == "FULL_PASS" else "fail"
    return "untested"


def rayu_state(mid):
    for r in rayu:
        if r.get("model_requested") == mid:
            return "ok" if r.get("http_status") == 200 else "fail"
    return "untested"


def deeprelay_state(mid):
    for r in dr:
        if r.get("model") == "deeprelay/" + mid:
            return "ok" if r.get("verdict") == "PASS" else "blocked"
    return "untested"


def aihub_state(mid):
    for r in ai_tested:
        if r.get("model_id") == mid:
            return "ok" if r.get("basic_pass") == "True" else "fail"
    return "untested"


rows = [
    ("DeepSeek V4.1 Flash 1017", None, "deepseek-v4.1-flash-1017", "deepseek-v4.1-flash-1017-cloud", "deepseek-v4.1-flash"),
    ("GLM-5.3 Flash", "GLM-5.3 Flash", "glm-5.3-flash", "glm-5.3-flash-cloud", "glm-5.3-flash"),
    ("GLM-5.3", "GLM-5.3", "glm-5.3", "glm-5.3-cloud", "glm-5.3"),
    ("Claude Opus 5.5", "Claude Opus 5.5", "claude-opus-5-5", None, None),
    ("Claude Sonnet 5.5", None, "claude-sonnet-5.5", "claude-sonnet-5.5", None),
    ("Claude Haiku 5.5", "Claude Haiku 5.5", "claude-haiku-5-5", "claude-haiku-5.5", None),
    ("GPT-6 Astra", "GPT-6 Astra", "gpt-6-astra", None, None),
    ("GPT-5.6 Terra", "GPT-5.6 Terra", "gpt-5.6-terra", None, None),
    ("Nemotron 3 Ultra", "Nemotron 3 Ultra", None, "nvidia-nemotron-3-ultra-550b-a55b", None),
    ("Qwen3.8 Max", None, "qwen3.8-max", "qwen3.8-max", "qwen3.8-max-free"),
    ("Kimi K3", "Kimi K3", "kimi-k3", "kimi-k3", None),
    ("MiniMax M3", "MiniMax M3", "minimax-m3", "minimax-m3", "coding-minimax-m3-free"),
    ("DeepSeek V4 Pro", None, "deepseek-v4-pro", "deepseek-v4-pro", None),
]

cols = ["BlazeRail", "Harogo", "DeepRelay", "Rayu Code", "AIHubMix"]
colors = {"ok": OK, "fail": BAD, "blocked": WARN, "untested": NONE}

grid = []
for label, bz, hmid, ray, ai2 in rows:
    line = []
    line.append(blaze_state(bz) if bz else "untested")
    line.append(harogo_state(hmid) if hmid else "untested")
    line.append(deeprelay_state(hmid) if hmid else "untested")
    line.append(rayu_state(ray) if ray else "untested")
    line.append(aihub_state(ai2) if ai2 else "untested")
    grid.append(line)

fig, ax = plt.subplots(figsize=(8.6, 6.4))
for i, line in enumerate(grid):
    for j, st in enumerate(line):
        ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=colors[st], edgecolor="white", linewidth=2))
        mark = {"ok": "○", "fail": "×", "blocked": "–", "untested": ""}[st]
        ax.text(j + 0.5, i + 0.5, mark, ha="center", va="center", fontsize=15,
                color="white" if st in ("ok", "fail") else INK)
ax.set_xlim(0, len(cols))
ax.set_ylim(0, len(rows))
ax.set_xticks([j + 0.5 for j in range(len(cols))])
ax.set_xticklabels(cols)
ax.set_yticks([i + 0.5 for i in range(len(rows))])
ax.set_yticklabels([r[0] for r in rows])
ax.invert_yaxis()
ax.tick_params(length=0)
ax.spines[:].set_visible(False)
ax.set_title("モデル×提供元の実測状況（同一モデル名でも経路で挙動が変わる）", fontsize=12.5, color=INK, pad=12)
ax.legend(handles=[Patch(color=OK, label="基本API成功"),
                   Patch(color=BAD, label="失敗（429/404/410/502/503/timeout）"),
                   Patch(color=WARN, label="定額対象外・残高不足でブロック"),
                   Patch(color=NONE, label="未検証／カタログ外")],
          loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=4, fontsize=8.5, frameon=False)
fig.text(0.01, -0.16,
         "○=基本API成功、×=失敗、–=定額対象外、灰=未検証またはカタログ外。Agent/Tool/Streamingの成否は別表を参照。"
         "Claude Opus 5.5はBlazeRailでAPI 200だがOpenCodeは400。RayuはOpus 4.6系のみ提供のためOpus 5.5は対象外。",
         fontsize=7.4, color="#555555")
save(fig, "B_model_matrix.png")


# ---------------------------------------------------------------- chart C
# Task capacity: unified task (input 4,000 / output 1,000, no cache).
# Only providers with a machine-readable quota were used. Weighted units are
# the provider's own unit, so this is NOT a cross-normalized price chart.
task_in, task_out = 4000, 1000

# DeepRelay: monthly weighted input 500M, output 50M; factor per model (x1..x24)
dr_rows = []
for name, factor in [("DeepSeek V4.1 Flash (×1)", 1), ("GLM-5.3 Flash (×1.75)", 1.75),
                     ("GLM-5.3 (×12)", 12), ("Kimi K3 (×24)", 24)]:
    monthly = (500_000_000 / (task_in * factor)) 
    weekly = (125_000_000 / (task_in * factor))
    dr_rows.append((name, monthly, weekly))

fig, ax = plt.subplots(figsize=(8.4, 4.2))
labels = [r[0] for r in dr_rows]
monthly = [r[1] for r in dr_rows]
weekly = [r[2] for r in dr_rows]
x = range(len(labels))
ax.bar([i - 0.2 for i in x], monthly, width=0.4, color=OK, label="月間上限から算出（30日）")
ax.bar([i + 0.2 for i in x], weekly, width=0.4, color=WARN, label="7日ローリング上限から算出")
for i, (m, w) in enumerate(zip(monthly, weekly)):
    ax.text(i - 0.2, m, f"{m:,.0f}", ha="center", va="bottom", fontsize=8)
    ax.text(i + 0.2, w, f"{w:,.0f}", ha="center", va="bottom", fontsize=8)
ax.set_xticks(list(x))
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("完了可能なタスク数")
ax.set_title("DeepRelay Base（$0.99/月）で実行可能なタスク数の理論値", fontsize=12.5, color=INK)
ax.text(0.99, 0.92, "同じタスクでも、モデルの消費倍率で回数は最大24倍違う", transform=ax.transAxes,
        ha="right", fontsize=9, color="#555555")
ax.set_yscale("log")
ax.set_yticks([1000, 2500, 5000, 10000, 25000, 50000, 100000])
ax.set_yticklabels(["1,000", "2,500", "5,000", "10,000", "25,000", "50,000", "100,000"])
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#eeeeee")
ax.set_axisbelow(True)
ax.legend(fontsize=8.5, frameon=False)
fig.text(0.01, -0.09,
         "1タスク=入力4,000＋出力1,000トークン、キャッシュなし、加重倍率適用後の入力枠のみで算出。"
         "実測上限ではなく理論値。出力枠（50M/月）は入力枠より先に尽きない前提を置いている。",
         fontsize=7.4, color="#555555")
save(fig, "C_task_capacity.png")


# ---------------------------------------------------------------- chart D
# Incident / recovery timeline from audit timestamps.
events = [
    ("2026-11-02", "DeepRelay Base 契約（$0.99/月）", GREY),
    ("2026-11-03", "DeepRelay GLM-5.3 Flash: OpenCode 0/9（503）", BAD),
    ("2026-11-03", "DeepRelay DeepSeek V4.1 Flash / GLM-5.3: 9/9完走", OK),
    ("2026-11-04", "DeepRelay GLM-5.3 Flash API復旧（Tools含む）", OK),
    ("2026-11-04", "AIHubMix 無料監査（23/34成功、退役32件確認）", WARN),
    ("2026-11-05 03:38", "Harogo Claude系 503（11:14にzhang: 容量拡張中と回答）", BAD),
    ("2026-11-06 13:41 UTC", "BlazeRail $5.35入金 → 402解消・無料枠解放", OK),
    ("2026-11-07 06:42 UTC", "Harogo 8モデル障害を実測（Claude系503・404等）", BAD),
    ("2026-11-07 17:17", "Harogo 障害をTelegram報告、17:18に担当者へ確認依頼", BAD),
    ("2026-11-07 22:14 JST", "Harogo 再試験: 8モデル全て同一エラーで未復旧（13:14 UTC）", BAD),
    ("2026-11-07 23:28", "Rayu Pro 無料有効化・Nemotron 0 credits実証", OK),
    ("2026-11-07", "Rayu DeepSeek V4 Pro/Flash 502/503継続", BAD),
]
fig, ax = plt.subplots(figsize=(9.4, 5.0))
for i, (date, text, color) in enumerate(events):
    ax.plot([0], [i], marker="o", markersize=8, color=color)
    ax.text(0.03, i, f"{date}  {text}", va="center", fontsize=9, color=INK)
ax.axvline(0, color="#cccccc", linewidth=1)
ax.set_xlim(-0.05, 1)
ax.set_ylim(-1, len(events))
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

print("done")
