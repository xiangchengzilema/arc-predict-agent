"""单元测试 - Kelly Criterion仓位计算器"""

import pytest, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kelly_sizer import KellySizer

@pytest.fixture
def ks(tmp_path):
    return KellySizer(str(tmp_path / "test.db"), default_fraction=0.25)

class TestKellyCalculation:
    def test_positive_edge_yes(self, ks):
        """Our prob > market odds → bet YES"""
        r = ks.calculate(bankroll=1000, our_probability=0.4, market_odds=0.25)
        assert r["direction"] == "YES"
        assert r["should_bet"] is True
        assert r["stake_usdc"] > 0
        assert r["full_kelly"] > 0

    def test_negative_edge_no(self, ks):
        """Our prob < market odds → bet NO"""
        r = ks.calculate(bankroll=1000, our_probability=0.2, market_odds=0.4)
        assert r["direction"] == "NO"
        assert r["should_bet"] is True
        assert r["stake_usdc"] > 0

    def test_no_edge(self, ks):
        """No edge → no bet"""
        r = ks.calculate(bankroll=1000, our_probability=0.5, market_odds=0.5)
        assert r["full_kelly"] == 0
        assert r["stake_usdc"] == 0
        assert r["should_bet"] is False

    def test_quarter_kelly(self, ks):
        """Quarter Kelly should be 25% of full Kelly"""
        r = ks.calculate(bankroll=1000, our_probability=0.5, market_odds=0.3)
        assert abs(r["adjusted_kelly"] - r["full_kelly"] * 0.25) < 0.001

    def test_different_fractions(self, ks):
        """Different Kelly fractions"""
        full = ks.calculate(1000, 0.5, 0.3, fraction=1.0)
        half = ks.calculate(1000, 0.5, 0.3, fraction=0.5)
        quarter = ks.calculate(1000, 0.5, 0.3, fraction=0.25)
        assert full["stake_usdc"] > half["stake_usdc"] > quarter["stake_usdc"]

    def test_expected_value(self, ks):
        """Positive edge → positive EV"""
        r = ks.calculate(bankroll=1000, our_probability=0.5, market_odds=0.3)
        assert r["expected_value"] > 0

    def test_expected_value_formula_yes(self, ks):
        """EV must use p*payout - stake (payout includes principal), not p*payout - q*stake"""
        # YES bet: stake=$100, market_odds=0.3, our_prob=0.5
        # payout = 100/0.3 = 333.33; EV = 0.5*333.33 - 100 = 66.67
        r = ks.calculate(bankroll=1000, our_probability=0.5, market_odds=0.3, fraction=0.1)
        stake = r["stake_usdc"]
        if stake > 0 and r["direction"] == "YES":
            expected = round(stake * (1 / 0.3) * 0.5 - stake, 4)
            assert abs(r["expected_value"] - expected) < 0.01, (
                f"EV={r['expected_value']} vs expected {expected}"
            )

    def test_expected_value_formula_no(self, ks):
        """EV formula correct for NO direction"""
        # our_prob=0.2 < market_odds=0.4 → bet NO
        # NO payout = stake/(1-0.4) = stake/0.6; p_no = 0.8
        r = ks.calculate(bankroll=1000, our_probability=0.2, market_odds=0.4, fraction=0.1)
        stake = r["stake_usdc"]
        if stake > 0 and r["direction"] == "NO":
            expected = round(stake * (1 / (1 - 0.4)) * 0.8 - stake, 4)
            assert abs(r["expected_value"] - expected) < 0.01, (
                f"EV={r['expected_value']} vs expected {expected}"
            )

    def test_save_and_get(self, ks):
        """Save and retrieve recommendations"""
        r = ks.calculate(1000, 0.5, 0.3)
        rid = ks.save_recommendation("btc-100k", r)
        recs = ks.get_recommendations("btc-100k")
        assert len(recs) >= 1

    def test_stats(self, ks):
        """Stats endpoint"""
        r = ks.calculate(1000, 0.5, 0.3)
        ks.save_recommendation("btc-100k", r)
        stats = ks.get_stats()
        assert stats["total_recommendations"] >= 1
