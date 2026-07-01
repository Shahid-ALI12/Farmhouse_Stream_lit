"""
pdf_bill.py — generates a printable, itemized customer statement (bill)
as a PDF, in memory (no file written to disk), so it can be offered as
a download button directly inside Streamlit.
"""
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Credit limit — balances at or above this are flagged in red on screen
# and on the bill itself, as a warning.
CREDIT_LIMIT = 3_000_000


def generate_customer_bill_pdf(business_name: str, customer_name: str,
                                statement_lines: list, balance_due: float,
                                customer_phone: str = None) -> bytes:
    """
    Builds an itemized PDF statement for one customer and returns the
    raw PDF bytes, ready to hand to Streamlit's download_button.

    Each row shows: Date, Product, Qty, Rate, Amount, Paid, Balance —
    a real itemized invoice rather than a flattened description line.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"], fontSize=20, alignment=TA_CENTER,
        textColor=colors.HexColor("#1a3d5c"),
    )
    sub_style = ParagraphStyle(
        "SubStyle", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
    )
    section_label_style = ParagraphStyle(
        "SectionLabel", parent=styles["Normal"], fontSize=11, alignment=TA_LEFT,
        textColor=colors.HexColor("#1a3d5c"), fontName="Helvetica-Bold",
    )

    story = []

    # ---------- Header ----------
    story.append(Paragraph(business_name, title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Account Statement", sub_style))
    story.append(Spacer(1, 10))

    # ---------- Customer info box ----------
    customer_info = [["Customer:", customer_name]]
    if customer_phone:
        customer_info.append(["Phone:", customer_phone])
    customer_info.append(["Statement Date:", date.today().strftime('%d %b %Y')])

    info_table = Table(customer_info, colWidths=[100, 300])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # ---------- Itemized transaction table ----------
    story.append(Paragraph("Transaction Details", section_label_style))
    story.append(Spacer(1, 6))

    table_data = [["Date", "Product", "Qty", "Rate (Rs.)", "Amount (Rs.)",
                   "Paid (Rs.)", "Balance (Rs.)"]]

    for line in statement_lines:
        if line["type"] == "sale":
            qty_str = f"{line['quantity']:,.0f} {line['unit_label']}"
            product_str = line["product"]
            if line.get("rickshaw_fare"):
                product_str += f"\n(+ Rs.{line['rickshaw_fare']:,.0f} freight)"
        else:
            qty_str = f"{line['quantity']:,.0f} {line['unit_label']}"
            product_str = f"{line['product']} (paid in goods)"

        table_data.append([
            line["date"],
            product_str,
            qty_str,
            f"{line['rate']:,.0f}" if line["rate"] else "-",
            f"{line['charge']:,.0f}" if line["charge"] else "-",
            f"{line['payment']:,.0f}" if line["payment"] else "-",
            f"{line['running_balance']:,.0f}",
        ])

    # Totals row
    total_charge = sum(l["charge"] for l in statement_lines)
    total_payment = sum(l["payment"] for l in statement_lines)
    table_data.append(["", "", "", "TOTAL", f"{total_charge:,.0f}",
                        f"{total_payment:,.0f}", f"{balance_due:,.0f}"])

    table = Table(table_data, colWidths=[50, 115, 60, 60, 70, 65, 70], repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f4f6f8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fdf2d0")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    table.setStyle(TableStyle(style_commands))
    story.append(table)
    story.append(Spacer(1, 18))

    # ---------- Summary box: Owed / Paid / Outstanding ----------
    is_over_limit = balance_due >= CREDIT_LIMIT
    balance_color = colors.HexColor("#c0392b") if is_over_limit else colors.HexColor("#1a7a3c")

    summary_data = [
        ["Total Amount Owed (Rs.)", "Total Paid (Rs.)", "Total Outstanding (Rs.)"],
        [f"{total_charge:,.0f}", f"{total_payment:,.0f}", f"{balance_due:,.0f}"],
    ]
    summary_table = Table(summary_data, colWidths=[150, 150, 150])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 14),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (2, 1), (2, 1), balance_color),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)

    if is_over_limit:
        story.append(Spacer(1, 8))
        warn_style = ParagraphStyle(
            "WarnStyle", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER,
            textColor=balance_color, fontName="Helvetica-Bold",
        )
        story.append(Paragraph("This balance has crossed the credit limit.", warn_style))

    story.append(Spacer(1, 20))
    thanks_style = ParagraphStyle(
        "ThanksStyle", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        textColor=colors.HexColor("#888888"),
    )
    story.append(Paragraph("Thank you for your business.", thanks_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_custom_mix_bill_pdf(business_name: str, customer_name: str,
                                  order_date: str, target_weight_kg: float,
                                  ingredient_lines: list, customer_phone: str = None,
                                  payment_type: str = "credit",
                                  cash_received: float = 0,
                                  new_balance_due: float = None) -> bytes:
    """
    Builds the printable bill for a custom feed-mix order — a customer
    asks for a target total weight, made up of several ingredients
    added one at a time. Shows each ingredient's weight, rate, and
    cost, the target weight vs. actual weight used, and the grand
    total — this is its own document, separate from the running Khata
    statement, since the customer cares about THIS order's breakdown.

    ingredient_lines: list of {"product": str, "weight_kg": float,
                                "rate_per_kg": float, "amount": float}
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"], fontSize=20, alignment=TA_CENTER,
        textColor=colors.HexColor("#1a3d5c"),
    )
    sub_style = ParagraphStyle(
        "SubStyle", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
    )
    section_label_style = ParagraphStyle(
        "SectionLabel", parent=styles["Normal"], fontSize=11, alignment=TA_LEFT,
        textColor=colors.HexColor("#1a3d5c"), fontName="Helvetica-Bold",
    )

    story = []

    # ---------- Header ----------
    story.append(Paragraph(business_name, title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Custom Feed Mix — Order Bill", sub_style))
    story.append(Spacer(1, 10))

    # ---------- Customer info box ----------
    customer_info = [["Customer:", customer_name]]
    if customer_phone:
        customer_info.append(["Phone:", customer_phone])
    customer_info.append(["Order Date:", order_date])
    customer_info.append(["Target Weight:", f"{target_weight_kg:,.0f} kg"])

    info_table = Table(customer_info, colWidths=[100, 300])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # ---------- Ingredient breakdown table ----------
    story.append(Paragraph("Mix Composition", section_label_style))
    story.append(Spacer(1, 6))

    table_data = [["#", "Product", "Weight (kg)", "Rate/kg (Rs.)", "Amount (Rs.)"]]
    total_weight = 0.0
    total_amount = 0.0
    for i, line in enumerate(ingredient_lines, start=1):
        total_weight += line["weight_kg"]
        total_amount += line["amount"]
        table_data.append([
            str(i),
            line["product"],
            f"{line['weight_kg']:,.1f}",
            f"{line['rate_per_kg']:,.2f}",
            f"{line['amount']:,.0f}",
        ])

    table_data.append(["", "TOTAL", f"{total_weight:,.1f}", "", f"{total_amount:,.0f}"])

    table = Table(table_data, colWidths=[30, 175, 90, 90, 95], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f4f6f8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fdf2d0")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 10))

    weight_diff = target_weight_kg - total_weight
    if abs(weight_diff) > 0.01:
        note_style = ParagraphStyle(
            "NoteStyle", parent=styles["Normal"], fontSize=9, alignment=TA_LEFT,
            textColor=colors.HexColor("#c0392b"),
        )
        story.append(Paragraph(
            f"Note: target weight was {target_weight_kg:,.0f} kg; "
            f"{total_weight:,.1f} kg was filled "
            f"({'short by' if weight_diff > 0 else 'over by'} {abs(weight_diff):,.1f} kg).",
            note_style
        ))
        story.append(Spacer(1, 10))

    # ---------- Payment summary ----------
    payment_label = "Cash Paid" if payment_type == "cash" else "Added to Credit Account"
    summary_data = [
        ["Total Mix Weight (kg)", "Total Bill (Rs.)", payment_label + " (Rs.)"],
        [f"{total_weight:,.1f}", f"{total_amount:,.0f}",
         f"{cash_received:,.0f}" if payment_type == "cash" else f"{total_amount:,.0f}"],
    ]
    summary_table = Table(summary_data, colWidths=[150, 150, 150])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)

    if payment_type == "credit" and new_balance_due is not None:
        story.append(Spacer(1, 10))
        is_over_limit = new_balance_due >= CREDIT_LIMIT
        balance_color = colors.HexColor("#c0392b") if is_over_limit else colors.HexColor("#1a7a3c")
        balance_style = ParagraphStyle(
            "BalanceStyle", parent=styles["Normal"], fontSize=12, alignment=TA_CENTER,
            textColor=balance_color, fontName="Helvetica-Bold",
        )
        story.append(Paragraph(
            f"New Total Outstanding on Account: Rs. {new_balance_due:,.0f}", balance_style
        ))
        if is_over_limit:
            story.append(Paragraph(
                "This balance has crossed the credit limit.", balance_style
            ))

    story.append(Spacer(1, 20))
    thanks_style = ParagraphStyle(
        "ThanksStyle", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
        textColor=colors.HexColor("#888888"),
    )
    story.append(Paragraph("Thank you for your business.", thanks_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
