import yfinance as yf
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta


def get_fundamentals(ticker: str) -> dict:
    """Pull full fundamental data for a single ticker."""
    t = yf.Ticker(ticker)
    info = t.info

    # --- P/E and valuation ---
    pe = info.get("trailingPE") or info.get("forwardPE")
    forward_pe = info.get("forwardPE")
    pb = info.get("priceToBook")
    ps = info.get("priceToSalesTrailing12Months")
    ev_ebitda = info.get("enterpriseToEbitda")

    # --- Growth ---
    eps_ttm = info.get("trailingEps")
    eps_fwd = info.get("forwardEps")
    eps_growth = None
    if eps_ttm and eps_fwd and eps_ttm != 0:
        eps_growth = round((eps_fwd - eps_ttm) / abs(eps_ttm) * 100, 1)

    revenue_growth = info.get("revenueGrowth")
    earnings_growth = info.get("earningsGrowth")

    # --- 5-year revenue trend ---
    revenue_history = _get_revenue_history(t)

    # --- Balance sheet ---
    debt_equity = info.get("debtToEquity")
    if debt_equity:
        debt_equity = round(debt_equity / 100, 2)  # yfinance returns as %, normalise
    current_ratio = info.get("currentRatio")
    quick_ratio = info.get("quickRatio")

    # --- Dividend ---
    div_yield = info.get("dividendYield")
    div_rate = info.get("dividendRate")
    payout_ratio = info.get("payoutRatio")
    five_yr_div_growth = info.get("fiveYearAvgDividendYield")
    div_sustainability = _score_dividend(div_yield, payout_ratio, earnings_growth)

    # --- Price and targets ---
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    target_mean = info.get("targetMeanPrice")
    target_high = info.get("targetHighPrice")
    target_low = info.get("targetLowPrice")
    beta = info.get("beta")

    # --- Risk score ---
    risk_score = _compute_risk(beta, debt_equity, pe, revenue_growth)

    # --- Entry / stop zones ---
    week_52_low = info.get("fiftyTwoWeekLow")
    week_52_high = info.get("fiftyTwoWeekHigh")
    ma_50 = info.get("fiftyDayAverage")
    ma_200 = info.get("twoHundredDayAverage")
    entry_zone, stop_loss = _compute_entry_stop(current_price, ma_50, ma_200, week_52_low)

    # --- Moat proxy scores ---
    moat = _score_moat(info)

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName", ticker),
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "market": _classify_market(info.get("country", "US")),
        "mkt_cap": _fmt_cap(info.get("marketCap")),
        "mkt_cap_raw": info.get("marketCap"),
        "currency": info.get("currency", "USD"),
        "current_price": current_price,
        "valuation": {
            "pe_trailing": round(pe, 1) if pe else None,
            "pe_forward": round(forward_pe, 1) if forward_pe else None,
            "price_to_book": round(pb, 2) if pb else None,
            "price_to_sales": round(ps, 2) if ps else None,
            "ev_ebitda": round(ev_ebitda, 1) if ev_ebitda else None,
        },
        "growth": {
            "eps_ttm": eps_ttm,
            "eps_forward": eps_fwd,
            "eps_growth_fwd_pct": eps_growth,
            "revenue_growth_pct": round(revenue_growth * 100, 1) if revenue_growth else None,
            "earnings_growth_pct": round(earnings_growth * 100, 1) if earnings_growth else None,
            "revenue_5yr": revenue_history,
        },
        "balance_sheet": {
            "debt_to_equity": debt_equity,
            "current_ratio": round(current_ratio, 2) if current_ratio else None,
            "quick_ratio": round(quick_ratio, 2) if quick_ratio else None,
        },
        "dividend": {
            "yield_pct": round(div_yield, 2) if div_yield else 0,
            "annual_rate": div_rate,
            "payout_ratio_pct": round(payout_ratio * 100, 1) if payout_ratio else None,
            "five_yr_avg_yield": five_yr_div_growth,
            "sustainability_score": div_sustainability["score"],
            "sustainability_label": div_sustainability["label"],
            "sustainability_note": div_sustainability["note"],
        },
        "price_levels": {
            "current": current_price,
            "week_52_low": week_52_low,
            "week_52_high": week_52_high,
            "ma_50": round(ma_50, 2) if ma_50 else None,
            "ma_200": round(ma_200, 2) if ma_200 else None,
            "target_mean": target_mean,
            "target_high": target_high,
            "target_low": target_low,
            "entry_low": entry_zone[0],
            "entry_high": entry_zone[1],
            "stop_loss": stop_loss,
            "bull_target": target_high,
            "bear_target": target_low,
        },
        "risk": {
            "score": risk_score["score"],
            "label": risk_score["label"],
            "description": risk_score["description"],
            "beta": round(beta, 2) if beta else None,
        },
        "moat": moat,
        "rating": _derive_rating(risk_score["score"], eps_growth, revenue_growth, pe, target_mean, current_price),
    }


def get_news(ticker: str, limit: int = 8) -> list:
    """Pull recent news headlines for a ticker."""
    t = yf.Ticker(ticker)
    try:
        news = t.news or []
        return [
            {
                "title": n.get("content", {}).get("title") or n.get("title", ""),
                "publisher": n.get("content", {}).get("provider", {}).get("displayName") or n.get("publisher", ""),
                "published": n.get("content", {}).get("pubDate") or n.get("providerPublishTime", ""),
                "url": n.get("content", {}).get("canonicalUrl", {}).get("url") or n.get("link", ""),
            }
            for n in news[:limit]
        ]
    except Exception:
        return []


