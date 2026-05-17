#!/usr/bin/env python3
"""Portfolio risk manager for prediction market positions.

Enforces position limits, daily loss caps, drawdown circuit breakers,
and concentration limits across all active positions.
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utcnow() -> datetime:
    """Naive UTC now (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


DB_PATH = os.environ.get("DATABASE_PATH", "predict.db")


class RiskManager:
    """Manage portfolio-level risk for prediction market positions."""

    # Default risk parameters
    DEFAULTS = {
        "max_position_pct": 0.10,       # max 10% bankroll per position
        "max_daily_loss_pct": 0.05,      # max 5% daily loss
        "max_drawdown_pct": 0.15,        # circuit breaker at 15% drawdown
        "max_correlated_pct": 0.25,      # max 25% in correlated markets
        "max_open_positions": 20,        # max simultaneous open positions
        "min_bankroll_usdc": 10.0,       # stop trading if bankroll < $10
        "cooldown_after_loss_hours": 2,  # cool down after big loss
    }

    def __init__(self, db_path: str = DB_PATH, config: Optional[Dict] = None):
        self.db_path = db_path
        self.config = {**self.DEFAULTS, **(config or {})}
        self._init_db()

    def _init_db(self):
        con = sqlite3.connect(self.db_path)
        con.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                severity    TEXT DEFAULT 'info',
                message     TEXT,
                details_json TEXT DEFAULT '{}',
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS risk_config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS daily_pnl (
                date        TEXT PRIMARY KEY,
                start_bankroll REAL,
                end_bankroll   REAL,
                daily_pnl      REAL,
                trade_count    INTEGER DEFAULT 0
            )
        """)
        con.commit()
        con.close()

    # ── pre-trade checks ─────────────────────────────────────────────────

    def check_position_allowed(self,
                               bankroll: float,
                               stake_usdc: float,
                               market_id: str,
                               open_positions: int,
                               correlated_markets: List[str] = None) -> Dict[str, Any]:
        """Check if a new position passes all risk rules.

        Returns:
            Dict with 'allowed' (bool), 'reason' (str), 'warnings' (list).
        """
        warnings: List[str] = []
        reasons: List[str] = []

        # 1. Minimum bankroll check
        if bankroll < self.config["min_bankroll_usdc"]:
            reasons.append(f"Bankroll ${bankroll:.2f} below minimum ${self.config['min_bankroll_usdc']}")

        # 2. Position size limit
        max_stake = bankroll * self.config["max_position_pct"]
        if stake_usdc > max_stake:
            reasons.append(
                f"Stake ${stake_usdc:.2f} exceeds max position "
                f"${max_stake:.2f} ({self.config['max_position_pct']:.0%} of bankroll)"
            )

        # 3. Max open positions
        if open_positions >= self.config["max_open_positions"]:
            reasons.append(
                f"Already at max open positions ({self.config['max_open_positions']})"
            )

        # 4. Correlated markets concentration
        if correlated_markets:
            correlated_pct = len(correlated_markets) / max(open_positions, 1)
            if correlated_pct > self.config["max_correlated_pct"]:
                warnings.append(
                    f"High correlation concentration: {correlated_pct:.0%}"
                )

        # 5. Daily loss check (simplified - would query daily_pnl in production)
        self._check_daily_loss(bankroll, reasons)

        # 6. Cooldown check
        self._check_cooldown(reasons)

        # 7. Drawdown circuit breaker
        self._check_drawdown(bankroll, reasons)

        allowed = len(reasons) == 0
        result = {
            "allowed": allowed,
            "reason": "; ".join(reasons) if reasons else "OK",
            "warnings": warnings,
            "max_stake_usdc": round(max_stake, 2),
            "recommended_stake": round(min(stake_usdc, max_stake), 2),
        }

        if not allowed:
            self._log_event("trade_blocked", "warning", result["reason"], {
                "market_id": market_id, "stake": stake_usdc,
            })

        return result

    def _check_daily_loss(self, bankroll: float, reasons: List[str]):
        """Check if daily loss limit has been reached."""
        con = sqlite3.connect(self.db_path)
        today = _utcnow().strftime("%Y-%m-%d")
        row = con.execute(
            "SELECT daily_pnl FROM daily_pnl WHERE date = ?", (today,)
        ).fetchone()
        con.close()

        if row and row[0] < 0:
            daily_loss_pct = abs(row[0]) / bankroll if bankroll > 0 else 0
            if daily_loss_pct >= self.config["max_daily_loss_pct"]:
                reasons.append(
                    f"Daily loss limit reached: {daily_loss_pct:.1%} "
                    f"(max {self.config['max_daily_loss_pct']:.0%})"
                )

    def _check_cooldown(self, reasons: List[str]):
        """Check if we're in a cooldown period after a big loss."""
        con = sqlite3.connect(self.db_path)
        row = con.execute("""
            SELECT created_at FROM risk_events
            WHERE event_type = 'big_loss' AND severity = 'high'
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()
        con.close()

        if row:
            last_loss = datetime.fromisoformat(row[0])
            cooldown_hours = self.config["cooldown_after_loss_hours"]
            if _utcnow() - last_loss < timedelta(hours=cooldown_hours):
                remaining = timedelta(hours=cooldown_hours) - (_utcnow() - last_loss)
                reasons.append(
                    f"Cooldown active: {remaining.seconds // 60}min remaining"
                )

    def _check_drawdown(self, bankroll: float, reasons: List[str]):
        """Check drawdown circuit breaker."""
        con = sqlite3.connect(self.db_path)
        row = con.execute(
            "SELECT MAX(end_bankroll) as peak FROM daily_pnl"
        ).fetchone()
        con.close()

        if row and row[0]:
            peak = row[0]
            if peak > 0:
                dd = (peak - bankroll) / peak
                if dd >= self.config["max_drawdown_pct"]:
                    reasons.append(
                        f"Circuit breaker: drawdown {dd:.1%} "
                        f"exceeds limit {self.config['max_drawdown_pct']:.0%}"
                    )

    # ── post-trade recording ─────────────────────────────────────────────

    def record_trade_result(self,
                            bankroll: float,
                            pnl: float,
                            market_id: str,
                            outcome: str):
        """Record the result of a closed trade for risk tracking."""
        today = _utcnow().strftime("%Y-%m-%d")
        con = sqlite3.connect(self.db_path)

        # Upsert daily P&L
        existing = con.execute(
            "SELECT start_bankroll, trade_count FROM daily_pnl WHERE date = ?",
            (today,)
        ).fetchone()

        if existing:
            con.execute("""
                UPDATE daily_pnl
                SET end_bankroll = ?, daily_pnl = daily_pnl + ?, trade_count = trade_count + 1
                WHERE date = ?
            """, (bankroll, pnl, today))
        else:
            con.execute("""
                INSERT INTO daily_pnl (date, start_bankroll, end_bankroll, daily_pnl, trade_count)
                VALUES (?, ?, ?, ?, 1)
            """, (today, bankroll - pnl, bankroll, pnl))

        con.commit()

        # Log big losses
        if pnl < -bankroll * 0.03:  # > 3% loss on single trade
            self._log_event("big_loss", "high",
                          f"Large loss: ${pnl:.2f} on {market_id}",
                          {"market_id": market_id, "pnl": pnl, "outcome": outcome})

        con.close()

    # ── risk dashboard ───────────────────────────────────────────────────

    def get_portfolio_risk(self, bankroll: float, open_positions: int) -> Dict[str, Any]:
        """Get current portfolio risk status."""
        con = sqlite3.connect(self.db_path)

        # Recent risk events
        events = con.execute("""
            SELECT event_type, severity, message, created_at
            FROM risk_events ORDER BY created_at DESC LIMIT 10
        """).fetchall()

        # Today's P&L
        today = _utcnow().strftime("%Y-%m-%d")
        today_row = con.execute(
            "SELECT * FROM daily_pnl WHERE date = ?", (today,)
        ).fetchone()

        # 7-day P&L
        week_ago = (_utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        week_rows = con.execute("""
            SELECT SUM(daily_pnl), COUNT(*) FROM daily_pnl
            WHERE date >= ?
        """, (week_ago,)).fetchone()

        con.close()

        today_pnl = today_row[3] if today_row else 0
        week_pnl = week_rows[0] if week_rows and week_rows[0] else 0

        return {
            "bankroll": bankroll,
            "open_positions": open_positions,
            "max_position_usdc": round(bankroll * self.config["max_position_pct"], 2),
            "today_pnl": round(today_pnl, 2),
            "week_pnl": round(week_pnl, 2),
            "daily_loss_used_pct": round(abs(today_pnl) / bankroll, 4) if bankroll > 0 and today_pnl < 0 else 0,
            "position_slots_remaining": self.config["max_open_positions"] - open_positions,
            "recent_events": [
                {"type": e[0], "severity": e[1], "message": e[2], "time": e[3]}
                for e in events
            ],
            "config": self.config,
        }

    # ── helpers ──────────────────────────────────────────────────────────

    def _log_event(self, event_type: str, severity: str, message: str,
                   details: Dict = None):
        """Log a risk event."""
        con = sqlite3.connect(self.db_path)
        con.execute("""
            INSERT INTO risk_events (event_type, severity, message, details_json)
            VALUES (?, ?, ?, ?)
        """, (event_type, severity, message, json.dumps(details or {})))
        con.commit()
        con.close()

    def update_config(self, key: str, value: Any):
        """Update a risk parameter."""
        self.config[key] = value
        con = sqlite3.connect(self.db_path)
        con.execute(
            "INSERT OR REPLACE INTO risk_config (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
        con.commit()
        con.close()
