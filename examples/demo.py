#!/usr/bin/env python3
"""
Arc Predict Agent – Quick Demo
================================
Run this script to see the full prediction workflow in action:
  1. Register a market
  2. Add signals from multiple sources
  3. Run AI-style analysis
  4. Calculate Kelly Criterion position size
  5. Publish recommendation to Builder feed

Requirements: pip install -r requirements.txt && python app.py  (in another terminal)
"""
import json
import sys
import time
import urllib.request
import urllib.error
import os

BASE_URL = os.environ.get("PREDICT_API_URL", "http://localhost:5002")


def api(method, path, body=None):
    """Helper to call the REST API."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"\n  ERROR: Cannot reach API at {BASE_URL}")
        print(f"  Make sure the server is running: python app.py")
        print(f"  Details: {e}")
        sys.exit(1)


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    print("Arc Predict Agent – Demo")
    print("=" * 60)

    # ── Step 0: Check server ─────────────────────────────────────────────
    separator("Step 0: Check Server Status")
    stats = api("GET", "/api/stats")
    print(f"  Server is running!")
    print(f"  Markets: {stats.get('total_markets', 0)}")
    print(f"  Signals: {stats.get('total_signals', 0)}")

    # ── Step 1: Register a market ────────────────────────────────────────
    separator("Step 1: Register a Prediction Market")
    market = api("POST", "/api/markets", {
        "question": "Will Bitcoin exceed $100k by end of 2025?",
        "category": "crypto",
    })
    market_id = market.get("market_id", "demo_btc_100k")
    print(f"  Market: Will Bitcoin exceed $100k by end of 2025?")
    print(f"  ID: {market_id}")

    # ── Step 2: Add signals ──────────────────────────────────────────────
    separator("Step 2: Add Signals from Multiple Sources")
    sources = [
        {"source": "news_sentiment", "probability": 0.65, "confidence": 0.7,
         "notes": "Positive institutional adoption news"},
        {"source": "onchain_metrics", "probability": 0.58, "confidence": 0.8,
         "notes": "Whale accumulation increasing"},
        {"source": "social_twitter", "probability": 0.72, "confidence": 0.5,
         "notes": "Bullish sentiment trending"},
        {"source": "technical_analysis", "probability": 0.55, "confidence": 0.6,
         "notes": "Approaching resistance, RSI neutral"},
    ]

    for src in sources:
        result = api("POST", "/api/signal", {
            "market_id": market_id,
            **src,
        })
        sig_id = result.get("signal_id", "?")
        print(f"  Signal [{src['source']}]: prob={src['probability']:.0%} "
              f"conf={src['confidence']:.0%} → id={sig_id}")

    # ── Step 3: Analyze ──────────────────────────────────────────────────
    separator("Step 3: Run Multi-Source Analysis")
    analysis = api("POST", "/api/analyze", {"market_id": market_id})
    a = analysis.get("analysis", analysis)
    print(f"  Estimated probability: {a.get('probability', '?')}")
    print(f"  Confidence level:      {a.get('confidence', '?')}")
    print(f"  Recommended direction: {a.get('direction', '?')}")
    print(f"  Signal sources used:   {a.get('source_count', '?')}")

    # ── Step 4: Kelly Sizing ─────────────────────────────────────────────
    separator("Step 4: Kelly Criterion Position Sizing")
    kelly = api("POST", "/api/kelly", {
        "market_id": market_id,
        "bankroll": 1000.0,
        "our_probability": a.get("probability", 0.6),
        "market_odds": 0.55,
    })
    k = kelly.get("kelly", kelly)
    print(f"  Bankroll:        $1,000.00")
    print(f"  Full Kelly:      {k.get('full_kelly', '?')}")
    print(f"  Quarter Kelly:   {k.get('adjusted_kelly', '?')}")
    print(f"  Recommended bet: {k.get('direction', '?')}")
    print(f"  Stake USDC:      ${k.get('stake_usdc', '?')}")
    print(f"  Expected value:  ${k.get('expected_value', '?')}")
    print(f"  Expected ROI:    {k.get('expected_roi', '?')}")
    print(f"  Should bet:      {k.get('should_bet', '?')}")

    # ── Step 5: Publish ──────────────────────────────────────────────────
    separator("Step 5: Publish to Builder Feed")
    rec = api("POST", "/api/builder/publish", {
        "market_id": market_id,
        "direction": k.get("direction", "YES"),
        "probability": a.get("probability", 0.6),
        "odds": 0.55,
    })
    r = rec.get("recommendation", rec)
    print(f"  Published recommendation!")
    print(f"  Rec ID:    {r.get('rec_id', '?')}")
    print(f"  Direction: {r.get('direction', '?')}")
    print(f"  Expires:   {r.get('expires_at', '?')}")

    # ── Summary ──────────────────────────────────────────────────────────
    separator("Demo Complete!")
    print(f"""
  Full workflow executed successfully:
    1. Registered market: {market_id}
    2. Added {len(sources)} signals
    3. Analysis: {a.get('direction', '?')} @ {a.get('probability', '?')}
    4. Kelly sizing: ${k.get('stake_usdc', '?')}
    5. Published to Builder feed

  Next steps:
    - View dashboard: http://localhost:5002
    - CLI usage:      python cli.py --help
    - SDK usage:      see predict_sdk.py
    """)


if __name__ == "__main__":
    main()
