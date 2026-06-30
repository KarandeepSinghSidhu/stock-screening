from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import tempfile
from app.services.report_service import build_weekly_report
from app.services.pdf_service import generate_weekly_pdf

router = APIRouter()


@router.get("/weekly")
def weekly_report(
    sectors: Optional[str] = Query(None, description="Comma-separated: tech,health,energy,finance,consumer,industrials"),
    top_n: int = Query(8, ge=3, le=15),
    horizon: str = Query("long", description="short | long"),
    risk_appetite: str = Query("balanced", description="conservative | balanced | aggressive"),
):
    """Generate the full weekly report: ranked stocks + news, tailored to user preferences."""
    sector_list = [s.strip() for s in sectors.split(",")] if sectors else None
    return build_weekly_report(sectors=sector_list, top_n=top_n, horizon=horizon, risk_appetite=risk_appetite)


@router.get("/weekly/pdf")
def weekly_report_pdf(
    sectors: Optional[str] = Query(None, description="Comma-separated: tech,health,energy,finance,consumer,industrials"),
    top_n: int = Query(6, ge=3, le=10),
    horizon: str = Query("long", description="short | long"),
    risk_appetite: str = Query("balanced", description="conservative | balanced | aggressive"),
):
    """Generate and download the weekly consumer-friendly PDF report."""
    sector_list = [s.strip() for s in sectors.split(",")] if sectors else None
    report_data = build_weekly_report(sectors=sector_list, top_n=top_n, horizon=horizon, risk_appetite=risk_appetite)
    out_dir = tempfile.gettempdir()
    sector_tag = "-".join(report_data["sectors"])
    filename = f"weekly_report_{sector_tag}_{report_data['report_date']}.pdf"
    output_path = os.path.join(out_dir, filename)
    generate_weekly_pdf(report_data, output_path)
    return FileResponse(output_path, media_type="application/pdf", filename=filename)