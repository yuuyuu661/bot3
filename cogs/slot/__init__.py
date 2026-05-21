from .database import db
from .cog import SlotCog
from .view import SlotView

async def setup(bot):
    await db.init()
    await bot.add_cog(SlotCog(bot))
    bot.add_view(SlotView(bot))
    print("✅ スロットシステム 完全ロード完了")