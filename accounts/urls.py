from rest_framework.routers import DefaultRouter

from .views import RoleViewSet, UserProfileViewSet

app_name = "accounts"

router = DefaultRouter()
router.register("roles", RoleViewSet)
router.register("profiles", UserProfileViewSet)

urlpatterns = router.urls
