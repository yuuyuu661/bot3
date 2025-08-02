import discord
from discord.ext import commands
from discord import app_commands
import random
import json
import os
from keep_alive import keep_alive  # Flaskサーバーを別ファイルから読み込み
import asyncio
from datetime import datetime, timedelta

# 必要に応じて先頭で定義しておく
POKER_LOG_CHANNEL_ID = 1399363982552338576
POKER_BOT_NAME = "キバ#5711"
ENTRY_FEE = 1000
CURRENCY_UNIT = "spt"
PAY_COMMAND_PREFIX = "/pay"  # VirtualCryptoのコマンド

# --- Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEDEX = {int(k): v for k, v in json.load(f).items()}

games = {}
POKER_GAMES = {}  # チャンネルIDごとのポーカー状態

class PokerGameState:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.players = []  # 順番を保持するためリスト
        self.started = False

class GameState:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.participants = set()
        self.scores = {}
        self.active = False
        self.current_answer = None

class JoinView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)  # 永続Viewにするための条件1
        self.channel_id = channel_id

    @discord.ui.button(label="参加します", style=discord.ButtonStyle.success, custom_id="join_quiz_button")  # 条件2
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = games.get(self.channel_id)
        if not game or game.active:
            await interaction.response.send_message("参加は締め切られました。", ephemeral=True)
            return
        game.participants.add(interaction.user.id)
        await interaction.response.send_message(f"{interaction.user.display_name} が参加しました！", ephemeral=True)
class PokerJoinView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="参加する", style=discord.ButtonStyle.primary, custom_id="poker_join_button")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = POKER_GAMES.get(self.channel_id)
        if not game or game.started:
            await interaction.response.send_message("現在このチャンネルでは参加できません。", ephemeral=True)
            return

        if interaction.user.id in [p.id for p in game.players]:
            await interaction.response.send_message("すでに参加しています。", ephemeral=True)
            return

        game.players.append(interaction.user)
        await interaction.response.send_message(f"{interaction.user.display_name} さんが参加しました！", ephemeral=True)
        await interaction.channel.send(f"🃏 {interaction.user.mention} さんがポーカーに参加しました！")


@bot.tree.command(name="quiz_start")
async def quiz_start(interaction: discord.Interaction):
    if interaction.channel_id in games:
        await interaction.response.send_message("このチャンネルではすでにクイズが開催されています。", ephemeral=True)
        return
    games[interaction.channel_id] = GameState(owner_id=interaction.user.id)
    view = JoinView(channel_id=interaction.channel_id)
    await interaction.response.send_message("ポケモンフュージョンクイズを開始します！\n参加するには以下のボタンを押してください👇", view=view)

@bot.tree.command(name="quiz_begin")
async def quiz_begin(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("クイズが開始されていません。", ephemeral=True)
        return
    if interaction.user.id != game.owner_id:
        await interaction.response.send_message("このコマンドは主催者のみ使用できます。", ephemeral=True)
        return
    if not game.participants:
        await interaction.response.send_message("参加者がいません。", ephemeral=True)
        return
    game.active = True
    await interaction.response.send_message("クイズを開始します！")
    await send_quiz(interaction.channel, game)

async def send_quiz(channel, game):
    id1 = random.randint(1, 151)
    id2 = random.randint(1, 151)
    url = f"https://images.alexonsager.net/pokemon/fused/{id1}/{id1}.{id2}.png"
    game.current_answer = (id1, id2)
    embed = discord.Embed(title="このポケモンは誰と誰のフュージョン？")
    embed.set_image(url=url)
    embed.set_footer(text="例: フシギダネ ヒトカゲ のように日本語で回答してください")
    await channel.send(embed=embed)

def normalize(text):
    return text.replace("　", " ").replace(" ", "").lower()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    game = games.get(message.channel.id)
    if not game or not game.active:
        return
    if message.author.id not in game.participants:
        return
    name1 = POKEDEX.get(game.current_answer[0])
    name2 = POKEDEX.get(game.current_answer[1])
    if normalize(name1) in normalize(message.content) and normalize(name2) in normalize(message.content):
        uid = message.author.id
        game.scores[uid] = game.scores.get(uid, 0) + 1
        await message.channel.send(f"🎉 {message.author.display_name} 正解！ 現在のスコア: {game.scores[uid]}")
        if game.scores[uid] >= 10:
            await announce_winner(message.channel, game)
            del games[message.channel.id]
        else:
            game.current_answer = None
            await send_quiz(message.channel, game)

async def announce_winner(channel, game):
    sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="🏆 クイズ終了！ランキング発表 🏆")
    for i, (uid, score) in enumerate(sorted_scores, 1):
        member = await channel.guild.fetch_member(uid)
        embed.add_field(name=f"{i}位：{member.display_name}", value=f"{score}ポイント", inline=False)
    await channel.send(embed=embed)

@bot.tree.command(name="quiz_ranking")
async def quiz_ranking(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game or not game.scores:
        await interaction.response.send_message("ランキングはまだありません。", ephemeral=True)
        return
    sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="📊 現在のランキング")
    for i, (uid, score) in enumerate(sorted_scores, 1):
        member = await interaction.guild.fetch_member(uid)
        embed.add_field(name=f"{i}位：{member.display_name}", value=f"{score}ポイント", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="quiz_stop")
