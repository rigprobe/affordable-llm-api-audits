# グラフ用データ最終エクスポート REPORT

生成: 2026-11-08

## 出力

- `charts/data/A.json`, `B.json`, `C.json`, `D.json`
- `charts/A_api_success.png`, `B_model_matrix.png`, `C_task_capacity.png`, `D_timeline.png`（上書き）
- 元の `sns/make_charts.py` は未変更。`charts/export_and_draw.py` が新しいデータJSONを読む。

## 数値照合（RESULT.json との1件ずつ照合）

| 項目 | グラフ側 | RESULT.json側 | 一致 | 注記 |
|---|---:|---:|:---:|---|
| A BlazeRail ok | 17 | 17 | OK |  |
| A BlazeRail denom | 30 | 30 | OK | 11/07 basic test set |
| A Harogo ok | 10 | 10 | OK |  |
| A Harogo denom | 19 | 19 | OK |  |
| A AIHubMix ok | 23 | 23 | OK | chart A is the 11/04 basis; task5 recheck was 23/23 |
| A AIHubMix denom | 34 | 34 | OK | historical 11/04 tested set; task5 recheck_total=23 |
| A DeepRelay ok | 4 | 4 | OK |  |
| A Rayu ok | 17 | 17 | OK |  |
| B BlazeRail rows | 17 | 17 | OK |  |
| B Harogo rows | 19 | 19 | OK |  |
| B BlazeRail agent ok | 8 | 8 | OK |  |
| B Harogo tool ok | 10 | 10 | OK |  |
| C DeepSeek pass | 9/9 | 9/9 | OK |  |
| C DeepSeek median_s | 40.77 | 40.77 | OK |  |
| C DeepSeek p95_s | 51.8 | 51.8 | OK |  |
| C DeepSeek weighted_in_median | 87326.0 | 87326.0 | OK |  |
| C GLM pass | 9/9 | 9/9 | OK |  |
| C GLM median_s | 61.04 | 61.04 | OK |  |
| C GLM p95_s | 150.95 | 150.95 | OK |  |
| C GLM weighted_in_median | 139689.0 | 139689.0 | OK |  |
| D events | 16 | 16 | OK | timeline is an event list, not a RESULT.json count |

## 不一致

なし

## 注記

- AのAIHubMixは2026-11-04監査時点の23/34。2026-11-08再確認ではbasic_pass 23/23が応答し、有効カタログから5件が消失した。
- BのBlazeRail AgentはOpenCode 1.18.18で実走。Claude系は直接API 200でもOpenCodeでHTTP 400（extra usage）となり×。
- BのHarogoは既存JSONの機械集計のみ。Claude系は公式Claude Code経由の503/404実測。
- Cの実測は18ラン（DeepSeek 9/9、GLM-5.3 Flash 9/9）。加重入力は/v1/billing/subscriptionの前後差分で、全ランで (OpenCode input + cache_read) × 倍率 と一致した。理論4,000に対する倍率はDeepSeek 21.8倍、GLM 34.9倍。
- Dは既存イベントに2026-11-08の再測定・再取得を追加。
- Rayuの0.836は、ダッシュボードのトップライン46.18（7日/5時間カウンタ）とCredit Source Split 45.344（期間カウンタ）の差として再現した。ただしどちらが請求の正本かは未確定。
