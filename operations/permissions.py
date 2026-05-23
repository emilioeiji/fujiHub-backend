from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.helpers import has_any_role


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
