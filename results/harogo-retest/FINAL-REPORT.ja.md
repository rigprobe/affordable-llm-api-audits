# Harogo 障害モデル復旧確認・差分再テスト 最終報告

- 実施日: 2026-11-07
- 実測時間帯（UTC）: 13:14:20 – 13:17:09（前回監査は同日 06:39–06:51）
- 比較元: `runs\full-model-incident-audit-20261107-064043`
- 成果物: `runs\post-support-retest-20261107-131217`
- 前提: 2026-11-07 に運営Telegramへ障害報告済み。運営は担当者 Xinrui へ至急確認を指示。
- Telegram送信: **未実施**（追記メッセージ原稿のみ作成）

## 冒頭サマリー表

| モデル | 前回HTTP | 今回HTTP | 前回エラー | 今回エラー | 復旧判定 |
|---|---|---|---|---|---|
| `deepseek-v4-pro` | 404 | 404 | `Model "deepseek-v4-pro-0813" is not supported by any configured account in this group` | 同一 | **STILL_BROKEN** |
| `qwen3.8-max` | 404 | 404 | `qwen3.8-max-preview has been retired and is no longer available` | 同一（`tid` のみ更新） | **STILL_BROKEN** |
| `deepseek-v4-flash-0731` | 503 | 503 | `Service temporarily unavailable` | 同一 | **STILL_BROKEN** |
| `gpt-5.6-terra` | 503 | 503 | `Service temporarily unavailable` | 同一 | **STILL_BROKEN** |
| `claude-opus-5-5` | 503 | 503 | `No available accounts: no available accounts` | 同一 | **STILL_BROKEN** |
| `claude-haiku-5-5` | 503 | 503 | `No available accounts: no available accounts` | 同一 | **STILL_BROKEN** |
| `claude-fable-5-1` | 503 | 503 | `No available accounts: no available accounts` | 同一 | **STILL_BROKEN** |
| `claude-sonnet-5` | モデル選択エラー（HTTP非公開） | **404** | `There's an issue with the selected model (claude-sonnet-5)…` | 同一文面。今回は `api_error_status=404` を初確認 | **STILL_BROKEN** |
| `claude-sonnet-5.5` | 未試験 | 未試験 | — | — | **NOT_TESTED** |
| `minimax-m3`（対照） | 200 | 200 | — | — | 正常（対照） |

前回の実測は 2026-11-07T06:42–06:46Z、今回は 2026-11-07T13:14–13:15Z。約6.5時間経過しても**全対象モデルで同一障害が継続**している。

## 1. 復旧したモデル数

**0件。**

対象8モデル（API 4件＋Claude 4件）はいずれも前回と同じHTTP障害を再現した。HTTP 200かつ有効応答を返した対象モデルはない。

## 2. 依然として障害があるモデル数

**8件**（APIカタログ4件、Claude系4件）。

| 分類 | モデル |
|---|---|
| 404（モデル／ルーティング） | `deepseek-v4-pro`, `qwen3.8-max`, `claude-sonnet-5` |
| 503（供給・アカウント） | `deepseek-v4-flash-0731`, `gpt-5.6-terra`, `claude-opus-5-5`, `claude-haiku-5-5`, `claude-fable-5-1` |

## 3. エラー内容が変化したモデル数

**0件。**

ただし `claude-sonnet-5` は、前回HTTPステータスがCLIから公開されていなかったが、今回 `--output-format json` により **`api_error_status=404`** を確定できた。文面・挙動は前回と同一であり、エラー変化ではなく**計測精度の向上**として扱う。

`qwen3.8-max` の上流 `tid` は前回 `2026110706423274375097518076096`、今回 `2026110713142851205884904862367` と変わったが、これは上流のリクエスト識別子であり、エラー種別（retired）は同一。

## 4. Claude全体の現在の状態

**未復旧。**

