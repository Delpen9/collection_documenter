import streamlit as st
from contextlib import contextmanager
from azure.core.exceptions import ResourceNotFoundError

def import_blob_libs():
    from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
    return BlobServiceClient, generate_blob_sas, BlobSasPermissions

# --- Configuration ---
BLOB_CONN_STR = st.secrets.blob_storage["BLOB_CONN_STR"]
STATE_CONTAINER = st.secrets.blob_storage["STATE_CONTAINER"]
IMAGE_CONTAINER  = st.secrets.blob_storage["IMAGE_CONTAINER"]
ACCOUNT_KEY = st.secrets.blob_storage["BLOB_ACCOUNT_KEY"]

# Initialize blob client if needed
BlobServiceClient, generate_blob_sas, BlobSasPermissions = import_blob_libs()
blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)

# --- Persistence Helpers ---
from persistence import *

def display_item_details(collection, item_id):
    title_key = "item_title"
    with st.expander(
        st.session_state[item_id][title_key],
        expanded=False
    ):
        st.info(f"Collection Name: {collection}")
        c1, c2, c3 = st.columns([1, 1, 1])

        # Front & back images
        for col, label in zip((c1, c2), ("front", "back")):
            blob_name = st.session_state[item_id].get(f"image_{label}", "")
            if blob_name:
                url = build_sas_url(blob_name, blob_service, hours=1)
                col.image(url, caption=label.title())

        # Notes in the third column
        notes = st.session_state[item_id].get("notes", "")
        if notes:
            c3.write("**Notes:**")
            c3.write(notes)

def item_view_across_collections(collections: list[str], user_email: str):
    for collection in collections:
        blob_name = f"{user_email}/{collection}.json"
        blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=blob_name)
        raw = blob.download_blob().readall()
        saved = json.loads(raw)

        flush_session_state()
        for k, v in saved.items():
            st.session_state[k] = v

        for item_id in st.session_state.Items:
            display_item_details(collection, item_id)

        # flushing the state here prevents another catalog item
        # from showing up, and setting 'selected_collection' to 'None'
        # prevents a catalog from showing at the bottom of the page
        flush_session_state()
        st.session_state.selected_collection = None