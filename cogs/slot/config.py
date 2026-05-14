from dataclasses import dataclass

@dataclass
class SlotConfig:
    symbols = ["🍋", "🍒", "🍀", "🔔", "💰", "💎", "7️⃣"]
    weights = [40, 30, 20, 10, 7, 2, 1]
    symbol_rates = {"🍋":0.5, "🍒":0.9, "🍀":1.2, "🔔":1.5, "💰":3.0, "💎":7.0, "7️⃣":10.0}

config = SlotConfig()