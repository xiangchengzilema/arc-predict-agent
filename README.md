# Arc Predict Agent - AI Prediction Market Toolkit

An AI-powered prediction market toolkit for the [Arc](https://arc.network) ecosystem. Aggregates signals, estimates probabilities, sizes positions with Kelly Criterion, and monetizes agent recommendations via Polymarket Builder Code.

## Problem

AI agents can identify mispriced prediction markets, but lack:

1. **Signal aggregation** — News, sentiment, on-chain data scattered across sources
2. **Probability estimation** — No structured way to convert signals into calibrated probabilities
3. **Position sizing** — Agents overbet or underbet without Kelly Criterion
4. **Monetization** — Agent picks are valuable but currently earn zero revenue

Arc's ~$0.01 fees make micro-prediction strategies viable for the first time.

## Why Arc

| Arc Feature | Value for Prediction Markets |
|-------------|---------------------------|
| ~$0.01 fees | Bet $0.10, fee is only 10% (vs 2000%+ on Ethereum) |
| Sub-second finality | Lock in odds before they move |
| USDC native | Stable denomination — no gas token volatility |
| Nanopayments | Batch-settle hundreds of micro-bets |

## Architecture

```
Signals In          Processing           Output
──────────         ──────────          ─────────
News APIs  ──┐                          ┌── Market Report
Sentiment  ──┤──→ Signal Aggregator ──→ ├── Probability Est.
On-chain   ──┤    ↓                    ├── Kelly Sizing
Social     ──┘    Probability Engine   └── Builder Code (earn $)
                  ↓
              Kelly Criterion
                  ↓
              Position Manager
                  ↓
              Builder Feed (monetize)
```

## SDK Usage

```python
from predict_sdk import PredictAgent

agent = PredictAgent()

# Aggregate signals and estimate probability
analysis = agent.analyze_market(
    market_id="will-bitcoin-hit-100k",
    signals=["news", "sentiment", "onchain"]
)
# → {"probability": 0.35, "confidence": 0.82, "edge": 0.12}

# Calculate optimal position size
sizing = agent.kelly_size(
    bankroll=1000,        # USDC
    probability=0.35,     # our estimate
    market_odds=0.25,     # current market price
    fraction=0.25         # quarter-Kelly (conservative)
)
# → {"stake_usdc": 28.50, "expected_value": 8.92}

# Publish as builder recommendation (earns per fill)
agent.publish_recommendation(
    market_id="will-bitcoin-hit-100k",
    direction="YES",
    probability=0.35,
    sizing=sizing
)
```

## API Reference

### Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Analyze a market with all signals |
| `GET` | `/api/market/:id` | Get market data and our estimate |
| `GET` | `/api/markets` | List tracked markets |
| `POST` | `/api/signal` | Add a custom signal |

### Kelly Criterion
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/kelly` | Calculate optimal position size |
| `GET` | `/api/kelly/history` | Past sizing recommendations |

### Builder Feed
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/builder/publish` | Publish recommendation |
| `GET` | `/api/builder/feed` | Get builder feed |
| `GET` | `/api/builder/earnings` | Track builder earnings |

### Stats
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats` | Platform statistics |

## Use Cases

1. **AI Trading Agent** — Scan 1000+ markets, find +EV bets, auto-size with Kelly
2. **Content Creator** — Publish prediction feeds, earn via Builder Code
3. **Research Tool** — Aggregate signals, generate probability reports
4. **Vertical Markets** — Create custom prediction markets for specific domains

## Tech Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Math**: NumPy (Kelly Criterion, probability)
- **Signals**: News APIs, sentiment analysis, on-chain data
- **Monetization**: Polymarket Builder Code integration
- **Settlement**: USDC on Arc

## Roadmap

- [x] Signal aggregator with multi-source support
- [x] Probability estimation engine
- [x] Kelly Criterion position sizer
- [x] Builder Code monetization layer
- [x] Python SDK
- [x] Flask REST API
- [x] Unit tests
- [ ] Live market data integration
- [ ] Multi-market arbitrage detection
- [ ] Historical backtesting

## License

MIT License

## Author

Sicheng Zhang — Web3 Developer

## References

- [Kelly Criterion](https://en.wikipedia.org/wiki/Kelly_criterion)
- [Polymarket CLOB API](https://docs.polymarket.com)
- [Arc Documentation](https://docs.arc.network)
- [Canteen Research #2: Builder Codes](https://agora.thecanteenapp.com)
