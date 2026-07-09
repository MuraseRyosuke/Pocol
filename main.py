"""
Pocol (AI Dog Assistant) Main Script v1.5.0 (Gemma 4 E2B Refactored)
Target Hardware: Intel N100 Mini PC (Low Power / 8GB RAM)
"""

import os
# Windows環境でのlocalhostの名前解決問題を回避するため、最優先でIPv4を指定
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"

import asyncio
import random
import datetime
import xml.etree.ElementTree as ET

import discord
from discord.ext import tasks
import ollama
import aiohttp
import aiosqlite
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# --- Configuration & Constants ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

try:
    TALK_THEME_CHANNEL_ID = int(os.getenv('TALK_THEME_CHANNEL_ID', '0'))
except ValueError:
    TALK_THEME_CHANNEL_ID = 0

MAIN_TEXT_MODEL = os.getenv('TEXT_MODEL_ID', 'gemma4:e2b-it-qat')
BACKUP_TEXT_MODEL = os.getenv('BACKUP_MODEL_ID', 'deepseek-r1:1.5b')

HOTPEPPER_KEY = os.getenv('HOTPEPPER_API_KEY')
WEATHER_KEY = os.getenv('OPENWEATHER_API_KEY')
DB_NAME = "pocol.db"
MAX_HISTORY_LIMIT = 10

# --- System Prompt ---
SYSTEM_PROMPT = """
あなたは「Pocol（ポコル）」という名前の、知的で忠実な犬型AIアシスタントです。
以下のルールを厳格に守ってください：
1. 口調：語尾に「〜ワン」「〜だワン」を付け、親しみやすく話してください。
2. 役割：ユーザーの質問に対し、提供された[外部データ]や[過去の知識]を活用して回答してください。
3. 画像：画像が与えられた場合、その内容を正確に観察して回答してください。
4. 禁止事項：情報が見つからない場合、嘘をつかずに正直に「わからない」と伝えてください。
"""

# --- Class: Memory Management ---
class Memory:
    @staticmethod
    async def init_db():
        """データベースとテーブルの初期化"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id INTEGER NOT NULL, 
                    role TEXT NOT NULL, 
                    content TEXT NOT NULL, 
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    user_id INTEGER NOT NULL, 
                    content TEXT NOT NULL, 
                    source_channel TEXT, 
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
                    UNIQUE(content) ON CONFLICT IGNORE
                )
            """)
            await db.commit()

    @staticmethod
    async def add_message(user_id: int, role: str, content: str):
        """直近の会話を保存"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)", 
                (user_id, role, content)
            )
            await db.commit()

    @staticmethod
    async def get_recent_history(user_id: int, limit: int = MAX_HISTORY_LIMIT) -> list:
        """直近の会話履歴を取得"""
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                f"SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT {limit}", 
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
            return [{'role': row[0], 'content': row[1]} for row in reversed(rows)]

    @staticmethod
    async def learn_data(user_id: int, content: str, channel_name: str) -> bool:
        """長期記憶としてユーザーの発言を保存"""
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(
                "INSERT INTO knowledge (user_id, content, source_channel) VALUES (?, ?, ?)", 
                (user_id, content, channel_name)
            )
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def recall_knowledge(user_id: int, query: str, limit: int = 3) -> str:
        """ユーザーの質問に関連する過去の記憶を検索"""
        keywords = [w for w in query.replace("?", "").replace("！", "").split() if len(w) >= 2]
        if not keywords: 
            return ""
            
        search_query = " OR ".join([f"content LIKE '%{k}%'" for k in keywords])
        sql = f"SELECT content FROM knowledge WHERE user_id = ? AND ({search_query}) ORDER BY RANDOM() LIMIT {limit}"
        
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(sql, (user_id,)) as cursor:
                    rows = await cursor.fetchall()
            if rows: 
                return "\n".join([f"- {row[0]}" for row in rows])
            return ""
        except Exception as e: 
            print(f"Memory Recall Error: {e}")
            return ""

    @staticmethod
    async def clear_memory(user_id: int):
        """短期的な会話履歴のみを削除（リセット）"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
            await db.commit()

    @staticmethod
    async def clear_all_knowledge(user_id: int):
        """短期履歴と長期知識の両方を完全に削除（完全リセット）"""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM knowledge WHERE user_id = ?", (user_id,))
            await db.commit()


