#!/usr/bin/env python3
"""arc-predict-agent 定时分批推送脚本 - 15天日活版本"""
import subprocess, json, os
from datetime import datetime

PROJECT_DIR = r"D:\币圈项目\arc空投\arc-predict-agent"

COMMITS = [
    # Day 1
    {"files": ["signal_aggregator.py"],
     "message": "feat: add multi-source signal aggregator with weighted probability estimation",
     "description": "Signal aggregator collecting from news, social, on-chain sources. Weighted confidence merging, market registration, analysis history, and full REST API support."},
    # Day 2
    {"files": ["kelly_sizer.py"],
     "message": "feat: add Kelly Criterion position sizer with quarter/half/full Kelly",
     "description": "Kelly Criterion calculator: full/adjusted Kelly, YES/NO direction, expected value, ROI, recommendation persistence. Default quarter-Kelly for conservative sizing."},
    # Day 3
    {"files": ["builder_feed.py"],
     "message": "feat: add Builder Code monetization layer for agent recommendation earnings",
     "description": "Polymarket Builder Code integration: publish signed recommendations, track fills, calculate per-fill earnings, auto-expire old recommendations."},
    # Day 4
    {"files": ["predict_sdk.py"],
     "message": "feat: add Python SDK with quick_analysis one-liner flow",
     "description": "PredictAgent SDK: add_signal, analyze_market, kelly_size, publish_recommendation, quick_analysis (analyze+kelly+publish in one call). Zero external dependencies."},
    # Day 5
    {"files": ["app.py"],
     "message": "feat: add Flask REST API with analysis, Kelly, and builder endpoints",
     "description": "Flask app with 12 API endpoints: signal ingestion, market CRUD, AI analysis, Kelly sizing, builder feed/earnings. Stats and health check endpoints."},
    # Day 6
    {"files": ["templates/index.html"],
     "message": "feat: add web dashboard with market table and recommendation feed",
     "description": "Responsive HTML dashboard: system stats cards, markets table, recommendations feed, recent signals list. Bootstrap-based, auto-refresh capable."},
    # Day 7
    {"files": ["tests/test_signal.py", "tests/test_kelly.py", "tests/__init__.py"],
     "message": "test: add unit tests for signal aggregator and Kelly sizer",
     "description": "Test suite covering signal aggregation, batch operations, Kelly calculations (positive/negative/no edge, different fractions). SQLite temp DB isolation."},
    # Day 8
    {"files": ["tests/test_builder.py", "tests/test_integration.py"],
     "message": "test: add builder feed tests and end-to-end integration tests",
     "description": "Builder publish/fill/deactivate tests. Integration tests: signal→analyze→kelly→publish pipeline, backtest engine, risk manager position checks."},
    # Day 9
    {"files": ["cli.py"],
     "message": "feat: add CLI tool for prediction analysis from command line",
     "description": "argparse-based CLI with 7 sub-commands: signal, analyze, kelly, publish, earnings, markets, stats. Zero external dependencies, connects to running API server."},
    # Day 10
    {"files": ["backtest.py"],
     "message": "feat: add backtesting engine with Kelly sizing and Sharpe ratio",
     "description": "Historical strategy simulator: signal-based trades, P&L tracking, win rate, max drawdown, annualized Sharpe ratio. Result comparison between strategy runs."},
    # Day 11
    {"files": ["risk_manager.py"],
     "message": "feat: add portfolio risk manager with circuit breaker and position limits",
     "description": "Pre-trade risk checks: max position size (10%), daily loss cap (5%), drawdown circuit breaker (15%), cooldown after big loss, correlated market limits."},
    # Day 12
    {"files": ["examples/demo.py"],
     "message": "docs: add full workflow demo script with 5-step prediction pipeline",
     "description": "Working demo: register market → add 4 signals → analyze → Kelly sizing → publish recommendation. Uses only stdlib urllib for API calls."},
    # Day 13
    {"files": ["README.md", "requirements.txt", ".gitignore", ".env.example"],
     "message": "docs: add README with SDK usage, API reference, and Arc advantages",
     "description": "Full documentation: problem statement, Arc fee advantages for prediction markets, SDK quickstart, 12-endpoint API reference, Kelly formula explanation, use cases."},
    # Day 14
    {"files": ["Dockerfile", "docker-compose.yml"],
     "message": "infra: add Docker support with health check and persistent volume",
     "description": "Dockerfile with health check endpoint, docker-compose with persistent volume for SQLite data, configurable Kelly fraction via environment variable."},
    # Day 15
    {"files": [".github/workflows/test.yml", "CONTRIBUTING.md", "LICENSE", "CHANGELOG.md"],
     "message": "infra: add CI/CD, contributing guide, license, and changelog",
     "description": "GitHub Actions with Python 3.10/3.11/3.12 matrix + flake8 linting. MIT License, contributing guidelines with dev setup, detailed changelog."},
]

def run_git(args):
    return subprocess.run(["git"] + args, cwd=PROJECT_DIR, capture_output=True, text=True)

def get_step():
    try:
        with open(f"{PROJECT_DIR}/commit_state.json", "r") as f:
            return json.load(f).get("completed_count", 0)
    except:
        return 0

def save_step(n):
    with open(f"{PROJECT_DIR}/commit_state.json", "w") as f:
        json.dump({"completed_count": n, "last_run": datetime.now().isoformat()}, f)

def main():
    step = get_step()
    if step >= len(COMMITS):
        print(f"All {len(COMMITS)} commits done! No more to push.")
        return
    c = COMMITS[step]
    print(f"[Day {step+1}/{len(COMMITS)}] {c['message']}")
    for f in c["files"]:
        run_git(["add", f])
    msg = f"{c['message']}\n\n{c['description']}\n\nCo-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    r = run_git(["commit", "-m", msg])
    if r.returncode != 0:
        print(f"  Commit failed: {r.stderr}")
        return
    r = run_git(["push", "origin", "main"])
    if r.returncode != 0:
        print(f"  Push failed: {r.stderr}")
        return
    save_step(step + 1)
    remaining = len(COMMITS) - step - 1
    print(f"  Pushed! ({remaining} days remaining)")
    if remaining == 0:
        print(f"  All {len(COMMITS)} commits complete! Daily activity finished.")

if __name__ == "__main__":
    main()
