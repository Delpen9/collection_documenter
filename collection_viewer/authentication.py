import os
import streamlit as st
from authlib.integrations.requests_client import OAuth2Session
from dotenv import load_dotenv

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as grequests

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI")
ALLOWED_EMAILS = {"iantdover@gmail.com"}

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
        code_challenge_method="S256",
        token_endpoint_auth_method="client_secret_post",
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

def get_current_url():
    base_url = "http://localhost:8502"  # Replace with your actual Streamlit app URL in production
    query_params = st.query_params

    if not query_params:
        return base_url

    query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
    return f"{base_url}?{query_string}"

def login():
    client = get_oauth_client()

    # If we already have a user in state, just return their email immediately
    if "user" in st.session_state:
        return st.session_state.user["email"]

    # 1) Exchange code for token once
    if "token" not in st.session_state and "code" in st.query_params:
        callback_url = get_current_url()
        st.session_state.token = client.fetch_token(
            "https://oauth2.googleapis.com/token",
            authorization_response=callback_url,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
        )
        st.query_params.clear()  # clean up URL

        # Verify identity token and enforce allowed list
        id_info = google_id_token.verify_oauth2_token(
            st.session_state.token["id_token"],
            grequests.Request(),
            CLIENT_ID,
        )
        email = id_info["email"]
        if email not in ALLOWED_EMAILS:
            st.error("Unauthorized")
            st.stop()
        st.session_state.user = {"email": email, "name": id_info.get("name")}
        # Now that we’ve stored them, return it
        return email

    # 2) Not logged in yet? Show the button and halt
    auth_url, state = client.create_authorization_url(
        "https://accounts.google.com/o/oauth2/v2/auth",
        redirect_uri=REDIRECT_URI,
        access_type="offline",
        prompt="consent",
    )
    st.session_state.oauth_state = state
    google_button(auth_url)
    st.stop()