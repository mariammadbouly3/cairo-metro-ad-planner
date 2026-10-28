"""PDF price quote for a planned campaign, in Arabic (right to left) or English.

Arabic needs two extra steps that PDF libraries don't do on their own: joining the letters
(arabic_reshaper) and putting them in right-to-left display order (python-bidi).
"""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).parent
VAT = 0.14
NAVY, BLUE, RED, GREEN, GOLD = "#0E1630", "#2A78D6", "#E3572E", "#1B9E6B", "#F2C14E"
APP_URL = "https://cairo-metro-ad-planner-mwzqpnn7ozdv8uubvti5wu.streamlit.app"


def _font_file(name):
    for p in (HERE / "assets" / name, HERE / name):
        if p.exists():
            return str(p)
    raise FileNotFoundError(name)


_fonts_ready = False


def _register_fonts():
    global _fonts_ready
    if not _fonts_ready:
        pdfmetrics.registerFont(TTFont("Plex", _font_file("IBMPlexSansArabic-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Plex-Bold", _font_file("IBMPlexSansArabic-Bold.ttf")))
        _fonts_ready = True


def _shape(s, ar):
    s = str(s)
    if not ar:
        return s
    import arabic_reshaper
    try:
        from bidi import get_display  # python-bidi 0.5+
    except ImportError:
        from bidi.algorithm import get_display  # python-bidi 0.4
    return get_display(arabic_reshaper.reshape(s))


def _money(x, ar):
    return f"{x:,.0f} جنيه" if ar else f"EGP {x:,.0f}"


def build_quote(rows, meta, ar=True) -> bytes:
    """rows: list of dicts with station, lines, format, zone, monthly, months, total.
    meta: company, campaign, start (date), end (date), audience, impressions, cpm."""
    _register_fonts()
    S = lambda s: _shape(s, ar)  # noqa: E731
    T = lambda a, e: S(a if ar else e)  # noqa: E731
    align = TA_RIGHT if ar else TA_LEFT
    st_title = ParagraphStyle("t", fontName="Plex-Bold", fontSize=19, leading=26, alignment=align, textColor=NAVY)
    st_sub = ParagraphStyle("s", fontName="Plex", fontSize=10, leading=15, alignment=align, textColor="#5B6478")
    st_note = ParagraphStyle("n", fontName="Plex", fontSize=8.5, leading=13, alignment=align, textColor="#5B6478")

    now = dt.datetime.now()
    qno = f"Q-{now:%Y%m%d-%H%M}"
    buf = io.BytesIO()

    def frame(canvas, doc):
        w, h = A4
        canvas.saveState()
        # metro line strip on top, like the app header
        x = 18 * mm
        for color, width in ((BLUE, 46 * mm), (RED, 30 * mm), (GREEN, 40 * mm)):
            canvas.setFillColor(colors.HexColor(color))
            canvas.roundRect(x if not ar else w - x - width, h - 14 * mm, width, 2.6 * mm, 1.3 * mm, stroke=0, fill=1)
            x += width + 3 * mm
        canvas.setFont("Plex", 7.5)
        canvas.setFillColor(colors.HexColor("#8A93A6"))
        foot = T("مشروع بورتفوليو لتحليل البيانات. الأسعار تقديرية مبنية على أسعار الإعلانات الخارجية المنشورة في مصر، ومش عرض رسمي من المترو.",
                 "Portfolio project. Prices are estimates based on published Egyptian outdoor-ad rates; not an official Cairo Metro offer.")
        draw = canvas.drawRightString if ar else canvas.drawString
        x0 = w - 18 * mm if ar else 18 * mm
        draw(x0, 14 * mm, foot)
        draw(x0, 10 * mm, f"{qno}  |  {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=22 * mm,
                            bottomMargin=20 * mm, title=f"Cairo Metro Ad Planner {qno}", author="Cairo Metro Ad Planner")
    story = [Paragraph(T("عرض سعر حملة إعلانية في مترو القاهرة", "Cairo Metro advertising quote"), st_title),
             Paragraph(T(f"رقم العرض {qno}  |  بتاريخ {now:%d/%m/%Y}  |  صالح لمدة 14 يوم",
                         f"Quote {qno}  |  {now:%d %b %Y}  |  valid for 14 days"), st_sub),
             Spacer(1, 6 * mm)]

    # ---- client and campaign box
    cpm = f"{meta['cpm']:,.2f} جنيه" if ar else f"EGP {meta['cpm']:,.2f}"
    info = [
        (T("الشركة", "Company"), S(meta["company"] or "-")),
        (T("الحملة", "Campaign"), S(meta["campaign"] or "-")),
        (T("المدة", "Dates"), S(f"{meta['start']:%d/%m/%Y} " + ("لحد" if ar else "to") + f" {meta['end']:%d/%m/%Y}")),
        (T("الجمهور", "Audience"), S(meta["audience"])),
        (T("المشاهدات المتوقعة", "Expected impressions"), f"{meta['impressions']:,.0f}"),
        (T("تكلفة الوصول لكل 1000 راكب", "Cost per 1,000 riders"), S(cpm)),
    ]
    if ar:
        info = [(v, k) for k, v in info]
    box = Table(info, colWidths=[110 * mm, 64 * mm] if ar else [64 * mm, 110 * mm])
    box.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Plex", 10),
        ("FONT", (1 if ar else 0, 0), (1 if ar else 0, -1), "Plex-Bold", 10),
        ("TEXTCOLOR", (1 if ar else 0, 0), (1 if ar else 0, -1), colors.HexColor("#5B6478")),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if ar else "LEFT"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F6FB")),
        ("BOX", (0, 0), (-1, -1), .6, colors.HexColor("#D9DEEA")),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [box, Spacer(1, 7 * mm)]

    # ---- spaces table
    head = [T("#", "#"), T("المحطة", "Station"), T("الخط", "Line"), T("نوع الإعلان", "Format"), T("المكان", "Zone"),
            T("السعر الشهري", "Monthly"), T("شهور", "Months"), T("الإجمالي", "Total")]
    body = [[str(i), S(r["station"]), S(r["lines"]), S(r["format"]), S(r["zone"]), f"{r['monthly']:,.0f}",
             f"{r['months']:g}", f"{r['total']:,.0f}"] for i, r in enumerate(rows, 1)]
    widths = [7, 30, 18, 45, 20, 20, 13, 21]
    data = [head] + body
    if ar:  # right-to-left: first column on the right
        data = [list(reversed(r)) for r in data]
        widths = list(reversed(widths))
    tbl = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    num_cols = [0, 1, 2, 7] if ar else [0, 5, 6, 7]
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Plex-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Plex", 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FB")]),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if ar else "LEFT"),
        *[("ALIGN", (c, 0), (c, -1), "CENTER") for c in num_cols],
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#E1E5EE")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [tbl, Spacer(1, 5 * mm)]

    # ---- totals
    sub = sum(r["total"] for r in rows)
    vat = sub * VAT
    tot = [(T("الإجمالي قبل الضريبة", "Subtotal"), _money(sub, ar)),
           (T("ضريبة القيمة المضافة 14%", "VAT 14%"), _money(vat, ar)),
           (T("الإجمالي شامل الضريبة", "Total incl. VAT"), _money(sub + vat, ar))]
    tot = [(S(v), k) for k, v in tot] if ar else tot
    tt = Table(tot, colWidths=[40 * mm, 55 * mm] if ar else [55 * mm, 40 * mm], hAlign="LEFT" if ar else "RIGHT")
    tt.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Plex", 10),
        ("FONT", (0, 2), (-1, 2), "Plex-Bold", 12),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT" if ar else "LEFT"),
        ("ALIGN", (0 if ar else 1, 0), (0 if ar else 1, -1), "LEFT" if ar else "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), 1.2, colors.HexColor(GOLD)),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [tt, Spacer(1, 8 * mm)]

    notes = (lambda a, e: a if ar else e)("الأسعار شهرية لكل مكان، ومش داخل فيها الإنتاج والطباعة والتركيب. الحجز بيتأكد بعد موافقة الإدارة. لمراجعة الخطة أو تعديلها:",
              "Prices are per space per month and exclude production, printing and installation. Bookings are confirmed "
              "after admin approval. To review or change the plan:")
    story.append(_ar_lines(notes, st_note) if ar else Paragraph(notes, st_note))
    story.append(Paragraph(APP_URL, ParagraphStyle("u", parent=st_note, textColor=BLUE)))
    doc.build(story, onFirstPage=frame, onLaterPages=frame)
    return buf.getvalue()


def _ar_lines(text, style, max_chars=95):
    """Paragraph can't wrap right-to-left text correctly, so wrap by words first, then shape each line."""
    from reportlab.platypus import KeepTogether
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return KeepTogether([Paragraph(_shape(l, True), style) for l in lines])
