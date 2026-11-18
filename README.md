# DeFi & Token Intelligence Scanner (Vercel)

Defensive EVM research dashboard with a static web frontend and Python serverless API.

## Features
- Clayton Copula lower-tail dependence from paired price history.
- Solidity source-pattern triage (heuristics, not proof of exploitability).
- Oracle freshness, positivity, and cross-source deviation checks.
- Liquidity reserve/TVL decline and raw reserve imbalance checks.
- Transaction anomaly heuristics: large value, call count, borrow/repay in one transaction, and multi-protocol activity.
- JSON investigation report and responsive dashboard.

## Deploy
1. Import `LoOp575/Rs` in Vercel.
2. Keep the project root at repository root.
3. No build command or output directory is required for `index.html`.
4. Vercel detects `api/scan.py` as a Python Function and installs dependencies from `requirements.txt`.
5. Deploy, open the generated URL, and press **Jalankan demo**.

Health check: `GET /api/scan`. Analysis: `POST /api/scan`.

## API
Demo request:
```bash
curl -X POST https://YOUR-VERCEL-DOMAIN/api/scan -H "Content-Type: application/json" -d '{"demo":true}'
```
Custom request fields: `solidity_source` (string), `prices_csv` (CSV string with date and asset columns), `asset_x`, `asset_y`, `oracle_observations` (array), `pool_snapshots` (array), and `transactions` (array). Clayton requires at least 101 aligned price rows.

## Important limitations
- This is a dashboard/API for supplied data. It does not yet crawl EVM chains or fetch verified source, logs, oracle rounds, or pool reserves automatically.
- No persistent scan history is stored. Add Supabase or another database if persistence is needed.
- Request body limit is 2 MB; each JSON array is capped at 10,000 records.
- Never submit private keys or seed phrases. The app does not sign or submit transactions.
- Findings are triage signals. `exploit_confirmed` remains false. Flash-loan-like activity can be legitimate. Clayton measures market dependence, not exploit probability.
- Only analyze systems you own or are authorized to assess.

## Local tests
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```
For local Vercel emulation, install Vercel CLI and run `vercel dev`.
