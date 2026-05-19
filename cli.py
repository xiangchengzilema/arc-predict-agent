#!/usr/bin/env python3
"""Arc Predict Agent CLI - Command-line interface for prediction market analysis."""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_BASE = os.environ.get("PREDICT_API_URL", "http://localhost:5002")

# ── helpers ──────────────────────────────────────────────────────────────────

def _api(method, path, body=None):
    """Call the predict-agent REST API."""
    url = f"{DEFAULT_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"API error {e.code}: {err}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError:
        print("Cannot reach API – is the server running? (python app.py)", file=sys.stderr)
        sys.exit(1)


# ── sub-commands ─────────────────────────────────────────────────────────────

def cmd_signal(args):
    """Add a new signal to the aggregator."""
    payload = {
        "market_id": args.market_id,
        "source": args.source,
        "probability": args.probability,
        "confidence": getattr(args, "confidence", 0.5),
        "notes": getattr(args, "notes", ""),
    }
    result = _api("POST", "/api/signal", payload)
    print(f"Signal added  id={result['signal_id']}  "
          f"source={payload['source']}  prob={payload['probability']}")


def cmd_analyze(args):
    """Run AI-style analysis on a market."""
    result = _api("POST", "/api/analyze", {"market_id": args.market_id})
    a = result.get("analysis", result)
    print(f"Market: {args.market_id}")
    print(f"  Probability: {a.get('probability', '?')}")
    print(f"  Confidence:  {a.get('confidence', '?')}")
    print(f"  Direction:   {a.get('direction', '?')}")
    print(f"  Sources:     {a.get('source_count', '?')}")
    print(f"  Kelly edge:  {a.get('kelly_edge', '?')}")


def cmd_kelly(args):
    """Calculate Kelly Criterion position size."""
    payload = {
        "market_id": args.market_id,
        "bankroll": args.bankroll,
        "our_probability": args.prob,
        "market_odds": args.odds,
    }
    result = _api("POST", "/api/kelly", payload)
    k = result.get("kelly", result)
    print(f"Kelly Analysis for {args.market_id}")
    print(f"  Direction:     {k.get('direction', '?')}")
    print(f"  Kelly %:       {k.get('full_kelly', '?'):.2%}" if isinstance(k.get('full_kelly'), (int, float)) else f"  Kelly %:       {k.get('full_kelly', '?')}")
    print(f"  Adjusted %:    {k.get('adjusted_kelly', '?')}")
    print(f"  Stake USDC:    {k.get('stake_usdc', '?')}")
    print(f"  Expected Val:  {k.get('expected_value', '?')}")
    print(f"  Expected ROI:  {k.get('expected_roi', '?')}")
    print(f"  Should bet:    {k.get('should_bet', '?')}")


def cmd_publish(args):
    """Publish a recommendation to the Builder feed."""
    payload = {
        "market_id": args.market_id,
        "direction": args.direction,
        "probability": args.prob,
        "odds": args.odds,
    }
    result = _api("POST", "/api/builder/publish", payload)
    r = result.get("recommendation", result)
    print(f"Published recommendation")
    print(f"  Market:     {r.get('market_id', '?')}")
    print(f"  Direction:  {r.get('direction', '?')}")
    print(f"  Prob:       {r.get('probability', '?')}")
    print(f"  Rec ID:     {r.get('rec_id', '?')}")


def cmd_earnings(args):
    """Show Builder Code earnings summary."""
    result = _api("GET", "/api/builder/earnings")
    e = result.get("earnings", result)
    print("Builder Earnings Summary")
    print(f"  Total fills:    {e.get('total_fills', 0)}")
    print(f"  Total earned:   ${e.get('total_earned_usdc', 0):.2f}" if isinstance(e.get('total_earned_usdc'), (int, float)) else f"  Total earned:   {e.get('total_earned_usdc', '?')}")
    print(f"  Active recs:    {e.get('active_recommendations', 0)}")
    print(f"  Expired recs:   {e.get('expired_recommendations', 0)}")


def cmd_markets(args):
    """List registered markets."""
    result = _api("GET", "/api/markets")
    markets = result.get("markets", [])
    if not markets:
        print("No markets registered yet.")
        return
    print(f"{'ID':<20} {'Question':<40} {'Status':<10}")
    print("-" * 72)
    for m in markets:
        print(f"{m.get('id', '?'):<20} {m.get('question', '?')[:40]:<40} {m.get('status', '?'):<10}")


def cmd_stats(args):
    """Show system statistics."""
    result = _api("GET", "/api/stats")
    print("Predict Agent Stats")
    for k, v in result.items():
        print(f"  {k}: {v}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="arc-predict",
        description="Arc Predict Agent CLI – prediction market analysis & Kelly sizing",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # signal
    p_sig = sub.add_parser("signal", help="Add a signal")
    p_sig.add_argument("--market-id", required=True)
    p_sig.add_argument("--source", required=True, help="e.g. news, twitter, onchain")
    p_sig.add_argument("--probability", type=float, required=True)
    p_sig.add_argument("--confidence", type=float, default=0.5)
    p_sig.add_argument("--notes", default="")

    # analyze
    p_an = sub.add_parser("analyze", help="Analyze a market")
    p_an.add_argument("--market-id", required=True)

    # kelly
    p_kel = sub.add_parser("kelly", help="Kelly Criterion sizing")
    p_kel.add_argument("--market-id", required=True)
    p_kel.add_argument("--bankroll", type=float, required=True)
    p_kel.add_argument("--prob", type=float, required=True, help="Your estimated probability")
    p_kel.add_argument("--odds", type=float, required=True, help="Current market odds")

    # publish
    p_pub = sub.add_parser("publish", help="Publish recommendation")
    p_pub.add_argument("--market-id", required=True)
    p_pub.add_argument("--direction", required=True, choices=["YES", "NO"])
    p_pub.add_argument("--prob", type=float, required=True)
    p_pub.add_argument("--odds", type=float, required=True)

    # earnings
    sub.add_parser("earnings", help="Show builder earnings")

    # markets
    sub.add_parser("markets", help="List registered markets")

    # stats
    sub.add_parser("stats", help="Show system stats")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "signal": cmd_signal,
        "analyze": cmd_analyze,
        "kelly": cmd_kelly,
        "publish": cmd_publish,
        "earnings": cmd_earnings,
        "markets": cmd_markets,
        "stats": cmd_stats,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