def _get_revenue_history(ticker_obj) -> list:
    """Extract 5 years of annual revenue."""
    try:
        fs = ticker_obj.financials
        if fs is None or fs.empty:
            return []
        total_rev = fs.loc["Total Revenue"] if "Total Revenue" in fs.index else None
        if total_rev is None:
            return []
        result = []
        for col in sorted(total_rev.index, reverse=True)[:5]:
            val = total_rev[col]
            if pd.notna(val):
                result.append({
                    "year": str(col.year) if hasattr(col, 'year') else str(col),
                    "revenue": int(val),
                    "revenue_fmt": _fmt_cap(int(val)),
                })
        return list(reversed(result))
    except Exception:
        return []


def _score_dividend(div_yield, payout_ratio, earnings_growth) -> dict:
    if not div_yield or div_yield == 0:
        return {"score": None, "label": "No dividend", "note": "Company does not pay a dividend."}
    score = 50
    if payout_ratio:
        if payout_ratio < 0.35:
            score += 30
        elif payout_ratio < 0.60:
            score += 15
        elif payout_ratio > 0.90:
            score -= 25
    if earnings_growth:
        if earnings_growth > 0.10:
            score += 20
        elif earnings_growth < 0:
            score -= 20
    score = max(0, min(100, score))
    if score >= 80:
        label = "Exceptional"
    elif score >= 65:
        label = "Strong"
    elif score >= 45:
        label = "Adequate"
    else:
        label = "At risk"
    return {
        "score": score,
        "label": label,
        "note": f"Payout ratio {round(payout_ratio*100,1)}% — {'ample' if payout_ratio < 0.5 else 'stretched'} FCF coverage." if payout_ratio else "Payout data unavailable.",
    }


def _compute_risk(beta, debt_equity, pe, revenue_growth) -> dict:
    score = 5
    if beta:
        if beta > 1.5:
            score += 2
        elif beta > 1.2:
            score += 1
        elif beta < 0.8:
            score -= 1
    if debt_equity:
        if debt_equity > 2:
            score += 2
        elif debt_equity > 1:
            score += 1
        elif debt_equity < 0.3:
            score -= 1
    if pe and pe > 50:
        score += 1
    if revenue_growth and revenue_growth < 0:
        score += 1
    score = max(1, min(10, score))
    labels = {
        range(1, 3): "Conservative",
        range(3, 5): "Low-moderate",
        range(5, 7): "Moderate",
        range(7, 9): "Elevated",
        range(9, 11): "Speculative",
    }
    label = next((v for k, v in labels.items() if score in k), "Moderate")
    descs = {
        "Conservative": "Low beta, strong balance sheet. Suitable for capital preservation mandates.",
        "Low-moderate": "Below-average volatility with manageable leverage.",
        "Moderate": "Market-correlated risk profile. Standard equity risk.",
        "Elevated": "Above-average volatility or leverage warrants position sizing discipline.",
        "Speculative": "High beta and/or significant balance sheet risk. Aggressive mandates only.",
    }
    return {"score": score, "label": label, "description": descs.get(label, "")}


def _compute_entry_stop(price, ma50, ma200, low_52):
    if not price:
        return (None, None), None
    entry_low = round(price * 0.96, 2)
    entry_high = round(price * 1.01, 2)
    if ma50:
        entry_low = round(min(entry_low, ma50 * 0.99), 2)
    stop = round(price * 0.89, 2)
    if ma200:
        stop = round(min(stop, ma200 * 0.97), 2)
    return (entry_low, entry_high), stop


def _score_moat(info) -> dict:
    """Proxy moat dimensions from available yfinance data."""
    gross_margin = info.get("grossMargins", 0) or 0
    operating_margin = info.get("operatingMargins", 0) or 0
    roe = info.get("returnOnEquity", 0) or 0
    roa = info.get("returnOnAssets", 0) or 0
    revenue_growth = info.get("revenueGrowth", 0) or 0

    brand = min(100, int(gross_margin * 120))
    switching = min(100, int(operating_margin * 200 + 30))
    network = min(100, int(roe * 150 + 20)) if roe > 0 else 20
    cost = min(100, int(roa * 200 + 30)) if roa > 0 else 30
    intangible = min(100, int(gross_margin * 100 + revenue_growth * 50))

    return {
        "brand": brand,
        "switching": switching,
        "network": network,
        "cost_advantage": cost,
        "intangible": intangible,
        "overall": round((brand + switching + network + cost + intangible) / 5),
    }


def _derive_rating(risk, eps_growth, rev_growth, pe, target, price) -> str:
    score = 0
    if eps_growth and eps_growth > 15:
        score += 2
    if rev_growth and rev_growth > 0.10:
        score += 1
    if target and price and target > price * 1.10:
        score += 2
    if risk and risk <= 5:
        score += 1
    if pe and pe > 60:
        score -= 1
    if score >= 4:
        return "Buy"
    if score >= 2:
        return "Hold"
    return "Underperform"


def _classify_market(country: str) -> str:
    eu = {"Germany", "France", "Netherlands", "Denmark", "Sweden", "Spain", "Italy", "Switzerland"}
    apac = {"China", "Japan", "South Korea", "Taiwan", "Australia", "India", "Hong Kong"}
    if country in eu:
        return "EU"
    if country in apac:
        return "APAC"
    return "US"


def _fmt_cap(val) -> str:
    if not val:
        return "N/A"
    if val >= 1e12:
        return f"{val/1e12:.1f}T"
    if val >= 1e9:
        return f"{val/1e9:.0f}B"
    if val >= 1e6:
        return f"{val/1e6:.0f}M"
    return str(val)
