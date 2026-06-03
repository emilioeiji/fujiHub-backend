from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.helpers import has_any_role
from .rbac import (
    get_user_operation_role_code,
    user_can_access_scope,
    user_can_edit_operations_settings,
    user_can_edit_schedule,
    user_can_view_admin_notes,
    user_can_view_schedule,
)


MASTER_DATA_WRITE_ROLES = {"admin", "escritorio"}
CALENDAR_WRITE_ROLES = {"admin", "escritorio", "supervisor", "gl"}


class OperationsMasterDataPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return has_any_role(request.user, MASTER_DATA_WRITE_ROLES)


class OperationsCalendarPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return has_any_role(request.user, CALENDAR_WRITE_ROLES)


class OperationsScopedPermission(BasePermission):
    read_roles = {
        "director",
        "vice_director",
        "hr",
        "senior_manager",
        "manager",
        "supervisor",
        "gl",
        "kl",
        "responsavel",
        "viewer",
    }
    write_roles = {"director", "vice_director", "senior_manager", "manager", "supervisor", "gl", "trainer_master"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        role_code = get_user_operation_role_code(user)
        if not role_code:
            return False

        if request.method in SAFE_METHODS:
            return role_code in self.read_roles

        return role_code in self.write_roles

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        if request.method in SAFE_METHODS:
            return user_can_view_schedule(user, obj)
        return user_can_edit_schedule(user, obj)


class OperationsSettingsPermission(BasePermission):
    READ_ALLOWED = {"director", "vice_director", "senior_manager", "manager", "responsavel", "hr"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        role_code = get_user_operation_role_code(user)
        if not role_code:
            return False

        if request.method in SAFE_METHODS:
            return role_code in self.READ_ALLOWED

        return user_can_edit_operations_settings(user)


class EmployeeAdminNotePermission(BasePermission):
    READ_ALLOWED = {"director", "vice_director", "senior_manager", "manager", "responsavel", "supervisor", "hr"}
    WRITE_ALLOWED = {"director", "vice_director", "hr", "manager"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        role_code = get_user_operation_role_code(user)
        if not role_code:
            return False

        if request.method in SAFE_METHODS:
            return role_code in self.READ_ALLOWED and user_can_view_admin_notes(user)

        return role_code in self.WRITE_ALLOWED


class AttendanceDashboardPermission(BasePermission):
    READ_ALLOWED = {
        "director",
        "vice_director",
        "hr",
        "senior_manager",
        "responsavel",
        "manager",
        "supervisor",
        "gl",
        "kl",
        "viewer",
        "dashboard_tv",
    }
    IMPORT_ALLOWED = {"director", "vice_director", "hr", "senior_manager", "manager", "supervisor"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        role_code = get_user_operation_role_code(user)
        if not role_code or role_code not in self.READ_ALLOWED:
            return False

        if request.method not in SAFE_METHODS:
            return getattr(view, "action", None) == "import_timecard" and role_code in self.IMPORT_ALLOWED

        # Dashboard TV cannot open sensitive individual details.
        if role_code == "dashboard_tv" and getattr(view, "action", None) in {"employee_detail", "employee-detail"}:
            return False

        return True


class ScheduleWritePermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return True

        calendar = None
        if hasattr(view, "get_object"):
            try:
                calendar = view.get_object()
            except Exception:
                calendar = None

        if calendar is None and "pk" in getattr(view, "kwargs", {}):
            return False

        if calendar is None:
            role_code = get_user_operation_role_code(user)
            if role_code not in {"director", "vice_director", "senior_manager", "manager", "supervisor", "gl", "trainer_master"}:
                return False

            department = request.data.get("department")
            process = request.data.get("process")
            shift = request.data.get("shift")
            return user_can_access_scope(user, department=department, process=process, shift=shift)

        return user_can_edit_schedule(user, calendar)


class HikitsuguiPermission(BasePermission):
    WRITE_ALLOWED = {"director", "vice_director", "kl", "gl", "supervisor", "manager", "senior_manager"}
    READ_ALLOWED = WRITE_ALLOWED | {"responsavel", "hr", "viewer"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        role_code = get_user_operation_role_code(user)
        if not role_code:
            return False

        if request.method in SAFE_METHODS:
            return role_code in self.READ_ALLOWED
        return role_code in self.WRITE_ALLOWED


class OperationsRBACManagementPermission(BasePermission):
    READ_ALLOWED = {"director", "vice_director", "hr", "manager", "supervisor"}
    WRITE_ALLOWED = {"director", "vice_director", "hr"}

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        role_code = get_user_operation_role_code(user)
        if not role_code:
            return False

        if request.method in SAFE_METHODS:
            return role_code in self.READ_ALLOWED

        return role_code in self.WRITE_ALLOWED
