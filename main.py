import os
import discord
import ollama
import asyncio
import aiohttp
import aiosqlite  # 追加
from datetime import datetime
from dotenv import load_dotenv

# --- 設定の読み込み ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
TEXT_MODEL = os.getenv('TEXT_MODEL_ID', 'qwen2.5:3b')
VISION_MODEL = os.getenv('VISION_MODEL_ID', 'moondream')
HOTPEPPER_KEY = os.getenv('HOTPEPPER_API_KEY')
WEATHER_KEY = os.getenv('OPENWEATHER_API_KEY')

# 記憶する会話の長さ (N100の負荷を考慮して直近10メッセージ=5往復に制限)
MAX_HISTORY_LIMIT = 10 
DB_NAME = "pocol.db"

# --- Pocolの人格設定 ---
SYSTEM_PROMPT = """
あなたは「Pocol（ポコル）」という名前の、知的で忠実な犬型AIアシスタントです。
以下のルールを厳格に守ってください：
1. 口調：語尾に「〜ワン」「〜だワン」を付け、親しみやすく話してください。
2. 記憶：直近の会話内容を覚えています。文脈を踏まえて回答してください。
3. 制約：回答は日本語で、簡潔に行ってください。
"""

# --- 記憶管理 (Database Layer) ---
class Memory:
    """SQLiteを使った長期記憶管理クラス"""
    
    @staticmethod
    async def init_db():
        """データベースとテーブルの初期化"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    @staticmethod
    async def add_message(role: str, content: str):
        """メッセージをDBに保存"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO history (role, content) VALUES (?, ?)",
                (role, content)
            )
            await db.commit()

    @staticmethod
    async def get_recent_history(limit: int = MAX_HISTORY_LIMIT):
        """直近の会話履歴を取得し、Ollama形式のリストで返す"""
        async with aiosqlite.connect(DB_NAME) as db:
            # 最新のN件を取得して、古い順（時系列順）に並べ替える
            async with db.execute(
                f"SELECT role, content FROM history ORDER BY id DESC LIMIT {limit}"
            ) as cursor:
                rows = await cursor.fetchall()
                
            # rowsは (role, content) のタプルのリスト。これを逆順にして辞書化
            history = [{'role': row[0], 'content': row[1]} for row in reversed(rows)]
            return history

    @staticmethod
    async def clear_memory():
        """記憶を消去する"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM history")
            await db.commit()

# --- 道具箱 (External Tools) ---
class Tools:
    @staticmethod
    async def get_weather(city_name: str = "Tokyo") -> str:
        if not WEATHER_KEY: return "（APIキーなし）"
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {'q': city_name, 'appid': WEATHER_KEY, 'units': 'metric', 'lang': 'ja'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200: return "天気取得エラー"
                data = await resp.json()
                return f"【{city_name}の天気】{data['weather'][0]['description']}, {data['main']['temp']}℃"

    @staticmethod
    async def search_gourmet(keyword: str) -> str:
        if not HOTPEPPER_KEY: return "（APIキーなし）"
        url = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
        params = {'key': HOTPEPPER_KEY, 'keyword': keyword, 'format': 'json', 'count': 3, 'order': 4}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200: return "店舗検索エラー"
                # content_type=None でJS/JSON問題を回避
                data = await resp.json(content_type=None)
                shops = data['results'].get('shop', [])
                if not shops: return "お店が見つかりませんでした。"
                text = "【おすすめのお店】\n"
                for s in shops: text += f"- {s['name']} ({s['mobile_access']})\n  {s['urls']['pc']}\n"
                return text

# --- AI脳 (Ollama Wrapper) ---
class Brain:
    @staticmethod
    async def think(user_input: str, context_data: str = "") -> str:
        """
        思考プロセス:
        1. DBから過去の会話履歴を取得
        2. 今回のユーザー入力とコンテキストを結合
        3. Ollamaに投げる
        """
        
        # 1. 過去の記憶をロード
        history = await Memory.get_recent_history()
        
        # 2. プロンプト構築
        current_content = user_input
        if context_data:
            current_content += f"\n\n[外部データ]\n{context_data}\n\n指示: 外部データを使って回答せよ。"

        # メッセージリスト作成: [システム設定] + [過去ログ] + [今の発言]
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + history
        messages.append({'role': 'user', 'content': current_content})

        try:
            # 3. 推論 (CPUスレッド制限付き)
            response = await asyncio.to_thread(
                ollama.chat,
                model=TEXT_MODEL,
                messages=messages,
                options={'temperature': 0.7, 'num_thread': 3},
                keep_alive='5m'
            )
            return response['message']['content']
        except Exception as e:
            print(f"Error: {e}")
            return "クゥーン... (思考回路エラーだワン)"

    @staticmethod
    async def see(image_bytes: bytes, user_query: str) -> str:
        # 画像認識は履歴に含めない（データ量が多すぎるため今回は除外）
        try:
            vision_res = await asyncio.to_thread(
                ollama.generate, model=VISION_MODEL, prompt="Describe this image.", 
                images=[image_bytes], options={'num_thread': 3}, keep_alive='1m'
            )
            desc = vision_res['response']
            # 翻訳のためにBrain.thinkを呼ぶが、ここは記憶に残さない一時的な思考
            return await Brain.think(f"画像内容(英): {desc}\n質問: {user_query}\nこれについて日本語で答えて。", "")
        except:
            return "ワン？ (見えなかったワン...)"

# --- Bot本体 ---
class PocolBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def on_ready(self):
        # 起動時にDBを初期化
        await Memory.init_db()
        print(f'--- Pocol Phase 4 (Memory Enabled) Ready! ---')
        print(f'Logged in as: {self.user}')

    async def on_message(self, message):
        if message.author == self.user:
            return

        is_mentioned = self.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)

        if is_mentioned or is_dm:
            async with message.channel.typing():
                user_text = message.content.replace(f'<@{self.user.id}>', '').strip()
                
                # --- 特殊コマンド: 記憶消去 ---
                if user_text == "!reset" or user_text == "忘れて":
                    await Memory.clear_memory()
                    await message.reply("記憶をさっぱり消去したワン！はじめましてだワン！")
                    return

                # --- 画像処理 ---
                if message.attachments:
                    if message.attachments[0].content_type.startswith('image'):
                        img = await message.attachments[0].read()
                        reply = await Brain.see(img, user_text)
                        await message.reply(reply)
                        return

                # --- ツール判定 & コンテキスト取得 ---
                context_info = ""
                if "天気" in user_text:
                    city = "Tokyo" # 簡易ロジック
                    if "大阪" in user_text: city = "Osaka"
                    elif "札幌" in user_text: city = "Sapporo"
                    context_info = await Tools.get_weather(city)
                elif "店" in user_text or "ご飯" in user_text:
                    context_info = await Tools.search_gourmet(user_text)

                # --- 思考 & 回答 ---
                reply = await Brain.think(user_text, context_info)
                
                # --- 記憶への書き込み (非同期で実行) ---
                # ユーザーの発言と、Botの返答をペアで保存する
                await Memory.add_message('user', user_text)
                await Memory.add_message('assistant', reply)
                
                await message.reply(reply)

if __name__ == "__main__":
    if not TOKEN:
        print("エラー: TOKENがありません")
    else:
        client = PocolBot()
        client.run(TOKEN)