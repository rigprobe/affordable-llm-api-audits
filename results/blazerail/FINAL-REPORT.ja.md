# BlazeRail 入金後・無料API完全監査 最終報告

- 実施: 2026-11-06 22:44〜23:10 JST（13:44〜14:10 UTC）
- 環境: Windows 11 / PowerShell 7 / OpenCode 1.18.18 / Node.js v24.14.0
- 作業フォルダ: `opencode\blazerail-verification\runs\20261106-224402`
- 追加支払い: **$0**（入金・追加チャージ・Auto-reload変更なし）
- 推論リクエスト: **37件 / 上限40件**
- 既存設定: DGXデフォルトモデル `dgx-deepseek-v41/DeepSeek-V4.1-Flash-1017` は**変更なし**。既存プロバイダーも無傷。

> **結論**: $5入金により**402 `free_models_require_deposit` は解消**し、無料ルートは解放された。ただし「掲載30件」のうち今回推論を送った重点7件で**実際に動いたのは3件**（Claude Opus 5.5、GPT-6 Astra、Gemini 4 Argon）。DeepSeek V4.1 Flashは無料ルート503、GLM-5.3とKimi K3は上流EOLで410、GLM-5.3 Flashは180秒タイムアウト。Tool Callingは動いた3件すべて成功し、OpenCodeエージェントはGeminiとGPT-6でタスク完走（42を出力、cost 0）。**追加課金のシグナルは0**だが、`usage.cost` が応答に存在せず、残高APIもないため、$5.00の維持は「ダッシュボードにログインしての目視確認」が未完了。

## 1. $5入金で無料モデルは解放されたか

**解放された（402ゲートは通過）。**

| 日時 | リクエスト | 結果 |
|---|---|---|
| 2026-11-03 | `deepseek/deepseek-v4.1-flash:free` | **402 `free_models_require_deposit`** |
| 2026-11-06 13:47 UTC（入金後初回） | 同上・非ストリーム | **408 `upstream_timeout`**（181.2秒、402ではない） |
| 2026-11-06 13:50 UTC | 同上・ストリーム | **503**（free route temporarily unavailable） |
| 2026-11-06 13:50〜14:00 UTC | Opus 5.5 / GPT-6 Astra / Gemini 4 Argon | **200**（チャット・ツール・ストリーム） |

- 402が消え、`free_models_require_deposit` は一度も再発していない。**入金は認識されている**。
- 初回の408は「入金しても402が続く」ケースではなく、DeepSeek無料ルートの上流タイムアウト。**追加の$5入金は不要**と判断した（実行していない）。
- 408/503/410はすべて**モデル/上流固有**で、アカウント全体のゲートではない。

## 2. 無料モデルの総数と実際に動作した数

- カタログ: **299モデル**（前回310から-11、削除はすべて有料の旧OpenAIモデル）
- `:free`: **30件**（前回と同一ID・同一価格0/0・属性変更なし）
- 今回推論を送った重点モデル: **7件**
- 実際にHTTP 200で応答した: **3件**
  - `anthropic/claude-opus-5-5:free`
  - `openai/gpt-6-astra:free`
  - `google/gemini-4-argon:free`
- 動作しなかった: **4件**
  - `deepseek/deepseek-v4.1-flash:free` → 503（無料ルート一時停止、2回試行）
  - `zai/glm-5.3:free` → 410（上流が2026-10-28にEOL）
  - `zai/glm-5.3-flash:free` → 408（180秒で上流デッドライン、ストリームでもトークン到着なし）
  - `moonshot/kimi-k3:free` → 410（上流が2026-10-15にEOL）
- **残り23件は未検証**（haiku/sonnet系、gpt-5.5/5.6系、gemma、nemotron、laguna等）。予算37/40と時間の制約で、重点7件に絞った。

**重要**: 「30件掲載」は「30件稼働」ではない。カタログはEOLモデルを無料として掲載し続けており、DeepSeekはルート自体が落ちている。**掲載情報と推論成功は明確に別**である。

## 3. Opus 5.5 / GPT-6 Astra / GPT-6.1 Sol の実用可否