# --- Class: Tools ---
class Tools:
    @staticmethod
    def extract_keywords(text: str) -> str:
        """検索用にノイズとなる言葉を除去"""
        for w in ["教えて", "探して", "検索", "知りたい", "調べて", "とは"]: 
            text = text.replace(w, "")
        for p in ["の", "と", "や", "で", "を", "が", "は"]: 
            text = text.replace(p, " ")
        return " ".join(text.split())

    @staticmethod
    async def get_weather(city_name: str = "Sapporo") -> str:
        if not WEATHER_KEY: 
            return "（Error: API Key missing）"
            
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {'q': city_name, 'appid': WEATHER_KEY, 'units': 'metric', 'lang': 'ja'}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as r:
                    d = await r.json()
                    return f"【{city_name}の天気】{d['weather'][0]['description']}, 気温:{d['main']['temp']}℃"
            except Exception as e: 
                print(f"Weather API Error: {e}")
                return "天気取得エラー"

    @staticmethod
    async def search_gourmet(user_text: str) -> str:
        if not HOTPEPPER_KEY: 
            return ""
            
        url = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
        params = {'key': HOTPEPPER_KEY, 'keyword': Tools.extract_keywords(user_text), 'format': 'json', 'count': 3}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as r:
                    d = await r.json(content_type=None)
                    shops = d['results'].get('shop', [])
                    if not shops: 
                        return "店が見つかりません。"
                    
                    shop_info = [f"- {s['name']}\n  {s['urls']['pc']}" for s in shops]
                    return "【お店】\n" + "\n".join(shop_info)
            except Exception as e: 
                print(f"Gourmet API Error: {e}")
                return "グルメ検索エラー"

    @staticmethod
    async def search_books(user_text: str) -> str:
        url = "https://ndlsearch.ndl.go.jp/api/opensearch"
        params = {'title': Tools.extract_keywords(user_text), 'cnt': 3}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as r:
                    root = ET.fromstring(await r.text())
                    items = root.findall('.//item')
                    if not items: 
                        return "本が見つかりません。"
                        
                    book_info = [f"- {i.find('title').text}" for i in items]
                    return "【本】\n" + "\n".join(book_info)
            except Exception as e: 
                print(f"Book Search Error: {e}")
                return "書籍検索エラー"

    @staticmethod
    async def search_web(user_text: str) -> str:
        keyword = Tools.extract_keywords(user_text)
        try:
            results = await asyncio.to_thread(lambda: list(DDGS().text(keywords=keyword, region='jp-jp', max_results=3)))
            if not results: 
                return "Web情報が見つかりません。"
                
            web_info = [f"- {r.get('title')}\n  {r.get('body')}" for r in results]
            return "【検索】\n" + "\n".join(web_info)
        except Exception as e: 
            print(f"Web Search Error: {e}")
            return "Web検索エラー"


# --- Class: AI Brain (Gemma 4 Unified) ---
class Brain:
    _lock = asyncio.Lock()

    @staticmethod
    async def think(user_id: int, user_input: str, context_data: str = "", image_bytes: bytes = None) -> tuple[str, str]:
        # 記憶とコンテキストの構築
        past_memories = await Memory.recall_knowledge(user_id, user_input)
        history = await Memory.get_recent_history(user_id)
        
        current_content = user_input
        if context_data: 
            current_content += f"\n\n[外部データ]\n{context_data}"
        if past_memories: 
            current_content += f"\n\n[過去の知識]\n{past_memories}"

        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + history
        
        user_msg = {'role': 'user', 'content': current_content}
        if image_bytes:
            user_msg['images'] = [image_bytes]  # Gemma 4のネイティブ画像認識を使用
            
        messages.append(user_msg)

        async with Brain._lock:
            try:
                print(f"DEBUG: Inference Start (User: {user_id}, Model: {MAIN_TEXT_MODEL})")
                response = await asyncio.to_thread(
                    ollama.chat, 
                    model=MAIN_TEXT_MODEL, 
                    messages=messages,
                    options={'temperature': 0.7, 'num_thread': 3}, 
                    keep_alive='5m'
                )
                return response['message']['content'], MAIN_TEXT_MODEL
                
            except Exception as e:
                print(f"WARNING: Main Model Failed. Switching to Backup. {e}")
                try:
                    response = await asyncio.to_thread(
                        ollama.chat, 
                        model=BACKUP_TEXT_MODEL, 
                        messages=messages,
                        options={'temperature': 0.7, 'num_thread': 3}, 
                        keep_alive='5m'
                    )
                    return f"(予備回路: {response['message']['content']})", BACKUP_TEXT_MODEL
                except Exception as backup_e: 
                    print(f"CRITICAL: Backup Model Failed. {backup_e}")
                    return "思考回路ダウンだワン...", "Error"


