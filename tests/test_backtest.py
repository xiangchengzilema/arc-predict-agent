"""Regression tests for backtest.py edge cases."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import BacktestEngine


@pytest.fixture
def engine():
    fd, path = tempfile.mkstemp(suffix=".db", prefix="backtest_test_")
    os.close(fd)
    eng = BacktestEngine(db_path=path)
    yield eng
    try:
        os.unlink(path)
    except OSError:
        pass


class TestMissingOdds:
    def test_signals_without_odds_are_marked_skipped_not_silently_dropped(self, engine):
        """Previously: missing 'odds' fell back to our_prob → edge=0 → silent zero
        trades. Now: market is recorded with skip_reason so the user can see why."""
        signals = [
            {"market_id": "m1", "probability": 0.7, "confidence": 0.9},
            {"market_id": "m2", "probability": 0.3, "confidence": 0.8},
        ]
        outcomes = {"m1": "YES", "m2": "NO"}
        result = engine.run("missing-odds", signals, outcomes)

        assert result["total_trades"] == 2
        for t in result["trades"]:
            assert t["direction"] == "SKIPPED"
            assert t.get("skip_reason") == "no_market_odds"
            assert t["pnl"] == 0.0
        assert result["final_bankroll"] == result["initial_bankroll"]

    def test_signals_with_odds_actually_trade(self, engine):
        signals = [
            {"market_id": "m1", "probability": 0.7, "confidence": 0.9, "odds": 0.5},
        ]
        outcomes = {"m1": "YES"}
        result = engine.run("with-odds", signals, outcomes)

        actionable = [t for t in result["trades"] if t["direction"] != "SKIPPED"]
        assert len(actionable) == 1
        assert actionable[0]["stake_usdc"] > 0
