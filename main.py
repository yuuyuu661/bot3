import discord
from discord.ext import commands
from discord import app_commands
import random
import json
import os
from keep_alive import keep_alive  # Flaskサーバーを別ファイルから読み込み

# --- Discord Bot設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEDEX = {int(k): v for k, v in json.load(f).items()}

games = {}

class GameState:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.participants = set()
        self.scores = {}
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

@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.add_view(JoinView(None))  # <-- これを追加！
    print(f"Bot connected as {bot.user}")

keep_alive()  # Flaskサーバー起動

bot.run(os.environ["DISCORD_TOKEN"])
