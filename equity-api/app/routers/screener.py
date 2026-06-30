from fastapi import APIRouter, Query
from typing import Optional
from app.services.screener_service import run_screener

router = APIRouter()


@router.get("/run")
def screen(
    sectors: Optional[str] = Query(None, description="Comma-separated: tech,health,energy,finance,consumer,industrials"),
    top_n: int = Query(10, ge=3, le=25),
    horizon: str = Query("long", description="short | long"),
    risk_appetite: str = Query("balanced", description="conservative | balanced | aggressive"),
):
    """Run the sector screener and return ranked results."""
    sector_list = [s.strip() for s in sectors.split(",")] if sectors else None
    return run_screener(sectors=sector_list, top_n=top_n, horizon=horizon, risk_appetite=risk_appetite)