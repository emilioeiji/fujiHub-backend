from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceStatusViewSet,
    EmployeeVisualCategoryViewSet,
    HikitsuguiItemViewSet,
    HikitsuguiOccurrenceCategoryViewSet,
    HikitsuguiReportViewSet,
    ProductionMachineStatusViewSet,
    ProductionMetricsViewSet,
    ProductionMonitorSourceViewSet,
    ProductionSnapshotViewSet,
    OperationsSettingsViewSet,
    OperationsMePermissionViewSet,
    OperationsAccessManagementViewSet,
    EmployeeAdministrativeNoteViewSet,
    AttendanceDashboardViewSet,
    MonthlyOperationCalendarViewSet,
    OperationalCodeViewSet,
    OperationalPositionViewSet,
    OperationCalendarTemplateViewSet,
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
router.register("calendar-templates", OperationCalendarTemplateViewSet, basename="operations-calendar-templates")
router.register("hikitsugui-categories", HikitsuguiOccurrenceCategoryViewSet, basename="operations-hikitsugui-categories")
router.register("hikitsugui-reports", HikitsuguiReportViewSet, basename="operations-hikitsugui-reports")
router.register("hikitsugui-items", HikitsuguiItemViewSet, basename="operations-hikitsugui-items")
router.register("production-monitor-sources", ProductionMonitorSourceViewSet, basename="operations-production-monitor-sources")
router.register("production-snapshots", ProductionSnapshotViewSet, basename="operations-production-snapshots")
router.register("production-machine-statuses", ProductionMachineStatusViewSet, basename="operations-production-machine-statuses")
router.register("production-metrics", ProductionMetricsViewSet, basename="operations-production-metrics")
router.register("attendance-dashboard", AttendanceDashboardViewSet, basename="operations-attendance-dashboard")
router.register("settings", OperationsSettingsViewSet, basename="operations-settings")
router.register("employee-admin-notes", EmployeeAdministrativeNoteViewSet, basename="operations-employee-admin-notes")
router.register("access-rbac", OperationsAccessManagementViewSet, basename="operations-access-rbac")

urlpatterns = [
    path("me/permissions/", OperationsMePermissionViewSet.as_view({"get": "list"}), name="operations-me-permissions"),
    path("", include(router.urls)),
]
