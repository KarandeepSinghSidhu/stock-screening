from fastapi import APIRouter, HTTPException, Query
from app.services.stock_service import get_fundamentals, get_news

router = APIRouter()


@router.get("/{ticker}")
def stock_analysis(ticker: str):
    """Full fundamental analysis for a single ticker."""
    try:
        return get_fundamentals(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch data for {ticker}: {str(e)}")


@router.get("/{ticker}/news")
def stock_news(ticker: str, limit: int = Query(8, ge=1, le=20)):
    """Recent news headlines for a ticker."""
    try:
        return {"ticker": ticker.upper(), "news": get_news(ticker.upper(), limit)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ticker}/summary")
def stock_summary(ticker: str):
    """Lightweight summary payload — price, rating, targets."""
    data = get_fundamentals(ticker.upper())
    return {
        "ticker": data["ticker"],
        "name": data["name"],
        "rating": data["rating"],
        "current_price": data["price_levels"]["current"],
        "target_mean": data["price_levels"]["target_mean"],
        "composite_score": None,
        "risk_score": data["risk"]["score"],
        "pe": data["valuation"]["pe_trailing"],
        "eps_growth": data["growth"]["eps_growth_fwd_pct"],
    }
