"""
Pocol (AI Dog Assistant) Main Script
Target Hardware: Intel N100 Mini PC (Low Power / 8GB RAM)
Features:
- LLM: Qwen 2.5 3B (Main) / DeepSeek R1 1.5B (Fallback)
- Vision: Moondream
- Tools: Weather, Gourmet, Books, Web Search
- Memory: SQLite (User-isolated)
- Help Command: Embed based tutorial
"""

import os
import asyncio
import xml.etree.ElementTree as ET

# Third-party libraries
import discord
import ollama
import aiohttp
import aiosqlite
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# --- Configuration & Constants ---
load_dotenv()

# Discord Token
TOKEN = os.getenv('DISCORD_TOKEN')

# AI Models (Ollama)
MAIN_TEXT_MODEL = os.getenv('TEXT_MODEL_ID', 'qwen2.5:3b')
MAIN_VISION_MODEL = os.getenv('VISION_MODEL_ID', 'moondream')
BACKUP_TEXT_MODEL = os.getenv('BACKUP_MODEL_ID', 'deepseek-r1:1.5b')

# API Keys
HOTPEPPER_KEY = os.getenv('HOTPEPPER_API_KEY')
WEATHER_KEY = os.getenv('OPENWEATHER_API_KEY')

# Database Settings
DB_NAME = "pocol.db"
MAX_HISTORY_LIMIT = 10  # Context window limit for N100 optimization

# System Prompt
SYSTEM_PROMPT = """
あなたは「Pocol（ポコル）」という名前の、知的で忠実な犬型AIアシスタントです。
以下のルールを厳格に守ってください：
1. 口調：語尾に「〜ワン」「〜だワン」を付け、親しみやすく話してください。
2. 役割：ユーザーの質問に対し、**必ず提供された[外部データ]のみ**を使って回答してください。
3. 禁止事項：[外部データ]にお店や本が見つからない場合、**架空の名前を捏造してはいけません**。「見つからなかった」と正直に伝えてください。
"""


# --- Class: Memory Management (SQLite) ---
class Memory:
    """Manages conversation history using SQLite, isolated by user_id."""

    @staticmethod
    async def init_db():
        """Initialize database and create table if not exists."""
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
            await db.commit()

    @staticmethod
    async def add_message(user_id: int, role: str, content: str):
        """Save a message to the database."""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )
            await db.commit()

    @staticmethod
    async def get_recent_history(user_id: int, limit: int = MAX_HISTORY_LIMIT) -> list:
        """Retrieve recent conversation history for a specific user."""
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                f"SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT {limit}",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
            
            # Convert to Ollama message format (reversed to chronological order)
            return [{'role': row[0], 'content': row[1]} for row in reversed(rows)]

    @staticmethod
    async def clear_memory(user_id: int):
        """Clear history for a specific user."""
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
            await db.commit()


