from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceStatusViewSet,
    EmployeeVisualCategoryViewSet,
    MonthlyOperationCalendarViewSet,
    OperationalCodeViewSet,
    OperationalPositionViewSet,
    RotationGroupStyleViewSet,
    WorkTimeCodeViewSet,
)

app_name = "operations"

router = DefaultRouter()
router.register("positions", OperationalPositionViewSet, basename="operations-positions")
router.register("attendance-statuses", AttendanceStatusViewSet, basename="operations-attendance-statuses")
router.register("work-time-codes", WorkTimeCodeViewSet, basename="operations-work-time-codes")
router.register("rotation-group-styles", RotationGroupStyleViewSet, basename="operations-rotation-group-styles")
router.register("visual-categories", EmployeeVisualCategoryViewSet, basename="operations-visual-categories")
router.register("operational-codes", OperationalCodeViewSet, basename="operations-operational-codes")
router.register("calendars", MonthlyOperationCalendarViewSet, basename="operations-calendars")

urlpatterns = [
    path("", include(router.urls)),
]
