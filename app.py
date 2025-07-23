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
def tag_filter_widget(label, list_key, input_key, select_key):
    tags = st.session_state.setdefault(list_key, [])

    def _add():
        v = st.session_state[input_key].strip()
        if v and v not in tags:
            tags.append(v)
        st.session_state[input_key] = ""

    st.text_input(label, key=input_key, on_change=_add, placeholder="Type & press Enter")

    cols = st.columns(len(tags)) if tags else []
    for i, t in enumerate(tags):
        if cols[i].button(f"❌ {t}", key=f"{list_key}_del_{i}"):
            tags.pop(i)
            st.rerun()

    selected = st.multiselect(
        "Filter by tags",
        options=tags,
        default=st.session_state.get(select_key, tags),
        key=select_key,
    )
    return tags, selected

# --- Item Handlers ---
def add_Item(idx: int):
    next_id = max(st.session_state.Items, default=-1) + 1
    st.session_state.Items.insert(idx+1, next_id)

@st.dialog("Confirm delete", width="small")
def confirm_delete(idx, cid):
    st.write(f"Delete item **#{cid}**?")
    yes, no = st.columns(2)
    with yes:
        if st.button("Yes, delete"):
            delete_item_assets(cid, LOCAL_MODE, blob_service)
            st.session_state.Items.pop(idx)
            for k in list(st.session_state.keys()):
                if k.endswith(f"_{cid}"):
                    st.session_state.pop(k)
            st.rerun()
    with no:
        if st.button("Cancel"):
            st.rerun()

# --- Render Item ---
def render_Item(idx, cid, allow_delete, model, tag_options, selected_filters):
    # Initialize default name before widget
    name_key = f"Item_name_{cid}"
    if name_key not in st.session_state:
        st.session_state[name_key] = "Default Item Name"

    st.text_input("", st.session_state[name_key], key=name_key)

    with st.container():
        with st.expander("Details", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            for col, label in zip((c1, c2), ("front", "back")):
                with col:
                    st.markdown(f"**Upload {label.title()} Image**")
                    tabs = st.tabs(["Upload", "Camera"])
                    with tabs[0]:
                        upload = st.file_uploader(
                            "",
                            type=["png","jpg","jpeg"],
                            key=f"upload_{label}_{cid}"
                        )

                    with tabs[1]:
                        camera = st.camera_input(
                            f"Snap {label.title()} Photo",
                            key=f"camera_{label}_{cid}"
                        )
                    img = upload or camera

                    if img:
                        url = save_image(st.session_state.user["email"], cid, label, img, LOCAL_MODE, blob_service)
                        st.session_state[f"{label}_{cid}"] = url

                    if st.session_state.get(f"{label}_{cid}"):
                        st.image(st.session_state[f"{label}_{cid}"], caption=label.title())
                        if st.button("🗑️ Remove Image", key=f"rm_{label}_{cid}"):
                            remove_image(cid, label, LOCAL_MODE, blob_service)

            with c3:
                audio_data = audiorecorder(key=f"audio_{cid}")
                if audio_data:
                    st.audio(audio_data.export().read(), format="audio/wav")

                if st.button("📝 Transcribe", key=f"trans_{cid}"):
                    buf = io.BytesIO(audio_data.export().read())
                    data, sr = sf.read(buf)

                    if data.ndim > 1:
                        data = data.mean(axis=1)

                    if sr != 16000:
                        data = librosa.resample(data, orig_sr=sr, target_sr=16000)

                    text = model.transcribe(data.astype("float32"), fp16=False)["text"]
                    st.session_state[f"transcript_{cid}"] = text

                # Use unique key for text_area to avoid duplicates
                st.text_area(
                    "Transcription",
                    value=st.session_state.get(f"transcript_{cid}", ""),
                    height=150,
                    key=f"note_{cid}"
                )

            # Initialize tag state and render widget
            tag_key = f"tag_selection_{cid}"
            if tag_key not in st.session_state:
                st.session_state[tag_key] = []

            st.multiselect(
                "Add Tags",
                options=tag_options,
                default=st.session_state[tag_key],
                key=tag_key
            )

        if not selected_filters and st.button("➕ Add Item Below", key=f"add_{cid}"):
            add_Item(idx)

        if allow_delete and st.button("🗑️ Delete Item", key=f"del_{cid}"):
            confirm_delete(idx, cid)

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
        "main_tags_input",
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