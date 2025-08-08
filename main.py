import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import json
import os
from keep_alive import keep_alive  # Flaskサーバーを別ファイルから読み込み
import asyncio
from datetime import datetime, timedelta, timezone

# ========= 基本設定 =========
ENTRY_FEE = 1000
CURRENCY_UNIT = "spt"
PAY_COMMAND_PREFIX = "/pay"  # VirtualCryptoのコマンド

# Guild 固定
GUILD_ID = 1398607685158440991

# 管理ロール（このロールだけが一部コマンド実行可）
ADMIN_ROLE_ID = 1398724601256874014

# タイムゾーン（JST）
JST = timezone(timedelta(hours=9), name="Asia/Tokyo")

# ========= Discord Bot 初期化 =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========= メモリ管理（クイズ／VCスケジュール） =========
games = {}
with open("pokedex.json", "r", encoding="utf-8") as f:
    POKEDEX = {int(k): v for k, v in json.load(f).items()}

class GameState:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.participants = set()
        self.scores = {}
        self.active = False
        self.current_answer = None

# 作成したプライベートVCの情報を保持
# { channel_id: {"owner_id": int, "start": datetime, "end": datetime} }
PRIVATE_VC: dict[int, dict] = {}

# ========= 共通ユーティリティ =========
def requires_admin_role():
    """指定ロール必須のチェックデコレータ"""
    def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        return isinstance(member, discord.Member) and any(r.id == ADMIN_ROLE_ID for r in member.roles)
    return app_commands.check(predicate)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        try:
            await interaction.response.send_message(
                "このコマンドは指定ロールのメンバーのみ実行できます。", ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                "このコマンドは指定ロールのメンバーのみ実行できます。", ephemeral=True
            )

def parse_period_str(period: str) -> tuple[datetime, datetime]:
    """
    'YYYY-MM-DD-HH:MM～YYYY-MM-DD-HH:MM'（全角/半角チルダ両対応）をJSTでdatetimeに。
    """
    s = period.replace("~", "～")
    if "～" not in s:
        raise ValueError("区切りの『～』が見つかりません。")
    start_s, end_s = [x.strip() for x in s.split("～", 1)]
    fmt = "%Y-%m-%d-%H:%M"
    start = datetime.strptime(start_s, fmt).replace(tzinfo=JST)
    end = datetime.strptime(end_s, fmt).replace(tzinfo=JST)
    if end <= start:
        raise ValueError("終了は開始より後の日時を指定してください。")
    return start, end

def parse_point_str(point: str) -> datetime:
    """
    'YYYY-MM-DD-HH:MM' をJSTでdatetimeに。
    """
    fmt = "%Y-%m-%d-%H:%M"
    dt = datetime.strptime(point.strip(), fmt).replace(tzinfo=JST)
    return dt

# ========= クイズ参加ボタン =========
class JoinView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)  # 永続View
        self.channel_id = channel_id

    @discord.ui.button(label="参加します", style=discord.ButtonStyle.success, custom_id="join_quiz_button")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = games.get(self.channel_id)
        if not game or game.active:
            await interaction.response.send_message("参加は締め切られました。", ephemeral=True)
            return
        game.participants.add(interaction.user.id)
        await interaction.response.send_message(f"{interaction.user.display_name} が参加しました！", ephemeral=True)

# ========= クイズ系コマンド =========
@bot.tree.command(name="quiz_start", guild=discord.Object(id=GUILD_ID))
async def quiz_start(interaction: discord.Interaction):
    if interaction.channel_id in games:
        await interaction.response.send_message("このチャンネルではすでにクイズが開催されています。", ephemeral=True)
        return
    games[interaction.channel_id] = GameState(owner_id=interaction.user.id)
    view = JoinView(channel_id=interaction.channel_id)
    await interaction.response.send_message("ポケモンフュージョンクイズを開始します！\n参加するには以下のボタンを押してください👇", view=view)

@bot.tree.command(name="quiz_begin", guild=discord.Object(id=GUILD_ID))
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
    if game and game.active and message.author.id in game.participants:
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

    # ✅ 常に最後に入れること
    await bot.process_commands(message)

async def announce_winner(channel, game):
    sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title="🏆 クイズ終了！ランキング発表 🏆")
    for i, (uid, score) in enumerate(sorted_scores, 1):
        member = await channel.guild.fetch_member(uid)
        embed.add_field(name=f"{i}位：{member.display_name}", value=f"{score}ポイント", inline=False)
    await channel.send(embed=embed)

@bot.tree.command(name="quiz_ranking", guild=discord.Object(id=GUILD_ID))
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

