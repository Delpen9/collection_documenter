import os
import io
import re
import json
import time
import streamlit as st
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
    
def save_state(user_email, LOCAL_MODE, blob_service):
    if LOCAL_MODE:
        return

    # only persist keys we know are JSON-safe
    state_to_save = {
        k: st.session_state[k]
        for k in st.session_state
    }

    blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=f"{user_email}.json")
    blob.upload_blob(json.dumps(state_to_save), overwrite=True)

def load_state(user_email, LOCAL_MODE, blob_service):
    if LOCAL_MODE:
        return

    try:
        blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=f"{user_email}.json")
        raw = blob.download_blob().readall()
        saved = json.loads(raw)
        for k, v in saved.items():
            st.session_state[k] = v

    except Exception:
        pass

def save_image(user_email, item_id, label, img, local_mode, blob_service):
    ext = img.type.split("/")[-1]
    blob_name = f"{user_email}/{item_id}_{label}.{ext}"

    if local_mode:
        # local disk write
        path = os.path.join("images", blob_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # read the bytes once:
        content = img.read()
        with open(path, "wb") as f:
            f.write(content)
        # reset buffer so Streamlit can read it later if needed
        img.seek(0)
        return blob_name

    # for Azure upload, grab raw bytes (not a memoryview)
    content = img.read()                     # <-- use read()
    # if you ever need getbuffer, convert it:
    # content = bytes(img.getbuffer())

    container_client = blob_service.get_container_client(IMAGE_CONTAINER)
    container_client.upload_blob(
        name=blob_name,
        data=content,                         # <-- now real bytes
        overwrite=True,
    )
    # reset buffer so any downstream code that inspects img still works
    img.seek(0)

    return blob_name

def build_sas_url(blob_path, blob_service, hours=1):
    start = datetime.utcnow() - timedelta(minutes=5)      # see next point
    expiry = datetime.utcnow() + timedelta(hours=hours)
    sas = generate_blob_sas(
        account_name = blob_service.account_name,
        container_name = IMAGE_CONTAINER,
        blob_name = blob_path,
        account_key = ACCOUNT_KEY,
        permission = BlobSasPermissions(read=True),
        start = start,
        expiry = expiry,
    )
    return (f"https://{blob_service.account_name}"
            f".blob.core.windows.net/{IMAGE_CONTAINER}"
            f"/{blob_path}?{sas}")

def rehydrate_image_urls(LOCAL_MODE, blob_service):
    if LOCAL_MODE or blob_service is None:
        return

    for item_id, labels in st.session_state.get("_image_paths", {}).items():
        for label, blob_path in labels.items():
            st.session_state[f"{label}_{item_id}"] = build_sas_url(blob_path, blob_service, LOCAL_MODE)

def delete_blob_by_path(blob_path, LOCAL_MODE, blob_service):
    if LOCAL_MODE or blob_service is None:
        return

    try:
        blob_service.get_blob_client(IMAGE_CONTAINER, blob_path).delete_blob(delete_snapshots="include")
    except Exception:
        pass

def remove_image(item_id, label, LOCAL_MODE, blob_service):
    paths = st.session_state.get("_image_paths", {}).get(str(item_id), {})
    blob_path = paths.pop(label, None)

    if not blob_path and st.session_state.get(f"{label}_{item_id}"):
        url = st.session_state[f"{label}_{item_id}"]
        # fallback if you only have a SAS url
        blob_path = url.split(f"{IMAGE_CONTAINER}/", 1)[-1].split("?", 1)[0]

    if blob_path:
        delete_blob_by_path(blob_path, LOCAL_MODE, blob_service)

    for k in (f"{label}_{item_id}", f"upload_{label}_{item_id}", f"camera_{label}_{item_id}"):
        st.session_state.pop(k, None)

    st.rerun()

def delete_item_assets(item_id, LOCAL_MODE, blob_service):
    paths = st.session_state.get("_image_paths", {}).pop(str(item_id), {})
    for blob_path in paths.values():
        delete_blob_by_path(blob_path, LOCAL_MODE, blob_service)