- クライアント: 公式 Claude Code CLI **2.1.318**、`CLAUDE_CODE_MAX_RETRIES=0`、`--no-session-persistence`、`--max-budget-usd 0.02`、`--output-format json`、OSレベル30秒制限。
- `claude-opus-5-5` / `claude-haiku-5-5` / `claude-fable-5-1` → **HTTP 503** `No available accounts: no available accounts`（1.2–1.4秒、exit 1）。
- `claude-sonnet-5` → **HTTP 404**、`There's an issue with the selected model (claude-sonnet-5). It may not exist or you may not have access to it.`
- **`this group only allows Claude Code clients` は今回も不出現。** クライアント制限ではなく、アカウント選択段階の失敗である。
- Claude CodeのJSON出力は全4回で `total_cost_usd=0`、`duration_api_ms=0`、`is_error=true`、`terminal_reason=api_error`。課金対象の完了は0件。
- クォータは十分（残枠 $11.9978 / $12、月次 $0.2973 / $60）。クォータ切れではない。
- 内部再送信の回数は**未確認**。`CLAUDE_CODE_MAX_RETRIES=0` は設定したが、CLIは内部試行回数を公開しない。応答時間1.2–1.4秒・usage増分0から、再送ループは起きていないと推定される（推定であり確定値ではない）。

## 5. DeepSeek/Qwenのルーティング改善状況

**改善なし。**

- `deepseek-v4-pro`: 前回と同じ `404 model_not_found`。エイリアスは解決されるが、上流 `deepseek-v4-pro-0813` を扱えるアカウントがグループ内に存在しない状態が継続。
- `qwen3.8-max`: 前回と同じ `404 not_found_error`。上流 `qwen3.8-max-preview` は依然 retired。現行Qwenモデルへの再マッピングが未実施。
- `deepseek-v4-flash-0731`: 前回と同じ `503 api_error`（`Service temporarily unavailable`）。
- `gpt-5.6-terra`: 前回と同じ `503 api_error`。
- 参考: `deepseek-v4.1-flash-1017` は今回未試験だが、前回FULL_PASSであり、`model_stats` に変化なし。

## 6. カタログの変更

**変更なし。**

- `GET /v1/models`: 前回14件、今回14件、ID完全一致（追加0・削除0・名称変更0）。
- Claude系5件（`claude-opus-5-5`, `claude-sonnet-5`, `claude-sonnet-5.5`, `claude-haiku-5-5`, `claude-fable-5-1`）は引き続きAPIカタログ非掲載。
- APIのみの3件（`deepseek-v4-flash-0731`, `kimi-k3`, `gpt-5.6-terra`）も変化なし。
- `docs.harogo.ai` の Last-Modified は前回監査時と同じ **2026-11-07T05:27:45Z**。`claude-sonnet-5` をClaude Codeの例として掲載したまま。
- 公開情報からは「修正完了」の告知を確認できず。Telegramはグループ招待ページのためタイムラインを直接確認できない。

## 7. Tool CallingとStreamingの結果

- 対象8モデルは**すべて基本テストで失敗**したため、仕様どおり追加検証の対象外（**NOT_TESTED**）。
- プラットフォーム全体の退行ではないことを示すため、対照モデル `minimax-m3` で追加検証を実施した（予算内）。
  - **Tool Calling**: ツール名 `add_integers` 一致、引数 `{"a":19,"b":23}` 一致、`tool_calls` 生成成功、結果42を受け取り最終回答42。**生成・継続とも成功**。
  - **Streaming**: HTTP 200、TTFT 947.2ms、content delta 3件、増分配信、`finish_reason=stop`、usageあり（入力209／出力50、reasoning 34）、エラーなし。**成功**。
- したがって「Tool Calling / Streaming の経路自体は正常。障害はモデル単位（アカウント／マッピング）」と切り分けられる。

## 8. 今回の実行数

| 種別 | 件数 |
|---|---|
| API基本テスト（対象4モデル） | 4 |
| Claude Code 起動（opus / haiku / fable / sonnet-5） | 4（上限4） |
| 対照モデル基本テスト（`minimax-m3`） | 1 |
| 対照 Tool Calling（生成＋継続） | 2 |
| 対照 Streaming | 1 |
| **合計HTTPリクエスト** | **12**（上限15） |
| 自動再試行 | **0** |
| 手動再試験 | **0**（全対象が初回で前回エラーを再現） |
| Claude Code内部再送信 | **未確認** |

