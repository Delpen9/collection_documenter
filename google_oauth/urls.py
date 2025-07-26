# auth_landing/google_oauth/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login, name="login"),
    path("auth/callback/", views.auth_callback, name="auth_callback"),
    path("me/", views.me, name="me"),
]