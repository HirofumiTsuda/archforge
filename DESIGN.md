# archforge 設計ノート

問題を自動生成して自分で解くCLIツール。まずはClaude Certified Architect – Foundations (CCA-F) の受験勉強用に作るが、資格名を固定しない汎用な名前・設計にしておき、他のAnthropic資格や別の勉強にも使い回せるようにする（プロジェクト名を`ccaf-quizsmith`のような資格固有名にしなかった理由もこれ）。

## 前提・目的

- **主目的は自分の勉強効率化。** 転職活動の書類・面接で語れる経験になる点はあくまで副次的な効果（詳細は`~/resume/notes/resume-improvement-todos.md`参照）。優先順位を取り違えると、設計が資格試験の勉強という本来の目的からズレて過剰装飾になる（実際、一度そうなりかけて訂正した経緯がある）
- 自分で問題を解く。生成AIには解かせない
- 間違えた問題・気になった問題だけ、都度AIに解説を頼む
- 受験自体はAnthropicのPartner Network経由の会社メールが要る（個人Gmailは登録時に弾かれる）。**Bain（現所属）が既にPartner Networkに参加済みのため、現在の会社メールで登録・受験できる見通し**（2026-08-26確定）。準備用の公式コース（Skilljar、13コース）も登録の有無に関係なく無料公開されている
- **将来的な公開（OSS化）を見据えている**。同資格は2026年にできたばかりで、既に非公式の対策サイト・ブログが複数存在する（claudecertificationguide.com等）＝需要はあるがAnthropic公式の練習問題集はまだ無い状態。公開する場合はREADMEに「Anthropic非公式・AI生成の練習問題であり、本物の試験問題ではない」ことを明記する。プロジェクト名を資格の略称（CCAF）に固定しなかったのも、この想定（資格名がブランド的に見えるリスク回避・他資格への拡張性）を踏まえた判断
- **公式Skilljarコースを実際に試した所感（2026-08-27、本人より）**: 「学べることと、他の非公式対策で難易度がちがいすぎる」。→ 公式コースは概念を教える教材止まりで、本番試験（シナリオに基づく設計判断を問う形式）や非公式対策サイトが想定している難易度と段差がある。これは`generate.py`のsystem promptで最初から狙っていた設計（公式ドキュメントの教え方をなぞるのではなく、シナリオベースの設計判断・もっともらしい誤答選択肢という本番試験の形式・難易度に合わせて出題する）の妥当性を裏付ける実体験。この方針は崩さないこと

## 対象試験: Claude Certified Architect – Foundations (CCA-F)

- 120分・60問（本番は6シナリオ中4つがランダム選出され、それに紐づく設問が出る）、scaled score 720/1000で合格
- シナリオ設問形式（API パラメータ名当てのようなトリビアではなく、実運用の状況に対する設計判断を問う）
- ドメイン構成（重み）:
  | ドメイン | 重み |
  |---|---|
  | Agentic Architecture & Orchestration | 27% |
  | Tool Design & MCP Integration | 18% |
  | Claude Code Configuration & Workflows | 20% |
  | Prompt Engineering & Structured Output | 20% |
  | Context Management & Reliability | 15% |

出典: freecodecamp、dev.to（Claude Certified Architect Exam記事）、Pearson VUE、Anthropic Skilljar（2026年8月時点の調査）。

## アーキテクチャ

### generate（問題生成）— マルチエージェント

1. **ドメイン生成エージェント × 5（並列 fan-out）**
   - 各ドメインに1体、独立して並列実行（asyncio.gather）
   - 各エージェントは **ReAct**: `web_search` ツール（`web_search_20260209`）を持ち、`allowed_domains` を公式ソースのみに制限
     - `docs.claude.com`, `claude.com`, `anthropic.skilljar.com`, `anthropic-partners.skilljar.com`
     - サーバーサイドツールなのでクライアント側でループを自前実装する必要はない。1回の`messages.create()`呼び出し内でClaudeが「検索→読む→出題」を自律的に回す
   - 出力は `tools` + `output_config.format`（生JSON schema）を同一呼び出しで併用し、最後に構造化JSONを確定させる（`.messages.parse()`ではなく`.messages.create()`を使う。理由: サーバーツール併用時の構造化出力はこちらの経路で確認済み）
   - 各設問には `grounding_notes`（正解・誤りの根拠）を持たせる。practice時の解説生成で再利用し、後から解説だけをハルシネーションさせない

