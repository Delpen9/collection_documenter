import streamlit as st
from collections import OrderedDict
from typing import Dict, List, Union
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

def format_accounting(value: float) -> str:
    if value < 0:
        return f"(${abs(value):,.2f})"

    return f"${value:,.2f}"

def sort_items_by_price(
    sorting_dict: Dict[str, List[Union[str, float]]],
    ascending: bool = True,
) -> List[str]:
    """
    Return list of item_ids sorted by price_estimate (index 1) ascending or descending.
    """
    return sorted(
        sorting_dict.keys(),
        key=lambda k: float(sorting_dict[k][1]) if sorting_dict[k][1] is not None else float("inf"),
        reverse=not ascending,
    )

def display_item_details(collection, item_id, tag_selections_for_item):
    price_estimate = st.session_state[item_id].get('price_estimate', '0.00')
    title_key = "item_title"
    with st.expander(
        label=f"**{st.session_state[item_id][title_key]}** ({format_accounting(float(price_estimate))})",
        expanded=False
    ):
        st.metric(label="Your Price Estimate", value=format_accounting(float(price_estimate)))

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

        def pills(tags, selected):
            selected_set = set(selected or [])
            # inject styling once
            st.markdown(
                """
                <style>
                .tag-pills span {
                    display: inline-block;
                    padding: 4px 10px;
                    border-radius: 999px;
                    font-size: 12px;
                    margin-right: 4px;
                    margin-bottom: 4px;
                    border: 1px solid #1a73e8;
                    font-weight: 500;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            html = (
                "<div class='tag-pills'>"
                + "".join(
                    f"<span style=\"background:{'#1a73e8' if t in selected_set else '#e8f0fe'};"
                    f"color:{'white' if t in selected_set else '#1a73e8'};"
                    f"\">{t}</span>"
                    for t in tags
                )
                + "</div>"
            )
            st.markdown(html, unsafe_allow_html=True)

        if tag_selections_for_item:
            st.write("---")
            # show all tags as unselected pills (or pass them as selected if you want them highlighted)
            pills(tag_selections_for_item, selected=[])
            st.write("")
            st.write("")

def item_view_across_collections(collections: list[str], user_email: str):
    sorting_option = st.selectbox("Sort by", options=[
        "No Sorting",
        "Estimated Item Value (Ascending)",
        "Estimated Item Value (Descending)"
    ])
    keyword_filter = st.text_input("Keyword filter", placeholder="Type & press Enter")

    if keyword_filter != "":
        st.info(f"Keyword filtering for '{keyword_filter}' is being applied.")

    # this O(n) routine gets all tag options to be displayed in the filter
    all_tags_list = []
    for collection in collections:
        blob_name = f"{user_email}/{collection}.json"
        blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=blob_name)
        raw = blob.download_blob().readall()
        saved = json.loads(raw)

        flush_session_state()
        for k, v in saved.items():
            st.session_state[k] = v

        main_tags_list = st.session_state.get("main_tags_list", [])
        all_tags_list += main_tags_list

    all_tags_list = list(set(all_tags_list))
    sel_tags = st.multiselect(
        "Filter by tags",
        options=all_tags_list,
        default=[],
    )

    st.write("---")

    total = 0
    shown = 0
    total_of_price_estimates = 0.00

    # this O(n) routine actually displays every item
    for collection in collections:
        if sorting_option == "No Sorting":
            st.info(f"Collection Name: {collection}")
            if st.button(f"Go to Collection: '{collection}'", key=f"go_to_collection_{collection}"):
                st.session_state.selected_collection = collection
                st.rerun()

        blob_name = f"{user_email}/{collection}.json"
        blob = blob_service.get_blob_client(container=STATE_CONTAINER, blob=blob_name)
        raw = blob.download_blob().readall()
        saved = json.loads(raw)

        flush_session_state()
        for k, v in saved.items():
            st.session_state[k] = v

        sorting_dict = {}
        for item_id in st.session_state.Items:
            total += 1
            tag_selections_for_item = st.session_state[item_id].get("tag_selections", [])
            item_title = st.session_state[item_id].get("item_title", "")
            price_estimate = float(st.session_state[item_id].get("price_estimate", "0.00"))

            # does this item pass the filters?
            tag_conditions = (not sel_tags) or set(tag_selections_for_item).intersection(sel_tags)
            title_conditions = keyword_filter.lower() in item_title.lower()
            if tag_conditions and title_conditions:
                shown += 1

                # if sorting is enabled, we want to skip rendering the item at 
                # this point in time
                if sorting_option == "No Sorting":
                    display_item_details(collection, item_id, tag_selections_for_item)

                total_of_price_estimates += price_estimate

                # if sorting is turned off, we want to create this
                # dictionary such that we can sort the items and have the
                # details we need to render the item
                if sorting_option != "No Sorting":
                    sorting_dict[item_id] = (collection, price_estimate)

    ##############################
    ## if sorting is being used
    ##############################
    sorted_items_list = None
    if sorting_option != "Estimated Item Value (Ascending)":
        sorted_items_list = sort_items_by_price(sorting_dict, ascending=True)

    elif sorting_option != "Estimated Item Value (Descending)":
        sorted_items_list = sort_items_by_price(sorting_dict, ascending=False)

    if sorted_items_list:
        for item_id in sorted_items_list:
            collection, _ = sorting_dict[item_id]
            tag_selections_for_item = st.session_state[item_id].get("tag_selections", [])
            display_item_details(collection, item_id, tag_selections_for_item)

    ##############################

    st.write("")

    formatted_total = format_accounting(total_of_price_estimates)

    st.metric(label="Total Estimate", value=formatted_total)

    hidden = total - shown
    st.write("---")
    st.info(f"{hidden} item{'s' if hidden!=1 else ''} hidden")

    # flushing the state here prevents another catalog item
    # from showing up, and setting 'selected_collection' to 'None'
    # prevents a catalog from showing at the bottom of the page
    flush_session_state()
    st.session_state.selected_collection = None