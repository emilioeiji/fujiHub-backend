from __future__ import annotations

from typing import Optional

from .models import MonthlyOperationCalendar, UserOperationProfile
from accounts.helpers import get_user_role

GLOBAL_ROLE_CODES = {"director", "vice_director"}
READONLY_ROLE_CODES = {"viewer", "responsavel", "dashboard_tv"}
ADMIN_NOTES_ROLE_CODES = {"director", "vice_director", "hr", "manager", "senior_manager", "supervisor"}
OPERATIONS_SETTINGS_EDIT_ROLE_CODES = {"director", "vice_director", "hr"}
DASHBOARD_ONLY_ROLE_CODES = {"dashboard_tv"}
SCOPED_ROLE_CODES = {
    "kl",
    "gl",
    "supervisor",
    "manager",
    "senior_manager",
    "responsavel",
    "trainer_master",
}
SCHEDULE_READ_GLOBAL_CODES = {"director", "vice_director", "hr"}
SCHEDULE_WRITE_SCOPED_CODES = {"gl", "supervisor", "manager", "senior_manager", "trainer_master"}


def get_user_operation_profile(user) -> Optional[UserOperationProfile]:
    if not user or not getattr(user, "is_authenticated", False):
        return None

    if getattr(user, "is_superuser", False):
        return None

    try:
        profile = user.operation_profile
    except UserOperationProfile.DoesNotExist:
        return None

    if not profile.is_active or not profile.role_id or not profile.role.is_active:
        return None

    return profile


def user_has_role(user, role_code: str) -> bool:
    if not role_code:
        return False

    if user and getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False):
        return role_code in GLOBAL_ROLE_CODES or role_code == "director"

    profile = get_user_operation_profile(user)
    return bool(profile and profile.role.code == role_code)


def _user_role_code(user) -> Optional[str]:
    profile = get_user_operation_profile(user)
    if profile:
        return profile.role.code

    if user and getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False):
        return "director"

    legacy_role = get_user_role(user)
    if not legacy_role:
        return None
    legacy_map = {
        "admin": "director",
        "escritorio": "hr",
        "supervisor": "supervisor",
        "gl": "gl",
        "consulta": "viewer",
    }
    return legacy_map.get(legacy_role.code)


def get_user_operation_role_code(user) -> Optional[str]:
    return _user_role_code(user)


