import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.stock_service import get_fundamentals

# Sector-organised universe across all supported themes
UNIVERSE = {
    "tech": [
        "NVDA", "MSFT", "GOOGL", "META", "AMZN", "AVGO", "AMD",
        "CRWD", "SNOW", "DDOG", "NET", "PLTR", "ARM", "SMCI",
        "ASML", "TSM", "ANET",
    ],
    "health": [
        "LLY", "UNH", "NVO", "JNJ", "ABBV", "MRK", "PFE",
        "ISRG", "REGN", "VRTX", "GILD", "TMO", "DHR", "AMGN",
    ],
    "energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "PSX", "OXY",
        "NEE", "ENPH", "FSLR",
    ],
    "finance": [
        "JPM", "V", "MA", "BAC", "GS", "MS", "BRK-B",
        "SCHW", "BLK", "AXP",
    ],
    "consumer": [
        "AMZN", "COST", "WMT", "NKE", "SBUX", "MCD", "TGT",
        "HD", "LOW", "DIS",
    ],
    "industrials": [
        "CAT", "BA", "HON", "UNP", "GE", "RTX", "LMT",
        "DE", "UPS", "ETN",
    ],
}

SECTOR_LABELS = {
    "tech": "Technology & AI",
    "health": "Healthcare",
    "energy": "Energy",
    "finance": "Finance",
    "consumer": "Consumer",
    "industrials": "Industrials",
}


def _score_stock(data: dict, horizon: str = "long", risk_appetite: str = "balanced") -> float:
    """
    Composite scoring, tunable by investing horizon and risk appetite.

    horizon: 'short' (momentum/news-driven) | 'long' (fundamentals/compounding)
    risk_appetite: 'conservative' | 'balanced' | 'aggressive'
    """
    g = data.get("growth", {})
    v = data.get("valuation", {})
    r = data.get("risk", {})
    d = data.get("dividend", {})
    m = data.get("moat", {})
    pl = data.get("price_levels", {})

    eps_g = g.get("eps_growth_fwd_pct") or 0
    rev_g = g.get("revenue_growth_pct") or 0
    pe = v.get("pe_trailing") or v.get("pe_forward") or 999
    de = data.get("balance_sheet", {}).get("debt_to_equity") or 0
    risk_score = r.get("score") or 5
    moat = m.get("overall") or 50
    div_sustain = d.get("sustainability_score") or 0

    # Momentum proxy: price vs 50/200 day MA
    momentum = 0
    current = pl.get("current")
    ma50 = pl.get("ma_50")
    ma200 = pl.get("ma_200")
    if current and ma50 and ma200:
        if current > ma50 > ma200:
            momentum = 100
        elif current > ma50:
            momentum = 65
        elif current > ma200:
            momentum = 40
        else:
            momentum = 15

    score = 0.0
    if horizon == "short":
        # Weight momentum and earnings growth heavily; less on long-term moat/dividend
        score += min(eps_g / 100, 1.0) * 25
        score += (momentum / 100) * 35
        score += min(rev_g / 30, 1.0) * 15
        pe_score = 1.0 if pe < 25 else 0.6 if pe < 45 else 0.2
        score += pe_score * 10
        score += (moat / 100) * 10
        score += max(0, 1 - (risk_score - 1) / 9) * 5
    else:
        # Long-term: fundamentals, moat, dividend stability, balance sheet
        score += min(eps_g / 100, 1.0) * 25
        score += min(rev_g / 30, 1.0) * 20
        de_score = 1.0 if de < 0.3 else 0.6 if de < 0.8 else 0.2
        score += de_score * 15
        score += (moat / 100) * 25
        score += (div_sustain / 100) * 5
        score += max(0, 1 - (risk_score - 1) / 9) * 10

    # Risk appetite adjustment: penalise/reward based on stock's own risk score
    if risk_appetite == "conservative" and risk_score > 5:
        score *= 0.85
    elif risk_appetite == "aggressive" and risk_score <= 4:
        score *= 0.92  # slightly de-prioritise overly safe picks for aggressive investors

    return round(min(score, 100), 1)


def run_screener(sectors: list = None, top_n: int = 10, horizon: str = "long", risk_appetite: str = "balanced") -> dict:
    """Screen selected sectors and return top N ranked stocks."""
    if not sectors:
        sectors = list(UNIVERSE.keys())

    tickers = set()
    for sec in sectors:
        tickers.update(UNIVERSE.get(sec, []))
    tickers = list(tickers)

    results = []

    def fetch(ticker):
        try:
            data = get_fundamentals(ticker)
            data["composite_score"] = _score_stock(data, horizon, risk_appetite)
            return data
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch, t): t for t in tickers}
        for f in as_completed(futures):
            result = f.result()
            if result and result.get("current_price"):
                results.append(result)

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    top = results[:top_n]

    avg_score = round(sum(r["composite_score"] for r in top) / len(top), 1) if top else 0
    buy_count = sum(1 for r in top if r.get("rating") == "Buy")

    return {
        "universe_screened": len(tickers),
        "results_returned": len(top),
        "avg_composite_score": avg_score,
        "buy_signals": buy_count,
        "sectors": sectors,
        "horizon": horizon,
        "risk_appetite": risk_appetite,
        "stocks": top,
    }