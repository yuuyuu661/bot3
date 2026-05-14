# cogs/slot/cog.py
import discord
from discord import app_commands
from discord.ext import commands
from .view import SlotView, create_panel_embed
from .database import db   # ← ここを追加
GUILD_ID = 1420918259187712093

@app_commands.guilds(discord.Object(id=GUILD_ID))
class SlotCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.view = SlotView(bot)

    @app_commands.command(name="panel", description="スロットパネルを設置")
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = create_panel_embed()
        await interaction.followup.send(embed=embed, view=self.view)

    @app_commands.command(name="panel_resend", description="パネルを再送信")
    @app_commands.default_permissions(administrator=True)
    async def panel_resend(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = create_panel_embed()
        await interaction.followup.send(embed=embed, view=self.view)

    # ====================== 所持金編集コマンド ======================
    @app_commands.command(name="addmoney", description="ユーザーの所持金を増やす（管理者用）")
    @app_commands.default_permissions(administrator=True)
    async def addmoney(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ 金額は1以上を指定してください。", ephemeral=True)

        user_data = await db.get_user(str(user.id))
        old_balance = user_data["balance"]
        user_data["balance"] += amount
        
        await db.update_user(str(user.id), balance=user_data["balance"])

        await interaction.response.send_message(
            f"✅ **{user.mention}** の所持金を **{amount:,}** コイン追加しました。\n"
            f"{old_balance:,} → **{user_data['balance']:,}** コイン",
            ephemeral=False
        )

    @app_commands.command(name="setmoney", description="ユーザーの所持金を直接設定（管理者用）")
    @app_commands.default_permissions(administrator=True)
    async def setmoney(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if amount < 0:
            return await interaction.response.send_message("❌ 金額は0以上にしてください。", ephemeral=True)

        await db.update_user(str(user.id), balance=amount)

        await interaction.response.send_message(
            f"✅ **{user.mention}** の所持金を **{amount:,}** コイン に設定しました。",
            ephemeral=False
        )

    # 現在の所持金確認コマンド（おまけ）
    @app_commands.command(name="bal", description="指定ユーザーの所持金を確認")
    @app_commands.default_permissions(administrator=True)
    async def bal(self, interaction: discord.Interaction, user: discord.Member):
        user_data = await db.get_user(str(user.id))
        await interaction.response.send_message(
            f"**{user.mention}** の所持金\n**{user_data['balance']:,}** コイン",
            ephemeral=False
        )

