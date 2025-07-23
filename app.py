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

# --- Persistence Helpers ---
from persistence import *

# --- Item Helpers ---
from item import *

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

# --- Tag Widget ---
def tag_filter_widget(label, list_key, select_key):
    if list_key not in st.session_state:
        st.session_state[list_key] = []

    tag = st.text_input(label, placeholder="Type & press Enter")

    if tag != "" and tag not in st.session_state[list_key]:
        st.session_state[list_key].append(tag)

    st.info(f"Available tags: {st.session_state[list_key]}")


    selected = st.multiselect(
        "Filter by tags",
        options=st.session_state[list_key],
        default=st.session_state.get(select_key, st.session_state[list_key]),
        key=select_key,
    )
    return st.session_state[list_key], selected

# --- Main ---
def run_collection():
    user_email = login()
    st.subheader(f"Welcome {user_email}!")
    load_state(user_email, LOCAL_MODE, blob_service)
    rehydrate_image_urls(LOCAL_MODE, blob_service)

    setup_page()
    st.write("---")

    all_tags, sel_tags = tag_filter_widget(
        "Add tag",
        "main_tags_list",
        "main_tags_select"
    )
    st.session_state["main_tags_list"] = all_tags

    if "Items" not in st.session_state:
        st.session_state.Items = [0]

    model = load_model()
    allow_del = len(st.session_state.Items) > 1

    for i, cid in enumerate(st.session_state.Items):
        st.markdown("---")
        render_Item(i, cid, allow_del, model, all_tags, sel_tags)

    save_state(user_email, PERSIST_KEYS, LOCAL_MODE, blob_service)

if __name__ == "__main__":
    run_collection()