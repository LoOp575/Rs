# Rs

## DeFi & Token Intelligence Scanner

Defensive, offline-first EVM research prototype. The complete source bundle is provided in `defi_token_intelligence_scanner.zip`.

### Contents
- Clayton Copula lower-tail dependence analysis
- Solidity source-pattern triage
- Oracle freshness and deviation checks
- Liquidity pool reserve/TVL change checks
- Transaction anomaly heuristics
- Local demo and unit tests

### Quick start

1. Download `defi_token_intelligence_scanner.zip` from this repository.
2. Extract it.
3. Follow `defi_token_intelligence_scanner/README.md`.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python scanner.py --demo
python -m unittest discover -s tests -v
```

**Important:** This version is an offline prototype. It does not connect to live EVM RPC endpoints or prove that a contract has been exploited. Heuristic findings require manual verification. Use only on contracts and systems you own or are authorized to assess.
