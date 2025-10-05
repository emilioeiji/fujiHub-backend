# core/urls.py
from django.urls import re_path
from .views import HomeView

urlpatterns = [
    re_path(r"^.*$", HomeView.as_view(), name="home"),  # sempre por último
]