| モデル | 無料ID | API推論 | Tool Calling | OpenCode | 判定 |
|---|---|---|---|---|---|
| Claude Opus 5.5 | あり | **成功**（READY、ストリーム8デルタ） | **成功**（`{"a":19,"b":23}`、42継続） | **不可**（上流Anthropic 400） | **B（API可・エージェント不可）** |
| GPT-6 Astra | あり | **成功**（READY） | **成功**（42継続） | **成功**（3ステップ、42、cost 0） | **A（ただしストリームはバッファ）** |
| GPT-6.1 Sol | **なし** | 未送信 | 未送信 | 未送信 | **D（カタログに存在しない）** |

- **Opus 5.5**: 直接APIではチャット・ツール・ストリームすべて正常。ツールIDはAnthropic形式 `toolu_019UYqz4LsbXky6zXatRHffp`。しかしOpenCode経由では**HTTP 400**「Third-party apps now draw from your extra usage, not your plan limits. Add more at claude.ai/settings/usage」で2回とも失敗（Anthropicの実リクエストID `req_011CgmoCeG2v9KqdFHjQ5MSS` / `req_011CgmoRLeiuyTQhJPUNFLk1`）。BlazeRailの2Mトークン枠ではなく、**Anthropic側の「extra usage」残高**が原因と見られる。小さい直接API呼び出しは通るが、OpenCodeの約12kトークン入力は通らない。
- **GPT-6 Astra**: APIもOpenCodeも成功。`apply_patch` と `bash` でファイル作成・テスト実行まで完走。ただし**ストリーミングが1デルタで最後にまとめて届く**（TTFT約9.8秒＝応答時間とほぼ同じ）。対話UXは悪い。
- **GPT-6.1 Sol**: `openai/gpt-6.1-sol` はカタログに存在しない。近縁の `openai/gpt-5.6-sol-pro` は**有料のみ**で`:free`なし。したがって**推論を送っていない**（有料へ勝手に読み替えていない）。

## 4. Tool Calling・Streaming・OpenCodeの成功率

### Tool Calling（`add_integers(19,23)`）

| モデル | ツール呼び出し | 引数JSON | ツール結果後の応答 | 判定 |
|---|---|---|---|---|
| Opus 5.5 | 1件 | `{"a": 19, "b": 23}` | 「19 + 23 = **42**」 | 成功 |
| GPT-6 Astra | 1件 | `{"a":19,"b":23}` | 「19 + 23 = 42.」 | 成功 |
| Gemini 4 Argon | 1件 | `{"a":19,"b":23}` | 「The sum of 19 and 23 is 42.」 | 成功 |

- **成功率 3/3（100%）**、継続応答も3/3で42を確認。
- ツールIDは上流形式: `toolu_...`（Anthropic）、`call_a647...`（OpenAI）、`call_16696765865454808377`（Google）。
- 注: 最初のスモークでは**こちら側のバグ**で `tools` を配列ではなく単一オブジェクトとして送っており、3モデルとも「ツールが無い」と正しく回答した。修正版で再試験し、上記が確定値。**初回のツール判定は破棄**している。

### Streaming

| モデル | HTTP | 増分デルタ | TTFT中央値 | 評価 |
|---|---|---|---|---|
| Opus 5.5 | 200 | 8デルタ（増分あり） | 999.7ms | 実ストリーム |
| Gemini 4 Argon | 200 | 5デルタ（増分あり） | 4298.8ms | 実ストリーム |
| GPT-6 Astra | 200 | **1デルタ（最後に一括）** | 9802ms | 見かけ上のストリーム |

- HTTP 200は3/3。**増分配信は2/3**。GPT-6 AstraはBlazeRail側でバッファされている（`[DONE]`は正常）。

### OpenCodeエージェント（隔離Gitリポジトリ）

タスク: `math.js`（add関数）作成 → `test.js`作成 → `node test.js`実行 → 出力を返す。