Harogo側で課金集計されたリクエストは **4件**（`minimax-m3` のみ）。失敗8件（API 4件＋Claude 4件）はカウンタに載らず、課金されていない。

## 9. 実際のトークン・クォータ消費

| 項目 | 実測 |
|---|---|
| `usage.total.requests` | 220 → 224（**+4**） |
| `usage.total.cost` | 2.9727061872 → 2.9733046272（**+0.00059844**） |
| `usage.total.actual_cost` | 0.2972706186 → 0.2973304626（**+0.000059844**） |
| `subscription.daily_usage_usd` | 0.0021033 → 0.00216315（**+0.00005985**） |
| `subscription.monthly_usage_usd` | 0.29727066 → 0.29733051（**+0.00005985**） |
| 残枠（日次） | 11.9978967 → 11.99783685（**−0.00005985**） |
| 入力トークン | **+318** |
| 出力トークン | **+116** |
| キャッシュ読み取り | **+1 077** |
| 合計トークン | **+1 511** |

- 消費は停止閾値 **$0.01** の約0.6%（$0.000059844）。閾値到達前に終了。
- `cost` と `actual_cost` は前回同様に正確に10倍関係。サブスク枠は `actual_cost` を消費。
- Claude 4回は `total_cost_usd=0` をCLI自身が報告し、usage増分にも現れない。

## 10. 追加課金の有無

**なし。**

- `isValid=true`、`mode=unrestricted`、プラン・有効期限に変化なし。
- 残高・入金・プラン変更・自動チャージ変更は行っていない。
- 追加の従量課金ラインは出現していない。
- 失敗リクエストは無料。

## 11. 判定と解釈

- 運営がXinruiへ確認を指示したにもかかわらず、**2026-11-07T13:14Z時点で対象8モデルに変化はない**。
- 「サーバー側の対応が完了した」とは言えない。一方で、今回の単発試験が失敗したことを「対応が無効だった」と断定もできない。ただし、前回と同一のエラーが同一文言で再現しており、少なくとも**デプロイ済みの修正は観測できていない**。
- Claudeは引き続きアカウント選択段階で停止。DeepSeek V4 ProとQwen3.8 Maxはマッピング／上流retiredのまま。
- 対照モデルとTool/Streaming経路は正常であり、Harogo全体の停止ではない。

### 運営への確認依頼（優先順）

1. Claude: アカウント数、schedulable状態、除外理由（status/quota/expiry/concurrency/model mapping）、上流HTTP応答。`No available accounts` の内部サブケース。
2. `deepseek-v4-pro` → `deepseek-v4-pro-0813` のマッピングを修正するか、現行上流IDへ付け替える。
3. `qwen3.8-max` → `qwen3.8-max-preview` がretired。現行Qwenへ再マッピング。
4. `deepseek-v4-flash-0731` / `gpt-5.6-terra` の汎用503に、モデル名と理由コードを付与。
5. `claude-sonnet-5` の404を踏まえ、docsの例を現行Sonnet IDへ修正（`claude-sonnet-5.5` の実在確認を含む）。
6. 修正のデプロイ完了時刻と、どのモデルを対象にしたかの告知。

## 12. 成果物一覧

- `PREVIOUS-VS-CURRENT.csv` — モデル別の前回／今回比較
- `MODEL-CATALOG-DIFF.json` — カタログ差分（変更なし）
- `BASIC-RESULTS.json`, `CLAUDE-RESULTS.json`, `TOOL-RESULTS.json`, `STREAM-RESULTS.json`, `CONTROL-RESULT.json`
- `USAGE-BEFORE.json`, `USAGE-AFTER.json`, `BILLING-DIFF.md`, `REQUEST-ACCOUNTING.json`
- `SUPPORT-FOLLOWUP.en.md` — Telegram追記用英文（送信は未実施）
- `raw/` — 各リクエストの生レスポンスとClaude Codeのstdout/stderr
- `retest2.ps1`, `aggregate2.ps1` — 再現用スクリプト

APIキー・Cookie・個人情報は成果物に含まれない。
