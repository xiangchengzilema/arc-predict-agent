# Contributing to Arc Predict Agent

Thank you for your interest in contributing! This project is part of the
[Arc ecosystem](https://docs.arc.network) and aims to bring intelligent
prediction market tooling to Arc's stablecoin-native blockchain.

## How to Contribute

### Bug Reports
1. Check existing [issues](../../issues) to avoid duplicates
2. Open a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Python version and OS

### Feature Requests
1. Describe the feature and why it's useful for prediction markets on Arc
2. Include any relevant API references or research
3. Tag with `enhancement` label

### Pull Requests
1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes with clear, descriptive commits
4. Add tests for new functionality
5. Ensure all tests pass: `pytest tests/ -v`
6. Run linting: `flake8 *.py --max-line-length=120`
7. Submit PR with a clear description

### Development Setup

```bash
# Clone and install
git clone https://github.com/xiangchengzilema/arc-predict-agent.git
cd arc-predict-agent
pip install -r requirements.txt
pip install pytest flake8

# Run tests
pytest tests/ -v

# Run linting
flake8 *.py --max-line-length=120

# Start the API server
python app.py

# Run demo
python examples/demo.py
```

### Code Style
- Python 3.10+ compatible
- Max line length: 120 characters
- Use type hints for function signatures
- Docstrings for all public functions and classes
- Follow PEP 8 conventions

### Project Structure
```
arc-predict-agent/
├── signal_aggregator.py   # Multi-source signal collection
├── kelly_sizer.py         # Kelly Criterion position sizer
├── builder_feed.py        # Polymarket Builder Code integration
├── predict_sdk.py         # Zero-dependency Python SDK
├── cli.py                 # Command-line interface
├── backtest.py            # Backtesting engine
├── risk_manager.py        # Portfolio risk management
├── app.py                 # Flask REST API
├── templates/             # Dashboard HTML
├── tests/                 # Test suite
├── examples/              # Usage examples
├── Dockerfile             # Docker support
└── docker-compose.yml     # Docker orchestration
```

### Areas We'd Love Help With
- Additional signal source integrations (RSS, APIs)
- More sophisticated analysis algorithms
- Frontend dashboard improvements
- Additional prediction market platform support
- Performance benchmarking and optimization
- Documentation and tutorials

## License
By contributing, you agree that your contributions will be licensed under
the MIT License.