# --- Class: External Tools (APIs) ---
class Tools:
    """Handles external API calls and keyword extraction."""

    @staticmethod
    def extract_keywords(text: str) -> str:
        """
        Cleans user input for search APIs.
        - Removes conversational fillers (intent words).
        - Replaces particles with spaces to preserve context.
        """
        # Words to remove (verbs, politeness, adjectives that confuse search)
        # Note: We keep nouns like 'ニュース', 'トレンド' as they are valid search terms.
        noise_words = [
            "教えて", "探して", "検索", "知りたい", "お願いします", 
            "おすすめ", "詳細", "について", "ある？", "です", "ます",
            "調べて", "とは", "いつ", "誰", "どこ", "何か",
            "美味しい", "うまい", "有名な", "人気の", "評判の", "良い"
        ]
        
        cleaned = text
        for word in noise_words:
            cleaned = cleaned.replace(word, "")
            
        # Replace Japanese particles with space
        particles = ["の", "と", "や", "で", "にある", "・", "を", "が", "は"]
        for p in particles:
            cleaned = cleaned.replace(p, " ")
            
        return " ".join(cleaned.split())

    @staticmethod
    async def get_weather(city_name: str = "Sapporo") -> str:
        """Fetch weather data from OpenWeatherMap."""
        print(f"DEBUG: Weather Search -> {city_name}")
        if not WEATHER_KEY:
            return "（Error: API Key missing）"
        
        url = "http://api.openweathermap.org/data/2.5/weather"
        params = {'q': city_name, 'appid': WEATHER_KEY, 'units': 'metric', 'lang': 'ja'}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return f"天気情報の取得に失敗 (Status: {resp.status})"
                    data = await resp.json()
                    desc = data['weather'][0]['description']
                    temp = data['main']['temp']
                    humidity = data['main']['humidity']
                    result = f"【{city_name}の天気】{desc}, 気温:{temp}℃, 湿度:{humidity}%"
                    print(f"DEBUG: Result -> {result}")
                    return result
            except Exception as e:
                print(f"ERROR: Weather API -> {e}")
                return "天気情報の取得中にエラーが発生しました。"

    @staticmethod
    async def search_gourmet(user_text: str) -> str:
        """Search restaurants using HotPepper Gourmet API."""
        keyword = Tools.extract_keywords(user_text)
        print(f"DEBUG: Gourmet Search Keyword -> '{keyword}'")
        if not HOTPEPPER_KEY:
            return "（Error: API Key missing）"
            
        url = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
        params = {
            'key': HOTPEPPER_KEY,
            'keyword': keyword,
            'format': 'json',
            'count': 3,
            'order': 4 # Recommendation order
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return "お店の検索に失敗しました。"
                    
                    # HotPepper returns text/javascript content-type sometimes
                    data = await resp.json(content_type=None)
                    shops = data['results'].get('shop', [])
                    
                    if not shops:
                        return "条件に合うお店が見つかりませんでした。"
                    
                    text = "【検索されたお店情報】\n"
                    for s in shops:
                        name = s['name']
                        genre = s['genre']['name']
                        link = s['urls']['pc']
                        text += f"- {name} ({genre})\n  {link}\n"
                    return text
            except Exception as e:
                print(f"ERROR: Gourmet API -> {e}")
                return "お店の検索中にエラーが発生しました。"

    @staticmethod
    async def search_books(user_text: str) -> str:
        """Search books using NDL (National Diet Library) OpenSearch."""
        keyword = Tools.extract_keywords(user_text)
        print(f"DEBUG: Book Search Keyword -> '{keyword}'")
        
        url = "https://ndlsearch.ndl.go.jp/api/opensearch"
        params = {'title': keyword, 'cnt': 3, 'dpid': 'iss-ndl-opac'}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return "国会図書館サーチに接続できませんでした。"
                    
                    xml_text = await resp.text()
                    root = ET.fromstring(xml_text)
                    items = root.findall('.//item')
                    
                    if not items:
                        return "その本は見つかりませんでした。"
                    
                    result_text = "【国立国会図書館の検索結果】\n"
                    for item in items:
                        title = item.find('title').text
                        author_tag = item.find('author')
                        author = author_tag.text if author_tag is not None else "不明"
                        result_text += f"- {title} (著: {author})\n"
                    return result_text
            except Exception as e:
                print(f"ERROR: Book API -> {e}")
                return "書籍の検索中にエラーが発生しました。"

    @staticmethod
    async def search_web(user_text: str) -> str:
        """Web Search using DuckDuckGo."""
        keyword = Tools.extract_keywords(user_text)
        print(f"DEBUG: Web Search Keyword -> '{keyword}'")
        
        try:
            # Run blocking DDGS call in a separate thread
            results = await asyncio.to_thread(
                lambda: list(DDGS().text(keywords=keyword, region='jp-jp', max_results=3))
            )
            
            if not results:
                return "Web検索しましたが、情報が見つかりませんでした。"

            result_text = f"【Web検索結果: {keyword}】\n"
            for res in results:
                title = res.get('title', 'No Title')
                body = res.get('body', 'No Description')
                href = res.get('href', '')
                result_text += f"- {title}\n  {body}\n  {href}\n"
            
            return result_text
        except Exception as e:
            print(f"ERROR: Web Search -> {e}")
            return "Web検索中にエラーが発生しました。"


# --- Class: AI Brain (Ollama Wrapper) ---
class Brain:
    """Handles interaction with Ollama models, including fallback logic and concurrency locking."""
    
    # Mutex lock to prevent N100 overload (One inference at a time)
    _lock = asyncio.Lock()

    @staticmethod
    async def think(user_id: int, user_input: str, context_data: str = "") -> tuple[str, str]:
        """
        Process text input using LLM.
        Returns: (response_text, model_name_used)
        """
        # Load user-specific history
        history = await Memory.get_recent_history(user_id)
        
        # Build prompt with context
        current_content = user_input
        if context_data:
            current_content += f"\n\n[外部データ]\n{context_data}\n\n指示: 上記の外部データを使って回答してください。データがない場合は正直に答えてください。"

        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + history
        messages.append({'role': 'user', 'content': current_content})

        # Acquire Lock (Wait if another user is processing)
        async with Brain._lock:
            # 1. Try Main Model
            try:
                print(f"DEBUG: Inference Start (User: {user_id}, Model: {MAIN_TEXT_MODEL})")
                response = await asyncio.to_thread(
                    ollama.chat,
                    model=MAIN_TEXT_MODEL,
                    messages=messages,
                    options={'temperature': 0.7, 'num_thread': 3}, # Limit threads for N100
                    keep_alive='5m'
                )
                return response['message']['content'], MAIN_TEXT_MODEL
            
            except Exception as e:
                # 2. Fallback to Backup Model
                print(f"WARNING: Main Model Failed ({e}). Switching to Backup ({BACKUP_TEXT_MODEL}).")
                try:
                    messages.append({'role': 'system', 'content': '緊急事態: メイン回路ダウン。バックアップモデルで応答してください。'})
                    response = await asyncio.to_thread(
                        ollama.chat,
                        model=BACKUP_TEXT_MODEL,
                        messages=messages,
                        options={'temperature': 0.7, 'num_thread': 3},
                        keep_alive='5m'
                    )
                    reply = f"(予備回路起動: {BACKUP_TEXT_MODEL})\n" + response['message']['content']
                    return reply, BACKUP_TEXT_MODEL
                except Exception as e2:
                    print(f"CRITICAL: Backup Model Failed ({e2})")
                    return "ワオーン... (思考回路が完全にダウンしたワン...)", "Error"

    @staticmethod
    async def see(user_id: int, image_bytes: bytes, user_query: str) -> tuple[str, str]:
        """
        Process image input using Vision Model.
        Returns: (response_text, model_name_used)
        """
        try:
            # Vision inference
            vision_res = await asyncio.to_thread(
                ollama.generate,
                model=MAIN_VISION_MODEL,
                prompt="Describe this image in detail.",
                images=[image_bytes],
                options={'num_thread': 3},
                keep_alive='1m'
            )
            desc = vision_res['response']
            
            # Pass description to Thinking Brain for translation/personality
            translation_prompt = (
                f"画像内容(英): {desc}\n"
                f"ユーザーの質問: {user_query}\n"
                f"指示: 画像の内容を元に、質問に日本語でポコルとして答えて。"
            )
            return await Brain.think(user_id, translation_prompt, "")
        except Exception as e:
            print(f"ERROR: Vision Logic -> {e}")
            return "目がチカチカしてよく見えないワン...", MAIN_VISION_MODEL


# --- Class: Discord Client ---
class PocolBot(discord.Client):
    """Discord Bot Client handling events and status."""
    
    def __init__(self):
        # Enable message content intent
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def set_status_online(self, model_name: str = MAIN_TEXT_MODEL):
        """Set status to Online (Green) with model name."""
        status_text = f"{model_name} (待機中)"
        await self.change_presence(status=discord.Status.online, activity=discord.Game(status_text))

    async def set_status_busy(self, model_name: str = MAIN_TEXT_MODEL):
        """Set status to Do Not Disturb (Red) with model name."""
        status_text = f"{model_name} (思考中...)"
        await self.change_presence(status=discord.Status.dnd, activity=discord.Game(status_text))

    async def on_ready(self):
        """Called when bot is connected."""
        await Memory.init_db()
        await self.set_status_online()
        print(f'--- Pocol Bot Started ---')
        print(f'Logged in as: {self.user}')
        print(f'Models: Main={MAIN_TEXT_MODEL} / Backup={BACKUP_TEXT_MODEL}')

    async def on_message(self, message):
        """Called when a message is received."""
        # Ignore own messages
        if message.author == self.user:
            return

        # Respond only to mentions or DMs
        is_mentioned = self.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)

        if is_mentioned or is_dm:
            # Update status to Busy
            await self.set_status_busy(MAIN_TEXT_MODEL)
            user_id = message.author.id
            
            try:
                async with message.channel.typing():
                    # Clean user input (remove mention)
                    user_text = message.content.replace(f'<@{self.user.id}>', '').strip()

                    # --- Command: Help (Usage Guide) ---
                    if user_text in ["使い方", "ヘルプ", "help", "!help"]:
                        embed = discord.Embed(
                            title="🐶 Pocol (ポコル) の使い方",
                            description="Intel N100搭載の省電力AI Botだワン！\nメンションか返信で話しかけてね。",
                            color=0x00ff00 # Green
                        )
                        embed.add_field(name="🗣️ 会話", value="普通に話しかけると Qwen 2.5 が返事をするよ。", inline=False)
                        embed.add_field(name="🌐 Web検索", value="「ニュース」「調べて」「トレンド」を入れるとネット検索するよ。", inline=False)
                        embed.add_field(name="📷 画像認識", value="画像を貼って「これは何？」と聞くと内容を解説するよ。", inline=False)
                        embed.add_field(name="🛠️ 便利機能", value="「天気」「焼肉」「本」などの単語で専用検索ができるよ。", inline=False)
                        embed.add_field(name="🗑️ 記憶消去", value="「!reset」または「忘れて」で会話ログをリセット！", inline=False)
                        embed.set_footer(text="Powered by Ollama (Qwen/DeepSeek/Moondream)")
                        
                        await message.reply(embed=embed)
                        return
                    
                    # --- Command: Reset Memory ---
                    if user_text in ["!reset", "忘れて"]:
                        await Memory.clear_memory(user_id)
                        await message.reply("記憶を消去したワン！(あなたの分だけだワン)")
                        return

                    # --- Logic: Image Processing ---
                    if message.attachments and message.attachments[0].content_type.startswith('image'):
                        try:
                            img = await message.attachments[0].read()
                            reply, _ = await Brain.see(user_id, img, user_text)
                            await message.reply(reply)
                        except Exception:
                            await message.reply("画像の読み込みに失敗したワン...")
                        return

                    # --- Logic: Tool Selection (Routing) ---
                    context_info = ""
                    
                    # 1. Books (Specific keywords)
                    if "本" in user_text or "書籍" in user_text:
                        context_info = await Tools.search_books(user_text)
                    
                    # 2. Gourmet (Specific keywords)
                    elif any(w in user_text for w in ["店", "ご飯", "ランチ", "ディナー", "焼肉", "ラーメン", "寿司"]):
                        context_info = await Tools.search_gourmet(user_text)
                    
                    # 3. Weather (Specific keywords)
                    elif "天気" in user_text:
                        # Default to Sapporo, override if city mentioned
                        city = "Sapporo"
                        cities = {
                            "東京": "Tokyo", "大阪": "Osaka", "名古屋": "Nagoya",
                            "福岡": "Fukuoka", "沖縄": "Naha", "札幌": "Sapporo"
                        }
                        for k, v in cities.items():
                            if k in user_text:
                                city = v
                                break
                        context_info = await Tools.get_weather(city)
                    
                    # 4. Web Search (Strict keywords to avoid conversational triggers)
                    # "news", "trend", "tell me about...", "search for..."
                    elif any(w in user_text for w in ["ニュース", "トレンド", "とは", "調べて", "検索", "Wiki", "教えて"]):
                        context_info = await Tools.search_web(user_text)

                    # --- Logic: Thinking & Replying ---
                    reply, used_model = await Brain.think(user_id, user_text, context_info)
                    
                    # Update status if backup model was used
                    if used_model != MAIN_TEXT_MODEL:
                        await self.set_status_busy(used_model)

                    # Save to Memory
                    await Memory.add_message(user_id, 'user', user_text)
                    await Memory.add_message(user_id, 'assistant', reply)
                    
                    await message.reply(reply)
            
            except Exception as e:
                print(f"CRITICAL ERROR: {e}")
                await message.reply("システムエラーが発生したワン...")
            
            finally:
                # Always reset status to Online
                await self.set_status_online(MAIN_TEXT_MODEL)


# --- Main Entry Point ---
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN is missing in .env file.")
    else:
        client = PocolBot()
        client.run(TOKEN)