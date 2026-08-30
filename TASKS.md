# archforge タスク管理

進め方: 上から順にストーリー単位で完了させる。実装再開時は一番上の未完了ストーリーの一番上の🔲から着手。設計の詳細・理由は`DESIGN.md`参照。

各ストーリーはユーザー価値を主語にした単位（「〜できる」）。その下の「タスク」は実装都合の技術的な分解で、複数ストーリーにまたがって使われるものも含む。

**注記（2026-08-30）**: ストーリー構成を「技術レイヤー順（土台→生成→保存…）」から「ユーザー価値順」に見直し済み。QA（動作確認）はユーザーストーリーではないため番号を振らず末尾に残してある。ReAct（web_search）とcritique→reviseループは、どちらも生成の必須要件ではなく品質向上のための追加ストーリーとして分離した（最小のDoDは、素の生成＋見つかった問題は捨てるだけの単純なレビューで満たせる）。同様に、grounding（正確性）とプロンプトキャッシュ（コスト最適化）は別の価値軸なので別ストーリーに分けている。

## ストーリー1: 問題を作成することができる
状態: ✅ 完了（2026-08-30、`generate --count 5`を実際に3回実行し、`bank.json`への保存・内容の質を確認済み）

**目的**: 5ドメインエージェントが出題し、synthesis/レビューエージェントが結合+QAし、最終的に確定した問題がバンクに保存される

**DoD**: `generate_batch(15, exam_name)`を呼ぶと、5ドメインへ重み比例配分され、レビュー済みの設問リストが生成され、`bank.json`に保存される

### 基盤タスク（ストレージ。ストーリー7の`record_attempt`、ストーリー11の`domain_stats`もここに依存する共通土台）
- [x] `config.py`: 試験名・5ドメイン+重み・デフォルトモデル
- [x] `schema.py`: Pydanticモデル（GeneratedQuestion / DomainBatch / ReviewedBatch）
- [x] `bank.py`: load / save / add_questions / record_attempt / domain_stats を実装（`Bank`クラス化済み）
- [x] `bank.py`用のテストを書き、上記4操作が実際に動くことを確認する（`test_bank.py`、10ケース）

### 生成タスク（マルチエージェント生成のコア。web_searchなしの素の生成）
- [x] `_generate_domain_batch`/`_review`を`.messages.parse()`+`output_format`で実装（`generate.py`実装済み）

### 保存タスク
- [x] generate結果を`bank.add_questions`に渡す処理（`cli.py`の`generate`サブコマンドとして配線。ストーリー9「コマンドとして使える」の`cli.py`本体はまだ`generate`のみの最小実装で、`practice`/`stats`は未着手）

## ストーリー2: 生成した問題が公式ドキュメントに基づいた根拠を持つ
状態: ✅ 完了（2026-08-30、実際にweb_searchが発火し`grounding_notes`が検索結果を根拠にしていることを確認済み）

**目的**: web_search（公式ドメイン限定）で公式ドキュメントを参照しながら出題することで、設問と`grounding_notes`の正確性を上げる。`grounding_notes`はストーリー8（解説）がハルシネーションせず解説するための根拠になる

**DoD**: 生成エージェントがweb_searchツールで公式ドキュメントを参照し、その根拠に基づいた設問（と`grounding_notes`）が生成される

- [x] `_generate_domain_batch`を`.messages.parse()`から`.messages.create()`に書き換え
- [x] `tools=[web_search_20260209]`を追加、`allowed_domains`を公式ソースのみに限定（docs.claude.com / claude.com / anthropic.skilljar.com / anthropic-partners.skilljar.com）
- [x] `output_config.format`（生JSON schema）で構造化出力を確定させる
- [x] `domain_agent_system_prompt.jinja`にweb_search使用の指示を追加（`tools`に渡すだけではモデルが自発的に検索しなかったため。Anthropic公式の推奨〈プロンプト側でトリガー条件を明示する〉に沿って対応）

**既知の制限（2026-08-30、一旦保留）**: 実機確認で、`generate --count 5`実行時に5ドメイン中1ドメイン（Context Management & Reliability）が`questions: []`（0問）を返すことがあった。エラーは出ておらず、`_counts_per_domain`は各ドメインに最低1問を割り当てているので、モデルが「グラウンディングに足る材料が見つからなかった」と判断して意図的に空を返した可能性が高い。原因の深掘り・対処（該当ドメインだけ再試行する、など）は未着手。再発するようなら着手する。

