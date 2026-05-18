#!/usr/bin/env python3
"""Integration tests for the full prediction workflow.

Tests end-to-end flows: signal → analyze → kelly → publish → earnings.
Run with: pytest tests/test_integration.py -v
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from signal_aggregator import SignalAggregator
from kelly_sizer import KellySizer
from builder_feed import BuilderFeed
from backtest import BacktestEngine
from risk_manager import RiskManager


class TestSignalToKelly(unittest.TestCase):
    """Test the signal → analysis → Kelly pipeline."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.aggregator = SignalAggregator(db_path=self.tmp)
        self.kelly = KellySizer(db_path=self.tmp)

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_full_pipeline_positive_edge(self):
        """Signals → Analysis → Kelly with positive edge."""
        # Register market
        self.aggregator.register_market("test_btc", "Will BTC hit $100k?")
        # Add signals: add_signal(market_id, source, signal_type, value, confidence)
        self.aggregator.add_signal("test_btc", "news", "sentiment", 0.70, 0.8)
        self.aggregator.add_signal("test_btc", "social", "momentum", 0.65, 0.6)
        # Analyze
        analysis = self.aggregator.analyze_market("test_btc")
        self.assertGreater(analysis["our_probability"], 0.5)
        # Kelly sizing
        k = self.kelly.calculate(1000, analysis["our_probability"], 0.55)
        self.assertEqual(k["direction"], "YES")
        self.assertTrue(k["should_bet"])
        self.assertGreater(k["stake_usdc"], 0)

    def test_full_pipeline_negative_edge(self):
        """Signals → Analysis → Kelly with negative edge → no bet."""
        self.aggregator.register_market("test_eth", "Will ETH drop below $2k?")
        # Low value signals: add_signal(market_id, source, signal_type, value, confidence)
        self.aggregator.add_signal("test_eth", "news", "sentiment", 0.30, 0.7)
        self.aggregator.add_signal("test_eth", "onchain", "metrics", 0.25, 0.9)
        analysis = self.aggregator.analyze_market("test_eth")
        self.assertLess(analysis["our_probability"], 0.5)
        # Market says YES at 0.6, we think it's only ~0.27 → bet NO
        k = self.kelly.calculate(1000, analysis["our_probability"], 0.60)
        self.assertEqual(k["direction"], "NO")


class TestAnalyzeToBuilder(unittest.TestCase):
    """Test analysis → publish → earnings pipeline."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.aggregator = SignalAggregator(db_path=self.tmp)
        self.kelly = KellySizer(db_path=self.tmp)
        self.builder = BuilderFeed(db_path=self.tmp)

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_publish_and_earn(self):
        """Publish recommendation → record fill → check earnings."""
        self.aggregator.register_market("m1", "Test market")
        self.aggregator.add_signal("m1", "news", "sentiment", 0.65, 0.7)
        analysis = self.aggregator.analyze_market("m1")

        rec = self.builder.publish("m1", "YES", analysis["our_probability"], analysis["confidence"])
        self.assertIn("rec_id", rec)

        # Record multiple fills
        fill1 = self.builder.record_fill(rec["rec_id"], 50.0)
        fill2 = self.builder.record_fill(rec["rec_id"], 100.0)

        earnings = self.builder.get_earnings()
        self.assertGreater(earnings["total_fills"], 0)
        self.assertGreater(earnings["total_earnings_usdc"], 0)

    def test_recommendation_deactivate(self):
        """Recommendations can be deactivated."""
        self.aggregator.register_market("m2", "Deactivate test")
        rec = self.builder.publish("m2", "YES", 0.6, 0.5)
        # Deactivate it
        self.builder.deactivate(rec["rec_id"])
        # Active feed should not contain it
        feed = self.builder.get_feed(status="active")
        active_ids = [r["rec_id"] for r in feed]
        self.assertNotIn(rec["rec_id"], active_ids)


class TestBacktestPipeline(unittest.TestCase):
    """Test the backtesting engine with simulated data."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.engine = BacktestEngine(db_path=self.tmp, kelly_fraction=0.25)

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_profitable_strategy(self):
        """Backtest with accurate signals → positive P&L."""
        signals = [
            {"market_id": "m1", "probability": 0.70, "confidence": 0.8, "odds": 0.55},
            {"market_id": "m2", "probability": 0.65, "confidence": 0.7, "odds": 0.50},
            {"market_id": "m3", "probability": 0.75, "confidence": 0.9, "odds": 0.60},
        ]
        outcomes = {"m1": "YES", "m2": "YES", "m3": "YES"}
        result = self.engine.run("profit_test", signals, outcomes, initial_bankroll=1000)
        self.assertEqual(result["total_trades"], 3)
        self.assertGreater(result["final_bankroll"], 1000)
        self.assertGreater(result["win_rate"], 0.5)

    def test_losing_strategy(self):
        """Backtest with wrong signals → negative P&L."""
        signals = [
            {"market_id": "m1", "probability": 0.80, "confidence": 0.9, "odds": 0.60},
            {"market_id": "m2", "probability": 0.75, "confidence": 0.8, "odds": 0.55},
        ]
        outcomes = {"m1": "NO", "m2": "NO"}  # Wrong direction
        result = self.engine.run("loss_test", signals, outcomes, initial_bankroll=1000)
        self.assertLess(result["final_bankroll"], 1000)
        self.assertEqual(result["winning_trades"], 0)

    def test_results_persistence(self):
        """Backtest results are saved and retrievable."""
        signals = [{"market_id": "m1", "probability": 0.6, "confidence": 0.7, "odds": 0.5}]
        outcomes = {"m1": "YES"}
        self.engine.run("persist_test", signals, outcomes)
        results = self.engine.get_results()
        self.assertTrue(any(r["name"] == "persist_test" for r in results))


