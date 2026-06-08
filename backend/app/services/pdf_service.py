import os
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# --- Color Palette ---
COLOR_PRIMARY  = colors.HexColor("#1B4F72")  # deep blue
COLOR_SUCCESS  = colors.HexColor("#1E8449")  # green  (completed)
COLOR_WARNING  = colors.HexColor("#D68910")  # amber  (partial)
COLOR_DANGER   = colors.HexColor("#C0392B")  # red    (not built)
COLOR_LIGHT    = colors.HexColor("#F8F9FA")  # near-white background
COLOR_BORDER   = colors.HexColor("#D5D8DC")  # light grey border
COLOR_TEXT     = colors.HexColor("#1A1A2E")  # near-black text
COLOR_MUTED    = colors.HexColor("#7F8C8D")  # muted grey


def _get_styles() -> dict[str, ParagraphStyle]:
    return {
        "report_title": ParagraphStyle(
            "report_title",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=colors.white,
            leading=28,
            alignment=1,  # center
        ),
        "report_subtitle": ParagraphStyle(
            "report_subtitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#D6EAF8"),
            leading=14,
            alignment=1,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=COLOR_PRIMARY,
            leading=18,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=COLOR_MUTED,
            leading=12,
        ),
        "value": ParagraphStyle(
            "value",
            fontName="Helvetica",
            fontSize=10,
            textColor=COLOR_TEXT,
            leading=14,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=COLOR_MUTED,
            alignment=1,
        ),
    }


def _build_header(story, styles):
    """Draw a colored header banner."""
    header_data = [[
        Paragraph("CONSTRUCTION PROGRESS REPORT", styles["report_title"]),
        Paragraph("FPT AI — UAV Inspection System", styles["report_subtitle"]),
    ]]
    # Use a 1-row table as a colored banner
    tbl = Table(
        [[Paragraph("CONSTRUCTION PROGRESS REPORT", styles["report_title"])],
         [Paragraph("FPT AI — UAV Inspection System", styles["report_subtitle"])]],
        colWidths=[17 * cm],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), COLOR_PRIMARY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))


def _build_overview_table(report: dict[str, Any], element_type_name: str, styles) -> Table:
    generated_at = report.get("generated_at")
    if isinstance(generated_at, datetime):
        generated_str = generated_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        generated_str = str(generated_at) if generated_at else "—"

    data = [
        [Paragraph("Report ID",        styles["label"]), Paragraph(str(report.get("id", "—")), styles["value"])],
        [Paragraph("Run ID",           styles["label"]), Paragraph(str(report.get("run_id", "—")), styles["value"])],
        [Paragraph("Element Type",     styles["label"]), Paragraph(element_type_name,          styles["value"])],
        [Paragraph("Generated At",     styles["label"]), Paragraph(generated_str,              styles["value"])],
        [Paragraph("Current Stage",    styles["label"]), Paragraph(str(report.get("current_stage", "—") or "—"), styles["value"])],
    ]
    tbl = Table(data, colWidths=[5 * cm, 12 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), COLOR_LIGHT),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, COLOR_LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS",(0, 0), (-1, -1), [4, 4, 4, 4]),
    ]))
    return tbl


