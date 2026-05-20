"""
Arc Predict Agent SDK - 预测市场Agent Python SDK
3行代码完成市场分析、仓位计算、推荐发布
"""

import urllib.request
import json


class PredictAgent:
    """预测市场Agent SDK"""

    def __init__(self, base_url: str = "http://localhost:5002"):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, data: dict = None) -> dict:
        url = f"{self.base_url}/api/{path}"
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        response = urllib.request.urlopen(req)
        return json.loads(response.read().decode("utf-8"))

    # ==================== Signal ====================

    def add_signal(self, market_id: str, source: str, value: float,
                   signal_type: str = "generic", confidence: float = 0.5) -> dict:
        """Submit a new signal observation for a market.

        Each signal contributes to the aggregated probability estimate. Higher
        confidence signals get more weight. Returns the API response dict.
        """
        return self._request("POST", "signal", {
            "market_id": market_id, "source": source, "value": value,
            "type": signal_type, "confidence": confidence
        })

    # ==================== Analysis ====================

    def analyze_market(self, market_id: str) -> dict:
        """Run the aggregator + probability engine on this market.

        Returns dict with our_probability, market_odds, edge, direction,
        and confidence — the inputs you'd feed into kelly_size().
        """
        return self._request("POST", "analyze", {"market_id": market_id})

    def get_market(self, market_id: str) -> dict:
        """Fetch one market's metadata and current estimate."""
        return self._request("GET", f"market/{market_id}")

    def list_markets(self) -> list:
        """Return all tracked markets as a list of dicts."""
        return self._request("GET", "markets").get("markets", [])

    # ==================== Kelly ====================

    def kelly_size(self, bankroll: float, probability: float,
                   market_odds: float, fraction: float = 0.25) -> dict:
        """Compute the optimal stake using fractional Kelly.

        bankroll       — current USDC balance available for sizing
        probability    — our estimate of the YES outcome (0..1)
        market_odds    — current market price for YES (0..1)
        fraction       — Kelly fraction (default 0.25 = quarter-Kelly)

        Returns dict with stake_usdc, expected_value, edge, kelly_pct.
        """
        return self._request("POST", "kelly", {
            "bankroll": bankroll, "probability": probability,
            "market_odds": market_odds, "fraction": fraction
        })

    def kelly_history(self) -> list:
        """Return previous sizing recommendations made by the API."""
        return self._request("GET", "kelly/history").get("recommendations", [])

    # ==================== Builder ====================

    def publish_recommendation(self, market_id: str, direction: str,
                               probability: float, sizing: dict = None) -> dict:
        """Publish a builder-coded recommendation that earns on every fill.

        direction must be 'YES' or 'NO'. Optional sizing dict (returned by
        kelly_size) attaches stake/edge/EV fields for downstream consumers.
        """
        data = {
            "market_id": market_id, "direction": direction,
            "probability": probability
        }
        if sizing:
            data["stake_usdc"] = sizing.get("stake_usdc")
            data["expected_value"] = sizing.get("expected_value")
            data["edge"] = sizing.get("edge")
        return self._request("POST", "builder/publish", data)

    def builder_feed(self) -> list:
        """Return the public feed of all active builder recommendations."""
        return self._request("GET", "builder/feed").get("recommendations", [])

    def builder_earnings(self) -> dict:
        """Return cumulative builder-fee earnings for this account."""
        return self._request("GET", "builder/earnings").get("earnings", {})

    # ==================== Quick Flow ====================

    def quick_analysis(self, market_id: str, bankroll: float = 1000) -> dict:
        """一键完成：分析 → Kelly → 发布推荐"""
        # 分析
        analysis = self.analyze_market(market_id)
        if not analysis.get("success") or analysis.get("direction") == "neutral":
            return {"skipped": True, "reason": "No edge found"}

        # Kelly
        sizing = self.kelly_size(
            bankroll=bankroll,
            probability=analysis["our_probability"],
            market_odds=analysis["market_odds"]
        )

        # 发布
        rec = self.publish_recommendation(
            market_id=market_id,
            direction=analysis["direction"],
            probability=analysis["our_probability"],
            sizing=sizing
        )

        return {
            "analysis": analysis,
            "sizing": sizing,
            "recommendation": rec
        }
