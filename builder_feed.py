"""
Builder Feed - Agent推荐变现层
将Agent的预测推荐发布为签名数据流，通过Builder Code机制按成交赚取USDC
基于Polymarket V2 Builder Code规范
"""

import sqlite3
import hashlib
import json
import time
from typing import Dict, List, Optional
from datetime import datetime


class BuilderFeed:
    """Agent推荐Builder Feed"""

    def __init__(self, db_path: str = "predict.db"):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS builder_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rec_id TEXT UNIQUE NOT NULL,
                market_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                probability REAL NOT NULL,
                confidence REAL NOT NULL,
                edge REAL,
                stake_usdc REAL,
                expected_value REAL,
                builder_code TEXT,
                status TEXT DEFAULT 'active',
                fills INTEGER DEFAULT 0,
                earnings_usdc REAL DEFAULT 0,
                payload TEXT,
                signature TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS builder_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rec_id TEXT NOT NULL,
                fill_amount REAL NOT NULL,
                fee_earned REAL NOT NULL,
                tx_hash TEXT,
                filled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rec_id) REFERENCES builder_recommendations(rec_id)
            )
        ''')

        c.execute('CREATE INDEX IF NOT EXISTS idx_rec_id ON builder_recommendations(rec_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_rec_status ON builder_recommendations(status)')

        conn.commit()
        conn.close()

    def publish(self, market_id: str, direction: str, probability: float,
                confidence: float, edge: float = None, stake_usdc: float = None,
                expected_value: float = None, builder_code: str = "",
                expires_hours: int = 24) -> Dict:
        """
        发布推荐

        Builder Code规范：
        - 推荐包含市场ID、方向、概率、置信度
        - 每笔通过推荐链接成交的交易，Agent赚取builder fee
        """
        rec_id = "rec_" + hashlib.sha256(
            f"{market_id}{direction}{probability}{time.time()}".encode()
        ).hexdigest()[:16]

        # 生成签名payload（Builder Code格式）
        payload = {
            "market": market_id,
            "direction": direction,
            "probability": probability,
            "confidence": confidence,
            "timestamp": int(time.time()),
            "builder": builder_code or "arc-predict-agent-v1"
        }

        # 模拟签名（生产环境用私钥签名）
        signature = "0x" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()

        # 计算过期时间
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT datetime('now', '+{} hours')".format(expires_hours))
        expires_at = c.fetchone()[0]

        c.execute('''
            INSERT INTO builder_recommendations
            (rec_id, market_id, direction, probability, confidence, edge,
             stake_usdc, expected_value, builder_code, payload, signature, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (rec_id, market_id, direction, probability, confidence, edge,
              stake_usdc, expected_value, builder_code,
              json.dumps(payload), signature, expires_at))

        conn.commit()
        conn.close()

        return {
            "rec_id": rec_id,
            "market_id": market_id,
            "direction": direction,
            "status": "active",
            "expires_at": expires_at
        }

    def record_fill(self, rec_id: str, fill_amount: float, fee_rate: float = 0.01,
                    tx_hash: str = "") -> Dict:
        """记录成交和收入"""
        fee_earned = round(fill_amount * fee_rate, 6)

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            INSERT INTO builder_fills (rec_id, fill_amount, fee_earned, tx_hash)
            VALUES (?, ?, ?, ?)
        ''', (rec_id, fill_amount, fee_earned, tx_hash))

        # 更新推荐统计
        c.execute('''
            UPDATE builder_recommendations
            SET fills = fills + 1, earnings_usdc = earnings_usdc + ?
            WHERE rec_id = ?
        ''', (fee_earned, rec_id))

        conn.commit()
        conn.close()

        return {
            "rec_id": rec_id,
            "fill_amount": fill_amount,
            "fee_earned": fee_earned,
            "fee_rate": fee_rate
        }

    def get_feed(self, status: str = "active", limit: int = 20) -> List[Dict]:
        """获取推荐Feed"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM builder_recommendations WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        )
        rows = c.fetchall()
        conn.close()
        cols = ["id", "rec_id", "market_id", "direction", "probability", "confidence",
                "edge", "stake_usdc", "expected_value", "builder_code", "status",
                "fills", "earnings_usdc", "payload", "signature", "created_at", "expires_at"]
        return [dict(zip(cols, r)) for r in rows]

    def get_recommendation(self, rec_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM builder_recommendations WHERE rec_id = ?", (rec_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        cols = ["id", "rec_id", "market_id", "direction", "probability", "confidence",
                "edge", "stake_usdc", "expected_value", "builder_code", "status",
                "fills", "earnings_usdc", "payload", "signature", "created_at", "expires_at"]
        return dict(zip(cols, row))

    def deactivate(self, rec_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE builder_recommendations SET status = 'expired' WHERE rec_id = ?", (rec_id,))
        success = c.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_earnings(self) -> Dict:
        """获取总收益统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM builder_recommendations")
        total_recs = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(fills), 0) FROM builder_recommendations")
        total_fills = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(earnings_usdc), 0) FROM builder_recommendations")
        total_earnings = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(fill_amount), 0) FROM builder_fills")
        total_volume = c.fetchone()[0]
        conn.close()
        return {
            "total_recommendations": total_recs,
            "total_fills": total_fills,
            "total_earnings_usdc": round(total_earnings, 6),
            "total_volume_usdc": round(total_volume, 2),
            "avg_fee_per_fill": round(total_earnings / max(total_fills, 1), 6)
        }
