import streamlit as st
import io
import soundfile as sf
import librosa
from audiorecorder import audiorecorder
from authentication import login, show_streamlit_ui, hide_streamlit_ui

@st.cache_resource
def load_model():
    import whisper
    return whisper.load_model("base")

def setup_page():
    # Page config
    st.set_page_config(
        page_title="Collectible Documenter", 
        layout="wide", 
        initial_sidebar_state="expanded"
    )

    # Base CSS (hide menu/footer, base Item styling)
    st.markdown(
        """
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .stApp {padding: 2rem;}

            .banner-container {
                padding: 1rem 2rem;
                border-radius: 0.5rem;
                margin-bottom: 1.5rem;
                text-align: center;
                font-family: 'Segoe UI', sans-serif;
                border: 1px solid;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                transition: background-color 0.3s, color 0.3s, border-color 0.3s;
            }

            .Item-container {
                background: #f9f9f9;
                border-radius: 1rem;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                transition: background 0.3s, color 0.3s, box-shadow 0.3s;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Banner (media-query fallback for Auto mode)
    st.markdown(
        """
        <style>
        @media (prefers-color-scheme: light) {
            .banner-container {
                background-color: #f5f5f5;
                color: #333;
                border-color: #e0e0e0;
            }
        }
        @media (prefers-color-scheme: dark) {
            .banner-container {
                background-color: #1e1e1e;
                color: #f5f5f5;
                border-color: #444;
                box-shadow: 0 2px 8px rgba(255, 255, 255, 0.05);
            }
        }
        </style>

        <div class="banner-container">
            <h1 style="margin: 0; font-size: 2.2rem;">Collectible Documenter</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        .banner-container {
            background-color: #f5f5f5 !important;
            color: #333 !important;
            border-color: #e0e0e0 !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
        }
        .Item-container {
            background: #f9f9f9 !important;
            color: #000 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def tag_filter_widget(label, list_key, input_key, select_key):
    if list_key not in st.session_state:
        st.session_state[list_key] = []
    if input_key not in st.session_state:
        st.session_state[input_key] = ""

    def add_tag():
        new = st.session_state[input_key].strip()

        if new and new not in st.session_state[list_key]:
            st.session_state[list_key].append(new)

        st.session_state[input_key] = ""

    def remove_tag(tag):
        st.session_state[list_key].remove(tag)

    st.text_input(label, key=input_key, on_change=add_tag)
    for t in st.session_state[list_key]:
        if st.button(f"❌ {t}", key=f"{list_key}_del_{t}", on_click=remove_tag, args=(t,)):
            pass

    return st.session_state[list_key], st.multiselect(
        "Filter by tags",
        options=st.session_state[list_key],
        default=st.session_state[list_key],
        key=select_key
    )

def add_Item(idx: int):
    next_id = max(st.session_state.Items, default=-1) + 1
    st.session_state.Items.insert(idx + 1, next_id)

@st.dialog("Confirm delete", width="small")   # "large" is ~750 px
def confirm_delete(idx, cid):
    st.write(f"Delete item **#{cid}**?")
    yes, no = st.columns(2)
    with yes:
        if st.button("Yes, delete"):
            # remove card
            st.session_state.Items.pop(idx)
            # optional: clean up any related keys
            for k in list(st.session_state.keys()):
                if k.endswith(f"_{cid}"):
                    st.session_state.pop(k)
            st.rerun()          # closes the dialog + refreshes page
    with no:
        if st.button("Cancel"):
            st.rerun()          # just close the dialog
    
# Item renderer
def render_Item(
    idx: int,
    Item_id: int,
    allow_delete: bool,
    model: any = None,
    tag_options: list[str] = [], 
    selected_filters: list[str] = []
):
    tag_selection_key = f"tag_selection_{Item_id}"

    # initialize tag selection
    if tag_selection_key not in st.session_state:
        st.session_state[tag_selection_key] = []

    has_overlap = False
    if selected_filters:
        session_tags = st.session_state[tag_selection_key]
        has_overlap = bool(set(selected_filters) & set(session_tags))

    overlap_condition = (has_overlap or not selected_filters)
    with st.container():
        # Provide a default name
        default_name = f"Default Item Name"

        # Allow user to edit the name
        Item_name = st.text_input(f"", value=default_name, key=f"Item_name_{idx}", disabled=not overlap_condition)

        with st.expander("Details", expanded=overlap_condition):
            c1, c2, c3 = st.columns([1,1,1], gap="small")

            # Image Uploaders + Camera Capture
            for col, label in zip((c1, c2), ("Front", "Back")):
                with col:
                    st.markdown(f"**Upload {label} Image**")
                    tabs = st.tabs(["Upload", "Camera"])
                    with tabs[0]:
                        upload = st.file_uploader(
                            "", type=["png","jpg","jpeg"],
                            key=f"upload_{label.lower()}_{Item_id}",
                            disabled=not overlap_condition
                        )
                    with tabs[1]:
                        camera = st.camera_input(
                            f"Snap {label} Photo",
                            key=f"camera_{label.lower()}_{Item_id}",
                            disabled=not overlap_condition
                        )

                    image = upload or camera
                    if image:
                        st.image(image, caption=label, use_container_width=True)

                    # capture for return
                    if label == "Front":
                        front_image = image
                        st.session_state[f"front_{Item_id}"] = image
                    else:
                        back_image = image
                        st.session_state[f"back_{Item_id}"] = image

            # Audio recorder & transcription
            with c3:
                st.markdown("**Record & Transcribe**")

                if overlap_condition:
                    audio_data = audiorecorder(
                        start_prompt="",
                        stop_prompt="",
                        pause_prompt="",
                        show_visualizer=True,
                        key=f"audio_{Item_id}",
                    )

                    if audio_data:
                        st.audio(audio_data.export().read(), format="audio/wav", disabled=not overlap_condition)

                if st.button("📝 Transcribe", key=f"trans_{Item_id}", disabled=not overlap_condition):
                    if audio_data and len(audio_data) > 0:
                        buf = io.BytesIO(audio_data.export().read())

                        data, sr = sf.read(buf)

                        if data.ndim > 1:
                            data = data.mean(axis=1)

                        audio = data.astype("float32")

                        if sr != 16000:
                            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)

                        result = model.transcribe(audio, fp16=False)

                        st.session_state[f"transcript_{Item_id}"] = result["text"]
                    else:
                        st.warning("No audio recorded!")

                transcript = st.session_state.get(f"transcript_{Item_id}", "")
                note = st.text_area("Transcription", transcript, height=150, key=f"note_{Item_id}", disabled=not overlap_condition)

            st.write("---")

            selected_tags = st.multiselect(
                "Add Tags",
                options=tag_options,
                default=[],
                key=tag_selection_key,
                disabled=not overlap_condition
            )

            for tag in selected_tags:
                if st.button(tag, key=f"{tag_selection_key}_del_{tag}"):
                    pass
        
        # Can only add items when filters are not present
        if not selected_filters:
            if st.button("➕ Add Item Below", key=f"add_{Item_id}"):
                add_Item(idx)

        if allow_delete:
            if st.button("🗑️ Delete Item", key=f"del_{Item_id}"):
                confirm_delete(idx, Item_id)   # ← opens modal

    return front_image, back_image

def run_collection():
    hide_streamlit_ui() # converts to white background
    user_email = login()
    show_streamlit_ui() # converts to black background

    setup_page()

    st.subheader(f"Welcome {user_email} !!!")

    st.write("---")

    if "tags" not in st.session_state:
        st.session_state.tags = []

    all_options, selected_tags = tag_filter_widget(
        "Add tag", 
        list_key="main_tags_list", 
        input_key="main_tags_input", 
        select_key="main_tags_select"
    )

    all_options = list(all_options)

    # Initialise Items state
    if "Items" not in st.session_state:
        st.session_state.Items = [0]

    model = load_model()

    allow_delete = len(st.session_state.Items) > 1

    # Render items
    for i, cid in enumerate(st.session_state.Items):
        st.markdown("---")

        front_image = st.session_state.get(f"front_{cid}")
        back_image  = st.session_state.get(f"back_{cid}")

        if front_image or back_image:
            c1, c2 = st.columns([4, 1], gap="small")
            with c1:
                render_Item(
                    i, cid,
                    allow_delete=allow_delete,
                    model=model,
                    tag_options=all_options, selected_filters=selected_tags
                )

            with c2:
                if front_image:
                    st.image(front_image, caption="Front", use_container_width=True)

                if back_image:
                    st.image(back_image,  caption="Back",  use_container_width=True)
        else:
            render_Item(
                i, cid,
                allow_delete=allow_delete,
                model=model,
                tag_options=all_options, selected_filters=selected_tags
            )

if __name__ == "__main__":
    run_collection()
