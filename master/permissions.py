from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.helpers import has_any_role


class EmployeePermission(BasePermission):
    read_roles = {"admin", "escritorio", "supervisor", "gl"}
    write_roles = {"admin", "escritorio"}

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return has_any_role(request.user, self.read_roles)

        return has_any_role(request.user, self.write_roles)
