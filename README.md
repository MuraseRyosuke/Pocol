# 🐶 Pocol (AI Dog Assistant)

![Python](https://img.shields.io/badge/Python-3.14-blue.svg?style=flat-square&logo=python)
![Ollama](https://img.shields.io/badge/AI-Ollama-orange.svg?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)

**Pocol（ポコル）** は、Intel N100 搭載のミニPC（省電力・ローエンド環境）での常時稼働に最適化された、自律型 AI Discord Bot です。

軽量なローカルLLM（Qwen 2.5 / DeepSeek R1）を脳として持ち、インターネット検索や視覚機能を駆使して、あなたの生活をサポートする「賢い番犬」です。

## ✨ 特徴 (Features)

* **⚡ N100 最適化設計**
    * 非同期処理と排他制御（ロック機構）により、8GBメモリのミニPCでもクラッシュせずに動作。
    * CPU負荷を考慮したスレッド制限とモデル選定。
* **🧠 ハイブリッド脳 & フォールバック**
    * **メイン:** `Qwen 2.5 (3B)` - 高速で自然な日本語会話。
    * **予備:** `DeepSeek R1 (1.5B)` - メインが応答しない場合に自動で切り替わる緊急回路。
    * **視覚:** `Moondream` - 画像を見て内容を理解・解説。
* **🛠 多彩なツール (Function Calling)**
    * **Web検索:** DuckDuckGo を使用し、最新のニュースやトレンドを解説。
    * **天気予報:** OpenWeatherMap API によるリアルタイム天気。
    * **グルメ:** ホットペッパーグルメ API でお店検索。
    * **書籍:** 国立国会図書館サーチ API で書籍情報を網羅。
* **🔒 プライバシー保護メモリ**
    * ユーザーごとの会話履歴をデータベース（SQLite）に分離して保存。Aさんの秘密がBさんに漏れることはありません。
* **🚦 ステータス連動**
    * 思考中は「取り込み中（🔴）」、待機中は「オンライン（🟢）」にステータスが自動で変化。

## 📦 必要要件 (Requirements)

### ハードウェア
* **CPU:** Intel N100 以上推奨
* **RAM:** 8GB 以上 (16GB 推奨)
* **Disk:** SSD (空き容量 10GB以上)

### ソフトウェア
* **OS:** Windows 10/11 (Linux/Macでも動作可能)
* **Python:** 3.14 以上
* **Package Manager:** [uv](https://github.com/astral-sh/uv) (推奨)
* **Ollama:** 最新版のインストール

## 🚀 インストール手順 (Installation)

### 1. Ollama の準備
Ollama をインストールし、ターミナルで以下のコマンドを実行してモデルを準備します。

```bash
ollama pull qwen2.5:3b
ollama pull deepseek-r1:1.5b
ollama pull moondream
```

### 2. リポジトリのクローン
```bash
git clone [https://github.com/YourUsername/pocol.git](https://github.com/YourUsername/pocol.git)
cd pocol
```

### 3. 依存ライブラリのインストール
高速パッケージマネージャー `uv` を使用して環境を構築します。
```bash
uv sync
```

### 4. 環境変数の設定
プロジェクトルートに `.env` ファイルを作成し、以下の内容を記述してください。

**`.env` ファイル:**
```ini
# Discord Bot Token (必須)
DISCORD_TOKEN=your_discord_bot_token_here

# AI Models (Ollama)
TEXT_MODEL_ID=qwen2.5:3b
VISION_MODEL_ID=moondream
BACKUP_MODEL_ID=deepseek-r1:1.5b

# API Keys (各機能を使う場合は必須)
HOTPEPPER_API_KEY=your_hotpepper_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
```

## 🎮 使い方 (Usage)

### 起動方法
Windowsの場合は `start_pocol.bat` をダブルクリックするだけで起動します（自動再起動機能付き）。

ターミナルから手動で起動する場合：
```bash
uv run main.py
```

### 会話コマンド例
* **基本会話:** 「こんにちは」「自己紹介して」
* **Web検索:** 「今日の**ニュース**教えて」「N100**とは**？」「PS5の値段を**調べて**」
    * ※日常会話と区別するため、「ニュース」「検索」「調べて」などの単語を含めてください。
* **天気:** 「札幌の**天気**」「東京の**天気**」
* **グルメ:** 「渋谷の**焼肉**」「美味しい**ラーメン**屋を教えて」
* **書籍:** 「夏目漱石の**本**」「Pythonの**書籍**」
* **画像認識:** Discordに画像をアップロードして「これは何？」「文字を読んで」とコメント。
* **記憶消去:** 「!reset」または「忘れて」

## 📂 プロジェクト構成

```text
pocol/
├── main.py           # Botのメインロジック
├── pocol.db          # 会話履歴データベース (SQLite / 自動生成)
├── start_pocol.bat   # 自動再起動付き起動スクリプト (Windows用)
├── pyproject.toml    # 依存関係定義ファイル
├── uv.lock           # バージョン固定ファイル
├── .python-version   # Pythonバージョン指定 (3.14)
├── .gitignore        # Git除外設定
└── README.md         # このファイル
```

## 🤝 貢献 (Contributing)

プルリクエストは歓迎します！
特に、新しい「ツール（機能）」の追加や、システムプロンプトの改善などをお待ちしています。

## 📜 ライセンス (License)

このプロジェクトは [MIT License](LICENSE) の下で公開されています。

---

**Author:** Ryosuke Murase  
**Powered by:** [Ollama](https://ollama.com/) & [Discord.py](https://github.com/Rapptz/discord.py)