| モデル | 結果 | ステップ | ツール | 最終出力 | cost |
|---|---|---|---|---|---|
| Gemini 4 Argon | **成功**（exit 0） | 3 | write×2, bash×1 | **42** | 0 |
| GPT-6 Astra | **成功**（exit 0） | 3 | apply_patch×1, bash×1 | **42** | 0 |
| Opus 5.5 | **失敗**（exit 1） | 0 | なし | - | - |

- 完走した2/2は独立に `node test.js` で **42** を再確認（ファイル内容はエージェントのツール入力と一致）。
- OpenCodeのトークン: Gemini 合計36,867（出力209）、GPT-6 合計27,694（出力159）。入力の大半はOpenCodeのシステムプロンプト＋ツール定義（約12k）。
- OpenCodeの `cost` は全ステップ **0**（カタログ価格由来のクライアント計算）。
- 機密ファイルは送っていない（一時リポジトリのREADMEと生成2ファイルのみ）。

## 5. 実際のトークン使用量・性能

### 直接APIの usage（サーバ返却値）

| リクエスト | input | output | total | cost |
|---|---|---|---|---|
| GPT-6 Astra chat | 13 | 5 | 18 | **なし** |
| GPT-6 Astra tool | 21 | 33 | 54 | **なし** |
| GPT-6 Astra stream | 25 | 62 | 87 | **なし** |
| Opus 5.5 非ストリーム（READY） | 48 | 4 | 52 | **なし** |
| Gemini 4 Argon | 返却なし | 返却なし | 返却なし | **なし** |

- `usage.cost` は**全レスポンスで欠落**。公式ドキュメントの「応答に `usage.cost`」は、少なくとも無料ルートでは確認できなかった。
- GeminiとOpusのストリームは `usage` 自体を返さない。

### 性能（3サンプル、同一プロンプト「1〜20をカンマ区切り」）

| モデル | TTFT中央値 | 応答時間中央値 | デコード速度中央値 | 備考 |
|---|---|---|---|---|
| Opus 5.5 | **999.7ms** | **1677.5ms** | **10.59 tok/s** | 8デルタで増分配信 |
| Gemini 4 Argon | **4298.8ms** | **4816ms** | **8.73 tok/s** | 5デルタで増分配信 |
| GPT-6 Astra | **9802ms** | **9810.5ms** | 計測不能（1デルタ） | 62トークン/応答、実効4.1〜8.5 tok/s |

- デコード速度は「コンテンツデルタ数÷（最終デルタ−初回デルタ）」の**チャンク速度近似**であり、正確なトークナイザ数ではない。GPT-6はデルタが1つなので、`usage.completion_tokens / 応答時間` の実効値のみ。
- 参考: DeepRelayのDeepSeek V4.1 Flashは過去のOpenCodeベンチで「フルタスク中央値18.94秒、ツール80回、0エラー」。単純比較はできないが、BlazeRailのOpusは1ターン約1.7秒で、エージェント用途では十分速い部類。

## 6. 無料枠の公称上限と実測

- 公称（公式OpenAPI・前回取得分、変更なし）:
  - Claude/GPT系: **200万加重トークン/日**、00:00 UTCリセット、haiku×1 / sonnet×3 / opus・fable×5。超過は429 `free_tier_exhausted`。
  - $0トライアル系（deepseek, glm, kimi等）: **モデルごとのreq/min＋日次トークンポット**。数値は非公開。
- 実測:
  - **429は0回**。上限に触れていない。
  - 消費はごく小さい（Opus 52、GPT-6 87/応答、GeminiはOpenCode1ステップ約12k）。200万枠には遠い。
  - **上限値そのものは測定できていない**。GLM/KimiがEOL、DeepSeekが503で、枠を掘り切る前に落ちたため。
  - Anthropicの「extra usage」400は、BlazeRailの2M枠とは別の**上流Anthropic側の残高ゲート**。ここが尽きると、2M枠が残っていてもOpusは400になる。

## 7. ウォレット残高が維持されたか