## ストーリー3: 繰り返し実行してもコストが抑えられる
状態: 🔲 未着手

**目的**: 個人の勉強用に何度も`generate`を回す想定なので、プロンプトキャッシュで繰り返し実行時のコストを抑える（効果はストーリー6のコスト表示で確認できる）

**DoD**: system promptの共通部分に`cache_control`が付与され、2回目以降の`generate`実行でcache_read対象のトークンが発生する

- [ ] system promptを「共通の固定部分」「ドメイン固有部分」に分割
- [ ] 共通部分にfew-shot例（1〜2問）を足して1024トークン超にする（品質向上とキャッシュ閾値クリアを兼ねる）
- [ ] 共通部分に`cache_control: {"type": "ephemeral"}`
- [ ] `_review`は完全固定文言なので`.parse()`のままでOK、こちらにも`cache_control`

## ストーリー4: レビューで見つかった問題を捨てずに直せる
状態: 🔲 未着手

**目的**: 現状は「レビューが問題を見つけたら捨てて`dropped_count`に数えるだけ」。捨てるのではなく、レビューエージェント自身の判断で該当ドメインエージェントに再生成させ、問題を直して活かす（FLYWHEELのRAGでの分岐は決定論的〈ページ数・ファイル形式などコードが読める条件〉だったのに対し、こちらは**LLMの判断そのものが分岐条件**になる点が本質的に違う）

**DoD**: レビューが問題を検出した設問について、該当ドメインエージェントへの再生成→再レビューが自動的に行われ、`dropped_count`に数えて捨てるのではなく修正済みとして最終リストに残る（上限回数に達するか、レビューがクリーンと判断したら打ち切る）

- [ ] レビューが問題を検出した設問だけ、該当ドメインエージェントに具体的な修正フィードバックを渡して再生成させる
- [ ] 再生成分だけ再レビューする
- [ ] 上限回数（例: 2〜3回）に達するか、レビューがクリーンと判断したら打ち切る
- [ ] ループ自体は素のPython `while`で書く（分岐パターンが単純なので状態グラフライブラリは不要という結論は維持）

## ストーリー5: 一問ずつではなく、複数問題が自動的に作成される
状態: ✅ 完了

**目的**: `generate`を1回実行するだけで、1問ずつ生成を繰り返す必要なく、5ドメイン分の問題がまとめて自動的に作成される

**DoD**: `generate_batch`を呼ぶと、ユーザー操作を挟まず5ドメイン分の生成がまとめて自動的に進み、複数問がまとまって返ってくる

- [x] `_generate_domain_batch`を5ドメイン分`asyncio.gather`で並列実行し、まとめて自動生成する（`generate.py`実装済み）

## ストーリー6: 1回のgenerate実行にかかったコストを見ることができる
状態: 🔲 未着手

**目的**: token/cost最適化を「測っただけ」で終わらせない。generate実行後にコストが見える（キャッシュ効果〈ストーリー3〉が入っていれば、その内訳も表示に反映される）

**DoD**: `generate`を実行すると、ターミナルにコスト（input/output/cache_read/cache_creation別の内訳、キャッシュ効果込み）のサマリーが表示される

- [ ] usage集計 + コスト計算のヘルパー関数
- [ ] コストサマリーの表示フォーマット決定・実装（input/output/cache_read/cache_creation別の内訳）
- [ ] コストモニタリングが揃った状態で、`_generate_domain_batch`/`_review`の`output_config.effort`を最終決定する（2026-08-30の手動比較では、`low`は`grounding_notes`の説明が薄くなり誤答の質も下がる劣化が確認済み・非推奨。`high`→`medium`→`low`で$0.17→$0.12→$0.06。開発中は`low`のまま進めるが、開発が一段落してコスト可視化ができてから、実測コストと品質を見て`medium`以上を軸に最終値を決める）

## ストーリー7: 問題を解いて、その場で正誤がわかる
状態: 🔲 未着手

**目的**: 自分で問題を解いて即座に採点される

**DoD**: `practice`で未回答の問題がシャッフル出題され、回答すると正誤がAPIコールなしでその場に表示され、`bank.json`の`attempts`に記録される

