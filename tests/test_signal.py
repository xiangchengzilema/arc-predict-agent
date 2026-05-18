"""单元测试 - 信号聚合器"""

import pytest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from signal_aggregator import SignalAggregator

@pytest.fixture
def agg(tmp_path):
    return SignalAggregator(str(tmp_path / "test.db"))

class TestSignalAggregator:
    def test_add_signal(self, agg):
        sid = agg.add_signal("btc-100k", "news", "sentiment", 0.7, 0.8)
        assert sid > 0

    def test_add_batch(self, agg):
        count = agg.add_signals_batch("btc-100k", [
            {"source": "news", "type": "sentiment", "value": 0.7, "confidence": 0.8},
            {"source": "twitter", "type": "social", "value": 0.6, "confidence": 0.6},
            {"source": "onchain", "type": "volume", "value": 0.8, "confidence": 0.9}
        ])
        assert count == 3

    def test_aggregate_empty(self, agg):
        result = agg.aggregate_signals("nonexistent")
        assert result["probability"] == 0.5
        assert result["signal_count"] == 0

    def test_aggregate_signals(self, agg):
        agg.add_signals_batch("btc-100k", [
            {"source": "news", "value": 0.7, "confidence": 0.8},
            {"source": "social", "value": 0.6, "confidence": 0.6}
        ])
        result = agg.aggregate_signals("btc-100k")
        assert result["signal_count"] == 2
        assert 0.5 < result["probability"] < 0.8

class TestMarket:
    def test_register_market(self, agg):
        result = agg.register_market("btc-100k", "Will BTC hit 100K?")
        assert result["status"] == "created"

    def test_get_market(self, agg):
        agg.register_market("btc-100k", "BTC 100K")
        m = agg.get_market("btc-100k")
        assert m["title"] == "BTC 100K"

    def test_list_markets(self, agg):
        for i in range(3):
            agg.register_market(f"market-{i}", f"Market {i}")
        markets = agg.list_markets()
        assert len(markets) == 3

class TestAnalysis:
    def test_analyze_market(self, agg):
        agg.register_market("btc-100k", "BTC 100K", current_odds=0.25)
        agg.add_signals_batch("btc-100k", [
            {"source": "news", "value": 0.4, "confidence": 0.7},
            {"source": "social", "value": 0.3, "confidence": 0.5},
            {"source": "onchain", "value": 0.5, "confidence": 0.8}
        ])
        result = agg.analyze_market("btc-100k")
        assert "our_probability" in result
        assert "edge" in result
        assert result["signal_count"] == 3

    def test_analysis_history(self, agg):
        agg.register_market("btc-100k", "BTC", current_odds=0.5)
        agg.add_signal("btc-100k", "test", "test", 0.6)
        agg.analyze_market("btc-100k")
        agg.add_signal("btc-100k", "test2", "test", 0.7)
        agg.analyze_market("btc-100k")
        history = agg.get_analysis_history("btc-100k")
        assert len(history) == 2