- **API側の課金シグナルは0**:
  - 37件すべて `:free`、呼び出し時カタログで price 0/0（コードでガード）。
  - `402 insufficient_balance` は0回。
  - `usage.cost > 0` の検出は0回（検出したら即全停止する設計）。
  - `allow_model_substitution` は未送信（有料ルートへの置換なし）。
- **残高APIは存在しない**: `/v1/credits` `/v1/me` `/v1/usage` `/v1/key` `/v1/balance` `/v1/account` `/v1/wallet` `/v1/deposit` はすべて404。`/api/analytics/usage/allowance` はAPIキーでは401 `Invalid JWT token`。
- **ダッシュボードは未ログイン**: アプリ内ブラウザで `/dashboard` を開くと `/login` へリダイレクト。$5.00 の目視確認は**未完了**。
- 判定: **$5は維持されている可能性が高い**（402消滅＋課金シグナルなし）。ただし「1セントも減っていない」ことをAPIだけで証明はできず、**ログインしての確認が残る**。

## 8. モデル真正性の確度と未解決の疑義

**真正性を支持する材料**
- ツールコールIDが上流ネイティブ形式: `toolu_019UYqz4LsbXky6zXatRHffp`（Anthropic）、`call_a647f7ba085b4ab790871432ea1e59fc`（OpenAI）、`call_16696765865454808377`（Google）。
- Opusの400応答はAnthropic実APIの形式で、`request_id=req_011Cgmo...` を含む。**リクエストが実際にAnthropicへ到達している**強い証拠。
- 振る舞い: Opusは「ツールが提供されていない」と正確に指摘し、計算結果を返した。GPT-6は簡潔、Geminiは説明的。各ファミリーらしい応答。
- ツール引数・継続・算術は3モデルとも正確。

**疑義・限界**
- 補完IDはすべてBlazeRail生成の `chatcmpl-<hex>`。`x-model-served` は要求した`:free` IDをそのまま返すだけで、**重みの同一性は証明しない**。
- `system_fingerprint` は今回取得できず、logprobs・重みハッシュもない。
- `gpt-6-astra` / `gemini-4-argon` / `claude-opus-5-5` は**ベンダー独自の命名**。公開モデル名との対応はBlazeRailの主張。
- `deepseek-v4.1-flash:free` の `owned_by` は **Nvidia**（DeepSeek自身ではない）。無料ルートはNvidiaのトライアル枠経由。
- GPT-6 Astraのストリームが1デルタでバッファされるのは、上流が非ストリームで中継されている可能性を示す。

**確度**: 「要求が各社の実APIに到達している」は**中〜高**。「公式と同一の重み・同一バージョン」は**中**。「モデル名の通り」は**中**（名前だけでは証明にならない）。

## 9. DeepRelay・Harogoとの比較

| 項目 | BlazeRail | DeepRelay | Harogo |
|---|---|---|---|
| 必要支払 | **$5（一回）** | $0.99/月〜（プラン） | **サブスク必須**（初月$4.90） |
| 無料枠 | 掲載30件／今回動作3件 | プラン内のモデル（DeepSeek等） | **無料枠なし** |
| 実推論 | Opus/GPT-6/Gemini 200 | DeepSeek 9/9、GLM-5.3 9/9 | 未契約時403 `INSUFFICIENT_BALANCE` |
| OpenCodeエージェント | **2/3モデル成功**（Gemini, GPT-6） | DeepSeek 9/9、GLM-5.3 9/9、GLM-5.3 Flash 0/9（toolsで503） | 未検証 |
| Tool Calling | 3/3成功（直接API） | DeepSeek/GLM成功、GLM-5.3 Flashは503 | 未検証 |
| 速度 | Opus TTFT 1.0s/10.6tok/s、Gemini 4.3s/8.7、GPT-6 9.8sバッファ | DeepSeekフルタスク中央値18.94s | 未検証 |
| 残高/使用量API | **なし**（ダッシュボードのみ） | ダッシュボード | usageエンドポイントあり（検証済みJSONあり） |
| 課金事故リスク | **低い**（`:free`は有料へ行かない） | PAYGオーバーageの可能性 | サブスク＋日次$12枠 |
| 安定性 | **低〜中**（EOL/503/408、Anthropic extra usage 400） | 中（GLM-5.3は遅い、Flashはtools不可） | 未検証 |

