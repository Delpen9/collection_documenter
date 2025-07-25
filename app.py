import os
import io
import re
import json
import time
import streamlit as st
import soundfile as sf
import librosa
from audiorecorder import audiorecorder
from authentication import login, show_streamlit_ui, hide_streamlit_ui
from datetime import datetime, timedelta

# Optional Azure imports only when not in local mode
def import_blob_libs():
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
    return BlobServiceClient, generate_blob_sas, BlobSasPermissions

# --- Persistence Helpers ---
from persistence import *

# --- Item Helpers ---
from item import *

# --- Configuration ---
LOCAL_MODE = os.getenv("LOCAL_MODE", "false").lower() == "true"
BLOB_CONN_STR = os.getenv("BLOB_CONN_STR")
STATE_CONTAINER = os.getenv("STATE_CONTAINER", "session-state")
IMAGE_CONTAINER = os.getenv("IMAGE_CONTAINER", "user-images")
ACCOUNT_KEY = os.getenv("BLOB_ACCOUNT_KEY") or re.search(r"AccountKey=([^;]+)", BLOB_CONN_STR).group(1)
PERSIST_KEYS = {"main_tags_list", "Items", "_image_paths"}

# Initialize blob client if needed
if not LOCAL_MODE:
    BlobServiceClient, generate_blob_sas, BlobSasPermissions = import_blob_libs()
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
else:
    blob_service = None

@st.cache_resource
def load_model():
    import whisper
    return whisper.load_model("base")

# --- UI Setup ---
def setup_page():
    st.set_page_config(
        page_title="Collectible Documenter",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    hide_streamlit_ui()
    show_streamlit_ui()
    st.markdown("""
        <style>
            #MainMenu {visibility: hidden;} footer {visibility: hidden;} .stApp {padding: 2rem;}
            .banner-container { padding: 1rem 2rem; border-radius: 0.5rem; margin-bottom:1.5rem; text-align:center;
                font-family:'Segoe UI',sans-serif;border:1px solid;box-shadow:0 2px 8px rgba(0,0,0,0.05);
                transition:background-color .3s,color .3s,border-color .3s; }
            .Item-container { background:#f9f9f9;border-radius:1rem;padding:1.5rem;margin-bottom:1.5rem;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);transition:background .3s,color .3s,box-shadow .3s; }
        </style>
        <div class="banner-container">
            <h1 style="margin:0;font-size:2.2rem;">Collectible Documenter</h1>
        </div>
    """, unsafe_allow_html=True)

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
def tag_filter_widget(label, list_key):
    def pills(tags, selected):
        html = "<div class='tag-pills'>" + "".join(
            f"<span style=\"background:{'#1a73e8' if t in selected else '#e8f0fe'};"
            f"color:{'white' if t in selected else '#1a73e8'}\">{t}</span>"
            for t in tags
        ) + "</div>"
        st.markdown(html, unsafe_allow_html=True)

    if list_key not in st.session_state:
        st.session_state[list_key] = []

    tag = st.text_input(label, placeholder="Type & press Enter")

    if tag != "" and tag not in st.session_state[list_key]:
        st.session_state[list_key].append(tag)

    st.markdown(
        "<div class='tag-pills'>" +
        "".join(f"<span>{t}</span>" for t in st.session_state[list_key]) +
        "</div>",
        unsafe_allow_html=True
    )
    st.write("")

    selected = st.multiselect(
        "Filter by tags",
        options=st.session_state[list_key],
        default=[],
    )
    return st.session_state[list_key], selected

# --- Main ---
def run_collection(DEBUG_MODE: bool):
    user_email = login()
    st.subheader(f"Welcome {user_email}!")
    load_state(user_email, LOCAL_MODE, blob_service)
    rehydrate_image_urls(LOCAL_MODE, blob_service)

    setup_page()
    st.write("---")

    all_tags, sel_tags = tag_filter_widget(
        "Add tag",
        "main_tags_list",
    )
    st.session_state["main_tags_list"] = all_tags

    if "Items" not in st.session_state:
        st.session_state.Items = [generate_item_id()]

    model = load_model()
    allow_del = len(st.session_state.Items) > 1

    total = len(st.session_state.Items)
    shown = 0

    for item_index, item_id in enumerate(st.session_state.Items):
        item_tags = st.session_state[item_id]["tag_selections"]

        # does this item pass the filter?
        if (not sel_tags) or set(item_tags).intersection(sel_tags):
            shown += 1
            st.markdown("---")
            render_Item(item_index, item_id, allow_del, model, all_tags, sel_tags)

    hidden = total - shown
    st.write("---")
    st.info(f"{hidden} item{'s' if hidden!=1 else ''} hidden")

    save_state(user_email, LOCAL_MODE, blob_service)

    if DEBUG_MODE:
        st.write("---")
        st.write(st.session_state)

if __name__ == "__main__":
    DEBUG_MODE = False
    run_collection(DEBUG_MODE=DEBUG_MODE)