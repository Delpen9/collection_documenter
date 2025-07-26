import os
import io
import re
import json
import time
import string
import secrets
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
BLOB_CONN_STR = os.getenv("BLOB_CONN_STR")
STATE_CONTAINER = os.getenv("STATE_CONTAINER", "session-state")
IMAGE_CONTAINER = os.getenv("IMAGE_CONTAINER", "user-images")
ACCOUNT_KEY = os.getenv("BLOB_ACCOUNT_KEY") or re.search(r"AccountKey=([^;]+)", BLOB_CONN_STR).group(1)

# Initialize blob client if needed
BlobServiceClient, generate_blob_sas, BlobSasPermissions = import_blob_libs()
blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)

# --- Persistence Helpers ---
from persistence import *

# --- Item Handlers ---
def generate_item_id(length: int=10):
    alphabet = string.ascii_letters + string.digits
    return "item_id_" + ''.join(secrets.choice(alphabet) for _ in range(length))

def add_Item(collection_name: str, item_index: int, user_email: str):
    new_item_id = generate_item_id()
    st.session_state.Items.insert(item_index + 1, new_item_id)
    st.session_state[new_item_id] = {}
    save_state(collection_name, user_email, blob_service)

@st.dialog("Confirm delete", width="small")
def confirm_delete(collection_name, item_index, item_id, user_email):
    st.write(f"Delete item **#{item_id}**?")
    yes, no = st.columns(2)
    with yes:
        if st.button("Yes, delete", key=f"DO_NOT_PERSIST_yes_delete_{item_id}"):
            delete_item_assets(item_id, blob_service)

            # there is a generic item_id list that is maintained
            # this line removes that
            st.session_state.Items.pop(item_index)

            # each item has a dictionary of key entries
            # this removes that dictionary from the session_state
            del st.session_state[item_id]

            save_state(collection_name, user_email, blob_service)
            st.rerun()

    with no:
        if st.button("Cancel", key=f"DO_NOT_PERSIST_no_{item_id}"):
            st.rerun()

# --- Render Item ---
def render_Item(collection_name, item_index, item_id, allow_delete, model, tag_options, selected_filters):
    # we really want every item to be a nested dictionary
    # in the session_state
    if item_id not in st.session_state:
        st.session_state[item_id] = {}

    title_key = "item_title"
    if title_key not in st.session_state[item_id]:
        st.session_state[item_id][title_key] = "Default Item Title"

    title_input = st.text_input(
        "",
        value=st.session_state[item_id][title_key],
        key=f"DO_NOT_PERSIST_title_input_{item_id}"
    )
    st.session_state[item_id][title_key] = title_input

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
                            key=f"DO_NOT_PERSIST_file_uploader_{label}_{item_id}"
                        )

                    with tabs[1]:
                        camera = st.camera_input(
                            f"Snap {label.title()} Photo",
                            key=f"DO_NOT_PERSIST_camera_{label}_{item_id}"
                        )

                    img = upload or camera
                    image_key = f"image_{label}"

                    if img:
                        url = save_image(collection_name, st.session_state.user["email"], item_id, label, img, blob_service)

                        if image_key not in st.session_state[item_id]:
                            st.session_state[item_id][image_key] = url

                    blob_name = st.session_state[item_id].get(image_key, "")
                    if blob_name.startswith(st.session_state.user["email"]):
                        # build a brand‐new SAS URL (with fresh start/expiry)
                        url = build_sas_url(blob_name, blob_service, hours=1)
                        st.image(url, caption=label.title())

                        if st.button("🗑️ Remove Image", key=f"DO_NOT_PERSIST_remove_image_{label}_{item_id}"):
                            remove_image(collection_name, item_id, label, blob_service)

            with c3:
                audio_data = audiorecorder(key=f"DO_NOT_PERSIST_audio_recorder_{item_id}")
                if audio_data:
                    st.audio(audio_data.export().read(), format="audio/wav")

                if st.button("📝 Transcribe", key=f"DO_NOT_PERSIST_transcribe_{item_id}"):
                    buf = io.BytesIO(audio_data.export().read())
                    data, sr = sf.read(buf)

                    if data.ndim > 1:
                        data = data.mean(axis=1)

                    if sr != 16000:
                        data = librosa.resample(data, orig_sr=sr, target_sr=16000)

                    text = model.transcribe(data.astype("float32"), fp16=False)["text"]
                    st.session_state[item_id][f"transcript"] = text

                # Use unique key for text_area to avoid duplicates
                text_area = st.text_area(
                    "Transcription",
                    value=st.session_state[item_id].get(f"transcript", ""),
                    height=150,
                    key=f"DO_NOT_PERSIST_text_area_{item_id}"
                )

                st.session_state[item_id][f"transcript"] = text_area

            # Initialize tag state and render widget
            tag_key = "tag_selections"
            if tag_key not in st.session_state[item_id]:
                st.session_state[item_id][tag_key] = []

            # if the user deletes a tag at the top of the page
            # this logic makes sure this tag is removed from the
            # tag selections
            st.session_state[item_id][tag_key] = [
                t for t in st.session_state[item_id][tag_key]
                if t in tag_options
            ]

            tag_selections_for_item = st.multiselect(
                "Add Tags",
                options=tag_options,
                default=st.session_state[item_id][tag_key],
                key=f"DO_NOT_PERSIST_add_item_tags_{item_id}",
            )

            st.session_state[item_id][tag_key] = tag_selections_for_item
            
        if not selected_filters:
            st.button(
                "➕ Add Item Below",
                on_click=add_Item,
                args=(collection_name, item_index, st.session_state.user["email"]),
                key=f"DO_NOT_PERSIST_add_item_below_{item_id}"
            )

        if allow_delete:
            if st.button("🗑️ Delete Item", key=f"DO_NOT_PERSIST_delete_item_{item_id}"):
                confirm_delete(collection_name, item_index, item_id, st.session_state.user["email"])