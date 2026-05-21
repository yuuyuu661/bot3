# cogs/slot/engine.py
from typing import List, Tuple, Dict
import random
from .config import config

class SlotEngine:
    @staticmethod
    def generate_grid() -> List[List[str]]:
        normalized = [w / sum(config.weights) for w in config.weights]
        return [[random.choices(config.symbols, weights=normalized, k=1)[0] for _ in range(5)] for _ in range(3)]

    @staticmethod
    def calculate_payout(grid: List[List[str]], bet: int) -> Tuple[int, List[str]]:
        total = 0
        winning_lines = []

        # 横ライン
        for r in range(3):
            payout = SlotEngine._horizontal_payout(grid[r], bet)
            if payout > 0:
                total += payout
                winning_lines.append(f"横{r+1}")

        # 縦ライン
        for c in range(5):
            symbols = [grid[r][c] for r in range(3)]
            if len(set(symbols)) == 1:
                sym = symbols[0]
                rate = config.symbol_rates.get(sym, 0)
                payout = int(bet * rate)
                if payout > 0:
                    total += payout
                    winning_lines.append(f"縦{c+1}")

        # 斜めライン
        diagonals = [
            [(0,0),(1,1),(2,2)], [(0,1),(1,2),(2,3)], [(0,2),(1,3),(2,4)],
            [(2,0),(1,1),(0,2)], [(2,1),(1,2),(0,3)], [(2,2),(1,3),(0,4)]
        ]
        for pos in diagonals:
            symbols = [grid[r][c] for r, c in pos]
            if len(set(symbols)) == 1:
                sym = symbols[0]
                rate = config.symbol_rates.get(sym, 0) * 1.1
                payout = int(bet * rate)
                if payout > 0:
                    total += payout
                    winning_lines.append("斜め")

        return total, winning_lines

    @staticmethod
    def _horizontal_payout(row: List[str], bet: int) -> int:
        total = 0
        i = 0
        while i < 5:
            j = i
            while j < 5 and row[j] == row[i]:
                j += 1
            length = j - i
            if length >= 3:
                sym = row[i]
                multiplier = config.symbol_rates.get(sym, 0)
                if length == 4:
                    multiplier *= 1.5
                elif length == 5:
                    multiplier *= 2.0
                total += int(bet * multiplier)
            i = j
        return total

    @staticmethod
    def check_jackpot(user_data: Dict, bet: int) -> int:
        """完全ランダムJP（約0.03%）"""
        user_data["jp_gauge"] += bet
        if random.random() < 0.0003:   # 0.03%
            jp_win = bet * 30
            user_data["jp_gauge"] = 0
            return jp_win
        return 0