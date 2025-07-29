import streamlit as st

from collection_viewer.collection import run_collection
from collection_catalog.catalog import catalog

from login import login

if __name__ == "__main__":
    st.set_page_config(
        page_title="Collection Documenter",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    DEBUG_MODE = False

    user_email = login()

    # Make sure we have a place to stash our choice
    if "selected_collection" not in st.session_state:
        st.session_state.selected_collection = None

    if not st.session_state.selected_collection:
        st.info(f"Welcome user {user_email}!")
        catalog(user_email)

    if st.session_state.selected_collection:
        run_collection(collection_name=st.session_state.selected_collection, user_email=user_email, DEBUG_MODE=DEBUG_MODE)