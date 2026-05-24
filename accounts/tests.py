from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from master.models import Department

from .helpers import get_user_role, has_any_role, has_role, user_department
from .models import Role, UserProfile
from .permissions import (
    AccountManagementPermission,
    HasAnyRole,
    IsAdminRole,
    IsSameDepartmentOrAdmin,
)


class AccountHelperTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="helper-user",
            password="password",
        )
        self.role = Role.objects.get(code="supervisor")
        self.department = Department.objects.create(
            code="D1",
            label_pt="Departamento 1",
            label_jp="部署 1",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role=self.role,
            department=self.department,
        )

    def test_get_user_role_returns_active_role(self):
        self.assertEqual(get_user_role(self.user), self.role)

    def test_has_role_and_has_any_role(self):
        self.assertTrue(has_role(self.user, "supervisor"))
        self.assertTrue(has_any_role(self.user, ["admin", "supervisor"]))
        self.assertFalse(has_role(self.user, "admin"))

    def test_user_department_returns_profile_department(self):
        self.assertEqual(user_department(self.user), self.department)

    def test_inactive_profile_has_no_role_or_department(self):
        self.profile.is_active = False
        self.profile.save()

        self.assertIsNone(get_user_role(self.user))
        self.assertIsNone(user_department(self.user))

    def test_superuser_without_profile_is_treated_as_admin_role(self):
        superuser = get_user_model().objects.create_superuser(
            username="root-admin",
            password="password",
        )

        self.assertEqual(get_user_role(superuser).code, "admin")
        self.assertTrue(has_role(superuser, "admin"))
        self.assertTrue(has_any_role(superuser, ["saude", "admin"]))
        self.assertFalse(has_role(superuser, "supervisor"))


class AccountPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin_role = Role.objects.get(code="admin")
        self.supervisor_role = Role.objects.get(code="supervisor")
        self.escritorio_role = Role.objects.get(code="escritorio")
        self.consulta_role = Role.objects.get(code="consulta")
        self.department = Department.objects.create(
            code="D2",
            label_pt="Departamento 2",
            label_jp="部署 2",
        )

        User = get_user_model()
        self.admin = User.objects.create_user(username="admin-user", password="password")
        self.supervisor = User.objects.create_user(
            username="supervisor-user",
            password="password",
        )
        self.escritorio = User.objects.create_user(username="escritorio-user", password="password")
        self.consulta = User.objects.create_user(username="consulta-user", password="password")
        UserProfile.objects.create(user=self.admin, role=self.admin_role)
        UserProfile.objects.create(
            user=self.supervisor,
            role=self.supervisor_role,
            department=self.department,
        )
        UserProfile.objects.create(user=self.escritorio, role=self.escritorio_role)
        UserProfile.objects.create(user=self.consulta, role=self.consulta_role)

    def authenticated_request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def authenticated_request_with_method(self, user, method):
        request = getattr(self.factory, method.lower())("/")
        request.user = user
        return request

    def test_is_admin_role_permission(self):
        permission = IsAdminRole()

        self.assertTrue(permission.has_permission(self.authenticated_request(self.admin), None))
        self.assertFalse(
            permission.has_permission(self.authenticated_request(self.supervisor), None)
        )

    def test_has_any_role_uses_view_allowed_roles(self):
        permission = HasAnyRole()
        view = SimpleNamespace(allowed_roles=["supervisor", "rh"])

        self.assertTrue(
            permission.has_permission(self.authenticated_request(self.supervisor), view)
        )
        self.assertFalse(permission.has_permission(self.authenticated_request(self.admin), view))

    def test_same_department_or_admin_object_permission(self):
        permission = IsSameDepartmentOrAdmin()
        same_department_object = SimpleNamespace(department=self.department)
        other_department = Department.objects.create(
            code="D3",
            label_pt="Departamento 3",
            label_jp="部署 3",
        )
        other_department_object = SimpleNamespace(department=other_department)

        self.assertTrue(
            permission.has_object_permission(
                self.authenticated_request(self.supervisor),
                None,
                same_department_object,
            )
        )
        self.assertFalse(
            permission.has_object_permission(
                self.authenticated_request(self.supervisor),
                None,
                other_department_object,
            )
        )
        self.assertTrue(
            permission.has_object_permission(
                self.authenticated_request(self.admin),
                None,
                other_department_object,
            )
        )

    def test_account_management_permission_read(self):
        permission = AccountManagementPermission()
        view = SimpleNamespace()

        self.assertTrue(
            permission.has_permission(
                self.authenticated_request_with_method(self.admin, "get"),
                view,
            )
        )
        self.assertTrue(
            permission.has_permission(
                self.authenticated_request_with_method(self.escritorio, "get"),
                view,
            )
        )
        self.assertTrue(
            permission.has_permission(
                self.authenticated_request_with_method(self.supervisor, "get"),
                view,
            )
        )
        self.assertFalse(
            permission.has_permission(
                self.authenticated_request_with_method(self.consulta, "get"),
                view,
            )
        )

    def test_account_management_permission_write(self):
        permission = AccountManagementPermission()
        view = SimpleNamespace()

        self.assertTrue(
            permission.has_permission(
                self.authenticated_request_with_method(self.admin, "patch"),
                view,
            )
        )
        self.assertTrue(
            permission.has_permission(
                self.authenticated_request_with_method(self.escritorio, "patch"),
                view,
            )
        )
        self.assertFalse(
            permission.has_permission(
                self.authenticated_request_with_method(self.supervisor, "patch"),
                view,
            )
        )