- [ ] `practice.py`: 未回答フィルタ + シャッフル + `--domain`オプション + `--count`（1セッションで何問出すか指定、省略時は未回答全部）
- [ ] 出題表示（シナリオ・設問・選択肢、正解は伏せる、`select_count_hint`も表示）
- [ ] 回答パース（"A" や "A,C" を0-basedインデックスへ変換）
- [ ] 採点 + `record_attempt`呼び出し（振り返り用のオマケではなく、次回practice実行時に同じ問題を再出題しないための必須要素）
- [ ] 未回答が0件のときは「未回答なし」と表示して終了（復習モード・誤答再挑戦はv1では作らない）

## ストーリー8: 間違えた/合っていた理由を知りたい時に見られる
状態: 🔲 未着手

**目的**: 正誤に関わらず、都度「解説を見ますか？」と聞き、希望すれば根拠付きの解説が出る

**DoD**: practice中にy/nを聞かれ、yを押すと1回のAPI呼び出しで`grounding_notes`を根拠にした解説が表示される

- [ ] `explain.py`: grounding_notes + 選択した回答 + 正解をコンテキストに渡すプロンプト設計
- [ ] モデルはgenerateと同じSonnet 5をデフォルトにする（`--model`での上書きはストーリー10「パラメーターを変更できる」で対応）
- [ ] `practice.py`からの呼び出し統合

## ストーリー9: コマンドとして使える
状態: 🔶 一部実装（パッケージングのみ完了、`cli.py`/READMEは未着手）

**目的**: `generate` / `practice` / `stats` を実際にコマンドとして動かせる

**DoD**: 3コマンドがargparseで動く。`uv sync`で環境が揃う。READMEに手順が書いてある

**パッケージング（2026-08-27、前倒しで完了済み）**: `uv`ベースに確定。generate/practice/stats全ストーリーの実行環境の前提。
- [x] `pyproject.toml`（`[project]`で`anthropic`/`pydantic`、`[dependency-groups] dev`で`ruff`。`uv sync`で`.venv`作成済み）
- [x] `.gitignore`（`.venv/`、`__pycache__/`、`data/bank.json`）
- [x] `archforge.code-workspace`のPython interpreterを`${workspaceFolder}/.venv/bin/python`に設定
- [x] `ruff check .` / `ruff format .`が通ることを確認済み（既存の`config.py`/`schema.py`/`bank.py`/`generate.py`草稿に適用し、warningゼロ）

**残り**:
- [ ] `cli.py`（argparse、3サブコマンド）。起動は`uv run python -m archforge <cmd>`（console_scriptsのインストールは今はしない）（`generate`サブコマンドのみ、ストーリー1の保存タスクの一環で最小実装済み。`practice`/`stats`はまだ）
- [ ] `README.md`（セットアップ・実行手順: `uv sync`→`uv run python -m archforge ...`、`uv run ruff check .`等）

## ストーリー10: パラメーター（モデルなど）を変更できる
状態: 🔲 未着手

**目的**: generate/practice(explain)の実行時にモデルを差し替えられる

**DoD**: `--model`を指定すると、`config.py`のデフォルト（Sonnet 5）を上書きしてそのモデルで実行される

- [ ] `generate`/`practice`/`explain`の呼び出しに`--model`フラグを用意し、`config.py`のデフォルト（Sonnet 5）を上書きできるようにする

## ストーリー11: 自分の弱点ドメインがわかる
状態: 🔲 未着手

**目的**: ドメイン別正答率を本番の重みと並べて見て、弱点がわかる

**DoD**: `stats`で5ドメイン分の正答率・本番重みが並んだ表が出る

- [ ] `bank.domain_stats`の結果を整形して表示。並び順は正答率順ではなく**本番の重み順（27/18/20/20/15%）で固定**し、本番の出題比率と並べて弱点が見えるようにする

## QA: 動作確認
状態: 🔲 未着手

ストーリーではなく、全ストーリー完了後の最終確認チェックリスト。

- [ ] `generate --count 15`を実行し、`bank.json`の中身とコストサマリーを目視確認
- [ ] `practice`を1周回して採点・解説フローを確認
- [ ] `stats`の表示を確認
- [ ] `practice --domain <ドメイン名>`で該当ドメインだけ絞り込み出題されることを確認
- [ ] `practice --count <N>`で出題数が指定通り制御されることを確認
- [ ] `generate`/`practice`/`explain`に`--model`を指定し、別モデルで実行されることを確認
