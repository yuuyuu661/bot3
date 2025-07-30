import discord
from discord.ext import commands
from discord import app_commands
import random
import json
from flask import Flask
from threading import Thread

app = Flask(__name__)  # ← これが必要！

@app.route("/")
def home():
    return "Bot is running!", 200

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run).start()
# --- 初期設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- ポケモン図鑑読み込み ---
with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEDEX = {int(k): v for k, v in json.load(f).items()}

# --- ゲーム状態の管理 ---
games = {}  # channel_id: GameState

class GameState:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.participants = set()
        self.scores = {}  # user_id: score
        self.active = False
        self.current_answer = None

class JoinView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="参加します", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = games.get(self.channel_id)
        if not game or game.active:
            await interaction.response.send_message("参加は締め切られました。", ephemeral=True)
            return

        game.participants.add(interaction.user.id)
        await interaction.response.send_message(f"{interaction.user.display_name} が参加しました！", ephemeral=True)

@bot.tree.command(name="quiz_start", description="フュージョンクイズの参加受付を開始します（オーナー専用）")
async def quiz_start(interaction: discord.Interaction):
    if interaction.channel_id in games:
        await interaction.response.send_message("このチャンネルではすでにクイズが開催されています。", ephemeral=True)
        return

    games[interaction.channel_id] = GameState(owner_id=interaction.user.id)
    view = JoinView(channel_id=interaction.channel_id)
    await interaction.response.send_message("ポケモンフュージョンクイズを開始します！\n参加するには以下のボタンを押してください👇", view=view)

@bot.tree.command(name="quiz_begin", description="参加受付を終了し、クイズを開始します（オーナー専用）")
async def quiz_begin(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("このチャンネルではクイズが開始されていません。", ephemeral=True)
        return
    if interaction.user.id != game.owner_id:
        await interaction.response.send_message("このコマンドは主催者のみが使用できます。", ephemeral=True)
        return
    if len(game.participants) < 1:
        await interaction.response.send_message("参加者がいません。開始できません。", ephemeral=True)
        return

    game.active = True
    await interaction.response.send_message("参加受付を終了しました！クイズを開始します！")
    await send_quiz(interaction.channel, game)

async def send_quiz(channel, game: GameState):
    id1 = random.randint(1, 151)
    id2 = random.randint(1, 151)
    image_url = f"https://images.alexonsager.net/pokemon/fused/{id1}/{id1}.{id2}.png"
    game.current_answer = (id1, id2)

    embed = discord.Embed(title="このポケモンは誰と誰のフュージョン？")
    embed.set_image(url=image_url)
    embed.set_footer(text="例: フシギダネ ヒトカゲ のように日本語で回答してください")
    await channel.send(embed=embed)

def normalize(text: str):
    return text.replace("　", " ").replace(" ", "").lower()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = message.channel.id
    game = games.get(channel_id)
    if not game or not game.active:
        return
    if message.author.id not in game.participants:
        return
    if not game.current_answer:
        return

    name1 = POKEDEX.get(game.current_answer[0])
    name2 = POKEDEX.get(game.current_answer[1])
    if not name1 or not name2:
        return

    answer_text = normalize(message.content)
    if normalize(name1) in answer_text and normalize(name2) in answer_text:
        uid = message.author.id
        game.scores[uid] = game.scores.get(uid, 0) + 1
        score = game.scores[uid]
        await message.channel.send(f"🎉 {message.author.display_name} 正解！現在のスコア: {score}")

        if score >= 10:
            await announce_winner(message.channel, game)
            del games[channel_id]
        else:
            game.current_answer = None
            await send_quiz(message.channel, game)

async def announce_winner(channel, game: GameState):
    sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="🏆 クイズ終了！ランキング発表 🏆")
    for i, (user_id, score) in enumerate(sorted_scores, 1):
        member = await channel.guild.fetch_member(user_id)
        embed.add_field(name=f"{i}位：{member.display_name}", value=f"{score}ポイント", inline=False)
    await channel.send(embed=embed)

@bot.tree.command(name="quiz_ranking", description="現在のクイズのスコアランキングを表示します")
async def quiz_ranking(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game or not game.active:
        await interaction.response.send_message("現在クイズは実行されていません。", ephemeral=True)
        return
    if not game.scores:
        await interaction.response.send_message("まだ得点がありません。", ephemeral=True)
        return

    sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="📊 現在のランキング")
    for i, (user_id, score) in enumerate(sorted_scores, 1):
        member = await interaction.guild.fetch_member(user_id)
        embed.add_field(name=f"{i}位：{member.display_name}", value=f"{score}ポイント", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="quiz_stop", description="クイズを強制終了して、途中までのランキングを表示します（主催者専用）")
async def quiz_stop(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("このチャンネルではクイズが実行されていません。", ephemeral=True)
        return
    if interaction.user.id != game.owner_id:
        await interaction.response.send_message("このコマンドは主催者のみ使用できます。", ephemeral=True)
        return

    await interaction.response.send_message("クイズを中断しました。現在のランキングを表示します。")
    await announce_winner(interaction.channel, game)
    del games[interaction.channel_id]

@bot.tree.command(name="quiz_skip", description="現在の問題をスキップして、次の問題を出題します（主催者専用）")
async def quiz_skip(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game or not game.active:
        await interaction.response.send_message("クイズは現在行われていません。", ephemeral=True)
        return
    if interaction.user.id != game.owner_id:
        await interaction.response.send_message("このコマンドは主催者のみ使用できます。", ephemeral=True)
        return

    game.current_answer = None
    await interaction.response.send_message("現在の問題をスキップしました。次の問題を出題します。")
    await send_quiz(interaction.channel, game)

@app.route("/")
def home():
    return "Bot is running!", 200

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run).start()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot connected as {bot.user}")

bot.run("YOUR_BOT_TOKEN")