- **DeepRelay**は「安く安定したエージェント」では依然優位（DeepSeek 9/9、0プロバイダエラー）。BlazeRailはモデルの**質**（Opus/GPT-6/Gemini）で勝るが、**可用性**で劣る。
- **Harogo**は無料枠がなく、契約しないと1リクエストも実行できない。$12/日の共有枠でGPT-6.1 Sol/Opus 5.5/GLM-5.3/Kimi K3.1 Pro/DeepSeekをカバーする点は魅力。ただし実APIは未検証。
- BlazeRailの`gpt-6-astra`はHarogoの`gpt-6.1-sol`とは別物。**Solを無料で試したいならBlazeRailでは不可**（Harogo/xKiro側）。

## 10. 今後使い続ける価値があるか

**条件付きで「ある」。ただし主力にはしない。**

- 使う価値:
  - **Gemini 4 Argon** と **GPT-6 Astra** はOpenCodeエージェントで実タスクを完走し、cost 0。無料でこの2つが使えるのは大きい。
  - **Opus 5.5** は直接APIのチャット/ツールとしては高品質。Anthropicのextra usageが回復すればエージェントにも使える。
  - `:free` は有料へフォールバックしないため、**課金事故リスクは低い**。
- 使わない/注意:
  - DeepSeek V4.1 Flashの無料ルートは現在503。GLM-5.3/Kimi K3はEOLで410。GLM-5.3 Flashは180秒タイムアウト。**重点7件中4件が死んでいる**。
  - GPT-6 Astraのストリームは実質バッファで、TTFT約10秒。長い応答では体感が悪い。
  - 残高・コストがAPIで見えず、ダッシュボード依存。
  - OpusのOpenCode利用はAnthropic側の財布次第。
- 推奨:
  1. **DGXをデフォルトのまま**（変更なし）。BlazeRailはセカンダリのOpenCodeプロバイダーとして追加。
  2. 日常のエージェント作業はDGX/DeepRelay。BlazeRailは「Gemini 4 Argon」「GPT-6 Astra」の難問・別視点用。
  3. DeepSeek/GLM/Kimiの復活を待って再試験（カタログから消える可能性もある）。
  4. ダッシュボードにログインして$5.00の維持を確認。
  5. Anthropic extra usageが回復したらOpus 5.5のエージェント再試験。

## 11. 安全条件の遵守

| 条件 | 結果 |
|---|---|
| 入金・追加チャージを自動実行しない | 実行なし（$0） |
| Auto-reloadを有効化しない | 変更なし |
| 価格$0の`:free`だけを呼ぶ | 37件すべて`:free`、カタログ0/0をコードでガード |
| 有料モデルへの自動フォールバック禁止 | `allow_model_substitution` 未送信、有料ID呼び出し0 |
| 最大40件、同じ失敗の自動再試行なし | **37件**。再試行は「クライアントタイムアウト1回」と「Opusエージェント1回」の意図的な2回のみ |
| 残高が減ったら即停止 | `usage.cost > 0` 検出で全停止する設計。発動0回 |
| APIキー・決済情報を保存しない | 成果物に `blaze_user_` 文字列なし（確認済み） |
| 既存プロバイダー・DGXデフォルトを変更しない | `model` は `dgx-deepseek-v41/...` のまま。既存設定は未変更 |
| 元の結果を上書きしない | 新規 `runs/20261106-224402` のみ。既存18ファイルのmtimeは2026-11-03のまま |

補足: 初回のクライアント側120秒タイムアウトは**サーバ失敗ではない**ため1回だけ再送した。Opusの400は`isRetryable:false`だが、上流の一時的な残高問題かを確認するため1回だけ意図的に再試行し、同一400を確認した。**無限再試行はしていない**。

## 12. 未解決事項と次の手順

