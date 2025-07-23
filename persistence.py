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
PERSIST_KEYS = {"main_tags_list", "main_tags_select", "Items", "_image_paths"}

# Initialize blob client if needed
if not LOCAL_MODE:
    BlobServiceClient, generate_blob_sas, BlobSasPermissions = import_blob_libs()
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
else:
    blob_service = None
    
def save_state(user_email, PERSIST_KEYS, LOCAL_MODE, blob_service):
    if LOCAL_MODE:
        return
    state = {k: st.session_state[k] for k in PERSIST_KEYS if k in st.session_state}
    blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=f"{user_email}.json")
    blob.upload_blob(json.dumps(state), overwrite=True)

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

def save_image(user_email, item_id, label, image_data, LOCAL_MODE, blob_service):
    if LOCAL_MODE or blob_service is None:
        return image_data

    img_bytes = image_data.read() if hasattr(image_data, "read") else image_data
    blob_path = f"{user_email}/{item_id}_{label}.png"
    blob_cli = blob_service.get_blob_client(container=IMAGE_CONTAINER, blob=blob_path)
    blob_cli.upload_blob(img_bytes, overwrite=True)

    # remember the path so we can rebuild a SAS later
    st.session_state.setdefault("_image_paths", {}).setdefault(str(item_id), {})[label] = blob_path
    return build_sas_url(blob_path, blob_service, LOCAL_MODE)

def build_sas_url(blob_path, blob_service, hours=1):
    sas = generate_blob_sas(
        account_name=blob_service.account_name,
        container_name=IMAGE_CONTAINER,
        blob_name=blob_path,
        account_key=ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=hours),
    )
    return f"https://{blob_service.account_name}.blob.core.windows.net/{IMAGE_CONTAINER}/{blob_path}?{sas}"

def rehydrate_image_urls(LOCAL_MODE, blob_service):
    if LOCAL_MODE or blob_service is None:
        return
    for cid, labels in st.session_state.get("_image_paths", {}).items():
        for label, blob_path in labels.items():
            st.session_state[f"{label}_{cid}"] = build_sas_url(blob_path, blob_service, LOCAL_MODE)

def delete_blob_by_path(blob_path, LOCAL_MODE, blob_service):
    if LOCAL_MODE or blob_service is None:
        return
    try:
        blob_service.get_blob_client(IMAGE_CONTAINER, blob_path).delete_blob(delete_snapshots="include")
    except Exception:
        pass

def remove_image(cid, label, LOCAL_MODE, blob_service):
    paths = st.session_state.get("_image_paths", {}).get(str(cid), {})
    blob_path = paths.pop(label, None)
    if not blob_path and st.session_state.get(f"{label}_{cid}"):
        url = st.session_state[f"{label}_{cid}"]
        # fallback if you only have a SAS url
        blob_path = url.split(f"{IMAGE_CONTAINER}/", 1)[-1].split("?", 1)[0]
    if blob_path:
        delete_blob_by_path(blob_path, LOCAL_MODE, blob_service)
    for k in (f"{label}_{cid}", f"upload_{label}_{cid}", f"camera_{label}_{cid}"):
        st.session_state.pop(k, None)
    st.rerun()

def delete_item_assets(cid, LOCAL_MODE, blob_service):
    paths = st.session_state.get("_image_paths", {}).pop(str(cid), {})
    for blob_path in paths.values():
        delete_blob_by_path(blob_path, LOCAL_MODE, blob_service)