class TestRiskManager(unittest.TestCase):
    """Test the risk management system."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.rm = RiskManager(db_path=self.tmp)

    def tearDown(self):
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_normal_trade_allowed(self):
        """Normal-sized trade should be allowed."""
        result = self.rm.check_position_allowed(
            bankroll=1000, stake_usdc=50, market_id="m1",
            open_positions=5,
        )
        self.assertTrue(result["allowed"])

    def test_oversized_trade_blocked(self):
        """Trade exceeding max position size should be blocked."""
        result = self.rm.check_position_allowed(
            bankroll=1000, stake_usdc=200, market_id="m1",
            open_positions=5,
        )
        self.assertFalse(result["allowed"])
        self.assertIn("exceeds max position", result["reason"])

    def test_too_many_positions_blocked(self):
        """Opening beyond max positions should be blocked."""
        result = self.rm.check_position_allowed(
            bankroll=1000, stake_usdc=50, market_id="m1",
            open_positions=20,
        )
        self.assertFalse(result["allowed"])
        self.assertIn("max open positions", result["reason"])

    def test_low_bankroll_blocked(self):
        """Trading with insufficient bankroll should be blocked."""
        result = self.rm.check_position_allowed(
            bankroll=5, stake_usdc=1, market_id="m1",
            open_positions=0,
        )
        self.assertFalse(result["allowed"])
        self.assertIn("below minimum", result["reason"])

    def test_portfolio_risk_dashboard(self):
        """Risk dashboard should return meaningful data."""
        dash = self.rm.get_portfolio_risk(bankroll=1000, open_positions=5)
        self.assertEqual(dash["bankroll"], 1000)
        self.assertEqual(dash["open_positions"], 5)
        self.assertGreater(dash["max_position_usdc"], 0)
        self.assertEqual(dash["position_slots_remaining"], 15)

    def test_trade_result_recording(self):
        """Recording trade results should update daily P&L."""
        self.rm.record_trade_result(1050, 50, "m1", "WIN")
        self.rm.record_trade_result(1020, -30, "m2", "LOSS")
        dash = self.rm.get_portfolio_risk(1020, 2)
        # Net P&L should be 50 - 30 = 20
        self.assertAlmostEqual(dash["today_pnl"], 20, places=1)


if __name__ == "__main__":
    unittest.main()
