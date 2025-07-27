import streamlit as st
from urllib.parse import unquote_plus

DJANGO_LOGIN_URL  = "http://localhost:8000/oauth/login/"
DJANGO_LOGOUT_URL = "http://localhost:8000/oauth/logout/"

def login():
    # 1) Wipe any stale query-params before reading them
    qp = st.query_params

    # 2) If we’ve just come back from Django, grab email+name
    if "django_auth" in qp and "user" not in st.session_state:
        email = qp.get("email", [""])
        name  = qp.get("name",  [""])
        if email:
            st.session_state.user = {
                "email": unquote_plus(email),
                "name":  unquote_plus(name),
            }

    # 3) If still not logged in, redirect *top* window to Django’s /oauth/login/
    if "user" not in st.session_state:
        st.components.v1.html(
            f"""
            <script>
              window.top.location.href = "{DJANGO_LOGIN_URL}";
            </script>
            """,
            height=0,
        )
        st.stop()

    return st.session_state.user["email"]


def logout_button():
    if st.button("🔒 Log out"):
        # 1) Clear all Streamlit state
        for k in list(st.session_state.keys()):
            del st.session_state[k]

        # 3) Redirect top window to Django’s logout endpoint
        st.components.v1.html(
            f"""
            <script>
              window.top.location.href = "{DJANGO_LOGOUT_URL}";
            </script>
            """,
            height=0,
        )
        st.stop()