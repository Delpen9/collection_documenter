import os
import streamlit as st
from authlib.integrations.requests_client import OAuth2Session

from streamlit_js_eval import streamlit_js_eval

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as grequests

# Load from Streamlit secrets.toml
CLIENT_ID = st.secrets.google_oauth["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = st.secrets.google_oauth["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI  = st.secrets.google_oauth["OAUTH_REDIRECT_URI"]
ALLOWED_EMAILS = set(st.secrets.google_oauth["ALLOWED_EMAILS"])

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


def landing_page_decor(auth_url):
    # Page configuration
    st.set_page_config(
        page_title="Collectible Documenter",
        page_icon="🗂️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Inject custom CSS for styling + responsiveness
    st.markdown(
        """
        <style>
        /* Desktop styles */
        body {
            background-color: #121212;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 3rem;
        }
        .header h1 {
            font-size: 4rem;
            font-weight: 800;
            color: #FFDD57;
            text-shadow: 0 4px 6px rgba(0, 0, 0, 0.8);
            margin: 0;
            letter-spacing: 2px;
        }
        .subheader {
            text-align: center;
            font-size: 1.3rem;
            margin-top: 0.75rem;
            color: #CCCCCC;
        }
        .features {
            display: flex;
            justify-content: space-around;
            margin: 3rem 0;
            perspective: 1000px;
        }
        .feature {
            background: #1E1E1E;
            max-width: 300px;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 15px 25px rgba(0, 0, 0, 0.4);
            text-align: center;
            transform-style: preserve-3d;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .feature:hover {
            transform: translateY(-10px) rotateX(5deg);
            box-shadow: 0 25px 35px rgba(0, 0, 0, 0.5);
        }
        .feature h3 {
            margin-bottom: 1rem;
            color: #FFFFFF;
            font-size: 1.5rem;
        }
        .feature p {
            color: #AAAAAA;
            font-size: 1rem;
            line-height: 1.4;
        }
        .cta-button {
            display: block;
            margin: 2rem auto;
        }

        /* Mobile styles */
        @media only screen and (max-width: 768px) {
            .header {
                /* switch to text-align centering */
                text-align: center !important;
                width: 100% !important;
                margin: 2rem auto !important;
            }
            .header h1 {
                /* make it inline-block so auto margins work */
                display: inline-block !important;
                margin: 0 auto !important;
                font-size: 2.0rem !important;
                letter-spacing: 0.25px !important;
            }
            .subheader {
                font-size: 1rem !important;
                margin: 1rem 1rem;
            }
            .features {
                flex-direction: column !important;
                align-items: center;
                margin: 2rem 0;
            }
            .feature {
                max-width: 90% !important;
                padding: 1.5rem !important;
                margin-bottom: 1.5rem;
            }
            .feature h3 {
                font-size: 1.25rem !important;
            }
            .feature p {
                font-size: 0.9rem !important;
                line-height: 1.3;
            }
            .cta-button {
                margin: 1.5rem auto !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Grab the innerWidth from the browser
    screen_width = streamlit_js_eval(
        js_expressions="window.innerWidth", 
        key="SCREEN_WIDTH", 
        want_output=True
    )

    is_mobile = False
    if screen_width is not None:
        is_mobile = screen_width < 768

    if is_mobile:
        st.image("assets/login_banner.png", use_container_width=True)

    # Header section
    st.markdown(
        """
        <div class="header">
            <h1>Collectible Documenter</h1>
        </div>
        <div class="subheader">
            Organize, document, and preserve your collectibles with ease.
        </div>
        """,
        unsafe_allow_html=True
    )

    google_button(auth_url)

    # Features section
    st.markdown(
        """
        <div class="features">
            <div class="feature">
                <h3>📸 Upload Items</h3>
                <p>Add images, audio recordings, and notes for each collectible.</p>
            </div>
            <div class="feature">
                <h3>🔖 Tag & Categorize</h3>
                <p>Organize items with tags and metadata for easy search.</p>
            </div>
            <div class="feature">
                <h3>☁️ Cloud Storage</h3>
                <p>Securely store all your data in Azure Blob Storage.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not is_mobile:
        st.write("---")
        st.image("assets/login_banner.png", use_container_width=True)

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

    landing_page_decor(auth_url)

    st.stop()