import os
import io
import re
import json
import time
import streamlit as st
from datetime import datetime, timedelta

def import_blob_libs():
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
    return BlobServiceClient, generate_blob_sas, BlobSasPermissions

# --- Persistence Helpers ---
from persistence import *

# --- Item Helpers ---
from collection_viewer.item import *

# --- PDF Helpers ---
from collection_viewer.pdf_renderer import *

# --- Configuration ---
BLOB_CONN_STR = st.secrets.blob_storage["BLOB_CONN_STR"]
STATE_CONTAINER = st.secrets.blob_storage["STATE_CONTAINER"]
IMAGE_CONTAINER  = st.secrets.blob_storage["IMAGE_CONTAINER"]
ACCOUNT_KEY = st.secrets.blob_storage["BLOB_ACCOUNT_KEY"]

# Initialize blob client if needed
BlobServiceClient, generate_blob_sas, BlobSasPermissions = import_blob_libs()
blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)

# --- UI Setup ---
def setup_page(collection_name: str):
    go_back_press = st.button("⬅️ Go Back")

    st.image("assets/color_banner.jpeg", use_container_width=True)

    if go_back_press:
        st.session_state.selected_collection = None
        st.rerun()

    st.markdown(
        f"""
        <style>
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}

        .stApp {{ padding: 2rem; }}

        .banner-container {{
            padding: 1rem 2rem;
            border: 1px solid;s
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
            text-align: center;
            font-family: 'Segoe UI', sans-serif;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            transition: background-color .3s, color .3s, border-color .3s;
        }}

        .Item-container {{
            background: #f9f9f9;
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: background .3s, color .3s, box-shadow .3s;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<h3 style='text-align: center;'>{collection_name}</h3>",
        unsafe_allow_html=True,
    )

    st.markdown("""
    <style>
    .tag-pills span{
    display:inline-block;padding:2px 10px;margin:0 6px 6px 0;
    border-radius:9999px;background:#e8f0fe;color:#1a73e8;font-size:.85rem;
    white-space:nowrap;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Tag Widget ---
def tag_filter_widget(collection_name, list_key):
    def pills(tags, selected):
        html = "<div class='tag-pills'>" + "".join(
            f"<span style=\"background:{'#1a73e8' if t in selected else '#e8f0fe'};"
            f"color:{'white' if t in selected else '#1a73e8'}\">{t}</span>"
            for t in tags
        ) + "</div>"
        st.markdown(html, unsafe_allow_html=True)

    if list_key not in st.session_state:
        st.session_state[list_key] = []

    tag = st.text_input("Add tag", placeholder="Type & press Enter")

    if tag in st.session_state[list_key]:
        st.warning("This tag already exists.")

    if tag != "" and tag not in st.session_state[list_key]:
        st.session_state[list_key].append(tag)

    st.markdown(
        "<div class='tag-pills'>" +
        "".join(f"<span>{t}</span>" for t in st.session_state[list_key]) +
        "</div>",
        unsafe_allow_html=True
    )

    st.write("")

    # we want the user to type the tag in which they want to delete
    # because this will prevent them from deleting the tag accidentally
    tag_to_remove = st.text_input("Remove tag", placeholder="Type & press Enter to delete a tag")
    if tag_to_remove in st.session_state[list_key]:
        st.session_state[list_key].remove(tag_to_remove)
        save_state(collection_name, st.session_state.user["email"], blob_service)
        st.rerun()

    st.write("")

    selected = st.multiselect(
        "Filter by tags",
        options=st.session_state[list_key],
        default=[],
    )

    keyword_filter = st.text_input("Keyword filter", placeholder="Type & press Enter")

    if keyword_filter != "":
        st.info(f"Keyword filtering for '{keyword_filter}' is being applied.")

    return st.session_state[list_key], selected, keyword_filter

# --- Main ---
def run_collection(collection_name: str, user_email, DEBUG_MODE: bool):
    flush_session_state()
    load_state(collection_name, user_email, blob_service)

    setup_page(collection_name=collection_name)

    all_tags, sel_tags, keyword_filter = tag_filter_widget(
        collection_name,
        "main_tags_list",
    )

    if "Collection" not in st.session_state:
        st.session_state.Collection = collection_name

    if "Items" not in st.session_state:
        st.session_state.Items = [generate_item_id()]

    allow_del = len(st.session_state.Items) > 1

    total = len(st.session_state.Items)
    shown = 0

    total_of_price_estimates = 0.00
    for item_index, item_id in enumerate(st.session_state.Items):
        item_tags = st.session_state.get(item_id, {}).get("tag_selections", [])
        item_title = st.session_state[item_id].get("item_title", "")

        # does this item pass the filters?
        tag_conditions = (not sel_tags) or set(item_tags).intersection(sel_tags)
        title_conditions = keyword_filter.lower() in item_title.lower()
        if tag_conditions and title_conditions:
            shown += 1
            st.markdown("---")
            item_price = render_Item(collection_name, item_index, item_id, allow_del, all_tags, sel_tags)
            total_of_price_estimates += item_price

    st.write("")

    def format_accounting(value: float) -> str:
        if value < 0:
            return f"(${abs(value):,.2f})"

        return f"${value:,.2f}"

    formatted_total = format_accounting(total_of_price_estimates)

    st.metric(label="Total Estimate", value=formatted_total)

    hidden = total - shown
    st.write("---")
    st.info(f"{hidden} item{'s' if hidden!=1 else ''} hidden")

    # Usage in your Streamlit app (e.g. at bottom of run_collection):
    pdf_buf = generate_collection_pdf(
        collection_name=collection_name,
        blob_service=blob_service,   # pass in your Azure blob client
        sas_hours=1
    )

    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{collection_name}_{today_str}.pdf"

    # now render the button inside that div
    st.download_button(
        label="📄 Download Collection PDF",
        data=pdf_buf,
        file_name=filename,
        mime="application/pdf"
    )

    save_state(collection_name, user_email, blob_service)

    if DEBUG_MODE:
        st.write("---")
        with st.expander("Click here to view session details:", expanded=False):
            st.write(st.session_state)

    st.session_state.selected_collection = collection_name

    st.image("assets/color_banner.jpeg", use_container_width=True)