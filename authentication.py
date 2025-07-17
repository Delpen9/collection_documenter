import os
import streamlit as st
from authlib.integrations.requests_client import OAuth2Session

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI")
ALLOWED_EMAILS = {"alice@example.com","bob@example.com"}

def hide_streamlit_ui():
    st.markdown("""
    <style>
      /* hide header & footer */
      #MainMenu, header, footer { visibility: hidden; }
      /* full-viewport white background */
      .appview-container { background: #fafafa; padding: 4rem; }
    </style>
    """, unsafe_allow_html=True)

def show_streamlit_ui():
    st.markdown("""
    <style>
      /* restore header & footer */
      #MainMenu, header, footer { visibility: visible; }
      /* reset any custom appview styles */
      .appview-container { background: unset; padding: unset; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def get_oauth_client():
    return OAuth2Session(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scope="openid email profile",
        redirect_uri=REDIRECT_URI,
    )

def google_button(auth_url):
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@500&display=swap');
    .google-btn {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #fff;
        color: #3c4043;
        border: 1px solid #dadce0;
        border-radius: 4px;
        font-family: 'Roboto', sans-serif;
        font-weight: 500;
        font-size: 14px;
        height: 40px;
        padding: 0 12px;
        text-decoration: none;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: background-color .15s, box-shadow .15s;
        cursor: pointer;
    }}
    .google-btn:hover {{
        background-color: #f7f8f8;
        box-shadow: 0 1px 3px rgba(60,64,67,.15);
    }}
    .google-btn:active {{
        box-shadow: 0 1px 2px rgba(60,64,67,.30);
    }}
    .google-icon {{
        width: 18px;
        height: 18px;
        margin-right: 8px;
    }}
    /* NEW: flex container to center anything inside it */
    .center-container {{
        display: flex !important;
        justify-content: center !important;
        margin: 2rem 0;  /* optional vertical spacing */
    }}
    </style>

    <div class="center-container">
    <a class="google-btn" href="{auth_url}">
        <img class="google-icon"
            src="https://developers.google.com/identity/images/g-logo.png"
            alt="Google logo" />
        Sign in with Google
    </a>
    </div>
    """, unsafe_allow_html=True)

def login():
    client = get_oauth_client()
    # 1) handle callback
    if "code" in st.query_params:
        token = client.fetch_token(
            "https://oauth2.googleapis.com/token",
            authorization_response=st.experimental_get_url(),
        )
        id_info = client.parse_id_token(token)
        email = id_info["email"]
        if email not in ALLOWED_EMAILS:
            st.error("Unauthorized")
            st.stop()
        st.session_state.user = {"email": email, "name": id_info["name"]}
        st.experimental_set_query_params()
        return

    # 2) show the pretty button if not logged in
    if "user" not in st.session_state:
        auth_url, _ = client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth"
        )

        google_button(auth_url)

        st.stop()