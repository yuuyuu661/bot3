import discord
from discord.ext import commands
import asyncio
import os

# ====================== 設定 ======================
intents = discord.Intents.default()
intents.message_content = True  # 必要に応じて
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # デフォルトヘルプを無効化
)

# ====================== 起動処理 ======================
@bot.event
async def on_ready():
    print(f"✅ Botが正常に起動しました！")
    print(f"Bot名: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    try:
        synced = await bot.tree.sync()
        print(f"スラッシュコマンド同期完了: {len(synced)}個")
    except Exception as e:
        print(f"コマンド同期エラー: {e}")

# ====================== メイン関数 ======================
async def main():
    try:
        # Cogの読み込み
        await bot.load_extension("cogs.slot")
        print("🔧 スロットCogをロードしました")
        
        # Bot起動
        print("🚀 Botを起動しています...")
        await bot.start("MTQ5NTcxMjMxOTU3MjAxNzIzMw.GaLp28.U8sCuTHQ0ilYW6WPsRVHAlprGXyjEhQYE6Bo8U")
        
    except discord.LoginFailure:
        print("❌ トークンが無効です。正しいトークンを貼り付けてください。")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

# ====================== 実行 ======================
if __name__ == "__main__":
    asyncio.run(main())