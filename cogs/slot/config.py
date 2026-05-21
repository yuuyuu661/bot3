# cogs/slot/config.py
from dataclasses import dataclass

@dataclass
class SlotConfig:
    symbols = ["🍋", "🍒", "🍀", "🔔", "💰", "💎", "7️⃣"]
    weights = [38, 28, 20, 12, 8, 3, 1]          # 合計110
    symbol_rates = {
        "🍋": 0.45,
        "🍒": 0.95,
        "🍀": 1.6,
        "🔔": 2.2,
        "💰": 4.0,
        "💎": 9.0,
        "7️⃣": 13.0
    }

config = SlotConfig()