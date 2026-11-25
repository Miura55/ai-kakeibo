# AI家計簿

レシートを読み取り、収入・支出を記録するローカル家計簿アプリです。画面はStreamlit、レシートの画像認識はOllamaで動かすGLM-OCR、データ保存はSQLAlchemy ORMとSQLiteを使います。

## 主な機能

- PNG・JPG・WEBPのレシートを読み取り、日付・店名・金額・カテゴリの候補を表示
- OCR結果を確認・修正してから保存。レシートなしの手入力にも対応
- 収入・支出別のカテゴリ（給与、賞与、副業・事業収入、食費、交通費など）
- 月ごとの収支確認、記録の編集・削除、CSVダウンロード
- ローカルSQLiteへの保存

OCRの読み取り値は誤ることがあります。保存前にレシートと照合してください。

## 必要なもの

- Python 3.13以上
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/)

## セットアップと起動

リポジトリのルートで以下を実行します。

```bash
uv sync
ollama pull glm-ocr:latest
ollama serve  # Ollamaがすでに起動している場合は不要
uv run streamlit run main.py
```

Streamlitが表示するローカルURLをブラウザで開いてください。初回のOCRではモデルの読み込みに時間がかかることがあります。サイドバーの「Ollamaに接続」から接続先とモデルを確認できます。

## 使い方

### レシートから登録

1. 「レシートを読み取る」タブで画像をアップロードします。
2. 「GLM-OCRで読み取る」を押し、認識結果を確認します。
3. 必要に応じて日付・店名・金額・カテゴリを修正し、「家計簿に保存」を押します。

### 手入力・記録の管理

「手入力」タブで種別を選ぶと、収入または支出に合ったカテゴリが表示されます。「家計簿」タブでは対象月を選び、記録を編集したり、削除欄にチェックして削除したりできます。CSVは表示中の月の記録を出力します。

## 設定と保存データ

| 環境変数 | 既定値 | 用途 |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollamaの接続先 |
| `OLLAMA_MODEL` | `glm-ocr:latest` | 使用するOllamaモデル |
| `KAKEIBO_DB_PATH` | `data/kakeibo.db` | SQLiteデータベースの保存先 |

環境変数を使わない場合は、サイドバーでOllamaの接続先とモデルを変更できます。画像は設定されたOllamaホストに送信されるため、ローカル処理にする場合は `localhost` のままにしてください。

`database.py` にSQLAlchemyのモデルとデータ操作をまとめています。既定のDBファイルはGit管理対象外です。`.streamlit/config.toml` で画面テーマを設定します。

## 開発時の確認

```bash
uv run python -m py_compile main.py database.py
```

現在、自動テスト用の `tests/` ディレクトリはありません。
