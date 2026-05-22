from rest_framework.routers import DefaultRouter

from .views import (
    StockMovementViewSet,
    UniformCategoryViewSet,
    UniformItemViewSet,
    UniformRequestEventViewSet,
    UniformRequestViewSet,
)

app_name = "inventory"

router = DefaultRouter()
router.register("categories", UniformCategoryViewSet, basename="inventory-categories")
router.register("items", UniformItemViewSet, basename="inventory-items")
router.register("requests", UniformRequestViewSet, basename="inventory-requests")
router.register("movements", StockMovementViewSet, basename="inventory-movements")
router.register("events", UniformRequestEventViewSet, basename="inventory-events")

urlpatterns = router.urls