def _build_progress_summary(report: dict[str, Any], styles) -> list:
    total    = report.get("total_elements") or 0
    completed = report.get("completed") or 0
    partial   = report.get("partial") or 0
    not_built = report.get("not_built") or 0
    pct       = report.get("completion_pct") or 0.0

    # Status text table
    seg_data = [
        [
            Paragraph("Status",            styles["label"]),
            Paragraph("Count",            styles["label"]),
            Paragraph("Percentage",       styles["label"]),
        ],
        [
            Paragraph("✓  Completed",     styles["value"]),
            Paragraph(str(completed),     styles["value"]),
            Paragraph(f"{completed / max(total, 1) * 100:.1f} %", styles["value"]),
        ],
        [
            Paragraph("◑  Partial",      styles["value"]),
            Paragraph(str(partial),       styles["value"]),
            Paragraph(f"{partial / max(total, 1) * 100:.1f} %",   styles["value"]),
        ],
        [
            Paragraph("✗  Not Built",     styles["value"]),
            Paragraph(str(not_built),      styles["value"]),
            Paragraph(f"{not_built / max(total, 1) * 100:.1f} %", styles["value"]),
        ],
        [
            Paragraph("Total Elements",    styles["label"]),
            Paragraph(str(total),          styles["value"]),
            Paragraph("100.0 %",          styles["value"]),
        ],
    ]
    seg_tbl = Table(seg_data, colWidths=[6 * cm, 4 * cm, 4 * cm])
    seg_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), COLOR_PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, COLOR_LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))

    # Completion pct box
    pct_style = ParagraphStyle(
        "pct_big",
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=COLOR_PRIMARY,
        alignment=1,
    )
    pct_label_style = ParagraphStyle(
        "pct_label",
        fontName="Helvetica",
        fontSize=10,
        textColor=COLOR_MUTED,
        alignment=1,
    )
    pct_tbl = Table(
        [[Paragraph(f"{pct:.1f} %", pct_style)],
         [Paragraph("Completion Rate", pct_label_style)]],
        colWidths=[6 * cm],
    )
    pct_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), COLOR_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 1, COLOR_BORDER),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    return [seg_tbl, Spacer(1, 4), pct_tbl]


def _build_page_footer(canvas, doc, generated_at_str: str):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(COLOR_MUTED)
    page_num = canvas.getPageNumber()
    footer_center = f"Page {page_num}  |  Generated by FPT AI Construction Progress API  |  {generated_at_str}"
    canvas.drawCentredString(A4[0] / 2, 12 * mm, footer_center)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Custom Flowable: stacked horizontal progress bar
# ---------------------------------------------------------------------------

class StackedProgressBar(Flowable):
    """A stacked horizontal progress bar with a label row."""

    BAR_HEIGHT  = 14  # mm
    BAR_GAP     = 4   # mm between bar and legend
    TOTAL_H     = 24  # total flowable height in mm

    def __init__(
        self,
        total: int,
        completed: int,
        partial: int,
        not_built: int,
        width: float,
        color_completed: colors.Color,
        color_partial: colors.Color,
        color_not_built: colors.Color,
        color_border: colors.Color,
        color_text: colors.Color,
    ):
        super().__init__()
        self.total          = total
        self.completed      = completed
        self.partial        = partial
        self.not_built      = not_built
        self.bar_width      = width
        self.color_completed = color_completed
        self.color_partial   = color_partial
        self.color_not_built = color_not_built
        self.color_border    = color_border
        self.color_text      = color_text

    def wrap(self, available_width: float, available_height: float):
        # Use the full available width capped at the declared width
        self.bar_width = min(available_width, self.bar_width)
        return self.bar_width, self.TOTAL_H * mm

    def draw(self):
        c = self.canv
        total = self.total or 1  # avoid divide-by-zero

        pct_c = self.completed / total
        pct_p = self.partial   / total
        pct_n = self.not_built / total

        bar_y = self.BAR_GAP * mm
        bar_h = self.BAR_HEIGHT * mm
        bar_w = self.bar_width

        # Background track
        c.setFillColor(self.color_border)
        c.roundRect(0, bar_y, bar_w, bar_h, 3, stroke=0, fill=1)

        # Completed segment
        if pct_c > 0:
            c.setFillColor(self.color_completed)
            c.roundRect(0, bar_y, bar_w * pct_c, bar_h, 0, stroke=0, fill=1)

        # Partial segment
        if pct_p > 0:
            x_partial = bar_w * pct_c
            c.setFillColor(self.color_partial)
            c.rect(x_partial, bar_y, bar_w * pct_p, bar_h, stroke=0, fill=1)

        # Not-built segment
        if pct_n > 0:
            x_not_built = bar_w * (pct_c + pct_p)
            c.setFillColor(self.color_not_built)
            c.roundRect(x_not_built, bar_y, bar_w * pct_n, bar_h, 0, stroke=0, fill=1)

        # Left edge cap rounding for completed
        if pct_c > 0:
            c.setFillColor(self.color_completed)
            c.circle(0, bar_y + bar_h / 2, bar_h / 2, stroke=0, fill=1)

        # Right edge cap rounding for not-built
        if pct_n > 0 and pct_c + pct_p < 1:
            x_nb = bar_w * (pct_c + pct_p)
            c.setFillColor(self.color_not_built)
            c.circle(bar_w, bar_y + bar_h / 2, bar_h / 2, stroke=0, fill=1)

        # Legend row
        legend_y = bar_y + bar_h + 2 * mm
        c.setFont("Helvetica", 7.5)

        c.setFillColor(self.color_completed)
        c.circle(4, legend_y + 1.5 * mm, 2.5, stroke=0, fill=1)
        c.setFillColor(self.color_text)
        c.drawString(9, legend_y, f"Completed  {self.completed}  ({pct_c * 100:.1f}%)")

        mid = bar_w / 2
        c.setFillColor(self.color_partial)
        c.circle(mid - 6, legend_y + 1.5 * mm, 2.5, stroke=0, fill=1)
        c.setFillColor(self.color_text)
        c.drawString(mid - 1, legend_y, f"Partial  {self.partial}  ({pct_p * 100:.1f}%)")

        c.setFillColor(self.color_not_built)
        c.circle(bar_w - 20, legend_y + 1.5 * mm, 2.5, stroke=0, fill=1)
        c.setFillColor(self.color_text)
        c.drawString(bar_w - 15, legend_y, f"Not Built  {self.not_built}  ({pct_n * 100:.1f}%)")


