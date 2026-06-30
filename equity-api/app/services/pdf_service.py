"""
Generates a consumer-friendly weekly PDF report:
- Plain-English market narrative tailored to the user's sectors/horizon/risk
- "Winners and losers" section: which companies benefit or suffer from this week's news
- Per-stock summary cards in simple language with key figures and a buy/hold/avoid signal
- Charts (composite score ranking, revenue trend per stock)
Requires ANTHROPIC_API_KEY in environment for narrative generation.
"""
import os
import io
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import anthropic
except ImportError:
    anthropic = None


NAVY = colors.HexColor("#0c1f3f")
ACCENT = colors.HexColor("#2a78d6")
GREEN = colors.HexColor("#27500A")
GREEN_BG = colors.HexColor("#EAF3DE")
RED = colors.HexColor("#791F1F")
RED_BG = colors.HexColor("#FCEBEB")
GREY = colors.HexColor("#666666")
LIGHT_GREY = colors.HexColor("#f2f1ee")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("ReportTitle", parent=ss["Title"], fontSize=22, textColor=NAVY, spaceAfter=4, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("ReportSub", parent=ss["Normal"], fontSize=10, textColor=GREY, spaceAfter=16))
    ss.add(ParagraphStyle("SectionHead", parent=ss["Heading2"], fontSize=14, textColor=NAVY, spaceBefore=18, spaceAfter=8, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontSize=10.5, leading=16, textColor=colors.HexColor("#222222"), spaceAfter=10, alignment=TA_LEFT))
    ss.add(ParagraphStyle("TickerHead", parent=ss["Heading3"], fontSize=13, textColor=NAVY, spaceBefore=12, spaceAfter=4, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8.5, textColor=GREY, leading=12))
    ss.add(ParagraphStyle("WinLabel", parent=ss["Normal"], fontSize=10, textColor=GREEN, fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle("LoseLabel", parent=ss["Normal"], fontSize=10, textColor=RED, fontName="Helvetica-Bold"))
    return ss


def _call_claude(system: str, user: str, max_tokens: int = 1500) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or anthropic is None:
        return ""
    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join([b.text for b in msg.content if hasattr(b, "text")])
    except Exception:
        return ""


def _generate_narrative(stocks: list, sector_labels: list, horizon_label: str, risk_appetite: str) -> dict:
    """Plain-English market narrative + winners/losers, written for everyday investors."""
    stock_summary = "\n".join([
        f"- {s['ticker']} ({s['name']}, {s.get('sector','')}): score {s.get('composite_score','N/A')}/100, "
        f"rating {s.get('rating','N/A')}, EPS growth {s['growth'].get('eps_growth_fwd_pct','N/A')}%, "
        f"recent news: {'; '.join([n['title'] for n in s.get('news', [])[:2]]) or 'none'}"
        for s in stocks
    ])

    system = (
        "You are a friendly, sharp financial educator who explains the stock market to everyday "
        "people with no finance background. Avoid jargon — when you must use a financial term, "
        "explain it in plain words immediately after. Write in a warm, clear, confident voice, like "
        "a smart friend who works in finance explaining things over coffee. Identify real thematic "
        "trends visible in the data and news provided (e.g. 'AI spending keeps surging', 'a new "
        "competitor just launched and could squeeze margins', 'a major drug approval reshapes a "
        "healthcare niche', 'a new IPO is shaking up an industry'). For each major theme, clearly "
        "name which companies in the list look like WINNERS (benefit from this trend) and which look "
        "like LOSERS or at-risk (could be hurt by it) — be specific and grounded only in the data and "
        "news given, never invent facts not implied by the input. Output STRICT JSON only, no markdown, "
        "no preamble, matching exactly this schema: "
        '{"intro": "2 short paragraphs in plain English, separated by \\n\\n, summarising the week '
        'for this investor given their sectors/horizon/risk", '
        '"themes": [{"title": "short catchy theme name", "explanation": "2-3 plain-English sentences '
        'on what is happening and why it matters", "winners": ["TICKER1", "TICKER2"], '
        '"losers": ["TICKER3"]}]}'
    )
    user = (
        f"Investor profile: interested in {', '.join(sector_labels)}, investing horizon: {horizon_label}, "
        f"risk appetite: {risk_appetite}.\n\nThis week's screened stocks:\n{stock_summary}\n\n"
        "Write the intro and identify 2-4 themes with winners and losers."
    )
    text = _call_claude(system, user, max_tokens=1800)
    if text:
        try:
            cleaned = text.strip().strip("```json").strip("```").strip()
            return json.loads(cleaned)
        except Exception:
            pass
    return _fallback_narrative(stocks, sector_labels, horizon_label)


def _generate_stock_explainer(stock: dict, horizon_label: str) -> str:
    """Plain-English 3-sentence explainer for a consumer audience."""
    news_titles = "; ".join([n["title"] for n in stock.get("news", [])[:3]]) or "no recent headlines"
    system = (
        "You are a friendly financial educator writing for someone with no finance background. "
        "Write exactly 3 short sentences in plain English, explaining any necessary jargon inline: "
        "(1) what this company does and why its numbers look good or risky right now, "
        "(2) what's happening in the news that could affect it, "
        "(3) a simple plain-English takeaway suited to the investor's time horizon. No markdown."
    )
    user = (
        f"{stock['name']} ({stock['ticker']}), sector: {stock.get('sector','')}. "
        f"Rating: {stock.get('rating')}. EPS growth {stock['growth'].get('eps_growth_fwd_pct','N/A')}%. "
        f"Investor horizon: {horizon_label}. Recent headlines: {news_titles}"
    )
    text = _call_claude(system, user, max_tokens=300)
    return text or _fallback_stock_explainer(stock)


def _fallback_narrative(stocks, sector_labels, horizon_label) -> dict:
    avg_eps = sum(s["growth"].get("eps_growth_fwd_pct") or 0 for s in stocks) / max(len(stocks), 1)
    buy_names = [s["ticker"] for s in stocks if s.get("rating") == "Buy"][:3]
    return {
        "intro": (
            f"This week we looked at companies in {', '.join(sector_labels)} with a {horizon_label.lower()} "
            f"approach. On average, these companies are growing their profits about {avg_eps:.0f}% faster "
            "than they were a year ago, which is generally a good sign.\n\n"
            f"A few names stood out as strong picks: {', '.join(buy_names) if buy_names else 'none this week'}. "
            "As always, no single report should be your only reason to buy or sell — think of this as a "
            "starting point for your own research."
        ),
        "themes": [
            {
                "title": "Earnings momentum",
                "explanation": "Companies in this screen are growing profits faster than average, which often (but not always) supports rising stock prices over time.",
                "winners": buy_names,
                "losers": [],
            }
        ],
    }


def _fallback_stock_explainer(stock) -> str:
    g = stock["growth"]
    return (
        f"{stock['name']} is a {stock.get('sector','')} company currently rated '{stock.get('rating','Hold')}' "
        f"based on its financials, including {g.get('eps_growth_fwd_pct','N/A')}% profit growth expected this year. "
        f"No major news flagged this week that would change the picture. "
        f"For now, this fits a {stock.get('rating','Hold').lower()} stance depending on your own goals."
    )


def _score_chart(stocks: list) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(6.2, 2.6), dpi=150)
    tickers = [s["ticker"] for s in stocks]
    scores = [s.get("composite_score", 0) for s in stocks]
    colors_list = ["#2a78d6" if s.get("rating") == "Buy" else "#aaaaaa" for s in stocks]
    ax.barh(tickers[::-1], scores[::-1], color=colors_list[::-1], height=0.6)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Score (higher = stronger pick)", fontsize=8)
    ax.tick_params(labelsize=8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _revenue_chart(stock: dict):
    hist = stock.get("growth", {}).get("revenue_5yr", [])
    if not hist:
        return None
    fig, ax = plt.subplots(figsize=(3.0, 1.8), dpi=150)
    years = [h["year"] for h in hist]
    vals = [h["revenue"] / 1e9 for h in hist]
    ax.bar(years, vals, color="#2a78d6", width=0.55)
    ax.set_ylabel("Sales ($B)", fontsize=7)
    ax.tick_params(labelsize=7)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_weekly_pdf(report_data: dict, output_path: str) -> str:
    stocks = report_data["stocks"]
    sector_labels = report_data.get("sector_labels", [])
    horizon_label = report_data.get("horizon_label", "Long-term")
    risk_appetite = report_data.get("risk_appetite", "balanced")
    ss = _styles()
    story = []

    by_ticker = {s["ticker"]: s for s in stocks}

    # --- Header ---
    story.append(Paragraph("Your Weekly Investing Report", ss["ReportTitle"]))
    story.append(Paragraph(
        f"{report_data.get('report_week','')} &nbsp;·&nbsp; Sectors: {', '.join(sector_labels)} "
        f"&nbsp;·&nbsp; Horizon: {horizon_label} &nbsp;·&nbsp; Risk style: {risk_appetite.title()}",
        ss["ReportSub"]
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=14))

    # --- Plain-English intro ---
    narrative = _generate_narrative(stocks, sector_labels, horizon_label, risk_appetite)
    story.append(Paragraph("This Week, In Plain English", ss["SectionHead"]))
    for para in narrative["intro"].split("\n\n"):
        story.append(Paragraph(para, ss["Body"]))

    # --- Winners and losers ---
    story.append(Paragraph("What's Happening — Winners & Losers", ss["SectionHead"]))
    for theme in narrative.get("themes", []):
        story.append(Paragraph(f"<b>{theme['title']}</b>", ss["TickerHead"]))
        story.append(Paragraph(theme["explanation"], ss["Body"]))

        winners = theme.get("winners", [])
        losers = theme.get("losers", [])
        if winners or losers:
            cells = []
            if winners:
                names = ", ".join([f"{t} ({by_ticker[t]['name']})" if t in by_ticker else t for t in winners])
                cells.append([Paragraph("&#9650; LIKELY WINNERS", ss["WinLabel"]), Paragraph(names, ss["Body"])])
            if losers:
                names = ", ".join([f"{t} ({by_ticker[t]['name']})" if t in by_ticker else t for t in losers])
                cells.append([Paragraph("&#9660; LIKELY LOSERS", ss["LoseLabel"]), Paragraph(names, ss["Body"])])
            wl_table = Table(cells, colWidths=[1.4*inch, 4.8*inch])
            wl_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(wl_table)
        story.append(Spacer(1, 6))

    # --- Score ranking chart ---
    story.append(Paragraph("This Week's Top Picks, Ranked", ss["SectionHead"]))
    chart_buf = _score_chart(stocks)
    story.append(Image(chart_buf, width=6.2 * inch, height=2.6 * inch))
    story.append(Spacer(1, 6))

    # --- Summary table (simplified) ---
    table_data = [["Ticker", "Company", "Score /100", "Growing?", "Our Take"]]
    for s in stocks:
        eps = s["growth"].get("eps_growth_fwd_pct")
        growing = f"+{eps}%" if eps and eps > 0 else (f"{eps}%" if eps is not None else "—")
        table_data.append([
            s["ticker"], s["name"][:24], f"{s.get('composite_score','—')}",
            growing, s.get("rating", "—"),
        ])
    tbl = Table(table_data, colWidths=[0.6*inch, 2.1*inch, 0.8*inch, 0.8*inch, 0.9*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(PageBreak())

    # --- Per-stock plain-English cards ---
    story.append(Paragraph("Stock-by-Stock Breakdown", ss["SectionHead"]))
    for i, s in enumerate(stocks):
        g = s["growth"]; pl = s["price_levels"]
        story.append(Paragraph(f"{s['ticker']} — {s['name']}", ss["TickerHead"]))
        story.append(Paragraph(
            f"<font color='#666666'>{s.get('sector','')} · {s.get('market','')} · "
            f"Our take: <b>{s.get('rating','—')}</b></font>", ss["Small"]
        ))
        story.append(Spacer(1, 4))

        explainer = _generate_stock_explainer(s, horizon_label)
        story.append(Paragraph(explainer, ss["Body"]))

        simple_facts = [
            ["Current price", f"${pl.get('current','—')}"],
            ["Profit growth expected", f"{g.get('eps_growth_fwd_pct','—')}%"],
            ["Sales growth", f"{g.get('revenue_growth_pct','—')}%"],
            ["Risk level (1=low, 10=high)", f"{s['risk'].get('score','—')}/10"],
            ["A good price to consider buying", f"${pl.get('entry_low','—')} - ${pl.get('entry_high','—')}"],
            ["Consider selling if it drops below", f"${pl.get('stop_loss','—')}"],
        ]
        fact_tbl = Table(simple_facts, colWidths=[2.4*inch, 1.8*inch])
        fact_tbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))

        rev_chart = _revenue_chart(s)
        if rev_chart:
            row = Table([[fact_tbl, Image(rev_chart, width=2.6*inch, height=1.55*inch)]], colWidths=[4.3*inch, 2.7*inch])
        else:
            row = Table([[fact_tbl]], colWidths=[4.3*inch])
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(row)

        news = s.get("news", [])
        if news:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>In the news this week</b>", ss["Small"]))
            for n in news[:3]:
                story.append(Paragraph(f"• {n['title']} <font color='#999999'>({n.get('publisher','')})</font>", ss["Small"]))

        if i < len(stocks) - 1:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceBefore=12, spaceAfter=4))

    # --- Disclaimer ---
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd")))
    story.append(Paragraph(
        "This report is generated by an AI assistant for educational purposes only. It is not "
        "financial advice and should not be your only basis for investing decisions. Stock prices "
        "can go down as well as up, and past performance does not predict future results. Consider "
        "speaking with a licensed financial advisor before making investment decisions.",
        ss["Small"]
    ))

    doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=0.6*inch, bottomMargin=0.6*inch, leftMargin=0.7*inch, rightMargin=0.7*inch)
    doc.build(story)
    return output_path