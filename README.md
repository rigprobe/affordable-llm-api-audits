# affordable-llm-api-audits

低価格・無料枠のあるクラウドLLM API 5社を、実際に契約して叩いた記録と、図表を生成したスクリプトです。

記事: Zenn「月$0.99でコーディングエージェントを回す — 格安クラウドLLM 5社を実測した」
(https://zenn.dev/rigprobe/articles/9dedab8c9101f8)

対象: BlazeRail / Harogo / DeepRelay / AIHubMix / Rayu Code。試験日は2026年11月2日〜8日。

## 何が入っているか

- `results/` — 監査スクリプトが出力したJSON/CSV。モデルごとのHTTPコード、ツール呼び出し、ストリーミング、エージェント実行、課金差分、Usage集計。
- `scripts/` — 図の生成スクリプトと、測定・集計スクリプト。
- `scripts/CHART_VERIFICATION_REPORT.md` — 図の数値を生成元データと1件ずつ照合したレポート（不一致0）。

生のHTTPレスポンスボディやスクリーンショットは含めず、集計済みの結果だけを置いています。
APIキー、Cookie、メールアドレス、アカウントID、ローカルパスは除去済みです。

## 主な実測値

| 項目 | 値 |
| --- | --- |
| BlazeRail 基本API | 30件中17/30がHTTP 200（429×5、404×2、410×2、400×1、タイムアウト×3） |
| BlazeRail 429除外の再測定 | tool 15/17、stream 11/17、agent 8/17 |
| BlazeRail 実請求 | $5.35（credits $5.00＋手数料$0.35）、118リクエスト後も残高$5.00、Spend $0.00 |
| DeepRelay 1タスクあたり加重入力 | DeepSeek V4.1 Flash 87,326（理論値の21.8倍）、GLM-5.3 Flash 139,689（34.9倍） |
| DeepRelay 課金 | 18ランでPAYG $0、plan_covered 8/8（11/04の8推論で+15,791加重トークン） |
| Harogo | 19モデル中 FULL_PASS 10、UNAVAILABLE 8、NOT_ACCESSIBLE 1 |
| AIHubMix | 11/04の70件中32件が退役一覧。11/08の再確認23/23はHTTP 200 |
| Rayu Nemotron 3 Ultra | 4リクエストすべて200、消費0 credits |
| Rayu Usage | トップライン46.18とSource Split 45.344の差0.836（別カウンタの並置） |

DeepSeek系は、DeepRelayのV4.1 Flashが18ラン中9/9合格（中央値40.77秒）で、加重入力も18ラン中でもっとも小さい。Rayuでも `deepseek-v4.1-flash-1017` は200で正常だった。止まっていたのはRayuのV4 ProとV4 Flash（旧世代）で、同じカタログ内の現行V4.1 Flashは動いている。モデル単位の上流経路の問題として切り分けられている。

## 図の再生成

```bash
pip install matplotlib
AUDIT_ROOT=<監査成果物のルート> python scripts/export_and_draw.py
```

`AUDIT_ROOT` の下に `opencode/`、`harogo/`、`rayucode-api-audit/` が同じ構成であることを前提にしています。
このリポジトリだけでは `results/` の形が違うため、`scripts/export_and_draw.py` は元の監査ディレクトリ構成を指すようにできています。
集計値そのものは `results/` のJSON/CSVに全部入っているので、図を描き直す場合は `results/` を読む形に差し替えれば動きます。

## 注意

5社の成功率は、試験モデル・試験日時・試験数がそれぞれ違います。稼働率のランキングではなく、「その条件で何が動いたか」の記録として読んでください。

429（レート制限で到達せず）、404/410（退役）、タイムアウト（不明）、エージェント層のHTTP 400（到達したがクライアント経路が拒否）は別種の失敗です。記事でも分けて扱っています。