@bot.tree.command(name="quiz_stop", guild=discord.Object(id=GUILD_ID))
async def quiz_stop(interaction: discord.Interaction):
    game = games.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("クイズは実行されていません。", ephemeral=True)
        return
    await interaction.response.send_message("クイズを中断します。現在のランキングはこちら：")
    await announce_winner(interaction.channel, game)
    del games[interaction.channel_id]

@bot.tree.command(name="quiz_skip", guild=discord.Object(id=GUILD_ID))
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

# ========= 追加：運営コマンド（ロール制限対象） =========

@bot.tree.command(name="delete_range", description="指定期間（YYYY-MM-DD-HH:MM～YYYY-MM-DD-HH:MM）のメッセージを削除", guild=discord.Object(id=GUILD_ID))
@requires_admin_role()
@app_commands.describe(period="例: 2025-08-08-21:00～2025-08-08-22:30")
async def delete_range(interaction: discord.Interaction, period: str):
    """コマンド実行チャンネルの期間内メッセージを削除"""
    channel: discord.TextChannel = interaction.channel  # 実行チャンネル対象
    # 権限チェック
    me = interaction.guild.me
    if not channel.permissions_for(me).manage_messages:
        await interaction.response.send_message("Botに『メッセージの管理』権限が必要です。", ephemeral=True)
        return
    if not channel.permissions_for(interaction.user).manage_messages:
        await interaction.response.send_message("あなたに『メッセージの管理』権限が必要です。", ephemeral=True)
        return

    try:
        start, end = parse_period_str(period)
    except Exception as e:
        await interaction.response.send_message(f"日時の解釈に失敗しました：{e}", ephemeral=True)
        return

    await interaction.response.send_message(f"🧹 削除を開始します…（{start.strftime('%Y-%m-%d %H:%M')} ～ {end.strftime('%Y-%m-%d %H:%M')} JST）", ephemeral=True)

    # Discordの一括削除は14日以内のみ。範囲を2つに分割して処理。
    now = datetime.now(JST)
    bulk_limit_dt = now - timedelta(days=14)

    deleted = 0

    async def delete_iter(before: datetime, after: datetime):
        nonlocal deleted
        async for msg in channel.history(limit=None, before=before, after=after, oldest_first=True):
            try:
                await msg.delete()
                deleted += 1
                # 速すぎ対策で少し待つ（レート制限よけ）
                await asyncio.sleep(0.1)
            except Exception:
                # 削除不能メッセージなどは無視
                await asyncio.sleep(0.05)

    # ① 直近14日以内の部分
    part1_after = max(start, bulk_limit_dt)
    if end > bulk_limit_dt:
        try:
            purged = await channel.purge(limit=None, after=part1_after, before=end, bulk=True)
            deleted += len(purged)
        except Exception:
            # 失敗時は1件ずつ
            await delete_iter(before=end, after=part1_after)

    # ② 14日より前の部分は個別削除
    if start < bulk_limit_dt:
        await delete_iter(before=min(end, bulk_limit_dt), after=start)

    try:
        await interaction.followup.send(f"✅ 削除完了：{deleted} 件", ephemeral=True)
    except discord.InteractionResponded:
        pass

