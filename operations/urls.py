from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceStatusViewSet,
    MonthlyOperationCalendarViewSet,
    OperationalPositionViewSet,
    WorkTimeCodeViewSet,
)

app_name = "operations"

router = DefaultRouter()
router.register("positions", OperationalPositionViewSet, basename="operations-positions")
router.register("attendance-statuses", AttendanceStatusViewSet, basename="operations-attendance-statuses")
router.register("work-time-codes", WorkTimeCodeViewSet, basename="operations-work-time-codes")
router.register("calendars", MonthlyOperationCalendarViewSet, basename="operations-calendars")

urlpatterns = [
    path("", include(router.urls)),
]
