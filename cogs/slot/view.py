# cogs/slot/view.py
import discord
from discord.ui import View, button
from .database import db
from .engine import SlotEngine
import asyncio
import random

def create_panel_embed():
    embed = discord.Embed(
        title="🎰 スロットマシン 🎰",
        description="**スロットで運試し！**\n下のボタンからプレイできます！",
        color=0x6B00B6
    )
    embed.add_field(name="🎮 遊び方", value="ベットを選択 → 🎰 スピン", inline=False)
    embed.add_field(name="🎯 絵柄と倍率", value="🍋0.5× 🍒0.9× 🍀1.2× 🔔1.5× 💰3.0× 💎7.0× 7️⃣10.0×", inline=False)
    embed.set_footer(text="結果は個人メッセージでお届けします")
    return embed


class SlotView(View):
    def __init__(self, bot: discord.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.spinning = set()

    # ベットボタン
    @button(label="1,000", style=discord.ButtonStyle.gray, custom_id="slot:bet:1000", row=0)
    async def bet_1000(self, interaction: discord.Interaction, btn):
        await self._set_bet(interaction, 1000)

    @button(label="5,000", style=discord.ButtonStyle.gray, custom_id="slot:bet:5000", row=0)
    async def bet_5000(self, interaction: discord.Interaction, btn):
        await self._set_bet(interaction, 5000)

    @button(label="10,000", style=discord.ButtonStyle.gray, custom_id="slot:bet:10000", row=0)
    async def bet_10000(self, interaction: discord.Interaction, btn):
        await self._set_bet(interaction, 10000)

    @button(label="50,000", style=discord.ButtonStyle.gray, custom_id="slot:bet:50000", row=1)
    async def bet_50000(self, interaction: discord.Interaction, btn):
        await self._set_bet(interaction, 50000)

    @button(label="100,000", style=discord.ButtonStyle.gray, custom_id="slot:bet:100000", row=1)
    async def bet_100000(self, interaction: discord.Interaction, btn):
        await self._set_bet(interaction, 100000)

    @button(label="🎰 スピン", style=discord.ButtonStyle.green, custom_id="slot:spin", row=2)
    async def spin(self, interaction: discord.Interaction, btn):
        await self.do_spin(interaction)

    @button(label="💰 所持金", style=discord.ButtonStyle.blurple, custom_id="slot:balance", row=2)
    async def check_balance(self, interaction: discord.Interaction, btn):
        user_data = await db.get_user(str(interaction.user.id))
        await interaction.response.send_message(f"**現在の所持金**\n**{user_data['balance']:,}** コイン", ephemeral=True)

    async def _set_bet(self, interaction: discord.Interaction, amount: int):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data["balance"] < amount:
            return await interaction.response.send_message("❌ 残高が不足しています！", ephemeral=True)
        
        user_data["current_bet"] = amount
        await db.update_user(str(interaction.user.id), current_bet=amount)
        await interaction.response.send_message(f"✅ **ベット額を {amount:,} コイン** に設定しました", ephemeral=True)

    # ====================== 左から止まる＋停止時揺れアニメ ======================
    async def do_spin(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.spinning:
            return await interaction.response.send_message("現在スピン中です...", ephemeral=True)

        self.spinning.add(user_id)
        try:
            user_data = await db.get_user(user_id)
            bet = user_data["current_bet"]

            if user_data["balance"] < bet:
                return await interaction.response.send_message("❌ 残高が足りません！", ephemeral=True)

            await interaction.response.defer(ephemeral=True)

            user_data["balance"] -= bet
            await db.update_user(user_id, balance=user_data["balance"])

            temp_msg = await interaction.followup.send("🎰 **スロット回転開始！**", ephemeral=True)

            # 高速回転
            for i in range(8):
                temp_grid = SlotEngine.generate_grid()
                grid_text = "\n".join(" ".join(row) for row in temp_grid)
                embed = discord.Embed(title=f"🎰 高速回転中... {i+1}/8", description=grid_text, color=0xFFFF00)
                await temp_msg.edit(embed=embed)
                await asyncio.sleep(0.25)

            # 最終結果生成
            final_grid = SlotEngine.generate_grid()
            current_grid = [row[:] for row in final_grid]

            # 左から1列ずつ停止 + 揺れ演出
            for col in range(5):
                # その列を最終結果に固定
                for row in range(3):
                    current_grid[row][col] = final_grid[row][col]

                # 停止時の揺れアニメーション（3回軽く揺らす）
                for shake in range(3):
                    # 少しだけシンボルをずらして揺れを表現
                    display_grid = [row[:] for row in current_grid]
                    if shake % 2 == 1:  # 奇数回で軽く揺らす
                        for r in range(3):
                            if random.random() < 0.4:
                                display_grid[r][col] = random.choice(SlotEngine.generate_grid()[0])

                    grid_text = "\n".join(" ".join(row) for row in display_grid)
                    embed = discord.Embed(
                        title=f"🎰 {col+1}列目 停止中...",
                        description=grid_text,
                        color=0xFFAA00
                    )
                    embed.set_footer(text=f"━━━━━━━ {col+1}/5 列が止まりました ━━━━━━━")
                    await temp_msg.edit(embed=embed)
                    await asyncio.sleep(0.12)

                await asyncio.sleep(0.45)  # 次の列へ移る間隔

            # 結果判定
            payout, _ = SlotEngine.calculate_payout(final_grid, bet)
            jp_win = SlotEngine.check_jackpot(user_data, bet)
            total_win = jp_win if jp_win > 0 else payout

            user_data["balance"] += total_win
            await db.update_user(user_id, balance=user_data["balance"], jp_gauge=user_data.get("jp_gauge", 0))

            # JP当選時
            if jp_win > 0:
                jp_embed = discord.Embed(title="🎉💎 JACKPOT!!! 💎🎉", description="**前面が全て同じシンボルになりました！**", color=0xFFD700)
                jackpot_symbol = final_grid[0][0]
                jp_grid = [[jackpot_symbol] * 5 for _ in range(3)]
                jp_text = "\n".join(" ".join(row) for row in jp_grid)
                jp_embed.add_field(name="リール", value=jp_text, inline=False)
                jp_embed.add_field(name="報酬", value=f"**+{jp_win:,} コイン**", inline=False)
                await temp_msg.edit(embed=jp_embed)
                await asyncio.sleep(2.5)

            # 通常結果
            if jp_win == 0:
                color = 0x00FF00 if total_win > 0 else 0xFF0000
                result_embed = discord.Embed(title="🎰 スピン結果", color=color)
                grid_text = "\n".join(" ".join(row) for row in final_grid)
                result_embed.add_field(name="リール結果", value=grid_text, inline=False)
                if total_win > 0:
                    result_embed.add_field(name="💎 獲得", value=f"**+{total_win:,} コイン！**", inline=False)
                else:
                    result_embed.add_field(name="結果", value="**残念… 次こそ当たるかも！**", inline=False)
                result_embed.set_footer(text=f"現在の残高: {user_data['balance']:,} コイン")
                await temp_msg.edit(embed=result_embed)

            # パネル更新
            await interaction.message.edit(embed=create_panel_embed(), view=self)

        finally:
            self.spinning.discard(user_id)