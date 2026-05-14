import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

# ====================== .env読み込み ======================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# ====================== 設定 ======================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)
GUILD_ID = 1420918259187712093
GUILD_OBJ = discord.Object(id=GUILD_ID)

# ====================== 起動処理 ======================
@bot.event
async def on_ready():
    print(f"✅ Botが正常に起動しました！")
    print(f"Bot名: {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    try:
        synced = await bot.tree.sync(guild=GUILD_OBJ)
        print(f"スラッシュコマンド同期完了: {len(synced)}個")

    except Exception as e:
        print(f"コマンド同期エラー: {e}")

# ====================== メイン関数 ======================
async def main():

    try:
        # Cog読み込み
        await bot.load_extension("cogs.slot")
        print("🔧 スロットCogをロードしました")

        # Token確認
        if not TOKEN:
            raise ValueError("DISCORD_TOKEN が設定されていません")

        # Bot起動
        print("🚀 Botを起動しています...")
        await bot.start(TOKEN)

    except discord.LoginFailure:
        print("❌ トークンが無効です")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")

    finally:
        if not bot.is_closed():
            await bot.close()

# ====================== 実行 ======================
if __name__ == "__main__":
    asyncio.run(main())