async def quiz_stop(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("クイズは実行されていません。", ephemeral=True)
        return
    await interaction.response.send_message("クイズを中断します。現在のランキングはこちら：")
    await announce_winner(interaction.channel, game)
    del games[interaction.channel_id]

@bot.tree.command(name="quiz_skip")
async def quiz_skip(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game or not game.active:
        await interaction.response.send_message("クイズは現在行われていません。", ephemeral=True)
        return
    if interaction.user.id != game.owner_id:
        await interaction.response.send_message("このコマンドは主催者のみ使用できます。", ephemeral=True)
        return
    game.current_answer = None
    await interaction.response.send_message("問題をスキップしました。次の問題を出題します。")
    await send_quiz(interaction.channel, game)
@bot.tree.command(name="poker_join", description="ポーカーの参加者を募集します")
async def poker_join(interaction: discord.Interaction):
    if interaction.channel_id in POKER_GAMES:
        await interaction.response.send_message("このチャンネルではすでにポーカーが開催中です。", ephemeral=True)
        return

    POKER_GAMES[interaction.channel_id] = PokerGameState(owner_id=interaction.user.id)
    view = PokerJoinView(channel_id=interaction.channel_id)
    await interaction.response.send_message("ポーカーゲームを開始しました！\n参加するには以下のボタンを押してください👇", view=view)    
@bot.tree.command(name="poker_start", description="ポーカーを開始（主催者のみ）", guild=discord.Object(id=1398607685158440991))
async def poker_start(interaction: discord.Interaction):
    game = POKER_GAMES.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("このチャンネルではポーカーがまだ始まっていません。", ephemeral=True)
        return
    if interaction.user.id != game.owner_id:
        await interaction.response.send_message("このコマンドは主催者のみ使用できます。", ephemeral=True)
        return
    if len(game.players) < 2:
        await interaction.response.send_message("参加者が2人以上必要です。", ephemeral=True)
        return

    await interaction.response.send_message(f"🎮 ポーカーを開始します！\n参加費は **{ENTRY_FEE}{CURRENCY_UNIT}** です。\n3分以内に `{PAY_COMMAND_PREFIX} {POKER_BOT_NAME} {ENTRY_FEE}` を実行してください。")

    await verify_payments(interaction.channel, game)

async def verify_payments(channel, game):
    log_channel = bot.get_channel(POKER_LOG_CHANNEL_ID)
    if log_channel is None:
        await channel.send("⚠️ ログチャンネルが見つかりません。")
        return

    await asyncio.sleep(180)  # 3分待機
    after_time = datetime.utcnow() - timedelta(minutes=3)
    messages = [m async for m in log_channel.history(limit=200, after=after_time)]

    paid_user_ids = set()
    for msg in messages:
        if msg.author.name != "VirtualCrypto":
            continue
        if f"{ENTRY_FEE} {CURRENCY_UNIT}" in msg.content and POKER_BOT_NAME in msg.content:
            for player in game.players:
                if player.display_name in msg.content or player.mention in msg.content:
                    paid_user_ids.add(player.id)

    remaining_players = [p for p in game.players if p.id in paid_user_ids]
    removed_players = [p for p in game.players if p.id not in paid_user_ids]

    game.players = remaining_players

    if removed_players:
        names = ", ".join(p.display_name for p in removed_players)
        await channel.send(f"⏰ 支払い未確認のため、次のプレイヤーは除外されました: {names}")

    if len(game.players) < 2:
        await channel.send("参加者が2人未満のため、ゲームはキャンセルされました。")
        del POKER_GAMES[channel.id]
        return

    await channel.send(f"✅ 支払い確認完了！参加者数: {len(game.players)}人\nゲームを進行します...")
    # ここにゲーム進行処理を続けて実装（後ほど）
import uuid

SESSION_DATA = {}

@bot.tree.command(name="slot", description="スロットゲームを開始します")
@app_commands.describe(coins="初期コイン数（例：100）")
async def slot(interaction: discord.Interaction, coins: int):
    if coins <= 0:
        await interaction.response.send_message("コイン数は1以上にしてください。", ephemeral=True)
        return

    session_id = str(uuid.uuid4())
    SESSION_DATA[session_id] = {
        "user_id": interaction.user.id,
        "coins": coins,
        "expires_at": datetime.utcnow() + timedelta(minutes=10)
    }

    slot_url = f"https://slot-production-be36.up.railway.app/?session={session_id}"
    await interaction.response.send_message(
        f"🎰 スロットゲームを開始します！\n[こちらからプレイ](<{slot_url}>)",
        ephemeral=True
    )

@bot.event
async def on_ready():
    bot.add_view(JoinView(None))         
    bot.add_view(PokerJoinView(None))    
    await bot.tree.sync(guild=discord.Object(id=1398607685158440991))  # ギルドID指定で確実に同期
    print(f"Bot connected as {bot.user}")


keep_alive()  # Flaskサーバー起動

bot.run(os.environ["DISCORD_TOKEN"])


