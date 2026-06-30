from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.routers import stocks, screener, report, profile

app = FastAPI(
    title="Equity Research API",
    description="Personalized weekly stock research backend",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])

@app.get("/health")
def health():
    return {"status": "ok"}