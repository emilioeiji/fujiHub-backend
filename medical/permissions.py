from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.helpers import has_any_role, has_role


MASTER_DATA_WRITE_ROLES = {"admin", "escritorio", "saude"}
REQUEST_CREATE_ROLES = {"admin", "escritorio", "saude", "supervisor", "gl", "kl"}
REQUEST_WORKFLOW_ROLES = {"admin", "escritorio", "saude"}
EVENT_READ_ROLES = {"admin", "escritorio", "saude"}


class MedicalMasterDataPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        if view.action in {"create", "update", "partial_update"}:
            return has_any_role(request.user, MASTER_DATA_WRITE_ROLES)

        return has_role(request.user, "admin")


class MedicalRequestPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        if view.action == "create":
            return has_any_role(request.user, REQUEST_CREATE_ROLES)

        if view.action in {"triage", "start", "complete", "cancel"}:
            return has_any_role(request.user, REQUEST_WORKFLOW_ROLES)

        return has_role(request.user, "admin")


class MedicalEventPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.method in SAFE_METHODS and has_any_role(request.user, EVENT_READ_ROLES)
