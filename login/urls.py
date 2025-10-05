# login/urls.py
from django.urls import path
from .views import LoginView, ping

urlpatterns = [
    path('api-token-auth/', LoginView.as_view(), name='api-token-auth'),
    path('ping/', ping, name='ping'),
]
