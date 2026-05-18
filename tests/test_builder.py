"""单元测试 - Builder Feed"""

import pytest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from builder_feed import BuilderFeed

@pytest.fixture
def bf(tmp_path):
    return BuilderFeed(str(tmp_path / "test.db"))

class TestBuilderFeed:
    def test_publish(self, bf):
        r = bf.publish("btc-100k", "YES", 0.45, 0.8, edge=0.12, stake_usdc=28.5)
        assert r["status"] == "active"
        assert r["rec_id"].startswith("rec_")

    def test_get_feed(self, bf):
        bf.publish("btc-100k", "YES", 0.45, 0.8)
        bf.publish("eth-5k", "NO", 0.3, 0.7)
        feed = bf.get_feed()
        assert len(feed) == 2

    def test_get_recommendation(self, bf):
        pub = bf.publish("btc-100k", "YES", 0.45, 0.8)
        rec = bf.get_recommendation(pub["rec_id"])
        assert rec["direction"] == "YES"
        assert rec["probability"] == 0.45

    def test_record_fill(self, bf):
        pub = bf.publish("btc-100k", "YES", 0.45, 0.8)
        fill = bf.record_fill(pub["rec_id"], fill_amount=100, fee_rate=0.01)
        assert fill["fee_earned"] == 1.0

    def test_deactivate(self, bf):
        pub = bf.publish("btc-100k", "YES", 0.45, 0.8)
        assert bf.deactivate(pub["rec_id"]) is True
        rec = bf.get_recommendation(pub["rec_id"])
        assert rec["status"] == "expired"

    def test_earnings(self, bf):
        pub = bf.publish("btc-100k", "YES", 0.45, 0.8)
        bf.record_fill(pub["rec_id"], 100, 0.01)
        bf.record_fill(pub["rec_id"], 200, 0.01)
        earnings = bf.get_earnings()
        assert earnings["total_fills"] == 2
        assert earnings["total_earnings_usdc"] == 3.0
