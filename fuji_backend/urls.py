# fuji_backend/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from pathlib import Path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # API
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path("api/", include("users.urls")),

    # SPA index.html
    path("", TemplateView.as_view(template_name="index.html")),
]

# Serve os assets do Vite em modo DEBUG
if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=Path(settings.BASE_DIR).parent / "web" / "dist" / "assets"
    )

# Fallback para SPA: qualquer rota não reconhecida → index.html
urlpatterns += [
    re_path(r"^(?!api/|admin/|static/).*$", TemplateView.as_view(template_name="index.html")),
]