def user_can_access_scope(user, department=None, process=None, shift=None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    role_code = _user_role_code(user)
    if not role_code:
        return False

    profile = get_user_operation_profile(user)
    if not profile:
        # Legacy users (accounts role) keep broad access in this transitional phase.
        return role_code in {"director", "vice_director", "hr", "supervisor", "gl", "manager", "senior_manager", "viewer"}

    role_code = profile.role.code
    if role_code in GLOBAL_ROLE_CODES or profile.role.is_global_scope:
        return True

    if role_code == "dashboard_tv":
        # dashboard_tv can read only within explicit scope definitions
        pass

    if role_code not in SCOPED_ROLE_CODES and role_code not in {"hr", "viewer", "dashboard_tv"}:
        return False

    scopes = profile.scopes.filter(is_active=True).select_related("role", "department", "process", "shift")
    if not scopes.exists():
        return False

    for scope in scopes:
        if scope.role_id and scope.role.code != role_code:
            continue

        if department is not None and scope.department_id is not None and scope.department_id != getattr(department, "id", department):
            continue
        if process is not None and scope.process_id is not None and scope.process_id != getattr(process, "id", process):
            continue
        if shift is not None and scope.shift_id is not None and scope.shift_id != getattr(shift, "id", shift):
            continue

        return True

    return False


def user_can_edit_schedule(user, calendar: MonthlyOperationCalendar | None) -> bool:
    role_code = _user_role_code(user)
    if not role_code:
        return False

    if role_code in GLOBAL_ROLE_CODES:
        return True

    if role_code in READONLY_ROLE_CODES or role_code == "hr" or role_code == "kl":
        return False

    if role_code in DASHBOARD_ONLY_ROLE_CODES:
        return False

    if calendar is None:
        return role_code in (SCOPED_ROLE_CODES | SCHEDULE_WRITE_SCOPED_CODES)

    return user_can_access_scope(
        user,
        department=calendar.department_id,
        process=calendar.process_id,
        shift=calendar.shift_id,
    )


def user_can_view_schedule(user, calendar: MonthlyOperationCalendar | None) -> bool:
    role_code = _user_role_code(user)
    if not role_code:
        return False

    if role_code in GLOBAL_ROLE_CODES or role_code in SCHEDULE_READ_GLOBAL_CODES:
        return True

    if role_code in {"dashboard_tv"}:
        return False

    if calendar is None:
        return role_code in (SCOPED_ROLE_CODES | {"viewer", "kl", "gl", "supervisor", "manager", "senior_manager", "responsavel"})

    return user_can_access_scope(
        user,
        department=calendar.department_id,
        process=calendar.process_id,
        shift=calendar.shift_id,
    )


def get_user_operation_scopes(user):
    profile = get_user_operation_profile(user)
    if not profile:
        return []
    scopes = (
        profile.scopes.filter(is_active=True)
        .select_related("department", "process", "shift", "role")
        .order_by("department_id", "process_id", "shift_id", "line", "area", "id")
    )
    return [
        {
            "id": scope.id,
            "role": scope.role.code if scope.role_id else profile.role.code,
            "department": scope.department_id,
            "department_code": getattr(scope.department, "code", None),
            "process": scope.process_id,
            "process_code": getattr(scope.process, "code", None),
            "shift": scope.shift_id,
            "shift_code": getattr(scope.shift, "code", None),
            "line": scope.line or "",
            "area": scope.area or "",
        }
        for scope in scopes
    ]


def get_user_operation_permissions_payload(user):
    role_code = get_user_operation_role_code(user)
    is_superuser = bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False))
    scopes = get_user_operation_scopes(user)
    has_scope = bool(scopes)

    can_view_schedule = is_superuser or role_code in {
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
    if role_code in {"dashboard_tv"}:
        can_view_schedule = False

    can_edit_schedule = is_superuser or role_code in {"director", "vice_director", "senior_manager", "manager", "supervisor", "gl", "trainer_master"}
    if role_code in {"kl", "viewer", "dashboard_tv", "responsavel", "hr"}:
        can_edit_schedule = False

    can_import_employees = bool(can_edit_schedule)
    can_sync_assignments = bool(can_edit_schedule)
    can_manage_templates = bool(can_edit_schedule)
    can_view_hikitsugui = is_superuser or role_code in {
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
    can_edit_hikitsugui = is_superuser or role_code in {"director", "vice_director", "senior_manager", "manager", "supervisor", "gl", "kl"}

    can_view_attendance_dashboard = is_superuser or role_code in {
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
        "dashboard_tv",
    }
    can_view_employee_detail = can_view_attendance_dashboard and role_code != "dashboard_tv"
    can_view_admin_notes = user_can_view_admin_notes(user)
    can_create_admin_notes = is_superuser or role_code in {"director", "vice_director", "hr", "manager"}
    can_edit_operations_settings = user_can_edit_operations_settings(user)
    can_export_attendance = can_view_employee_detail
    can_view_dashboard_tv = is_superuser or role_code == "dashboard_tv"

    # For scoped roles, keep flags conservative when there is no scope.
    if role_code in SCOPED_ROLE_CODES.union({"viewer", "dashboard_tv"}) and not has_scope and not is_superuser:
        can_view_schedule = False
        can_edit_schedule = False
        can_import_employees = False
        can_sync_assignments = False
        can_manage_templates = False
        can_view_hikitsugui = False
        can_edit_hikitsugui = False
        can_view_attendance_dashboard = role_code == "dashboard_tv"
        can_view_employee_detail = False

    can_view_rbac = is_superuser or role_code in {"director", "vice_director", "hr", "manager", "supervisor"}
    can_edit_rbac = is_superuser or role_code in {"director", "vice_director", "hr"}

    roles = []
    profile = get_user_operation_profile(user)
    if profile and profile.role_id:
        roles.append(profile.role.code)
        roles.extend(profile.additional_roles.filter(is_active=True).values_list("code", flat=True))
    elif role_code:
        roles.append(role_code)

    return {
        "is_superuser": is_superuser,
        "role": role_code,
        "roles": sorted(set([r for r in roles if r])),
        "scopes": scopes,
        "flags": {
            "can_view_schedule": bool(can_view_schedule),
            "can_edit_schedule": bool(can_edit_schedule),
            "can_import_employees": bool(can_import_employees),
            "can_sync_assignments": bool(can_sync_assignments),
            "can_manage_templates": bool(can_manage_templates),
            "can_view_hikitsugui": bool(can_view_hikitsugui),
            "can_edit_hikitsugui": bool(can_edit_hikitsugui),
            "can_view_attendance_dashboard": bool(can_view_attendance_dashboard),
            "can_view_employee_detail": bool(can_view_employee_detail),
            "can_view_admin_notes": bool(can_view_admin_notes),
            "can_create_admin_notes": bool(can_create_admin_notes),
            "can_edit_operations_settings": bool(can_edit_operations_settings),
            "can_export_attendance": bool(can_export_attendance),
            "can_view_dashboard_tv": bool(can_view_dashboard_tv),
            "can_view_rbac": bool(can_view_rbac),
            "can_edit_rbac": bool(can_edit_rbac),
        },
    }


def user_can_view_admin_notes(user) -> bool:
    role_code = _user_role_code(user)
    if not role_code:
        return False

    if role_code in GLOBAL_ROLE_CODES:
        return True

    return role_code in ADMIN_NOTES_ROLE_CODES


def user_can_edit_operations_settings(user) -> bool:
    role_code = _user_role_code(user)
    if not role_code:
        return False

    if role_code in GLOBAL_ROLE_CODES:
        return True

    return role_code in OPERATIONS_SETTINGS_EDIT_ROLE_CODES
