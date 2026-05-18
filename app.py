"""Arc Predict Agent - Flask Application"""

from flask import Flask, request, jsonify, render_template
from signal_aggregator import SignalAggregator
from kelly_sizer import KellySizer
from builder_feed import BuilderFeed
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
aggregator = SignalAggregator(os.getenv("DATABASE_PATH", "predict.db"))
kelly = KellySizer(os.getenv("DATABASE_PATH", "predict.db"), float(os.getenv("KELLY_FRACTION", "0.25")))
builder = BuilderFeed(os.getenv("DATABASE_PATH", "predict.db"))


# ==================== Pages ====================

@app.route("/")
def index():
    stats = aggregator.get_stats()
    kelly_stats = kelly.get_stats()
    earnings = builder.get_earnings()
    markets = aggregator.list_markets(limit=10)
    recs = builder.get_feed(limit=5)
    return render_template("index.html",
                           stats=stats, kelly_stats=kelly_stats,
                           earnings=earnings, markets=markets, recs=recs)


# ==================== Signal API ====================

@app.route("/api/signal", methods=["POST"])
def api_add_signal():
    data = request.get_json()
    if not data or not data.get("market_id") or "value" not in data:
        return jsonify({"success": False, "error": "market_id and value required"}), 400
    sid = aggregator.add_signal(
        market_id=data["market_id"],
        source=data.get("source", "api"),
        signal_type=data.get("type", "generic"),
        value=float(data["value"]),
        confidence=float(data.get("confidence", 0.5)),
        weight=float(data.get("weight", 1.0))
    )
    return jsonify({"success": True, "signal_id": sid})


# ==================== Market API ====================

@app.route("/api/market/<market_id>")
def api_get_market(market_id):
    market = aggregator.get_market(market_id)
    if market:
        return jsonify({"success": True, "market": market})
    return jsonify({"success": False, "error": "Market not found"}), 404


@app.route("/api/markets")
def api_list_markets():
    markets = aggregator.list_markets()
    return jsonify({"success": True, "markets": markets})


# ==================== Analysis API ====================

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json()
    if not data or not data.get("market_id"):
        return jsonify({"success": False, "error": "market_id required"}), 400

    market_id = data["market_id"]

    # Auto-register market if not exists
    if not aggregator.get_market(market_id):
        aggregator.register_market(
            market_id=market_id,
            title=data.get("title", market_id),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            current_odds=float(data.get("market_odds", 0.5))
        )

    result = aggregator.analyze_market(market_id)
    return jsonify({"success": True, "analysis": result})


# ==================== Kelly API ====================

@app.route("/api/kelly", methods=["POST"])
def api_kelly():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400

    required = ["bankroll", "probability", "market_odds"]
    for f in required:
        if f not in data:
            return jsonify({"success": False, "error": f"{f} required"}), 400

    result = kelly.calculate(
        bankroll=float(data["bankroll"]),
        our_probability=float(data["probability"]),
        market_odds=float(data["market_odds"]),
        fraction=float(data.get("fraction", 0.25))
    )

    # Save recommendation
    market_id = data.get("market_id", "unknown")
    kelly.save_recommendation(market_id, result)

    return jsonify({"success": True, "sizing": result})


@app.route("/api/kelly/history")
def api_kelly_history():
    market_id = request.args.get("market_id")
    recs = kelly.get_recommendations(market_id)
    return jsonify({"success": True, "recommendations": recs})


# ==================== Builder API ====================

@app.route("/api/builder/publish", methods=["POST"])
def api_builder_publish():
    data = request.get_json()
    if not data or not data.get("market_id") or not data.get("direction"):
        return jsonify({"success": False, "error": "market_id and direction required"}), 400

    result = builder.publish(
        market_id=data["market_id"],
        direction=data["direction"],
        probability=float(data.get("probability", 0.5)),
        confidence=float(data.get("confidence", 0.5)),
        edge=data.get("edge"),
        stake_usdc=data.get("stake_usdc"),
        expected_value=data.get("expected_value"),
        builder_code=data.get("builder_code", "")
    )
    return jsonify({"success": True, "recommendation": result})


@app.route("/api/builder/feed")
def api_builder_feed():
    recs = builder.get_feed()
    return jsonify({"success": True, "recommendations": recs})


@app.route("/api/builder/earnings")
def api_builder_earnings():
    earnings = builder.get_earnings()
    return jsonify({"success": True, "earnings": earnings})


# ==================== Stats ====================

@app.route("/api/stats")
def api_stats():
    return jsonify({
        "success": True,
        "markets": aggregator.get_stats(),
        "kelly": kelly.get_stats(),
        "builder": builder.get_earnings()
    })


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5002))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    print(f"\n  Arc Predict Agent on :{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
