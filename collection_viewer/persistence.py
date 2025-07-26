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

# --- Configuration ---
BLOB_CONN_STR = os.getenv("BLOB_CONN_STR")
STATE_CONTAINER = os.getenv("STATE_CONTAINER", "session-state")
IMAGE_CONTAINER = os.getenv("IMAGE_CONTAINER", "user-images")
ACCOUNT_KEY = os.getenv("BLOB_ACCOUNT_KEY") or re.search(r"AccountKey=([^;]+)", BLOB_CONN_STR).group(1)

# Initialize blob client if needed
BlobServiceClient, generate_blob_sas, BlobSasPermissions = import_blob_libs()
blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)

################################
## READ FUNCTIONALITY
################################
def load_state(collection_name, user_email, blob_service):
    try:
        blob_name = f"{user_email}/{collection_name}.json"
        blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=blob_name)
        raw = blob.download_blob().readall()
        saved = json.loads(raw)
        for k, v in saved.items():
            st.session_state[k] = v

        # there is a weird race condition where
        # when items are deleted, their session_state value remains with {}
        # while no longer being in the "Items" list
        # this is a bandaid to fix that situation
        for key_val in st.session_state.keys():
            if key_val.startswith("item_id") and key_val not in st.session_state.Items:
                del st.session_state[key_val]

    except Exception:
        pass

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

################################
## CREATE AND UPDATE FUNCTIONALITY
################################
def save_state(collection_name, user_email, blob_service):
    # if a key has particular patterns in the name, it needs to be deleted directly
    # before save
    patterns = [
        "DO_NOT_PERSIST",
        "del_main_tags_list_",
        "new_tag_input",
        "sel_main_tags_list",
        "main_tags_list_to_delete",
    ]

    for k in list(st.session_state.keys()):  # list(...) so we can delete safely
        if any(pat in k for pat in patterns):
            del st.session_state[k]

    if "token" in st.session_state:
        del st.session_state["token"]

    # only persist keys we know are JSON-safe
    state_to_save = {
        k: st.session_state[k]
        for k in st.session_state
    }

    blob_name = f"{user_email}/{collection_name}.json"
    blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=blob_name)
    blob.upload_blob(json.dumps(state_to_save), overwrite=True)

def save_image(collection_name, user_email, item_id, label, img, blob_service):
    ext = img.type.split("/")[-1]
    blob_name = f"{user_email}/{collection_name}/{item_id}_{label}.{ext}"

    # for Azure upload, grab raw bytes (not a memoryview)
    content = img.read()                     # <-- use read()
    # if you ever need getbuffer, convert it:
    # content = bytes(img.getbuffer())

    container_client = blob_service.get_container_client(IMAGE_CONTAINER)
    container_client.upload_blob(
        name=blob_name,
        data=content,
        overwrite=True,
    )

    # reset buffer so any downstream code that inspects img still works
    img.seek(0)

    return blob_name

################################
## DELETE FUNCTIONALITY
################################
def delete_blob_by_path(blob_path, blob_service):
    try:
        blob_service.get_blob_client(IMAGE_CONTAINER, blob_path).delete_blob(delete_snapshots="include")
    except Exception:
        pass

def remove_image(collection_name, item_id, label, blob_service):
    # get the image path that we are trying to delete
    image_path = st.session_state[item_id].get(f"image_{label}", None)

    # we need to delete the url and blob path from the session_state
    # to prevent the image from coming back
    del st.session_state[item_id][f"image_{label}"]
    save_state(collection_name, st.session_state.user["email"], blob_service)

    # delete the image in azure blob storage
    delete_blob_by_path(image_path, blob_service)
    
    # this forces the changes to be reflected on the webpage
    # otherwise the image simply remains there until a page refresh
    st.rerun()

def delete_item_assets(item_id, blob_service):
    front_image_path = st.session_state[item_id].get("image_front", None)
    back_image_path = st.session_state[item_id].get("image_back", None)

    if front_image_path:
        delete_blob_by_path(front_image_path, blob_service)

    if back_image_path:
        delete_blob_by_path(back_image_path, blob_service)