@bot.tree.command(name="create_private_vc", description="期間付きプライベートVCを作成", guild=discord.Object(id=GUILD_ID))
@requires_admin_role()
@app_commands.describe(target_user="初期メンバーに追加するユーザー", period="例: 2025-08-08-21:00～2025-08-09-00:00")
async def create_private_vc(interaction: discord.Interaction, target_user: discord.Member, period: str):
    """指定期間だけ存在するプライベートVCを作る"""
    try:
        start, end = parse_period_str(period)
    except Exception as e:
        await interaction.response.send_message(f"日時の解釈に失敗しました：{e}", ephemeral=True)
        return

    guild = interaction.guild
    me = guild.me

    # 権限前提チェック
    if not guild.me.guild_permissions.manage_channels:
        await interaction.response.send_message("Botに『チャンネルの管理』権限が必要です。", ephemeral=True)
        return

    # VC名
    vc_name = f"private-{interaction.user.display_name}"

    # 権限オーバーライト
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True),
        interaction.user: discord.PermissionOverwrite(view_channel=True, connect=True),
        target_user: discord.PermissionOverwrite(view_channel=True, connect=True),
    }

    # VC作成
    vc = await guild.create_voice_channel(name=vc_name, overwrites=overwrites, reason="期間付きプライベートVC")
    PRIVATE_VC[vc.id] = {"owner_id": interaction.user.id, "start": start, "end": end}

    msg = (
        f"✅ プライベートVCを作成しました：{vc.mention}\n"
        f"期間：{start.strftime('%Y-%m-%d %H:%M')} ～ {end.strftime('%Y-%m-%d %H:%M')} JST\n"
        f"オーナー：{interaction.user.mention}（このVCにいる状態で `/add_vc_user` 実行でユーザー追加できます）"
    )
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="update_vc_time", description="プライベートVCの期間を上書き", guild=discord.Object(id=GUILD_ID))
@requires_admin_role()
@app_commands.describe(channel_id="対象VCのチャンネルID", period="例: 2025-08-08-21:00～2025-08-09-00:00")
async def update_vc_time(interaction: discord.Interaction, channel_id: str, period: str):
    try:
        ch_id = int(channel_id)
    except ValueError:
        await interaction.response.send_message("channel_id は数値で指定してください。", ephemeral=True)
        return

    try:
        start, end = parse_period_str(period)
    except Exception as e:
        await interaction.response.send_message(f"日時の解釈に失敗しました：{e}", ephemeral=True)
        return

    channel = interaction.guild.get_channel(ch_id)
    if channel is None or not isinstance(channel, discord.VoiceChannel):
        await interaction.response.send_message("指定のチャンネルが見つからないか、ボイスチャンネルではありません。", ephemeral=True)
        return

    if ch_id not in PRIVATE_VC:
        # 既存VCでも強制的に管理対象にする（必要なら拒否にしてもOK）
        PRIVATE_VC[ch_id] = {"owner_id": interaction.user.id, "start": start, "end": end}
    else:
        PRIVATE_VC[ch_id]["start"] = start
        PRIVATE_VC[ch_id]["end"] = end

    await interaction.response.send_message(
        f"✅ 期間を更新しました：{channel.mention}\n"
        f"{start.strftime('%Y-%m-%d %H:%M')} ～ {end.strftime('%Y-%m-%d %H:%M')} JST",
        ephemeral=True
    )

# ========= 追加：/add_vc_user（チャンネル指定なし・入室中VCを自動判定） =========
@bot.tree.command(name="add_vc_user", description="現在入っているプライベートVCにユーザーを追加", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="追加したいユーザー")
async def add_vc_user(interaction: discord.Interaction, user: discord.Member):
    member: discord.Member = interaction.user  # 実行者
    if not member.voice or not member.voice.channel:
        await interaction.response.send_message("まず対象のVCに参加してください。", ephemeral=True)
        return

    vc = member.voice.channel
    # PRIVATE_VC 管理対象か確認（作成済みや手動登録済み）
    info = PRIVATE_VC.get(vc.id)
    # 管理対象でなくても「オーナー判定」をゆるくしたくなければここで弾く
    if info is None:
        await interaction.response.send_message("このVCは管理対象ではありません。", ephemeral=True)
        return

    # 権限：オーナー or チャンネル管理権限所持者のみ
    is_owner = info["owner_id"] == member.id
    can_manage = member.guild_permissions.manage_channels
    if not (is_owner or can_manage):
        await interaction.response.send_message("このVCのオーナー、または『チャンネルの管理』権限が必要です。", ephemeral=True)
        return

    try:
        await vc.set_permissions(user, view_channel=True, connect=True)
        await interaction.response.send_message(f"✅ 追加しました：{user.mention} → {vc.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("権限の設定に失敗しました（Botに『チャンネルの管理』権限が必要です）。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"エラー：{e}", ephemeral=True)

# ========= 自動削除ループ =========
@tasks.loop(minutes=1)
async def vc_cleanup_task():
    """終了時刻を過ぎたプライベートVCを自動削除"""
    if not bot.is_ready():
        return
    now = datetime.now(JST)
    to_delete = []
    for ch_id, meta in list(PRIVATE_VC.items()):
        end: datetime = meta["end"]
        if now >= end:
            to_delete.append(ch_id)

    for ch_id in to_delete:
        try:
            ch = bot.get_channel(ch_id)
            if isinstance(ch, discord.VoiceChannel):
                await ch.delete(reason="期間満了のため自動削除")
        except Exception:
            pass
        finally:
            PRIVATE_VC.pop(ch_id, None)
        await asyncio.sleep(0.2)  # 連続削除のスロットリング

# ========= 起動時処理 =========
@bot.event
async def on_ready():
    bot.add_view(JoinView(None))  # クイズ用ボタンだけ残す
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    if not vc_cleanup_task.is_running():
        vc_cleanup_task.start()
    print(f"✅ Bot connected as {bot.user}")

@bot.command()
async def sync(ctx):
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ コマンドを再同期しました")

# ========= 起動 =========
keep_alive()
bot.run(os.environ["DISCORD_TOKEN"])