def build_report_pdf(enriched_report: dict[str, Any]) -> bytes:
    styles = _get_styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
        title="Construction Progress Report",
        author="FPT AI",
        subject="UAV Inspection Progress Report",
    )

    story: list = []

    # --- Header ---
    _build_header(story, styles)

    # --- Section 1: Overview ---
    story.append(Paragraph("Report Overview", styles["section_header"]))
    element_type_name = (
        enriched_report.get("element_type", {}).get("name", "Unknown")
        if isinstance(enriched_report.get("element_type"), dict)
        else enriched_report.get("element_type_name", "Unknown")
    )
    story.append(_build_overview_table(enriched_report, element_type_name, styles))

    story.append(Spacer(1, 8))

    # --- Section 2: Progress Summary ---
    story.append(Paragraph("Progress Summary", styles["section_header"]))
    for item in _build_progress_summary(enriched_report, styles):
        story.append(item)

    story.append(Spacer(1, 10))

    # --- Section 3: Visual Progress Bar ---
    story.append(Paragraph("Visual Completion", styles["section_header"]))

    total     = enriched_report.get("total_elements") or 0
    completed = enriched_report.get("completed") or 0
    partial   = enriched_report.get("partial") or 0
    not_built = enriched_report.get("not_built") or 0
    bar_width = 17 * cm - 4 * mm  # account for horizontal margins

    story.append(
        StackedProgressBar(
            total=total,
            completed=completed,
            partial=partial,
            not_built=not_built,
            width=bar_width,
            color_completed=COLOR_SUCCESS,
            color_partial=COLOR_WARNING,
            color_not_built=COLOR_DANGER,
            color_border=COLOR_BORDER,
            color_text=COLOR_TEXT,
        )
    )

    # --- Build PDF with footer ---
    generated_at = enriched_report.get("generated_at")
    gen_str = (
        generated_at.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(generated_at, datetime)
        else str(generated_at) if generated_at else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    doc.build(story, onFirstPage=lambda c, d: _build_page_footer(c, d, gen_str),
                     onLaterPages=lambda c, d: _build_page_footer(c, d, gen_str))
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------

def get_output_dir() -> str:
    """Return the configured PDF output directory."""
    import os as _os
    _os.makedirs("storage/reports_pdf", exist_ok=True)
    return _os.environ.get("REPORT_OUTPUT_DIR", "storage/reports_pdf")


def save_pdf(pdf_bytes: bytes, run_id: str, report_id: str) -> str:
    """
    Save PDF bytes to disk and return the absolute path.

    Filename format: progress_report_{run_id}_{report_id}.pdf
    """
    output_dir = get_output_dir()
    filename = f"progress_report_{run_id}_{report_id}.pdf"
    filepath = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)
    return os.path.abspath(filepath)