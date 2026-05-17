#!/usr/bin/env python3
"""Backtesting engine for prediction market strategies.

Simulates historical signal-based trading with Kelly position sizing,
tracking P&L, win rate, max drawdown, and Sharpe ratio.
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.environ.get("DATABASE_PATH", "predict.db")


class BacktestEngine:
    """Run historical simulations of prediction market strategies."""

    def __init__(self, db_path: str = DB_PATH, kelly_fraction: float = 0.25):
        self.db_path = db_path
        self.kelly_fraction = kelly_fraction
        self._init_db()

    def _init_db(self):
        con = sqlite3.connect(self.db_path)
        con.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                market_id   TEXT NOT NULL,
                start_date  TEXT,
                end_date    TEXT,
                initial_bankroll REAL NOT NULL,
                final_bankroll   REAL NOT NULL,
                total_trades     INTEGER DEFAULT 0,
                winning_trades   INTEGER DEFAULT 0,
                win_rate         REAL DEFAULT 0,
                total_pnl        REAL DEFAULT 0,
                max_drawdown     REAL DEFAULT 0,
                sharpe_ratio     REAL DEFAULT 0,
                avg_roi          REAL DEFAULT 0,
                config_json      TEXT DEFAULT '{}',
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id   INTEGER NOT NULL,
                trade_date  TEXT,
                market_id   TEXT,
                direction   TEXT,
                stake_usdc  REAL,
                odds        REAL,
                outcome     TEXT,
                pnl         REAL,
                bankroll_after REAL,
                FOREIGN KEY (result_id) REFERENCES backtest_results(id)
            )
        """)
        con.commit()
        con.close()

    # ── core simulation ──────────────────────────────────────────────────

    def run(self,
            name: str,
            signals: List[Dict],
            outcomes: Dict[str, str],
            initial_bankroll: float = 1000.0,
            fee_rate: float = 0.01) -> Dict[str, Any]:
        """Run a backtest simulation.

        Args:
            name: Backtest run name.
            signals: List of signal dicts with keys:
                     market_id, probability, confidence, timestamp
            outcomes: Dict mapping market_id -> "YES" or "NO"
            initial_bankroll: Starting bankroll in USDC.
            fee_rate: Trading fee rate (Arc default ~1%).

        Returns:
            Summary dict with P&L, win rate, drawdown, etc.
        """
        bankroll = initial_bankroll
        peak = initial_bankroll
        max_dd = 0.0
        trades: List[Dict] = []
        daily_returns: List[float] = []

        # Group signals by market_id
        from collections import defaultdict
        market_signals: Dict[str, List] = defaultdict(list)
        for sig in signals:
            market_signals[sig["market_id"]].append(sig)

        for market_id, sigs in market_signals.items():
            if market_id not in outcomes:
                continue

            # Aggregate signals for this market (weighted average)
            total_weight = 0.0
            weighted_prob = 0.0
            for s in sigs:
                w = s.get("confidence", 0.5)
                weighted_prob += s["probability"] * w
                total_weight += w

            if total_weight == 0:
                continue
            our_prob = weighted_prob / total_weight

            # Determine market odds from signals — must be provided explicitly.
            # Falling back to our_prob makes edge always zero and silently skips
            # every trade, which masks missing data as "no opportunities found".
            odds_values = [s["odds"] for s in sigs if "odds" in s and 0 < s["odds"] < 1]
            if not odds_values:
                trades.append({
                    "market_id": market_id,
                    "direction": "SKIPPED",
                    "stake_usdc": 0.0,
                    "odds": 0.0,
                    "outcome": outcomes[market_id],
                    "pnl": 0.0,
                    "bankroll_after": round(bankroll, 2),
                    "skip_reason": "no_market_odds",
                })
                continue
            avg_odds = sum(odds_values) / len(odds_values)

            # Kelly sizing
            edge = our_prob - avg_odds
            full_kelly = edge / (1 - avg_odds) if (1 - avg_odds) > 0 else 0
            adjusted_kelly = full_kelly * self.kelly_fraction

            if abs(adjusted_kelly) < 0.001:
                continue  # Skip negligible positions

            direction = "YES" if edge > 0 else "NO"
            stake = min(abs(adjusted_kelly) * bankroll, bankroll * 0.10)  # cap at 10%

            if stake < 0.01:
                continue

            # Determine outcome
            actual_outcome = outcomes[market_id]
            won = (direction == actual_outcome)

            if won:
                payout = stake * (1 / avg_odds - 1) * (1 - fee_rate)
                pnl = payout
            else:
                pnl = -stake * (1 + fee_rate)

            bankroll += pnl
            if bankroll <= 0:
                bankroll = 0
                break

            # Track drawdown
            if bankroll > peak:
                peak = bankroll
            dd = (peak - bankroll) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

            daily_returns.append(pnl / (bankroll - pnl) if (bankroll - pnl) > 0 else 0)

            trades.append({
                "market_id": market_id,
                "direction": direction,
                "stake_usdc": round(stake, 2),
                "odds": round(avg_odds, 4),
                "outcome": actual_outcome,
                "pnl": round(pnl, 4),
                "bankroll_after": round(bankroll, 2),
            })

        # Calculate stats
        winning = [t for t in trades if t["pnl"] > 0]
        total_pnl = bankroll - initial_bankroll
        win_rate = len(winning) / len(trades) if trades else 0
        avg_roi = total_pnl / initial_bankroll if initial_bankroll > 0 else 0

        # Sharpe ratio (annualized, assuming 365 trading days)
        if len(daily_returns) > 1:
            avg_ret = sum(daily_returns) / len(daily_returns)
            var = sum((r - avg_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_ret = var ** 0.5
            sharpe = (avg_ret / std_ret) * (365 ** 0.5) if std_ret > 0 else 0
        else:
            sharpe = 0

        result = {
            "name": name,
            "initial_bankroll": initial_bankroll,
            "final_bankroll": round(bankroll, 2),
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "win_rate": round(win_rate, 4),
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 4),
            "avg_roi": round(avg_roi, 4),
            "trades": trades,
        }

        self._save_result(result)
        return result

    # ── persistence ──────────────────────────────────────────────────────

    def _save_result(self, result: Dict):
        """Save backtest result to database."""
        con = sqlite3.connect(self.db_path)
        cur = con.execute("""
            INSERT INTO backtest_results
                (name, market_id, initial_bankroll, final_bankroll,
                 total_trades, winning_trades, win_rate, total_pnl,
                 max_drawdown, sharpe_ratio, avg_roi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["name"], "batch",
            result["initial_bankroll"], result["final_bankroll"],
            result["total_trades"], result["winning_trades"],
            result["win_rate"], result["total_pnl"],
            result["max_drawdown"], result["sharpe_ratio"],
            result["avg_roi"],
        ))
        result_id = cur.lastrowid

        for t in result.get("trades", []):
            con.execute("""
                INSERT INTO backtest_trades
                    (result_id, trade_date, market_id, direction,
                     stake_usdc, odds, outcome, pnl, bankroll_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id, t.get("trade_date", ""), t["market_id"],
                t["direction"], t["stake_usdc"], t["odds"],
                t["outcome"], t["pnl"], t["bankroll_after"],
            ))

        con.commit()
        con.close()

    def get_results(self, limit: int = 20) -> List[Dict]:
        """Get recent backtest results."""
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]

    def compare(self, name1: str, name2: str) -> Dict[str, Any]:
        """Compare two backtest runs."""
        results = self.get_results(limit=100)
        r1 = next((r for r in results if r["name"] == name1), None)
        r2 = next((r for r in results if r["name"] == name2), None)

        if not r1 or not r2:
            return {"error": "One or both backtest runs not found"}

        return {
            "comparison": f"{name1} vs {name2}",
            "pnl_diff": round(r2["total_pnl"] - r1["total_pnl"], 2),
            "win_rate_diff": round(r2["win_rate"] - r1["win_rate"], 4),
            "sharpe_diff": round(r2["sharpe_ratio"] - r1["sharpe_ratio"], 4),
            "better": name2 if r2["total_pnl"] > r1["total_pnl"] else name1,
        }