**未解決**
1. ダッシュボードの$5.00目視確認（ログインが必要）。
2. DeepSeek V4.1 Flash無料ルートの復旧時期（503）。
3. GLM-5.3 / Kimi K3 のEOLがカタログに反映されるか（410のまま掲載）。
4. GLM-5.3 Flashの180秒タイムアウトの原因（上流停止か、単に遅いだけか）。
5. Anthropic extra usage 400の解消条件と、BlazeRailの2M枠との関係。
6. 残り23件の無料モデル（haiku/sonnet/gpt-5.5/5.6/gemma/nemotron等）の実力。
7. 無料枠の実上限（429の発生条件）— 今回は429 0回で未測定。
8. データ保持・学習利用（無料ルートのポリシー）。
9. GPT-6 Astraのストリームがバッファされる理由。
10. モデル真正性（重みの同一性）の独立確認。

**次の手順**
1. BlazeRailダッシュボードにログインし、残高が**$5.00**のままか、`usage.cost`相当の請求が0かを確認。
2. DeepSeek/GLM/Kimiを1日置いて再試験（410ならカタログからの削除を待つ）。
3. Anthropic extra usageが回復したら、Opus 5.5でOpenCodeエージェントを再試験。
4. 余力があれば残り23件を1件1リクエストでスモーク（最大23件、予算内）。
5. 本採用するなら、BlazeRail用のOpenCodeプロバイダーを既存設定へ追加（デフォルトはDGXのまま）。

## 付録: 証拠ファイル

| ファイル | 内容 |
|---|---|
| `catalog-raw-20261106.json` | 2026-11-06のカタログ生データ（299モデル） |
| `catalog-diff.json` / `catalog-2026-11-06.md` | 前回との差分、無料30件、重点モデルの状態 |
| `probe-deposit.json` | 入金後初回リクエストの生応答（408） |
| `requests.json` | スモーク16件の全記録（HTTP、usage、ヘッダ、本文、タイミング） |
| `tool-retest.json` | 修正版Tool Calling 6件（3モデル×ツール＋継続） |
| `perf-extra.json` / `perf-summary.json` | 性能3サンプルと中央値、非ストリームcostプローブ |
| `agent-gemini.jsonl` / `agent-gpt6.jsonl` / `agent-opus*.jsonl` | OpenCodeの生イベント |
| `opencode-agent-results.json` | エージェント結果の集約（トークン、cost、ツール） |
| `request-accounting.json` | 37件の内訳と安全条件 |
| `balance-and-billing.md` | 残高・課金の確認記録 |
| `verify-free.ps1` / `tool-retest.ps1` / `perf-and-cost.ps1` | 実行スクリプト（`:free`ガード、予算上限、停止条件） |
| `opencode.agent.jsonc` | 隔離OpenCode設定（30モデル、権限allow） |
| `agent-task/` | 一時Gitリポジトリ（README, math.js, test.js） |

## 判定一覧

| モデル | 判定 | 根拠 |
|---|---|---|
| `google/gemini-4-argon:free` | **A** | API・Tool・Stream・OpenCode完走（42、cost 0） |
| `openai/gpt-6-astra:free` | **A（ストリーム難）** | API・Tool・OpenCode完走。ただし1デルタバッファ、TTFT約9.8秒 |
| `anthropic/claude-opus-5-5:free` | **B** | API・Tool・Stream成功。OpenCodeは上流Anthropic 400で不可 |
| `deepseek/deepseek-v4.1-flash:free` | **C** | 無料ルート503（2回）。API未到達 |
| `zai/glm-5.3-flash:free` | **C** | 180秒タイムアウト（408）。ストリームでも到着なし |
| `zai/glm-5.3:free` | **D** | 上流EOL（410、2026-10-28） |
| `moonshot/kimi-k3:free` | **D** | 上流EOL（410、2026-10-15） |
| `openai/gpt-6.1-sol` | **D** | `:free` IDが存在しない（未送信） |
| 残り23件 | **未検証** | 今回は重点7件のみ |

判定基準: A=OpenCodeエージェント成功／B=API推論・Tool Calling成功だがエージェント不可／C=提供経路・安定性に問題／D=利用不可・未検証。
