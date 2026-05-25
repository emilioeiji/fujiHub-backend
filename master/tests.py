from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from .models import (
    BillingRate,
    BuildingFloor,
    Department,
    Employee,
    EntryType,
    Gender,
    HireType,
    Nationality,
    Process,
    Rejoined,
    Shift,
)


# Contract coverage for current API endpoints used by web/mobile:
# /api/employees/
# /api/employees/{employee_id}/
# /api/employees/housing/
# /api/genders/
# /api/shifts/
# /api/nationalities/
# /api/departments/
# /api/billingrates/
# /api/processes/
# /api/entrytypes/
# /api/hiretypes/
# /api/buildingfloors/
# /api/rejoined/
class MasterApiContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.read_role, _ = Role.objects.get_or_create(
            code="supervisor",
            defaults={"name": "Supervisor"},
        )
        self.write_role, _ = Role.objects.get_or_create(
            code="escritorio",
            defaults={"name": "Escritorio"},
        )
        self.admin_role, _ = Role.objects.get_or_create(
            code="admin",
            defaults={"name": "Admin"},
        )
        self.supervisor_user = user_model.objects.create_user(username="supervisor", password="x")
        self.escritorio_user = user_model.objects.create_user(username="escritorio", password="x")
        self.no_role_user = user_model.objects.create_user(username="norole", password="x")
        UserProfile.objects.create(user=self.supervisor_user, role=self.read_role)
        UserProfile.objects.create(user=self.escritorio_user, role=self.write_role)
        self.client.force_authenticate(self.escritorio_user)
        self.gender = Gender.objects.create(code="M", label_pt="Masculino", label_jp="男性")
        self.shift = Shift.objects.create(code="D", label_pt="Dia", label_jp="日勤")
        self.nationality = Nationality.objects.create(
            code="BR",
            name_pt="Brasil",
            name_jp="ブラジル",
        )
        self.department = Department.objects.create(
            code="DEP",
            label_pt="Departamento",
            label_jp="部署",
        )
        self.billing_rate = BillingRate.objects.create(
            code="BR1",
            label_pt="Tabela 1",
            label_jp="単価 1",
        )
        self.process = Process.objects.create(
            code="PROC",
            label_pt="Processo",
            label_jp="工程",
        )
        self.entry_type = EntryType.objects.create(
            code="NEW",
            label_pt="Novo",
            label_jp="新規",
        )
        self.hire_type = HireType.objects.create(
            code="FT",
            label_pt="Integral",
            label_jp="フルタイム",
        )
        self.building_floor = BuildingFloor.objects.create(
            code="E2F4",
            label_pt="E2 4F",
            label_jp="E2 4階",
        )
        self.rejoined = Rejoined.objects.create(
            code="N",
            label_pt="Nao",
            label_jp="いいえ",
        )
        self.employee = Employee.objects.create(
            employee_id="EMP001",
            employee_cd="CD001",
            name_jp="山田太郎",
            name_en="Taro Yamada",
            name_kana="ヤマダタロウ",
            internal_name="Taro",
            name_cd="NM001",
            gender=self.gender,
            shift=self.shift,
            nationality=self.nationality,
            billing_rate=self.billing_rate,
            rejoined=self.rejoined,
            process=self.process,
            building_floor=self.building_floor,
            department=self.department,
            entry_type=self.entry_type,
            hire_type=self.hire_type,
            joined_imc="2024-01-01",
            joined_fa="2024-01-02",
            new_joined="2024-01-03",
            dispatch_start="2024-01-04",
            birth_date="1990-01-01",
            end_work="2024-12-31",
            retired="2025-01-01",
            hourly_rate=1200,
            total_hourly=1300,
            months_worked=12,
            years_elapsed=1,
            months_elapsed=0,
            elapsed_str="1年0ヶ月",
            active_end_month=True,
            operational_category="normal",
            work_pattern="4x2",
            shift_type="day",
            rotation_group="A",
            manager_flag=False,
            view_flag=True,
        )

    def assert_list_contract(self, url, expected_fields):
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertTrue(expected_fields.issubset(response.data[0].keys()))

    def assert_paginated_results(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        return response.data["results"]

    def test_reference_endpoints_list_contracts_are_authenticated(self):
        endpoints = [
            ("/api/genders/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/shifts/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/nationalities/", {"id", "code", "name_pt", "name_jp"}),
            ("/api/departments/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/billingrates/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/processes/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/entrytypes/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/hiretypes/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/buildingfloors/", {"id", "code", "label_pt", "label_jp"}),
            ("/api/rejoined/", {"id", "code", "label_pt", "label_jp"}),
        ]

        for url, fields in endpoints:
            with self.subTest(url=url):
                self.assert_list_contract(url, fields)

    def test_reference_endpoint_detail_contract(self):
        response = self.client.get(f"/api/departments/{self.department.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.department.id)
        self.assertEqual(response.data["code"], "DEP")
        self.assertIn("label_pt", response.data)
        self.assertIn("label_jp", response.data)

    def test_employee_list_contract_is_role_based(self):
        response = self.client.get("/api/employees/")

        results = self.assert_paginated_results(response)
        self.assertEqual(results[0]["employee_id"], "EMP001")
        self.assertTrue(
            {
                "employee_id",
                "employee_cd",
                "name_jp",
                "name_en",
                "name_kana",
                "internal_name",
                "department",
                "process",
                "shift",
                "building_floor",
                "hire_type",
                "entry_type",
                "active_end_month",
                "operational_category",
                "work_pattern",
                "shift_type",
                "rotation_group",
                "five_two_off_days",
                "manager_flag",
                "view_flag",
            }.issubset(results[0].keys())
        )

    def test_employee_detail_contract_uses_employee_id_lookup(self):
        response = self.client.get("/api/employees/EMP001/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["employee_id"], "EMP001")
        self.assertEqual(response.data["name_en"], "Taro Yamada")
        self.assertEqual(response.data["department"], self.department.id)
        self.assertEqual(response.data["process"], self.process.id)
        self.assertEqual(response.data["shift"], self.shift.id)
        self.assertEqual(response.data["building_floor"], self.building_floor.id)
        self.assertIn("department_detail", response.data)

    def test_employee_create_contract_accepts_current_payload_shape(self):
        payload = {
            "employee_id": "EMP002",
            "employee_cd": "CD002",
            "name_jp": "佐藤花子",
            "name_en": "Hanako Sato",
            "name_kana": "サトウハナコ",
            "internal_name": "Hanako",
            "name_cd": "NM002",
            "gender": self.gender.id,
            "shift": self.shift.id,
            "nationality": self.nationality.id,
            "billing_rate": self.billing_rate.id,
            "rejoined": self.rejoined.id,
            "process": self.process.id,
            "building_floor": self.building_floor.id,
            "department": self.department.id,
            "entry_type": self.entry_type.id,
            "hire_type": self.hire_type.id,
            "joined_imc": None,
            "joined_fa": None,
            "new_joined": None,
            "dispatch_start": None,
            "birth_date": None,
            "end_work": None,
            "retired": None,
            "active_end_month": True,
            "operational_category": "trainer",
            "work_pattern": "5x2",
            "shift_type": "day",
            "rotation_group": "B",
            "five_two_off_days": [6, 0],
            "manager_flag": False,
            "view_flag": True,
        }

        response = self.client.post("/api/employees/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["employee_id"], "EMP002")
        self.assertEqual(response.data["department"], self.department.id)
        self.assertEqual(response.data["work_pattern"], "5x2")
        self.assertTrue(Employee.objects.filter(employee_id="EMP002").exists())

    def test_employee_update_contract_accepts_patch(self):
        response = self.client.patch(
            "/api/employees/EMP001/",
            {"name_en": "Taro Yamada Updated", "active_end_month": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name_en"], "Taro Yamada Updated")
        self.assertFalse(response.data["active_end_month"])

    def test_employee_list_filters_and_search(self):
        Employee.objects.create(
            employee_id="EMP777",
            name_jp="別名",
            name_en="Another User",
            department=self.department,
            operational_category="gl",
            work_pattern="4x2",
            active_end_month=False,
        )

        response = self.client.get("/api/employees/?search=Taro&active=true&operational_category=normal")
        results = self.assert_paginated_results(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["employee_id"], "EMP001")

    def test_employee_write_denied_for_user_without_role(self):
        self.client.force_authenticate(self.no_role_user)
        response = self.client.post(
            "/api/employees/",
            {
                "employee_id": "EMP009",
                "name_jp": "無権限",
                "name_en": "No Role",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_read_allowed_for_supervisor(self):
        self.client.force_authenticate(self.supervisor_user)
        response = self.client.get("/api/employees/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_employee_pagination_respects_page_and_page_size(self):
        for index in range(40):
            Employee.objects.create(
                employee_id=f"EMPX{index:03d}",
                name_jp=f"名{index}",
                name_en=f"Name {index}",
            )

        response = self.client.get("/api/employees/?page=2&page_size=10")
        results = self.assert_paginated_results(response)
        self.assertEqual(len(results), 10)
        self.assertGreaterEqual(response.data["count"], 41)

    def test_employee_pagination_enforces_page_size_limit(self):
        response = self.client.get("/api/employees/?page_size=1000")
        results = self.assert_paginated_results(response)
        self.assertLessEqual(len(results), 100)

    def test_employee_export_csv_uses_filters(self):
        Employee.objects.create(
            employee_id="EMP999",
            name_jp="除外",
            name_en="Filtered Out",
            active_end_month=False,
        )
        response = self.client.get("/api/employees/export/?active=true&search=Taro")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("EMP001", body)
        self.assertNotIn("EMP999", body)

    def test_employee_export_csv_denies_no_role(self):
        self.client.force_authenticate(self.no_role_user)
        response = self.client.get("/api/employees/export/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_housing_create_and_list_contract(self):
        payload = {
            "employee": self.employee.employee_id,
            "property_cd": "P001",
            "apartment_name": "Fuji Heights",
            "room_number": "101",
            "move_in_date": None,
            "move_out_date": None,
            "phone_number": "09000000000",
            "postal_code": "000-0000",
            "address": "Test address",
            "office_cd": "OFF1",
        }

        create_response = self.client.post("/api/employees/housing/", payload, format="json")
        list_response = self.client.get("/api/employees/housing/")

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["employee"], self.employee.employee_id)
        self.assertEqual(create_response.data["property_cd"], "P001")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data), 1)
        self.assertTrue(
            {
                "id",
                "employee",
                "property_cd",
                "apartment_name",
                "room_number",
                "move_in_date",
                "move_out_date",
            }.issubset(list_response.data[0].keys())
        )
