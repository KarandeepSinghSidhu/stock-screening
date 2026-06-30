from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.screener_service import run_screener, SECTOR_LABELS
from app.services.stock_service import get_news


def build_weekly_report(
    sectors: list = None,
    top_n: int = 8,
    horizon: str = "long",
    risk_appetite: str = "balanced",
) -> dict:
    """
    Build a full weekly report tailored to the user's chosen sectors,
    investing horizon, and risk appetite. Each stock is enriched with
    recent news headlines.
    """
    if not sectors:
        sectors = ["tech", "health"]

    screener_data = run_screener(
        sectors=sectors, top_n=top_n, horizon=horizon, risk_appetite=risk_appetite
    )
    stocks = screener_data["stocks"]

    def attach_news(stock):
        try:
            stock["news"] = get_news(stock["ticker"], limit=4)
        except Exception:
            stock["news"] = []
        return stock

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(attach_news, s) for s in stocks]
        for f in as_completed(futures):
            f.result()

    stocks.sort(key=lambda x: x["composite_score"], reverse=True)

    sector_labels = [SECTOR_LABELS.get(s, s) for s in sectors]

    return {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "report_week": datetime.now().strftime("Week of %B %d, %Y"),
        "sectors": sectors,
        "sector_labels": sector_labels,
        "horizon": horizon,
        "horizon_label": "Short-term (weeks to months)" if horizon == "short" else "Long-term (years)",
        "risk_appetite": risk_appetite,
        "universe_screened": screener_data["universe_screened"],
        "results_returned": screener_data["results_returned"],
        "avg_composite_score": screener_data["avg_composite_score"],
        "buy_signals": screener_data["buy_signals"],
        "stocks": stocks,
    }