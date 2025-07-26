from django.shortcuts import redirect
from django.conf import settings
from django.http import JsonResponse
from authlib.integrations.django_client import OAuth
from django.http import HttpResponseServerError
from urllib.parse import urlencode

# Set up OAuth *once*, using settings
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

def login(request):
    # must exactly match your OAUTH_REDIRECT_URI
    return oauth.google.authorize_redirect(request, settings.OAUTH_REDIRECT_URI)

def auth_callback(request):
    token = oauth.google.authorize_access_token(request)
    # try to parse an ID token first
    userinfo = None
    if token and token.get("id_token"):
        userinfo = oauth.google.parse_id_token(request, token)

    # if that failed, call the /userinfo endpoint
    if not userinfo:
        resp = oauth.google.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            token=token,
        )
        if resp.status_code == 200:
            userinfo = resp.json()
        else:
            return HttpResponseServerError("🔥 Couldn't fetch user info from Google")

    # now it should be a dict
    request.session["user"] = {
        "email": userinfo["email"],
        "name":  userinfo.get("name"),
    }

    user = userinfo["email"]
    name = userinfo.get("name", "")
    params = urlencode({"django_auth":"1", "email": user, "name": name})
    return redirect(f"{settings.STREAMLIT_URL}/?{params}")

def me(request):
    return JsonResponse(request.session.get("user", {}))