2. **レビュー/synthesisエージェント × 1（fan-in）**
   - 5ドメイン分の生成結果をまとめて受け取り、**結合と品質レビューを同じ1呼び出しで**行う（別ステップに分けない）
   - チェック項目:
     1. `select_count_hint`（Select one/two...）と`correct_indices`の数が一致しているか
     2. 正解が複数解釈できてしまう曖昧な設問がないか
     3. ドメイン横断でシナリオ・設問が重複していないか
     4. `grounding_notes`が実際に筋が通っているか
   - 出力: 最終確定リスト + `dropped_count` + `review_notes`

3. **モデル**: デフォルト **Sonnet 5**（`--model`で上書き可、必要な時だけOpus 5等へ）
   - 理由: 個人の勉強用で何度も回す想定。並列で複数回呼ぶ設計なのでコスト差が効く。品質は生成・解説用途に十分

4. **デフォルト件数**: 1回の`generate`で **15問**。5ドメインへ重み比例で自動配分（端数調整あり）。`--count`で変更可

5. **プロンプトキャッシュ + コスト計測**（token/cost最適化）
   - system promptを「共通の固定部分」と「ドメイン固有部分」に分割し、共通部分だけに`cache_control: {"type": "ephemeral"}`を付ける:
     ```python
     system = [
         {"type": "text", "text": SHARED_STATIC_INSTRUCTIONS, "cache_control": {"type": "ephemeral"}},
         {"type": "text", "text": f"Domain: {domain}\n\n{domain_specific_guidance}"},
     ]
     ```
     ドメイン名をformatで埋め込んだ文言を丸ごとcache_control対象にすると、5ドメイン分で毎回別内容になりキャッシュが当たらない。共通部分とドメイン部分を分けて、共通部分だけキャッシュ対象にするのが正しい
   - **落とし穴**: キャッシュ対象プレフィックスは最低約1024トークン必要。今の`DOMAIN_AGENT_SYSTEM`は数百トークン程度で足りない可能性が高く、そのままだと**キャッシュが静かに効かないまま終わる**。共通部分に良問の few-shot 例（1〜2問）を足して1024トークン超にする — 出題品質を上げる効果と、キャッシュ閾値を超える効果を両方兼ねる
   - レビュー/synthesisエージェントの`REVIEWER_SYSTEM`はドメイン名を含まず完全に固定文言なので、こちらは素直にキャッシュが効く（`generate`を繰り返すたびに再利用される）
   - `generate`実行後、5ドメイン分+レビュー1回、計6呼び出しの`usage`（`input_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens` / `output_tokens`）を合算し、モデル単価から実コストを計算して表示する。「測っただけ」で終わらせず、キャッシュ導入 → 実際にコストが下がったことを数字で示すところまでやる

### practice（解く）

- 未回答の問題からシャッフルして出題（`--domain`で絞り込み可）
- 正解はローカルJSON側にあるので、**採点はAPIコールなしで即時**（生成と解答セッションを完全に分離）
- シナリオ・設問・選択肢を表示、正解は伏せる。ユーザーは "A" や "A,C" のように入力
- **正解・不正解にかかわらず、毎回「解説を見ますか？」と確認**（y/n）。見る場合のみ、`grounding_notes`を根拠に解説エージェントを1回呼ぶ

### stats（振り返り）

- ドメイン別正答率を、本番試験の重み（27/18/20/20/15%）と並べて表示 → 弱点ドメインが一目でわかる

### ストレージ

- ローカルJSONファイル（`data/bank.json`）。DBは使わない
- 理由: 単一ユーザー・単一プロセスで競合を気にする必要がない、人間が中身を直接見て編集できる、スキーマ変更にマイグレーション不要
- SQLiteへの切り替えは「数千問規模になる」「複雑なクエリが欲しい」「複数プロセスから同時アクセスしたい」のどれかが発生してから検討

## ファイル構成（`/home/hirofumi/workspace/archforge/`）

```
archforge/
  config.py    # 試験名・5ドメイン+重み・デフォルトモデル      [作成済み]
  schema.py    # Pydanticモデル(GeneratedQuestion/DomainBatch/ReviewedBatch) [作成済み]
  bank.py      # JSONバンクのload/save/add/record_attempt/domain_stats [作成済み]
  generate.py  # マルチエージェント生成                        [ReAct対応で書き直し必要]
  practice.py  # 出題・採点・解説確認のCLIループ                [未作成]
  explain.py   # 解説オンデマンド生成                          [未作成]
  cli.py       # argparse: generate/practice/stats             [未作成]
data/
  bank.json    # 問題バンク本体（gitignore対象）
requirements.txt  # anthropic, pydantic                        [未作成]
README.md         # セットアップ手順                            [未作成]
```

## 実装再開時のTODO

ストーリー単位のタスク管理は `TASKS.md` に移した。実装を再開するときはそちらの一番上の未完了ストーリーから着手する。
