from io import BytesIO
import requests

import streamlit as st
import pandas as pd

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from persistence import build_sas_url

def generate_collection_pdf(collection_name: str, blob_service, sas_hours: int = 1):
    """
    Walk through st.session_state.Items and build a PDF:
      - At the top: a table of Title / Price / Tags / Notes (with wrapping)
      - Then one page per item with images and text
    Returns a BytesIO buffer ready for download.
    """
    # 1) Prepare canvas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50

    # --- Title above the table ---
    title_text = "Itemized Table"
    c.setFont("Helvetica-Bold", 16)
    title_y = height - margin
    c.drawString(margin, title_y, title_text)
    
    # 2) Build table_data using Paragraphs for wrapping
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        wordWrap="CJK",
    )

    header_style = ParagraphStyle(
        name="Header",
        parent=styles["Heading4"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=1,  # center
    )

    table_data = [
        [
            Paragraph("Title", header_style),
            Paragraph("Price", header_style),
            Paragraph("Tags", header_style),
            Paragraph("Notes", header_style),
        ]
    ]
    for item_id in st.session_state.Items:
        item = st.session_state.get(item_id, {})
        table_data.append([
            Paragraph(item.get("item_title", ""), body_style),
            Paragraph(item.get("price_estimate", "0.00"), body_style),
            Paragraph(", ".join(item.get("tag_selections", [])), body_style),
            Paragraph(item.get("notes", ""), body_style),
        ])

    # 3) Create and draw the table
    total_width = width - 2 * margin
    col_widths = [
        total_width * 0.40,  # Title
        total_width * 0.10,  # Price
        total_width * 0.25,  # Tags
        total_width * 0.25,  # Notes
    ]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
    ]))
    tbl_w, tbl_h = tbl.wrapOn(c, total_width, height)
    tbl.drawOn(c, margin, height - margin - tbl_h)

    # 4) Paginate items (one item per page)
    for item_id in st.session_state.Items:
        c.showPage()
        item = st.session_state.get(item_id, {})

        y = height - margin
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin, y, item.get("item_title", ""))

        y -= 24
        tags = item.get("tag_selections", [])
        if tags:
            c.setFont("Helvetica", 12)
            c.drawString(margin, y, "Tags: " + ", ".join(tags))
            y -= 18

        notes = item.get("notes", "")
        if notes:
            c.setFont("Helvetica", 12)
            text_obj = c.beginText(margin, y)
            text_obj.textLines(notes)
            c.drawText(text_obj)
            y -= 14 * len(notes.splitlines()) + 10

        # images
        img_w = (width - 2*margin - 10) / 2
        img_h = 150
        img_y = y - img_h
        for idx, label in enumerate(("front", "back")):
            blob_name = item.get(f"image_{label}", "")
            if blob_name:
                sas_url = build_sas_url(blob_name, blob_service, hours=sas_hours)
                resp = requests.get(sas_url, timeout=5)
                resp.raise_for_status()
                img = ImageReader(BytesIO(resp.content))

                x = margin + idx * (img_w + 10)
                c.drawImage(img, x, img_y, img_w, img_h, preserveAspectRatio=True)

    # 5) Finish up
    c.save()
    buffer.seek(0)
    return buffer