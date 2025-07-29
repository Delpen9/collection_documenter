import streamlit as st

from collection_viewer.collection import run_collection

from login import login

if __name__ == "__main__":
    collection_name = "My First Collection"
    DEBUG_MODE = True

    user_email = login()
    st.info(f"Welcome user {user_email}!")

    run_collection(collection_name=collection_name, user_email=user_email, DEBUG_MODE=DEBUG_MODE)