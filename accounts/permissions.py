from rest_framework.permissions import BasePermission

from .helpers import has_any_role, has_role, user_department


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, "admin")


class HasAnyRole(BasePermission):
    allowed_roles = []

    def get_allowed_roles(self, view):
        return getattr(view, "allowed_roles", self.allowed_roles)

    def has_permission(self, request, view):
        return has_any_role(request.user, self.get_allowed_roles(view))


class IsSameDepartmentOrAdmin(BasePermission):
    department_attr = "department"

    def has_object_permission(self, request, view, obj):
        if has_role(request.user, "admin"):
            return True

        current_department = user_department(request.user)
        if current_department is None:
            return False

        department_attr = getattr(view, "department_attr", self.department_attr)
        object_department = getattr(obj, department_attr, None)

        if object_department is None and hasattr(obj, "profile"):
            object_department = getattr(obj.profile, department_attr, None)

        return object_department == current_department


class AccountManagementPermission(BasePermission):
    read_roles = {"admin", "escritorio", "supervisor"}
    write_roles = {"admin", "escritorio"}

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return has_any_role(request.user, self.read_roles)

        return has_any_role(request.user, self.write_roles)
