# Equity Research API

FastAPI + yfinance backend for the Goldman-level stock screener.

## Prerequisites

Make sure you have Python 3.11+ installed. Check with:

```bash
python3 --version
```

If you don't have it, install via [Homebrew](https://brew.sh):

```bash
brew install python
```

## Setup

```bash
cd equity-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

To stop the server: `Ctrl + C`

To deactivate the virtual environment when done: `deactivate`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stocks/{ticker}` | Full fundamental analysis |
| GET | `/api/stocks/{ticker}/news` | Recent headlines |
| GET | `/api/stocks/{ticker}/summary` | Lightweight summary |
| GET | `/api/screener/run?market=all&top_n=10` | Run screener |
| GET | `/health` | Health check |

### Market filters
`all` `us` `eu` `apac` `intl`

## Example responses

### `GET /api/stocks/NVDA`
```json
{
  "ticker": "NVDA",
  "name": "NVIDIA Corporation",
  "sector": "Technology",
  "rating": "Buy",
  "current_price": 875.40,
  "valuation": { "pe_trailing": 65.2, "pe_forward": 32.1, ... },
  "growth": { "eps_growth_fwd_pct": 38.4, "revenue_growth_pct": 94.0, ... },
  "balance_sheet": { "debt_to_equity": 0.4, ... },
  "dividend": { "sustainability_score": 92, "sustainability_label": "Exceptional", ... },
  "price_levels": { "entry_low": 840.0, "entry_high": 884.0, "stop_loss": 779.0, ... },
  "risk": { "score": 4, "label": "Low-moderate", ... },
  "moat": { "brand": 88, "switching": 74, "overall": 72 }
}
```

### `GET /api/screener/run?market=us&top_n=5`
```json
{
  "universe_screened": 22,
  "results_returned": 5,
  "avg_composite_score": 71.4,
  "buy_signals": 4,
  "stocks": [ ... ]
}
```

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Connect repo to [Railway](https://railway.app)
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Your API URL goes into your Next.js `.env.local` as `NEXT_PUBLIC_API_URL`

## Connect to your Next.js dashboard

In your dashboard, replace the mock `STOCKS` object fetch with:

```js
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/stocks/${ticker}`);
const data = await res.json();
```

And the screener run button:
```js
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/screener/run?market=all&top_n=10`);
const data = await res.json();
```