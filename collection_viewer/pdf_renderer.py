import io
import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import streamlit as st

from persistence import build_sas_url

def generate_collection_pdf(collection_name: str, blob_service, sas_hours: int = 1):
    """
    Walk through st.session_state.Items and build a PDF:
      - title (item_title)
      - tags (tag_selections)
      - notes
      - front/back images via fresh SAS URLs

    Returns a BytesIO buffer ready for download.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    for item_id in st.session_state.Items:
        item = st.session_state.get(item_id, {})

        # --- TEXT ---
        title = item.get("item_title", "")
        tags = item.get("tag_selections", [])
        notes = item.get("notes", "")

        y = height - 50
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, title)

        y -= 20
        if tags:
            c.setFont("Helvetica", 12)
            c.drawString(50, y, "Tags: " + ", ".join(tags))
            y -= 20

        if notes:
            c.setFont("Helvetica", 12)
            text_obj = c.beginText(50, y)
            text_obj.textLines(notes)
            c.drawText(text_obj)
            y -= 14 * len(notes.splitlines()) + 10

        # --- IMAGES with Fresh SAS URLs ---
        img_w = (width - 100) / 2
        img_h = 150
        img_y = y - img_h

        for idx, label in enumerate(("front", "back")):
            blob_name = item.get(f"image_{label}", "")
            if blob_name:
                # regenerate a fresh SAS URL
                sas_url = build_sas_url(blob_name, blob_service, hours=sas_hours)
                resp = requests.get(sas_url, timeout=5)
                resp.raise_for_status()
                img = ImageReader(io.BytesIO(resp.content))

                x = 50 + idx * (img_w + 10)
                c.drawImage(img, x, img_y, img_w, img_h, preserveAspectRatio=True)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer