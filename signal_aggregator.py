"""
信号聚合器 - 从多源收集信号用于预测市场分析
支持：新闻、社交情绪、链上数据、自定义信号
"""

import sqlite3
import hashlib
import time
import json
from typing import Dict, List, Optional
from datetime import datetime


class SignalAggregator:
    """多源信号聚合器"""

    def __init__(self, db_path: str = "predict.db"):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                source TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                value REAL NOT NULL,
                confidence REAL DEFAULT 0.5,
                weight REAL DEFAULT 1.0,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'general',
                current_odds REAL DEFAULT 0.5,
                our_estimate REAL,
                edge REAL,
                volume_usdc REAL DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                probability REAL NOT NULL,
                confidence REAL NOT NULL,
                edge REAL,
                direction TEXT,
                signal_count INTEGER DEFAULT 0,
                breakdown TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('CREATE INDEX IF NOT EXISTS idx_signal_market ON signals(market_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_market_id ON markets(market_id)')

        conn.commit()
        conn.close()

    # ==================== Signals ====================

    def add_signal(self, market_id: str, source: str, signal_type: str,
                   value: float, confidence: float = 0.5, weight: float = 1.0,
                   payload: dict = None) -> int:
        """添加信号"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO signals (market_id, source, signal_type, value, confidence, weight, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (market_id, source, signal_type, value, confidence, weight,
              json.dumps(payload) if payload else None))
        signal_id = c.lastrowid
        conn.commit()
        conn.close()
        return signal_id

    def add_signals_batch(self, market_id: str, signals: List[Dict]) -> int:
        """批量添加信号"""
        count = 0
        for s in signals:
            self.add_signal(
                market_id=market_id,
                source=s.get("source", "unknown"),
                signal_type=s.get("type", "generic"),
                value=float(s.get("value", 0.5)),
                confidence=float(s.get("confidence", 0.5)),
                weight=float(s.get("weight", 1.0)),
                payload=s.get("payload")
            )
            count += 1
        return count

    def get_signals(self, market_id: str, limit: int = 100) -> List[Dict]:
        """获取市场信号"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM signals WHERE market_id = ? ORDER BY created_at DESC LIMIT ?",
            (market_id, limit)
        )
        rows = c.fetchall()
        conn.close()
        cols = ["id", "market_id", "source", "signal_type", "value",
                "confidence", "weight", "payload", "created_at"]
        return [dict(zip(cols, r)) for r in rows]

    def aggregate_signals(self, market_id: str) -> Dict:
        """
        聚合信号 → 加权平均概率
        使用加权置信度来合并不同来源的信号
        """
        signals = self.get_signals(market_id)

        if not signals:
            return {"probability": 0.5, "confidence": 0.0, "signal_count": 0, "breakdown": {}}

        # 按信号类型分组
        by_type = {}
        for s in signals:
            t = s["signal_type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(s)

        # 每种类型计算加权平均
        type_estimates = {}
        for sig_type, sigs in by_type.items():
            total_weight = sum(s["weight"] * s["confidence"] for s in sigs)
            if total_weight == 0:
                type_estimates[sig_type] = {"prob": 0.5, "weight": 0, "count": len(sigs)}
                continue

            weighted_prob = sum(s["value"] * s["weight"] * s["confidence"] for s in sigs)
            type_estimates[sig_type] = {
                "prob": round(weighted_prob / total_weight, 4),
                "weight": round(total_weight / len(sigs), 4),
                "count": len(sigs)
            }

        # 最终聚合：每种类型等权
        probs = [v["prob"] for v in type_estimates.values() if v["weight"] > 0]
        if not probs:
            final_prob = 0.5
        else:
            final_prob = round(sum(probs) / len(probs), 4)

        # 整体置信度
        total_confidence = sum(s["confidence"] * s["weight"] for s in signals)
        max_confidence = len(signals)  # 每个信号最大贡献1.0
        overall_confidence = round(min(total_confidence / max_confidence, 1.0), 4) if max_confidence > 0 else 0

        return {
            "probability": final_prob,
            "confidence": overall_confidence,
            "signal_count": len(signals),
            "breakdown": type_estimates
        }

    # ==================== Markets ====================

    def register_market(self, market_id: str, title: str, description: str = "",
                        category: str = "general", current_odds: float = 0.5) -> Dict:
        """注册/更新市场"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            c.execute('''
                INSERT INTO markets (market_id, title, description, category, current_odds)
                VALUES (?, ?, ?, ?, ?)
            ''', (market_id, title, description, category, current_odds))
            conn.commit()
            return {"market_id": market_id, "status": "created"}
        except sqlite3.IntegrityError:
            c.execute('''
                UPDATE markets SET current_odds = ?, updated_at = CURRENT_TIMESTAMP
                WHERE market_id = ?
            ''', (current_odds, market_id))
            conn.commit()
            return {"market_id": market_id, "status": "updated"}
        finally:
            conn.close()

    def get_market(self, market_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM markets WHERE market_id = ?", (market_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        cols = ["id", "market_id", "title", "description", "category",
                "current_odds", "our_estimate", "edge", "volume_usdc",
                "status", "created_at", "updated_at"]
        return dict(zip(cols, row))

    def list_markets(self, status: str = None, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if status:
            c.execute("SELECT * FROM markets WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                      (status, limit))
        else:
            c.execute("SELECT * FROM markets ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        cols = ["id", "market_id", "title", "description", "category",
                "current_odds", "our_estimate", "edge", "volume_usdc",
                "status", "created_at", "updated_at"]
        return [dict(zip(cols, r)) for r in rows]

    def update_market_estimate(self, market_id: str, probability: float, edge: float):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            UPDATE markets SET our_estimate = ?, edge = ?, updated_at = CURRENT_TIMESTAMP
            WHERE market_id = ?
        ''', (probability, edge, market_id))
        conn.commit()
        conn.close()

    # ==================== Analysis ====================

    def analyze_market(self, market_id: str) -> Dict:
        """完整分析一个市场"""
        market = self.get_market(market_id)

        # 聚合信号
        agg = self.aggregate_signals(market_id)

        # 计算edge（我们的估计 vs 市场价格）
        market_odds = market["current_odds"] if market else 0.5
        our_prob = agg["probability"]
        edge = round(our_prob - market_odds, 4)

        # 确定方向
        if abs(edge) < 0.05:
            direction = "neutral"
        elif edge > 0:
            direction = "YES"
        else:
            direction = "NO"

        # 更新市场估计
        if market:
            self.update_market_estimate(market_id, our_prob, edge)

        # 保存分析记录
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO analyses (market_id, probability, confidence, edge, direction, signal_count, breakdown)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (market_id, our_prob, agg["confidence"], edge, direction,
              agg["signal_count"], json.dumps(agg["breakdown"])))
        conn.commit()
        conn.close()

        return {
            "market_id": market_id,
            "market_odds": market_odds,
            "our_probability": our_prob,
            "confidence": agg["confidence"],
            "edge": edge,
            "direction": direction,
            "signal_count": agg["signal_count"],
            "breakdown": agg["breakdown"]
        }

    def get_analysis_history(self, market_id: str, limit: int = 20) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM analyses WHERE market_id = ? ORDER BY created_at DESC LIMIT ?",
            (market_id, limit)
        )
        rows = c.fetchall()
        conn.close()
        cols = ["id", "market_id", "probability", "confidence", "edge",
                "direction", "signal_count", "breakdown", "created_at"]
        return [dict(zip(cols, r)) for r in rows]

    def get_stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM markets")
        total_markets = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM signals")
        total_signals = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM analyses")
        total_analyses = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM markets WHERE edge IS NOT NULL AND ABS(edge) > 0.05")
        edge_markets = c.fetchone()[0]
        conn.close()
        return {
            "total_markets": total_markets,
            "total_signals": total_signals,
            "total_analyses": total_analyses,
            "markets_with_edge": edge_markets
        }
