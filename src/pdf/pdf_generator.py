"""Original AWS Invoice Generator ReportLab template, retained without layout redesign."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

import pandas as pd
from num2words import num2words
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from common.exceptions import PdfGenerationError
from config.settings import ASSETS_DIR, FONTS_DIR
from invoice.invoice_calculator import InvoiceColumns, calculate_due_date, prepare_invoice_data

FONT_FAMILY = "Helvetica"
try:
    pdfmetrics.registerFont(TTFont("Roboto", str(FONTS_DIR / "Roboto-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Roboto-Bold", str(FONTS_DIR / "Roboto-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Roboto-Italic", str(FONTS_DIR / "Roboto-Italic.ttf")))
    pdfmetrics.registerFontFamily("Roboto", normal="Roboto", bold="Roboto-Bold", italic="Roboto-Italic")
    FONT_FAMILY = "Roboto"
except Exception:
    # This is the original Helvetica fallback when the production font files are unavailable.
    pass


def format_currency(value: object, currency_symbol: str = "") -> str:
    if value is None or not isinstance(value, (int, float)):
        return f"{currency_symbol}0.00"
    if value < 0:
        return f"({currency_symbol}{abs(value):,.2f})"
    return f"{currency_symbol}{value:,.2f}"


def draw_letterhead(canvas: Any, doc: Any) -> None:
    """Original full-page Letter_Head.png placement."""
    canvas.saveState()
    letterhead_path = ASSETS_DIR / "Letter_Head.png"
    if letterhead_path.exists():
        canvas.drawImage(str(letterhead_path), 0, 0, width=letter[0], height=letter[1], preserveAspectRatio=True, anchor="c")
    canvas.restoreState()


def _invoice_details(dataframe: pd.DataFrame, columns: InvoiceColumns, client: dict[str, Any], invoice_number: str, invoice_date: str, rate: float, styles: Any) -> Table:
    billing_start = pd.to_datetime(dataframe[columns.billing_period_start].iloc[0]).strftime("%d-%b-%Y")
    billing_end = pd.to_datetime(dataframe[columns.billing_period_end].iloc[0]).strftime("%d-%b-%Y")
    due_date = calculate_due_date(datetime.strptime(invoice_date, "%d-%b-%Y"))
    details_data = [
        [Paragraph("<b>Billing Period:</b>", styles["Normal"]), f"{billing_start} to {billing_end}"],
        [Paragraph("<b>Account ID:</b>", styles["Normal"]), str(dataframe[columns.linked_account_id].iloc[0])],
        [Paragraph("<b>Exchange Rate:</b>", styles["Normal"]), f"1 USD = {rate} INR"],
        [Paragraph("<b>Invoice Number:</b>", styles["Normal"]), invoice_number],
        [Paragraph("<b>Invoice Date:</b>", styles["Normal"]), invoice_date],
        [Paragraph("<b>Due Date:</b>", styles["Normal"]), due_date],
        [Paragraph("<b>GSTIN:</b>", styles["Normal"]), "33AASFH0108G1ZP"],
    ]
    address_style = ParagraphStyle(name="AddressBillTo", parent=styles["Normal"], alignment=0)
    address = [
        Paragraph("<b>Bill To:</b>", address_style), Paragraph(client["name"], address_style), Paragraph(client["address"], address_style),
        Spacer(1, 0.1 * inch), Paragraph(f"<b>Contact:</b> {client.get('contact_person', '')} ({client.get('mobile', '')})", address_style),
        Spacer(1, 0.1 * inch), Paragraph(f"<b>GSTIN:</b> {client['gstin']}", address_style),
    ]
    left_table = Table(details_data, style=[("VALIGN", (0, 0), (-1, -1), "TOP")])
    table = Table([[left_table, address]], colWidths=["*", "*"])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return table


def _legacy_itemized_elements(dataframe: pd.DataFrame, columns: InvoiceColumns, rate: float) -> list[Any]:
    """Verbatim structure, widths, padding, hierarchy, and spacing of the original renderer."""
    style_service = ParagraphStyle(name="Service", fontName=f"{FONT_FAMILY}-Bold", fontSize=10, spaceAfter=0, leading=11)
    style_service_cost = ParagraphStyle(name="ServiceCost", parent=style_service, alignment=2)
    style_region = ParagraphStyle(name="Region", fontName=f"{FONT_FAMILY}-Bold", fontSize=9, leftIndent=0, spaceAfter=0, leading=10)
    style_region_cost = ParagraphStyle(name="RegionCost", parent=style_region, alignment=2)
    style_usage_type = ParagraphStyle(name="UsageType", fontName=FONT_FAMILY, fontSize=8, leftIndent=5, spaceAfter=0, leading=10)
    style_usage_type_cost = ParagraphStyle(name="UsageTypeCost", parent=style_usage_type, alignment=2)
    item_desc_color = colors.Color(107 / 255, 114 / 255, 128 / 255)
    style_item_desc = ParagraphStyle(name="ItemDescription", fontName=f"{FONT_FAMILY}-Italic", fontSize=7, leftIndent=13, leading=9, textColor=item_desc_color)
    style_item_cost = ParagraphStyle(name="ItemCost", fontName=FONT_FAMILY, fontSize=8, alignment=2, leading=9)
    style_item_usage = ParagraphStyle(name="ItemUsage", fontName=FONT_FAMILY, fontSize=8, alignment=2, leading=9)
    style_header = ParagraphStyle(name="Header", fontName=f"{FONT_FAMILY}-Bold", fontSize=8, alignment=1, spaceAfter=6, textColor=colors.black)

    def aligned(left_text: object, right_usd: str, right_inr: str, left_style: ParagraphStyle, right_style: ParagraphStyle, extra: list[tuple[Any, ...]] | None = None) -> Table:
        table = Table([[Paragraph(str(left_text), left_style), "", Paragraph(right_inr, right_style), Paragraph(right_usd, right_style)]], colWidths=["*", 1 * inch, 1.2 * inch, 1.2 * inch])
        commands: list[tuple[Any, ...]] = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]
        if extra:
            commands.extend(extra)
        table.setStyle(TableStyle(commands))
        return table

    def item_row(description: object, usage: object, usd: float, inr: float) -> Table:
        table = Table([[Paragraph(str(description), style_item_desc), Paragraph(str(usage), style_item_usage), Paragraph(format_currency(inr), style_item_cost), Paragraph(format_currency(usd), style_item_cost)]], colWidths=["*", 1 * inch, 1.2 * inch, 1.2 * inch])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return table

    header = Table([[Paragraph("Description", style_header), Paragraph("Usage Quantity", style_header), Paragraph("Amount in INR", style_header), Paragraph("Amount in USD", style_header)]], colWidths=["*", 1 * inch, 1.2 * inch, 1.2 * inch])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("TEXTCOLOR", (0, 0), (-1, 0), colors.black), ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black), ("BOTTOMPADDING", (0, 0), (-1, 0), 6), ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    elements: list[Any] = [header]
    dataframe[columns.product] = dataframe[columns.product].fillna("Uncategorized")
    first_product = True
    for product, product_group in dataframe.groupby(columns.product):
        if not first_product:
            elements.append(Spacer(1, 12))
        first_product = False
        product_total = float(product_group["Consolidated Cost"].sum())
        if 0 <= product_total < 0.005:
            product_total = 0
        elements.append(aligned(product, f"USD {format_currency(product_total)}", f"INR {format_currency(product_total * rate)}", style_service, style_service_cost, [("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey), ("BOTTOMPADDING", (0, 0), (-1, 0), 4)]))
        for region_name, region_group in product_group.groupby("Region"):
            region_total = float(region_group["Consolidated Cost"].sum())
            if 0 <= region_total < 0.005:
                region_total = 0
            elements.append(aligned(region_name, f"USD {format_currency(region_total)}", f"INR {format_currency(region_total * rate)}", style_region, style_region_cost))
            for usage_type, usage_group in region_group.groupby(columns.usage_type):
                usage_total = float(usage_group["Consolidated Cost"].sum())
                if 0 <= usage_total < 0.005:
                    usage_total = 0
                elements.append(aligned(usage_type, f"USD {format_currency(usage_total)}", f"INR {format_currency(usage_total * rate)}", style_usage_type, style_usage_type_cost))
                for _, row in usage_group.iterrows():
                    try:
                        usage = f"{float(row[columns.usage_quantity]):.2f}"
                    except (ValueError, TypeError):
                        usage = row[columns.usage_quantity]
                    cost_usd = float(row["Consolidated Cost"])
                    if 0 <= cost_usd < 0.005:
                        cost_usd = 0
                    elements.append(item_row(row[columns.item_description], usage, cost_usd, cost_usd * rate))
    return elements


def create_invoice_pdf(
    excel_path: Path,
    output_path: Path,
    client: dict[str, Any],
    invoice_number: str,
    invoice_date: str,
    exchange_rate: float,
    logger: logging.Logger | None = None,
) -> Path:
    """Render using the active legacy `process_invoice.py` page structure unchanged."""
    try:
        dataframe, columns = prepare_invoice_data(pd.read_excel(excel_path), logger)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=0.5 * inch, rightMargin=0.5 * inch, topMargin=1.5 * inch, bottomMargin=1.5 * inch)
        styles = getSampleStyleSheet()
        title = Paragraph("TAX INVOICE", ParagraphStyle(name="Title", parent=styles["h1"], fontName=f"{FONT_FAMILY}-Bold", fontSize=16, alignment=1))
        header = Table([[title]], colWidths=["*"])
        header.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elements: list[Any] = [header, Spacer(1, 0.5 * inch), _invoice_details(dataframe, columns, client, invoice_number, invoice_date, exchange_rate, styles), Spacer(1, 0.25 * inch)]

        total_usd = float(dataframe["Consolidated Cost"].sum())
        before_tax = total_usd * exchange_rate
        gst = before_tax * 0.18
        total_inr = before_tax + gst
        def truncate(value: float, decimals: int = 2) -> float:
            return int(value * (10 ** decimals)) / (10 ** decimals)
        summary = Table([["Description", "Amount"], ["Total Cost (USD)", f"USD {format_currency(truncate(total_usd))}"], ["Total Before Tax (INR)", f"INR {format_currency(truncate(before_tax))}"], ["GST Amount (18%)", f"INR {format_currency(truncate(gst))}"], ["Invoice Total (INR)", f"INR {format_currency(truncate(total_inr))}"]], colWidths=["*", 1.5 * inch])
        summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("TEXTCOLOR", (0, 0), (-1, 0), colors.black), ("FONTNAME", (0, 0), (-1, 0), f"{FONT_FAMILY}-Bold"), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("ALIGN", (0, 1), (0, 1), "LEFT"), ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        elements.extend([summary, Spacer(1, 0.2 * inch)])
        words = num2words(round(total_inr), lang="en_IN").title().replace("Lakh,", "Lakhs,") + " Rupees Only"
        elements.extend([Paragraph(f"<b>Total in Words:</b> {words}", styles["Normal"]), Spacer(1, 0.25 * inch)])
        elements.extend(_legacy_itemized_elements(dataframe, columns, exchange_rate))
        elements.append(Spacer(1, 0.4 * inch))
        footer_header = ParagraphStyle(name="FooterHeader", fontName=f"{FONT_FAMILY}-Bold", fontSize=10, spaceAfter=6)
        footer_body = ParagraphStyle(name="FooterBody", parent=styles["Normal"], fontSize=8, leading=12, leftIndent=10)
        bank_body = ParagraphStyle(name="BankBody", parent=styles["Normal"], fontSize=9, leading=11)
        elements.append(Paragraph("Terms and Conditions:", footer_header))
        for term in ["• Billing will be consolidated and invoiced through HADS, based on actual AWS usage.", "• GST will be applied as per Government of India regulations.", "• HADS may apply applicable discounts, credits, or pricing benefits as available through AWS partner programs.", "• HADS will provide monthly usage reports at no additional charge.", "• The Customer retains full ownership and root access to their AWS accounts.", "• HADS will not access customer data or services unless explicitly authorized in writing.", "• Payment terms 30 days from the date of invoice.", "• Confidentiality of customer data will be maintained as per our privacy policy.", "• HADS shall not be liable for any indirect, incidental, or consequential damages resulting from AWS service disruptions, pricing changes, or third-party service failures."]:
            elements.append(Paragraph(term, footer_body))
        elements.extend([Spacer(1, 0.4 * inch), Paragraph("Bank Account Details:", footer_header)])
        for detail in ["<b>Name:</b> M/S HADS TECHNOVATIONS LLP", "<b>Acc No:</b> 50200108839719", "<b>IFSC Code:</b> HDFC0000795", "<b>Bank:</b> HDFC BANK LTD", "<b>Branch:</b> Perungudi, Chennai"]:
            elements.append(Paragraph(detail, bank_body))
        doc.build(elements, onFirstPage=draw_letterhead, onLaterPages=draw_letterhead)
    except Exception as exc:
        raise PdfGenerationError(f"Unable to generate {output_path.name}: {exc}") from exc
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise PdfGenerationError(f"PDF generation did not create {output_path.name}")
    return output_path
