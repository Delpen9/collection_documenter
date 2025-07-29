import os
import io
import re
import json
import time
import string
import secrets
import streamlit as st
from login import login
from datetime import datetime, timedelta
from streamlit_js_eval import streamlit_js_eval
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

def retrieve_all_user_collections(user_email: str, blob_service: BlobServiceClient) -> list[str]:
    # get a ContainerClient
    container_client = blob_service.get_container_client(STATE_CONTAINER)
    # list only the blobs under your user’s “folder”
    blobs = container_client.list_blobs(name_starts_with=f"{user_email}/")
    # strip off the path and the “.json” suffix
    return [
        b.name.rsplit("/", 1)[-1].removesuffix(".json")
        for b in blobs
        if b.name.endswith(".json")
    ]

def create_new_collection(user_email: str, name: str):
    """
    Hook this up to your blob logic – e.g. upload an empty JSON
    at f"{user_email}/{name}.json" so it shows up in retrieve_all_user_collections.
    """
    container_client = blob_service.get_container_client(STATE_CONTAINER)
    blob_name = f"{user_email}/{name}.json"
    # write an empty JSON array (or whatever shape your app expects)
    container_client.upload_blob(blob_name, data="[]", overwrite=False)


def delete_collection(user_email: str, name: str):
    """
    Deletes the JSON blob for this collection.
    """
    container_client = blob_service.get_container_client(STATE_CONTAINER)
    blob_name = f"{user_email}/{name}.json"
    try:
        container_client.delete_blob(blob_name)
    except ResourceNotFoundError as e:
        # it’s already gone or never existed
        pass

def catalog(user_email):
    st.write("---")
    st.markdown(
        "<h3 style='text-align: center;'>Your Collection Catalog</h3>",
        unsafe_allow_html=True,
    )

    user_collection = retrieve_all_user_collections(user_email, blob_service)

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            width: 100% !important;
            height: 4rem !important;
            font-size: 2.5rem !important;
            text-align: left !important;
            padding-left: 1rem !important;
        }

        /* left-align all st.buttons (icon + label) */
        .stButton > button {
            display: flex !important;
            justify-content: flex-start !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for collection in user_collection:
        _, col_sel, _ = st.columns([1, 4, 1], gap="small")

        with col_sel:
            if st.button(collection, key=f"DO_NOT_PERSIST_sel-{collection}"):
                st.session_state.selected_collection = collection
                st.rerun()

    st.write("")

    st.markdown(
        "<h4 style='text-align: center;'>Manage</h4>",
        unsafe_allow_html=True,
    )

    @st.dialog("Confirm delete", width="small")
    def confirm_delete(user_email, collection):
        st.write(f"Delete collection **#{collection}**?")
        yes, _ = st.columns(2)
        with yes:
            if st.button("Yes, delete", key=f"DO_NOT_PERSIST_yes_delete_{collection}"):
                delete_collection(user_email, collection)
                st.rerun()

    _, col_sel, _ = st.columns([1, 4, 1], gap="small")

    with col_sel:
        delete_collection_text = st.text_input(
            label="🗑️ Delete a Collection",
            key=f"delete-txt-{collection}",
        )

        if delete_collection_text in user_collection:
            confirm_delete(user_email, delete_collection_text)
        elif delete_collection_text != "":
            st.warning("This collection does not exist.")

    # Centered input + add button
    _, mid, _ = st.columns([1, 4, 1])
    with mid:
        new_name = st.text_input("➕ Create a Collection", key="new_collection")

        if st.button("➕ Add Collection", key="add-new"):
            if new_name:
                create_new_collection(user_email, new_name)
                st.success(f"Created “{new_name}”")
                st.rerun()
            else:
                st.warning("Please enter a name before adding.")