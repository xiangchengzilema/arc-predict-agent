# Changelog

All notable changes to Arc Predict Agent are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-05-18

### Added
- **Flask REST API** (`app.py`): public HTTP endpoints for signal submission, probability analysis, Kelly sizing, and Builder Code earnings.
- **Python SDK** (`predict_sdk.py`): zero-dependency client wrapping the REST API.
- **Command-line tool** (`cli.py`): `signal`, `analyze`, `kelly`, `publish`, `earnings`, `markets`, `stats` subcommands.
- **Builder Code monetization** (`builder_feed.py`): per-signal attribution and royalty accrual.
- **Examples** (`examples/demo.py`): end-to-end usage walkthrough.
- **Containerization**: `Dockerfile` + `docker-compose.yml` for local + production deploy.
- **CI**: `.github/workflows/test.yml` runs the full test suite on every push.
- **Tests**: integration coverage in `tests/test_integration.py`, builder coverage in `tests/test_builder.py`, signal coverage in `tests/test_signal.py`.
- **MIT License** + `CONTRIBUTING.md`.

### Notes
- The full set of files above was developed locally between 2026-05-15 and 2026-05-17 but was only pushed to the public repository on 2026-05-18 (commit `97e90e0`). This release tags that point so the changelog matches the repo state.

## [0.1.0] - 2025-05-15

### Added
- **Signal Aggregator**: Multi-source signal collection with weighted probability estimation
  - News sentiment, social media, on-chain metrics, technical analysis sources
  - Configurable confidence weights per source
  - Signal history tracking with SQLite persistence
- **Kelly Criterion Sizer**: Optimal position sizing calculator
  - Full Kelly, half Kelly, quarter Kelly fractions
  - YES/NO direction detection based on edge
  - Expected value and ROI calculations
  - Conservative default (quarter Kelly = 0.25 fraction)
- **Builder Feed**: Polymarket Builder Code monetization layer
  - Publish signed recommendations with auto-expiry
  - Track fill events and per-fill earnings
  - Active/expired recommendation management
- **Python SDK** (`predict_sdk.py`): Zero-dependency client library
  - `quick_analysis()` one-liner: analyze → Kelly → publish
  - Full API coverage: signals, markets, analysis, Kelly, builder
  - Only uses Python stdlib (urllib)
- **Flask REST API**: 12 endpoints for integration
  - Signal ingestion and market CRUD
  - AI-style analysis engine
  - Kelly Criterion calculator
  - Builder feed management
  - Web dashboard with stats
- **CLI Tool** (`cli.py`): Command-line interface
  - `signal`, `analyze`, `kelly`, `publish`, `earnings`, `markets`, `stats` sub-commands
  - Zero external dependencies
- **Backtesting Engine**: Historical strategy simulation
  - Signal-based trade simulation with Kelly sizing
  - Win rate, P&L, max drawdown, Sharpe ratio tracking
  - Backtest result comparison
- **Risk Manager**: Portfolio-level risk controls
  - Position size limits (default 10% bankroll)
  - Daily loss caps (default 5%)
  - Drawdown circuit breaker (default 15%)
  - Cooldown period after big losses
  - Correlated market concentration limits
- **Docker support**: Dockerfile with health check + docker-compose
- **CI/CD**: GitHub Actions with Python 3.10/3.11/3.12 matrix
- **Tests**: 35+ unit and integration tests

### Arc Advantages
- ~$0.01 transaction fees enable micro-position prediction trading
- Sub-second finality for rapid signal-to-trade execution
- USDC-native: no gas token needed, direct stablecoin settlement
- Paymaster support: even transaction fees paid in USDC
