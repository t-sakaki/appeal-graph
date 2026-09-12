# AppealGraph

Daytona HackSprint Tokyo 向け MVP。
情報公開・審査請求における「機関 → 非開示条文 → 反論ロジック → 判例」の
関係性を **Neo4j** のグラフとして管理し、そのコンテキストのみを根拠に
反論書（Appeal）ドラフトを生成する。生成したドラフトが実在する判例のみを引用しているか
（LLMの判例ハルシネーション対策）を **Daytona** のサンドボックス内で検証する。

🔗 デモ: https://appeal-graph.vercel.app
🔗 リポジトリ: https://github.com/t-sakaki/appeal-graph

データは [civic-lens](https://github.com/t-sakaki/civic-lens) の
条例・反論ロジック資産（17機関: 自治体・警察・裁判所）を再利用している。

## グラフスキーマ

```
(:機関 {key, authority, category, authority_type, review_authority})
    -[:規定する]->(:非開示条文 {authority_key, number, name, description})
    -[:該当する]->(:反論パターン {category, number})
    -[:主張]->(:反論ロジック {text})
    -[:引用]->(:判例 {citation})
```

同じ category+number の反論パターンは複数機関から共有されるため、
「この論理・判例は複数機関の条文で共通して使える」という横断参照ができる。

## 構成

```
appeal-graph/
├── civic_lens_data/authorities/*.json   # civic-lens由来の17機関データ
├── civic_lens_ordinance_logic.py        # civic-lens由来の反論ロジック定義
├── src/
│   ├── load_graph.py      # civic-lensデータをNeo4jへ投入
│   ├── graph_context.py   # Neo4jから機関・条文コンテキストを取得
│   ├── sandbox_runner.py  # Daytonaサンドボックス初期化・コード実行
│   └── agent.py           # コアループ: Graph → ドラフト生成 → Sandboxで引用検証
├── requirements.txt
└── README.md
```

## セットアップ

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`.env` にDaytona API KeyとNeo4j Auraの接続情報を設定する（`NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` / `DAYTONA_API_KEY`）。

## 動作確認手順

1. **グラフ投入**
   ```bash
   python src/load_graph.py
   ```
   civic-lensの17機関分のデータ（機関・非開示条文・反論ロジック・判例）をNeo4jに投入する。

2. **コンテキスト取得確認**
   ```bash
   python src/graph_context.py
   ```

3. **コアループ実行**
   ```bash
   cd src && python agent.py
   ```
   - Neo4jから機関・条文のコンテキスト（反論ロジック・判例）を取得
   - コンテキストのみを根拠に反論書ドラフトを生成
   - Daytonaサンドボックス内で、ドラフト中の判例引用がすべてグラフ由来の
     実在する判例と一致するかを検証（ハルシネーション検知）

## デモで見せるポイント

- 正常系: `anjo-city` / `第7条第2号`（法人情報）→ 最判平14.2.8を正しく引用 → 検証OK
- 異常系: ドラフトに捏造判例（例: 「最判令99.99.99でっちあげ」）を混入 → Daytonaサンドボックスが `exit_code=1` で検知

## 拡張アイデア（時間があれば）

- `build_draft` をLLM生成に置き換え、Nosana上でホストした推論エンドポイントを呼び出す
- 実際の情報公開・個人情報保護審査会の答申データを取り込み、`(:答申)-[:引用]->(:判例)` を追加
- Neo4j Browserでグラフ全体（17機関×反論パターン×判例）を可視化してデモ画面に使う
