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