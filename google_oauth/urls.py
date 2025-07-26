# auth_landing/google_oauth/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login, name="oauth_login"),
    path("logout/", views.logout, name="oauth_logout"),
    path("auth/callback/", views.auth_callback, name="oauth_callback"),
    path("me/", views.me, name="oauth_me"),
]