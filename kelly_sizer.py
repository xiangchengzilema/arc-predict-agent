"""
Kelly Criterion 仓位计算器
根据概率估计和市场赔率计算最优投注比例
"""

import sqlite3
import json
from typing import Dict, Optional, List
from datetime import datetime


class KellySizer:
    """Kelly Criterion仓位计算器"""

    def __init__(self, db_path: str = "predict.db", default_fraction: float = 0.25):
        """
        Args:
            default_fraction: Kelly分数（0.25 = quarter-Kelly，保守策略）
        """
        self.db_path = db_path
        self.default_fraction = default_fraction
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS kelly_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                bankroll REAL NOT NULL,
                our_probability REAL NOT NULL,
                market_odds REAL NOT NULL,
                kelly_fraction REAL NOT NULL,
                full_kelly REAL NOT NULL,
                adjusted_kelly REAL NOT NULL,
                stake_usdc REAL NOT NULL,
                expected_value REAL,
                expected_roi REAL,
                direction TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def calculate(self, bankroll: float, our_probability: float,
                  market_odds: float, fraction: float = None) -> Dict:
        """
        计算Kelly Criterion仓位

        Kelly公式: f* = (bp - q) / b
        其中:
            b = 赔率 (1/odds - 1 for YES, odds/(1-odds) for NO)
            p = 我们估计的概率
            q = 1 - p

        Args:
            bankroll: 总资金(USDC)
            our_probability: 我们估计的概率(0-1)
            market_odds: 市场当前价格(0-1)
            fraction: Kelly分数(默认0.25 = quarter-Kelly)
        """
        fraction = fraction or self.default_fraction

        our_probability = max(0.01, min(0.99, our_probability))
        market_odds = max(0.01, min(0.99, market_odds))

        # 确定方向
        if our_probability > market_odds:
            direction = "YES"
            # YES的赔率: 花 market_odds 赚 (1 - market_odds)
            b = (1.0 - market_odds) / market_odds
            p = our_probability
        else:
            direction = "NO"
            # NO的赔率: 花 (1 - market_odds) 赚 market_odds
            b = market_odds / (1.0 - market_odds)
            p = 1.0 - our_probability

        q = 1.0 - p

        # Full Kelly
        full_kelly = (b * p - q) / b
        full_kelly = max(0, full_kelly)  # Kelly不能为负

        # Adjusted Kelly (fraction)
        adjusted_kelly = full_kelly * fraction

        # 实际投注金额
        stake_usdc = round(bankroll * adjusted_kelly, 2)

        # 期望值 (EV = p * payout - stake，因为 payout 已包含本金)
        if direction == "YES":
            payout = stake_usdc * (1.0 / market_odds)  # 赢了拿多少（含本金）
        else:
            payout = stake_usdc * (1.0 / (1.0 - market_odds))
        expected_value = round(payout * p - stake_usdc, 4)

        # 期望ROI
        expected_roi = round(expected_value / stake_usdc, 4) if stake_usdc > 0 else 0

        return {
            "direction": direction,
            "bankroll": bankroll,
            "our_probability": our_probability,
            "market_odds": market_odds,
            "edge": round(our_probability - market_odds, 4) if direction == "YES" else round((1 - our_probability) - (1 - market_odds), 4),
            "full_kelly": round(full_kelly, 6),
            "kelly_fraction": fraction,
            "adjusted_kelly": round(adjusted_kelly, 6),
            "stake_usdc": stake_usdc,
            "expected_value": expected_value,
            "expected_roi": expected_roi,
            "should_bet": full_kelly > 0
        }

    def save_recommendation(self, market_id: str, calc_result: Dict) -> int:
        """保存Kelly推荐"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO kelly_recommendations
            (market_id, bankroll, our_probability, market_odds, kelly_fraction,
             full_kelly, adjusted_kelly, stake_usdc, expected_value, expected_roi, direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            market_id,
            calc_result["bankroll"],
            calc_result["our_probability"],
            calc_result["market_odds"],
            calc_result["kelly_fraction"],
            calc_result["full_kelly"],
            calc_result["adjusted_kelly"],
            calc_result["stake_usdc"],
            calc_result["expected_value"],
            calc_result["expected_roi"],
            calc_result["direction"]
        ))
        rec_id = c.lastrowid
        conn.commit()
        conn.close()
        return rec_id

    def get_recommendations(self, market_id: str = None, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if market_id:
            c.execute(
                "SELECT * FROM kelly_recommendations WHERE market_id = ? ORDER BY created_at DESC LIMIT ?",
                (market_id, limit)
            )
        else:
            c.execute(
                "SELECT * FROM kelly_recommendations ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        rows = c.fetchall()
        conn.close()
        cols = ["id", "market_id", "bankroll", "our_probability", "market_odds",
                "kelly_fraction", "full_kelly", "adjusted_kelly", "stake_usdc",
                "expected_value", "expected_roi", "direction", "created_at"]
        return [dict(zip(cols, r)) for r in rows]

    def get_stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM kelly_recommendations")
        total = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(stake_usdc), 0) FROM kelly_recommendations")
        total_staked = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(expected_value), 0) FROM kelly_recommendations")
        total_ev = c.fetchone()[0]
        conn.close()
        return {
            "total_recommendations": total,
            "total_staked_usdc": round(total_staked, 2),
            "total_expected_value": round(total_ev, 2),
            "avg_roi": round(total_ev / max(total_staked, 1), 4)
        }