# --- Class: Discord Client ---
class PocolBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def set_status(self, text: str, status: discord.Status):
        await self.change_presence(status=status, activity=discord.Game(text))

    async def on_ready(self):
        await Memory.init_db()
        await self.set_status(f"{MAIN_TEXT_MODEL} (待機中)", discord.Status.online)
        print(f'--- Pocol Bot Started as {self.user} ---')
        
        if not self.bg_learning.is_running(): 
            self.bg_learning.start()
        if not self.weekly_topic.is_running(): 
            self.weekly_topic.start()

    @tasks.loop(hours=4)
    async def bg_learning(self):
        channels = [c for c in self.get_all_channels() if isinstance(c, discord.TextChannel)]
        if not channels: 
            return
            
        t_chan = random.choice(channels)
        try:
            async for m in t_chan.history(limit=50):
                if not m.author.bot and not m.content.startswith("!") and len(m.content) >= 4:
                    await Memory.learn_data(m.author.id, m.content, t_chan.name)
        except Exception as e: 
            print(f"Background Learning Error: {e}")

    @tasks.loop(minutes=60)
    async def weekly_topic(self):
        if TALK_THEME_CHANNEL_ID == 0: 
            return
            
        now = datetime.datetime.now()
        # 毎週月曜日の12時台に実行
        if now.weekday() == 0 and now.hour == 12:
            ch = self.get_channel(TALK_THEME_CHANNEL_ID)
            if not ch: 
                return
                
            try:
                t_data = await Tools.search_web("最近の面白いニュース")
                prompt = f"以下のニュースでDiscord用の「今週のトークテーマ」を1つ作り、「みんなはどう思うワン？」と聞いて。\n{t_data}"
                theme, _ = await Brain.think(0, prompt)
                
                await ch.send(embed=discord.Embed(title="🐶 今週のテーマ", description=theme, color=0xffa500))
                await asyncio.sleep(3600)  # 1時間スリープして連続投稿を防止
            except Exception as e: 
                print(f"Weekly Topic Error: {e}")

    @bg_learning.before_loop
    async def before_bg(self): 
        await self.wait_until_ready()
        
    @weekly_topic.before_loop
    async def before_wk(self): 
        await self.wait_until_ready()

    async def on_message(self, message):
        if message.author == self.user: 
            return
            
        is_mentioned = self.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)

        if is_mentioned or is_dm:
            await self.set_status(f"{MAIN_TEXT_MODEL} (思考中...)", discord.Status.dnd)
            user_id = message.author.id
            user_text = message.content.replace(f'<@{self.user.id}>', '').strip()

            try:
                async with message.channel.typing():
                    # --- コマンド処理 ---
                    if user_text in ["!help", "使い方", "ヘルプ"]:
                        embed = discord.Embed(title="🐶 Pocolの使い方", description="省電力マルチモーダルAIだワン！", color=0x00ff00)
                        embed.add_field(name="基本", value="メンションで会話 / 画像認識", inline=False)
                        embed.add_field(name="検索", value="「ニュース」「天気」「焼肉」「本」", inline=False)
                        embed.add_field(name="記憶", value="`!reset`(直近の会話を忘れる)\n`!clearall`(あなたに関する全記憶を消去)", inline=False)
                        await message.reply(embed=embed)
                        return
                        
                    if user_text in ["!reset", "忘れて"]:
                        await Memory.clear_memory(user_id)
                        await message.reply("記憶をリセットしたワン！")
                        return

                    if user_text in ["!clearall", "すべて忘れて", "完全リセット"]:
                        await Memory.clear_all_knowledge(user_id)
                        await message.reply("ワン！これまでの会話も、新しく覚えた知識も、あなたに関するすべてを綺麗さっぱり忘れたワン！")
                        return

                    # --- 画像処理 ---
                    img_bytes = None
                    if message.attachments and message.attachments[0].content_type.startswith('image'):
                        img_bytes = await message.attachments[0].read()
                        if not user_text: 
                            user_text = "この画像について詳しく教えて。"

                    # --- ツールルーティング ---
                    context = ""
                    if "本" in user_text: 
                        context = await Tools.search_books(user_text)
                    elif any(w in user_text for w in ["店", "焼肉", "ラーメン"]): 
                        context = await Tools.search_gourmet(user_text)
                    elif "天気" in user_text: 
                        context = await Tools.get_weather("Sapporo" if "札幌" in user_text else "Tokyo")
                    elif any(w in user_text for w in ["ニュース", "検索", "とは"]): 
                        context = await Tools.search_web(user_text)

                    # --- 推論の実行 ---
                    reply, model = await Brain.think(user_id, user_text, context, image_bytes=img_bytes)
                    
                    # 記憶へ保存
                    memory_text = "[画像あり] " + user_text if img_bytes else user_text
                    await Memory.add_message(user_id, 'user', memory_text)
                    await Memory.add_message(user_id, 'assistant', reply)
                    
                    if model != MAIN_TEXT_MODEL: 
                        await self.set_status(f"{model} (思考中...)", discord.Status.dnd)
                        
                    await message.reply(reply)

            except Exception as e:
                print(f"Message Processing ERROR: {e}")
                await message.reply("エラーだワン...（内部で何かが起きたみたいだワン）")
            finally:
                await self.set_status(f"{MAIN_TEXT_MODEL} (待機中)", discord.Status.online)

if __name__ == "__main__":
    if TOKEN: 
        PocolBot().run(TOKEN)
    else: 
        print("CRITICAL ERROR: Discord Token is missing from .env file.")