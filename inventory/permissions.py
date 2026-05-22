from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.helpers import has_any_role, has_role


ITEM_WRITE_ROLES = {"admin", "almoxarifado", "escritorio"}
REQUEST_CREATE_ROLES = {"admin", "escritorio", "supervisor", "gl", "kl"}
REQUEST_APPROVE_CANCEL_ROLES = {"admin", "escritorio", "supervisor"}
REQUEST_SEPARATE_DELIVER_ROLES = {"admin", "almoxarifado"}
STOCK_READ_ROLES = {"admin", "almoxarifado", "escritorio"}


class InventoryItemPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        if view.action in {"create", "update", "partial_update"}:
            return has_any_role(request.user, ITEM_WRITE_ROLES)

        return has_role(request.user, "admin")


class InventoryRequestPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        if view.action == "create":
            return has_any_role(request.user, REQUEST_CREATE_ROLES)

        if view.action in {"approve", "cancel"}:
            return has_any_role(request.user, REQUEST_APPROVE_CANCEL_ROLES)

        if view.action in {"separate", "deliver"}:
            return has_any_role(request.user, REQUEST_SEPARATE_DELIVER_ROLES)

        return has_role(request.user, "admin")


class InventoryStockReadPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.method in SAFE_METHODS and has_any_role(request.user, STOCK_READ_ROLES)
