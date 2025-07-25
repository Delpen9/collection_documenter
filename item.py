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

# --- Persistence Helpers ---
from persistence import *

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

                    blob_name = st.session_state.get(f"{label}_{cid}", "")
                    if blob_name.startswith(st.session_state.user["email"]):
                        # build a brand‐new SAS URL (with fresh start/expiry)
                        url = build_sas_url(blob_name, blob_service, hours=1)
                        st.image(url, caption=label.title())

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