from urllib.parse import unquote_plus
import streamlit as st
import os

from dotenv import load_dotenv

load_dotenv()  # if you’re using a .env file

DJANGO_LOGOUT_URL = os.getenv(
    "DJANGO_LOGOUT_URL",
    "http://localhost:8000/oauth/logout/"
)

def login():
    qp = st.query_params

    # 1) If we see the callback params, bootstrap session_state.user
    if "django_auth" in qp and "user" not in st.session_state:
        email = qp.get("email", [""])
        name = qp.get("name",  [""])
        if email:
            # decode in case of URL-encoding
            st.session_state.user = {
                "email": unquote_plus(email),
                "name":  unquote_plus(name),
            }

    # 2) If still not logged in, send them to Django’s login
    if "user" not in st.session_state:
        js = """
        <script>
          window.location.href = "http://localhost:8000/oauth/login/";
        </script>
        """
        st.components.v1.html(js, heisght=0)
        st.stop()

    return st.session_state.user["email"]

def logout_button():
    if st.button("🔒 Log out"):
        # 1) Clear Streamlit’s session_state
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        # 2) Redirect browser to Django’s logout
        js = f"""
        <script>
          window.location.href = "{DJANGO_LOGOUT_URL}";
        </script>
        """
        st.components.v1.html(js, height=0)
        st.stop()