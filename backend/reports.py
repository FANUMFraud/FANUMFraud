"""
PDF Report generation for compliance and risk assessment.

Generates comprehensive risk reports in PDF format.
"""

import logging
from datetime import datetime
from io import BytesIO
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        PageBreak,
        Image,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
except ImportError:
    # Fallback: if reportlab not available, provide mock
    colors = None
    A4 = None
    getSampleStyleSheet = None
    ParagraphStyle = None
    inch = 1
    TA_LEFT = 0
    SimpleDocTemplate = None
    Table = None
    TableStyle = None
    Paragraph = None
    Spacer = None

log = logging.getLogger(__name__)

HEADER_COLOR = colors.HexColor("#1a1a1a") if colors is not None else None
RISK_HIGH_COLOR = colors.HexColor("#dc2626") if colors is not None else None
RISK_MEDIUM_COLOR = colors.HexColor("#f59e0b") if colors is not None else None
RISK_LOW_COLOR = colors.HexColor("#10b981") if colors is not None else None


def generate_risk_report(
    company_id: int,
    company_name: str,
    nip: str | None,
    current_score: float,
    risk_level: str,
    momentum_7d: dict[str, Any] | None,
    momentum_30d: dict[str, Any] | None,
    top_categories: list[dict[str, Any]] | None,
    sanctions: dict[str, Any] | None,
    articles_count: int,
    generated_at: datetime | None = None,
) -> bytes | None:
    """
    Generate a PDF compliance report for a company.

    Returns:
        PDF bytes or None if reportlab unavailable
    """
    if SimpleDocTemplate is None:
        log.warning("reportlab not available, skipping PDF generation")
        return None

    try:
        return _build_pdf(
            company_id=company_id,
            company_name=company_name,
            nip=nip,
            current_score=current_score,
            risk_level=risk_level,
            momentum_7d=momentum_7d,
            momentum_30d=momentum_30d,
            top_categories=top_categories,
            sanctions=sanctions,
            articles_count=articles_count,
            generated_at=generated_at or datetime.now(),
        )
    except Exception as e:
        log.error(f"PDF generation failed: {e}")
        return None


def _build_pdf(
    company_id: int,
    company_name: str,
    nip: str | None,
    current_score: float,
    risk_level: str,
    momentum_7d: dict[str, Any] | None,
    momentum_30d: dict[str, Any] | None,
    top_categories: list[dict[str, Any]] | None,
    sanctions: dict[str, Any] | None,
    articles_count: int,
    generated_at: datetime,
) -> bytes:
    """Build PDF document and return bytes."""
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=HEADER_COLOR,
        spaceAfter=12,
        alignment=TA_LEFT,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=HEADER_COLOR,
        spaceAfter=10,
        spaceBefore=10,
    )
    normal_style = styles["Normal"]

    risk_color = _risk_to_color(risk_level)

    story: list[Any] = []

    # Title
    story.append(Paragraph("Compliance Risk Report", title_style))
    story.append(
        Paragraph(
            f"<b>{company_name}</b> | ID: {company_id}",
            normal_style,
        )
    )
    story.append(
        Paragraph(
            f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ParagraphStyle(
                "Meta",
                parent=normal_style,
                fontSize=9,
                textColor=colors.grey,
            ),
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    # Risk Summary
    story.append(Paragraph("Risk Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Current Score", f"{current_score:.2f} / 100"],
        ["Risk Level", risk_level.upper()],
        ["NIP", nip or "N/A"],
        ["Associated Articles", str(articles_count)],
    ]
    summary_table = Table(summary_data, colWidths=[2 * inch, 2.5 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.25 * inch))

    # Momentum
    if momentum_7d or momentum_30d:
        story.append(Paragraph("Reputation Momentum", heading_style))
        momentum_data = [["Window", "Past Score", "Current Score", "Delta", "Trend"]]
        if momentum_7d:
            momentum_data.append(
                [
                    "7 days",
                    f"{momentum_7d.get('past_score', 0):.1f}",
                    f"{momentum_7d.get('current_score', 0):.1f}",
                    f"{momentum_7d.get('delta', 0):+.1f}",
                    momentum_7d.get("label", "unknown"),
                ]
            )
        if momentum_30d:
            momentum_data.append(
                [
                    "30 days",
                    f"{momentum_30d.get('past_score', 0):.1f}",
                    f"{momentum_30d.get('current_score', 0):.1f}",
                    f"{momentum_30d.get('delta', 0):+.1f}",
                    momentum_30d.get("label", "unknown"),
                ]
            )
        momentum_table = Table(momentum_data, colWidths=[1.2 * inch, 1.2 * inch, 1.2 * inch, 1.0 * inch, 1.3 * inch])
        momentum_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )
        story.append(momentum_table)
        story.append(Spacer(1, 0.25 * inch))

    # Top Risk Categories
    if top_categories:
        story.append(Paragraph("Top Risk Categories", heading_style))
        categories_data = [["Category", "Points"]]
        for cat in top_categories[:5]:
            categories_data.append([cat.get("category", "Unknown"), f"{cat.get('points', 0):.1f}"])
        categories_table = Table(categories_data, colWidths=[3 * inch, 1.5 * inch])
        categories_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HEADER_COLOR),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]
            )
        )
        story.append(categories_table)
        story.append(Spacer(1, 0.25 * inch))

    # Sanctions
    if sanctions and sanctions.get("is_sanctioned"):
        story.append(Paragraph("⚠️ Sanctions Alert", heading_style))
        story.append(
            Paragraph(
                f"<b>This entity is on {len(sanctions.get('lists', []))} sanctions list(s).</b>",
                ParagraphStyle("Warning", parent=normal_style, textColor=RISK_HIGH_COLOR),
            )
        )
        for sanction_list in sanctions.get("lists", [])[:5]:
            story.append(
                Paragraph(
                    f"• {sanction_list.get('name', 'Unknown')} ({sanction_list.get('country', 'Unknown')})",
                    normal_style,
                )
            )
        story.append(Spacer(1, 0.25 * inch))
    elif sanctions and sanctions.get("status") == "unavailable":
        story.append(Paragraph("Sanctions Check Not Completed", heading_style))
        story.append(
            Paragraph(
                "The sanctions source was unavailable or not configured. Treat this as an unresolved compliance check, not as a confirmed clear result.",
                ParagraphStyle("Warning", parent=normal_style, textColor=RISK_MEDIUM_COLOR),
            )
        )
        story.append(Spacer(1, 0.25 * inch))

    # Footer
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            "<i>This report was automatically generated by the FANUM Fraud Detection System. "
            "Please review the accompanying analysis dashboard for full context.</i>",
            ParagraphStyle("Footer", parent=normal_style, fontSize=8, textColor=colors.grey),
        )
    )

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def _risk_to_color(risk_level: str) -> colors.Color:
    """Map risk level to color."""
    risk_lower = risk_level.lower()
    if "critical" in risk_lower or "high" in risk_lower:
        return RISK_HIGH_COLOR
    if "medium" in risk_lower:
        return RISK_MEDIUM_COLOR
    return RISK_LOW_COLOR


__all__ = ["generate_risk_report"]
