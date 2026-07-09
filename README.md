# 🐶 Pocol (AI Dog Assistant)

![Python](https://img.shields.io/badge/Python-3.14-blue.svg?style=flat-square&logo=python)
![Ollama](https://img.shields.io/badge/AI-Ollama-orange.svg?style=flat-square)
![Version](https://img.shields.io/badge/Version-1.5.0-blueviolet.svg?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)

**Pocol（ポコル）** は、Intel N100 搭載のミニPC（省電力・ローエンド環境）での常時稼働に最適化された、自律型 AI Discord Bot です。

最新鋭の完全統合マルチモーダルモデル「Gemma 4 E2B QAT」をメイン脳として採用し、テキストと画像をシームレスに理解。さらにインターネット検索や自律的な学習機能を駆使して、あなたの生活をサポートする「賢い番犬」です。

## ✨ 特徴 (Features)

* **⚡ N100・8GB RAM 最適化設計**
    * 超軽量なQAT（量子化）モデルを採用し、OSと共存可能な低メモリ消費（約2GB強）を実現。
    * 非同期処理と排他制御により、ミニPC環境でもスワップやクラッシュを防ぎます。
* **🧠 統合マルチモーダル & ハイブリッド脳**
    * **メイン:** `Gemma 4 E2B QAT` - 文章理解、画像認識、高度な推論（思考）を1つの脳で処理。
    * **予備:** `DeepSeek R1 (1.5B)` - メインが応答しない場合に自動で切り替わる超軽量な緊急回路。
* **🌱 自律学習と長期記憶 (RAG)**
    * **自動学習:** 4時間に1回、指定されたチャンネルの会話を静かに読み込み、長期知識として蓄積。
    * **週刊トークテーマ:** 毎週月曜日の12時に、最新ニュースを元にしたトークテーマを自動提案してサーバーを盛り上げます。
* **🛠 多彩なツール連携**
    * **Web検索:** DuckDuckGo を使用し、最新のニュースやトレンドを解説。
    * **天気予報:** OpenWeatherMap API によるリアルタイム天気。
    * **グルメ / 書籍:** ホットペッパーグルメ、国立国会図書館サーチAPIと連携。

## 📦 必要要件 (Requirements)

### ハードウェア
* **CPU:** Intel N100 以上推奨
* **RAM:** 8GB 以上 (16GB ならさらに余裕が生まれます)
* **Disk:** SSD (空き容量 5GB以上)

### ソフトウェア
* **OS:** Windows 10/11 (Linux/Macでも動作可能)
* **Python:** 3.14 以上
* **Package Manager:** [uv](https://github.com/astral-sh/uv) (推奨)
* **Ollama:** 最新版

## 🚀 インストール手順 (Installation)

### 1. Ollama の準備
Ollama をインストールし、ターミナルで以下のコマンドを実行してモデルをダウンロードします。

```bash
ollama pull gemma4:e2b-it-qat
ollama pull deepseek-r1:1.5b
```

### 2. リポジトリのクローンと環境構築
高速パッケージマネージャー `uv` を使用して環境を構築します。
```bash
git clone [https://github.com/YourUsername/pocol.git](https://github.com/YourUsername/pocol.git)
cd pocol
uv sync
```

### 3. 環境変数の設定
プロジェクトルートに `.env` ファイルを作成し、以下の内容を記述してください。

**`.env` ファイル例:**
```ini
# --- 1. Discord Configuration ---
DISCORD_TOKEN=your_discord_bot_token_here
TALK_THEME_CHANNEL_ID=your_channel_id_here

# --- 2. Ollama & AI Configuration ---
OLLAMA_HOST=[http://127.0.0.1:11434](http://127.0.0.1:11434)
TEXT_MODEL_ID=gemma4:e2b-it-qat
BACKUP_MODEL_ID=deepseek-r1:1.5b

# --- 3. External APIs ---
HOTPEPPER_API_KEY=your_hotpepper_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
```

## 🎮 使い方 (Usage)

### 起動方法
Windowsの場合は `start_pocol.bat` をダブルクリックするだけで起動します。
ターミナルから手動で起動する場合：
```bash
uv run main.py
```

### 会話とコマンド
* **基本会話:** Pocolにメンション（`@Pocol`）して話しかけます。
* **ツール検索:** 「今日の**ニュース**」「札幌の**天気**」「渋谷の**焼肉**」「Pythonの**本**」など、キーワードを含めると自動で外部データを検索します。
* **画像認識:** Discordに画像をアップロードして「これは何？」と尋ねるだけで、Gemma 4が直接画像を解析します。
* **記憶の管理:**
    * `!reset` または `忘れて`: 直近の会話（短期記憶）をリセットします。
    * `!clearall` または `すべて忘れて`: 短期記憶に加え、これまでに学習したあなたに関する長期知識も**完全に全消去**します。

## 📂 プロジェクト構成

```text
pocol/
├── main.py           # Botのメインロジック（Gemma 4 統合版）
├── pocol.db          # 会話履歴・学習知識データベース (自動生成)
├── start_pocol.bat   # 自動再起動付き起動スクリプト (Windows用)
├── pyproject.toml    # 依存関係定義ファイル
├── uv.lock           # バージョン固定ファイル
├── .python-version   # Pythonバージョン指定
├── .gitignore        # Git除外設定（セキュア設定済み）
└── README.md         # このファイル
```

## 📜 ライセンス (License)

このプロジェクトは [MIT License](LICENSE) の下で公開されています。

---

**Author:** Ryosuke Murase  
**Powered by:** [Ollama](https://ollama.com/) & [Discord.py](https://github.com/Rapptz/discord.py)