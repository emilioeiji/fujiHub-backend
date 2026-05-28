from datetime import date, datetime, time
from io import BytesIO
from tempfile import NamedTemporaryFile

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from master.models import BuildingFloor, Department, Employee, Process, Shift

from .models import (
    AttendanceStatus,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    CalendarPrintPreset,
    EmployeeVisualCategory,
    MonthlyOperationCalendar,
    OperationalCode,
    OperationalPosition,
    OperationCalendarTemplate,
    OperationCalendarTemplateAssignment,
    OperationCalendarTemplateCell,
    OperationCalendarHistory,
    PositionDailyRequirement,
    ProductionMachineStatus,
    ProductionMetrics,
    ProductionMonitorSource,
    ProductionSnapshot,
    OperationsSettings,
    EmployeeAdministrativeNote,
    RotationGroupStyle,
    WorkTimeCode,
    HikitsuguiOccurrenceCategory,
)
from .services import parse_production_file


class OperationsCalendarModelTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            code="54532",
            label_pt="Departamento 54532",
            label_jp="部署 54532",
        )
        self.process = Process.objects.create(
            code="P1",
            label_pt="Processo 1",
            label_jp="工程 1",
        )
        self.shift = Shift.objects.create(
            code="D",
            label_pt="Dia",
            label_jp="日勤",
        )
        self.building_floor = BuildingFloor.objects.create(
            code="E2-4F",
            label_pt="E2 4F",
            label_jp="E2棟4F",
        )
        self.employee = Employee.objects.create(
            employee_id="EMP-OPS-001",
            name_jp="山田太郎",
            name_en="Taro Yamada",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
        )

    def _create_calendar(self):
        return MonthlyOperationCalendar.objects.create(
            department=self.department,
            process=self.process,
            shift=self.shift,
            year=2026,
            month=5,
            title="54532 - Maio 2026",
        )

    def _create_calendar_with_scope(self, *, process=None, shift=None, title="Calendario"):
        return MonthlyOperationCalendar.objects.create(
            department=self.department,
            process=process,
            shift=shift,
            year=2026,
            month=6,
            title=title,
        )

    def _create_position(self):
        return OperationalPosition.objects.create(
            department=self.department,
            code="ECII",
            name_pt="ECII",
            name_jp="ECII",
            building_floor=self.building_floor,
            description="Posicao ECII E2 4F",
        )

    def test_initial_attendance_status_seeds_are_created(self):
        expected_codes = {
            "work",
            "off",
            "paid_leave",
            "absence",
            "late",
            "early_leave",
            "training",
        }

        self.assertTrue(expected_codes.issubset(set(AttendanceStatus.objects.values_list("code", flat=True))))
        self.assertTrue(AttendanceStatus.objects.get(code="work").is_working_day)
        self.assertTrue(AttendanceStatus.objects.get(code="paid_leave").is_paid_leave)
        self.assertTrue(AttendanceStatus.objects.get(code="absence").is_absence)

    def test_initial_work_time_code_seeds_are_created(self):
        expected_codes = {"regular", "overtime", "holiday_work"}

        self.assertTrue(expected_codes.issubset(set(WorkTimeCode.objects.values_list("code", flat=True))))
        self.assertFalse(WorkTimeCode.objects.get(code="regular").affects_overtime)
        self.assertTrue(WorkTimeCode.objects.get(code="overtime").affects_overtime)

    def test_initial_rotation_group_style_seeds_are_created(self):
        expected = {"A", "B", "C"}
        self.assertTrue(expected.issubset(set(RotationGroupStyle.objects.values_list("group_code", flat=True))))

    def test_initial_employee_visual_category_seeds_are_created(self):
        expected = {"normal", "relief", "koutei_leader", "trainer", "retired", "trainee"}
        self.assertTrue(expected.issubset(set(EmployeeVisualCategory.objects.values_list("code", flat=True))))

    def test_initial_operational_code_seeds_are_created(self):
        expected = {
            "normal",
            "teiji",
            "soutai",
            "chikoku",
            "sunday",
            "sunday_teiji",
            "holiday_work",
            "holiday_work_teiji",
            "checkman",
            "checkman_teiji",
            "vaccine",
        }
        self.assertTrue(expected.issubset(set(OperationalCode.objects.values_list("code", flat=True))))

    def test_initial_hikitsugui_categories_seeds_are_created(self):
        expected = {
            "seguranca",
            "qualidade",
            "equipamento",
            "material",
            "pessoal",
            "producao",
            "manutencao",
            "5s",
            "outros",
        }
        self.assertTrue(expected.issubset(set(HikitsuguiOccurrenceCategory.objects.values_list("code", flat=True))))

    def test_create_operational_position(self):
        position = self._create_position()

        self.assertEqual(position.department, self.department)
        self.assertEqual(position.building_floor, self.building_floor)
        self.assertTrue(position.is_active)

    def test_operational_position_is_unique_by_department_and_code(self):
        self._create_position()

        with self.assertRaises(IntegrityError):
            OperationalPosition.objects.create(
                department=self.department,
                code="ECII",
                name_pt="ECII duplicado",
                name_jp="ECII duplicate",
            )

    def test_create_calendar_assignment_cell_requirement_and_print_preset(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = CalendarEmployeeAssignment.objects.create(
            calendar=calendar,
            employee=self.employee,
            operational_category=CalendarEmployeeAssignment.OperationalCategory.NORMAL,
            start_date=date(2026, 5, 1),
            display_order=1,
        )
        day_cell = CalendarDayCell.objects.create(
            calendar=calendar,
            assignment=assignment,
            date=date(2026, 5, 1),
            position=position,
            attendance_status=AttendanceStatus.objects.get(code="work"),
            work_time_code=WorkTimeCode.objects.get(code="regular"),
            raw_value="ECII E2棟4F",
        )
        requirement = PositionDailyRequirement.objects.create(
            calendar=calendar,
            position=position,
            date=date(2026, 5, 1),
            required_headcount=20,
        )
        print_preset = CalendarPrintPreset.objects.create(calendar=calendar)

        self.assertEqual(calendar.status, MonthlyOperationCalendar.Status.DRAFT)
        self.assertEqual(assignment.employee, self.employee)
        self.assertEqual(day_cell.position, position)
        self.assertEqual(requirement.required_headcount, 20)
        self.assertEqual(print_preset.paper_size, CalendarPrintPreset.PaperSize.A4)
        self.assertEqual(print_preset.orientation, CalendarPrintPreset.Orientation.LANDSCAPE)

    def test_calendar_uniqueness_blocks_duplicate_when_process_and_shift_are_null(self):
        self._create_calendar_with_scope(process=None, shift=None, title="Calendario geral")

        with self.assertRaises(ValidationError):
            self._create_calendar_with_scope(process=None, shift=None, title="Duplicado geral")

    def test_calendar_uniqueness_blocks_duplicate_when_process_is_set_and_shift_is_null(self):
        self._create_calendar_with_scope(process=self.process, shift=None, title="Calendario por processo")

        with self.assertRaises(ValidationError):
            self._create_calendar_with_scope(process=self.process, shift=None, title="Duplicado processo")

    def test_calendar_uniqueness_blocks_duplicate_when_process_is_null_and_shift_is_set(self):
        self._create_calendar_with_scope(process=None, shift=self.shift, title="Calendario por turno")

        with self.assertRaises(ValidationError):
            self._create_calendar_with_scope(process=None, shift=self.shift, title="Duplicado turno")

    def test_calendar_uniqueness_blocks_duplicate_when_process_and_shift_are_set(self):
        self._create_calendar_with_scope(
            process=self.process,
            shift=self.shift,
            title="Calendario por processo e turno",
        )

        with self.assertRaises(ValidationError):
            self._create_calendar_with_scope(
                process=self.process,
                shift=self.shift,
                title="Duplicado processo e turno",
            )

    def test_calendar_uniqueness_allows_distinct_scopes(self):
        self._create_calendar_with_scope(process=None, shift=None, title="Geral")
        self._create_calendar_with_scope(process=self.process, shift=None, title="Processo")
        self._create_calendar_with_scope(process=None, shift=self.shift, title="Turno")
        self._create_calendar_with_scope(process=self.process, shift=self.shift, title="Processo e turno")

        self.assertEqual(MonthlyOperationCalendar.objects.count(), 4)

    def test_calendar_uniqueness_allows_updating_same_record(self):
        calendar = self._create_calendar_with_scope(process=None, shift=None, title="Original")

        calendar.title = "Original atualizado"
        calendar.save()

        self.assertEqual(MonthlyOperationCalendar.objects.get(pk=calendar.pk).title, "Original atualizado")

    def test_day_cell_is_unique_by_assignment_and_date(self):
        calendar = self._create_calendar()
        assignment = CalendarEmployeeAssignment.objects.create(
            calendar=calendar,
            employee=self.employee,
            start_date=date(2026, 5, 1),
        )
        CalendarDayCell.objects.create(
            calendar=calendar,
            assignment=assignment,
            date=date(2026, 5, 1),
        )

        with self.assertRaises(IntegrityError):
            CalendarDayCell.objects.create(
                calendar=calendar,
                assignment=assignment,
                date=date(2026, 5, 1),
            )

    def test_position_daily_requirement_is_unique_by_calendar_position_and_date(self):
        calendar = self._create_calendar()
        position = self._create_position()
        PositionDailyRequirement.objects.create(
            calendar=calendar,
            position=position,
            date=date(2026, 5, 1),
            required_headcount=20,
        )

        with self.assertRaises(IntegrityError):
            PositionDailyRequirement.objects.create(
                calendar=calendar,
                position=position,
                date=date(2026, 5, 1),
                required_headcount=21,
            )


class OperationsCalendarAPITests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            code="54532",
            label_pt="Departamento 54532",
            label_jp="部署 54532",
        )
        self.process = Process.objects.create(
            code="P1",
            label_pt="Processo 1",
            label_jp="工程 1",
        )
        self.shift = Shift.objects.create(
            code="D",
            label_pt="Dia",
            label_jp="日勤",
        )
        self.building_floor = BuildingFloor.objects.create(
            code="E2-4F",
            label_pt="E2 4F",
            label_jp="E2棟4F",
        )
        self.employee = Employee.objects.create(
            employee_id="EMP-OPS-API-001",
            name_jp="佐藤花子",
            name_en="Hanako Sato",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
            active_end_month=True,
        )
        self.second_employee = Employee.objects.create(
            employee_id="EMP-OPS-API-002",
            name_jp="鈴木一郎",
            name_en="Ichiro Suzuki",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
            active_end_month=True,
        )
        self.inactive_employee = Employee.objects.create(
            employee_id="EMP-OPS-API-003",
            name_jp="非稼働",
            name_en="Inactive Worker",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
            active_end_month=False,
        )
        self.admin_user = self._create_user_with_role("ops-admin", "admin")
        self.supervisor_user = self._create_user_with_role("ops-supervisor", "supervisor")
        self.consulta_user = self._create_user_with_role("ops-consulta", "consulta")
        self.client = APIClient()
        self.client.force_authenticate(self.admin_user)

    def _create_user_with_role(self, username, role_code):
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": role_code.title(), "is_active": True},
        )
        user = get_user_model().objects.create_user(username=username, password="password")
        UserProfile.objects.create(user=user, role=role, department=self.department)
        return user

    def _create_calendar(self, *, year=2026, month=5, title=None):
        response = self.client.post(
            "/api/operations/calendars/",
            {
                "department": self.department.pk,
                "process": self.process.pk,
                "shift": self.shift.pk,
                "year": year,
                "month": month,
                "title": title or f"54532 - {year}-{month:02d}",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def _create_position(self):
        response = self.client.post(
            "/api/operations/positions/",
            {
                "department": self.department.pk,
                "code": "ECII",
                "name_pt": "ECII",
                "name_jp": "ECII",
                "building_floor": self.building_floor.pk,
                "description": "ECII E2 4F",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def _create_assignment(self, calendar_id, **overrides):
        payload = {
            "employee": self.employee.pk,
            "operational_category": "normal",
            "start_date": "2026-05-01",
            "display_order": 1,
        }
        payload.update(overrides)
        response = self.client.post(
            f"/api/operations/calendars/{calendar_id}/assignments/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def _create_second_assignment(self, calendar_id, **overrides):
        payload = {
            "employee": self.second_employee.pk,
            "operational_category": "normal",
            "start_date": "2026-05-01",
            "display_order": 2,
        }
        payload.update(overrides)
        response = self.client.post(
            f"/api/operations/calendars/{calendar_id}/assignments/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def test_create_calendar(self):
        response_data = self._create_calendar()

        self.assertEqual(response_data["department"], self.department.pk)
        self.assertEqual(response_data["status"], "draft")

    def test_create_calendar_blocks_logical_duplicate(self):
        self._create_calendar()

        response = self.client.post(
            "/api/operations/calendars/",
            {
                "department": self.department.pk,
                "process": self.process.pk,
                "shift": self.shift.pk,
                "year": 2026,
                "month": 5,
                "title": "Duplicado",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_position(self):
        response_data = self._create_position()

        self.assertEqual(response_data["code"], "ECII")
        self.assertEqual(response_data["department"], self.department.pk)

    def test_create_assignment(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        self.assertEqual(assignment["employee"], self.employee.pk)
        self.assertEqual(assignment["calendar"], calendar["id"])

    def test_assignments_endpoint_returns_operational_order(self):
        calendar = self._create_calendar()
        third_employee = Employee.objects.create(
            employee_id="EMP-OPS-API-004",
            name_jp="田中次郎",
            name_en="Jiro Tanaka",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
            active_end_month=True,
        )
        fourth_employee = Employee.objects.create(
            employee_id="EMP-OPS-API-005",
            name_jp="高橋三郎",
            name_en="Saburo Takahashi",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
            active_end_month=True,
        )

        self._create_assignment(
            calendar["id"],
            employee=third_employee.pk,
            operational_category="koutei_leader",
            rotation_group="A",
            display_order=1,
        )
        self._create_assignment(
            calendar["id"],
            employee=self.employee.pk,
            operational_category="normal",
            rotation_group="B",
            display_order=5,
        )
        self._create_assignment(
            calendar["id"],
            employee=self.second_employee.pk,
            operational_category="normal",
            rotation_group="A",
            display_order=10,
        )
        self._create_assignment(
            calendar["id"],
            employee=fourth_employee.pk,
            operational_category="relief",
            rotation_group="C",
            display_order=1,
        )

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/assignments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ordered_categories = [item["operational_category"] for item in response.data]
        ordered_employee_ids = [item["employee_detail"]["employee_id"] for item in response.data]

        self.assertEqual(
            ordered_categories,
            ["normal", "normal", "koutei_leader", "relief"],
        )
        self.assertEqual(
            ordered_employee_ids,
            ["EMP-OPS-API-002", "EMP-OPS-API-001", "EMP-OPS-API-004", "EMP-OPS-API-005"],
        )
        self.assertIn("category_rank", response.data[0])
        self.assertIn("category_label", response.data[0])
        self.assertIn("visual_category", response.data[0])
        self.assertIn("billing_rate", response.data[0])
        self.assertIn("process", response.data[0])

    def test_import_uses_master_operational_category_kl_mapping(self):
        calendar = self._create_calendar()
        self.employee.operational_category = "kl"
        self.employee.save(update_fields=["operational_category"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"import_all": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment = CalendarEmployeeAssignment.objects.filter(calendar_id=calendar["id"], employee=self.employee).first()
        self.assertIsNotNone(assignment)
        self.assertEqual(
            assignment.operational_category,
            CalendarEmployeeAssignment.OperationalCategory.KOUTEI_LEADER,
        )

    def test_replicate_requirements_endpoint(self):
        calendar = self._create_calendar()
        position = self._create_position()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/requirements/replicate/",
            {
                "position": position["id"],
                "date": "2026-05-10",
                "required_headcount": 22,
                "mode": "remaining",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["affected_days"], 22)
        self.assertEqual(
            PositionDailyRequirement.objects.filter(
                calendar_id=calendar["id"],
                position_id=position["id"],
                required_headcount=22,
            ).count(),
            response.data["affected_days"],
        )

    def test_create_cell(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "position": position["id"],
                "attendance_status": work_status.pk,
                "work_time_code": regular.pk,
                "raw_value": "ECII E2棟4F",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["position"], position["id"])

    def test_get_cells_regression_returns_200_with_operational_code(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])
        code = OperationalCode.objects.get(code="teiji")
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")
        CalendarDayCell.objects.create(
            calendar_id=calendar["id"],
            assignment_id=assignment["id"],
            date=date(2026, 5, 1),
            position_id=position["id"],
            attendance_status=work_status,
            work_time_code=regular,
            operational_code=code,
            raw_value="定時",
        )

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/cells/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["operational_code_detail"]["code"], "teiji")

    def test_update_cell(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {"assignment": assignment["id"], "date": "2026-05-01", "raw_value": "休"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        patch_response = self.client.patch(
            f"/api/operations/calendars/{calendar['id']}/cells/{response.data['id']}/",
            {"memo": "Ajustado"},
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["memo"], "Ajustado")

    def test_create_requirement(self):
        calendar = self._create_calendar()
        position = self._create_position()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/requirements/",
            {
                "position": position["id"],
                "date": "2026-05-01",
                "required_headcount": 20,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["required_headcount"], 20)

    def test_update_requirement(self):
        calendar = self._create_calendar()
        position = self._create_position()
        create_response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/requirements/",
            {
                "position": position["id"],
                "date": "2026-05-01",
                "required_headcount": 20,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        update_response = self.client.patch(
            f"/api/operations/calendars/{calendar['id']}/requirements/{create_response.data['id']}/",
            {"required_headcount": 22, "notes": "Ajuste diario"},
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["required_headcount"], 22)

    def test_summary_returns_required_assigned_and_difference(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])
        work_status = AttendanceStatus.objects.get(code="work")

        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/requirements/",
            {
                "position": position["id"],
                "date": "2026-05-01",
                "required_headcount": 2,
            },
            format="json",
        )
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "position": position["id"],
                "attendance_status": work_status.pk,
            },
            format="json",
        )

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data[0]["requirement_id"])
        self.assertEqual(response.data[0]["required_headcount"], 2)
        self.assertEqual(response.data[0]["assigned_headcount"], 1)
        self.assertEqual(response.data[0]["difference"], -1)

    def test_paste_cells_simple_2x2(self):
        calendar = self._create_calendar()
        position = self._create_position()
        first_assignment = self._create_assignment(calendar["id"])
        second_assignment = self._create_second_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": first_assignment["id"],
                "start_date": "2026-05-01",
                "tsv": f"{position['code']}\t休\n片栗粉\t欠",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 4)
        self.assertEqual(CalendarDayCell.objects.count(), 4)
        self.assertEqual(
            CalendarDayCell.objects.get(assignment_id=second_assignment["id"], date="2026-05-02").raw_value,
            "欠",
        )

    def test_paste_maps_position(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": position["code"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-01")
        self.assertEqual(cell.position_id, position["id"])

    def test_paste_maps_attendance_statuses(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "休\t有休\t欠勤",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        statuses = list(
            CalendarDayCell.objects.filter(assignment_id=assignment["id"])
            .order_by("date")
            .values_list("attendance_status__code", flat=True)
        )
        self.assertEqual(statuses, ["off", "paid_leave", "absence"])

    def test_paste_maps_work_time_codes(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "定時\t残業",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = list(
            CalendarDayCell.objects.filter(assignment_id=assignment["id"])
            .order_by("date")
            .values_list("work_time_code__code", flat=True)
        )
        self.assertEqual(codes, ["regular", "overtime"])

    def test_paste_maps_operational_codes_and_derived_fields(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "teiji\t日曜\t休日出勤\t早退\t遅刻",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cells = list(CalendarDayCell.objects.filter(assignment_id=assignment["id"]).order_by("date"))
        self.assertEqual([cell.operational_code.code for cell in cells], ["teiji", "sunday", "holiday_work", "soutai", "chikoku"])
        self.assertEqual(cells[0].work_time_code.code, "regular")
        self.assertEqual(cells[1].attendance_status.code, "off")
        self.assertEqual(cells[2].work_time_code.code, "holiday_work")

    def test_paste_maps_position_with_regular_work_time(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "ECII 定時",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-01")
        self.assertEqual(cell.position_id, position["id"])
        self.assertEqual(cell.work_time_code.code, "regular")
        self.assertEqual(cell.raw_value, "ECII 定時")
        self.assertEqual(cell.memo, "")

    def test_paste_maps_position_with_overtime_work_time(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "ECII + 残業",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-01")
        self.assertEqual(cell.position_id, position["id"])
        self.assertEqual(cell.work_time_code.code, "overtime")
        self.assertEqual(cell.memo, "")

    def test_paste_maps_position_and_keeps_remaining_text_as_memo(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "ECII メモ qualquer",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unrecognized_values"], [])
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-01")
        self.assertEqual(cell.position_id, position["id"])
        self.assertEqual(cell.raw_value, "ECII メモ qualquer")
        self.assertEqual(cell.memo, "メモ qualquer")

    def test_paste_maps_position_and_keeps_vaccine_as_memo(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "ECII ワクチン",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-01")
        self.assertEqual(cell.position_id, position["id"])
        self.assertEqual(cell.operational_code.code, "vaccine")
        self.assertEqual(cell.memo, "")

    def test_paste_maps_composite_values_with_different_separators(self):
        calendar = self._create_calendar()
        self._create_position()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": 'ECII/定時\tECII・残業\t"ECII\n定時"',
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cells = list(CalendarDayCell.objects.filter(assignment_id=assignment["id"]).order_by("date"))
        self.assertEqual([cell.position.code for cell in cells], ["ECII", "ECII", "ECII"])
        self.assertEqual([cell.work_time_code.code for cell in cells], ["regular", "overtime", "regular"])
        self.assertEqual(cells[2].raw_value, "ECII\n定時")

    def test_paste_unknown_value_saves_raw_value_and_memo(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "valor livre",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["unrecognized_values"]), 1)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-01")
        self.assertEqual(cell.raw_value, "valor livre")
        self.assertEqual(cell.memo, "valor livre")

    def test_paste_does_not_exceed_assignments_or_calendar_month(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-31",
                "tsv": "休\t有休\n欠勤\t定時",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(CalendarDayCell.objects.count(), 1)

    def test_paste_write_permission_is_required(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])
        self.client.force_authenticate(self.consulta_user)

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "休",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_generate_schedule_4x2_group_a_uses_anchor_off_days(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(
            calendar["id"],
            rotation_group="A",
            work_pattern="4x2",
            default_position=position["id"],
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {"overwrite": False, "default_4x2_anchor_date": "2026-05-30"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 31)
        may_29 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-29")
        may_30 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-30")
        may_31 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-31")
        self.assertEqual(may_29.attendance_status.code, "work")
        self.assertEqual(may_29.position_id, position["id"])
        self.assertEqual(may_30.attendance_status.code, "off")
        self.assertEqual(may_30.raw_value, "休")
        self.assertEqual(may_31.attendance_status.code, "off")

    def test_generate_schedule_4x2_group_b_uses_offset_off_days(self):
        calendar = self._create_calendar(month=6)
        assignment = self._create_assignment(
            calendar["id"],
            start_date="2026-06-01",
            rotation_group="B",
            work_pattern="4x2",
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {"default_4x2_anchor_date": "2026-05-30"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        june_1 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-06-01")
        june_2 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-06-02")
        june_3 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-06-03")
        self.assertEqual(june_1.attendance_status.code, "off")
        self.assertEqual(june_2.attendance_status.code, "off")
        self.assertEqual(june_3.attendance_status.code, "work")

    def test_generate_schedule_4x2_group_c_uses_offset_off_days(self):
        calendar = self._create_calendar(month=6)
        assignment = self._create_assignment(
            calendar["id"],
            start_date="2026-06-01",
            rotation_group="C",
            work_pattern="4x2",
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {"default_4x2_anchor_date": "2026-05-30"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        june_3 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-06-03")
        june_4 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-06-04")
        june_5 = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-06-05")
        self.assertEqual(june_3.attendance_status.code, "off")
        self.assertEqual(june_4.attendance_status.code, "off")
        self.assertEqual(june_5.attendance_status.code, "work")

    def test_generate_schedule_5x2_defaults_to_saturday_and_sunday_off(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2")

        response = self.client.post(f"/api/operations/calendars/{calendar['id']}/generate-schedule/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        saturday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-02")
        sunday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-03")
        monday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-04")
        self.assertEqual(saturday.attendance_status.code, "off")
        self.assertEqual(sunday.attendance_status.code, "off")
        self.assertEqual(monday.attendance_status.code, "work")

    def test_generate_schedule_5x2_accepts_custom_off_days(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2", five_two_off_days=[6, 0])

        response = self.client.post(f"/api/operations/calendars/{calendar['id']}/generate-schedule/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sunday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-03")
        monday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-04")
        tuesday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-05")
        self.assertEqual(sunday.attendance_status.code, "off")
        self.assertEqual(monday.attendance_status.code, "off")
        self.assertEqual(tuesday.attendance_status.code, "work")

    def test_generate_schedule_respects_start_and_end_dates(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(
            calendar["id"],
            start_date="2026-05-10",
            end_date="2026-05-12",
            work_pattern="5x2",
        )

        response = self.client.post(f"/api/operations/calendars/{calendar['id']}/generate-schedule/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 3)
        dates = list(
            CalendarDayCell.objects.filter(assignment_id=assignment["id"]).order_by("date").values_list("date", flat=True)
        )
        self.assertEqual(dates, [date(2026, 5, 10), date(2026, 5, 11), date(2026, 5, 12)])

    def test_generate_schedule_does_not_overwrite_existing_cell_by_default(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2")
        CalendarDayCell.objects.create(
            calendar_id=calendar["id"],
            assignment_id=assignment["id"],
            date=date(2026, 5, 4),
            raw_value="Manual",
            memo="Nao mexer",
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {"overwrite": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["skipped"], 1)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-04")
        self.assertEqual(cell.raw_value, "Manual")
        self.assertEqual(cell.memo, "Nao mexer")

    def test_generate_schedule_overwrites_existing_cell_and_preserves_memo(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2")
        CalendarDayCell.objects.create(
            calendar_id=calendar["id"],
            assignment_id=assignment["id"],
            date=date(2026, 5, 4),
            raw_value="Manual",
            memo="Preservar memo",
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {"overwrite": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-04")
        self.assertEqual(cell.attendance_status.code, "work")
        self.assertEqual(cell.work_time_code.code, "regular")
        self.assertEqual(cell.memo, "Preservar memo")

    def test_generate_schedule_uses_last_known_position_when_default_position_is_empty(self):
        calendar = self._create_calendar()
        position = self._create_position()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2")
        CalendarDayCell.objects.create(
            calendar_id=calendar["id"],
            assignment_id=assignment["id"],
            date=date(2026, 5, 1),
            position_id=position["id"],
            raw_value="ECII",
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {"overwrite": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cell = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-04")
        self.assertEqual(cell.position_id, position["id"])
        self.assertEqual(cell.raw_value, "ECII")

    def test_generate_schedule_write_permission_is_required(self):
        calendar = self._create_calendar()
        self._create_assignment(calendar["id"])
        self.client.force_authenticate(self.consulta_user)

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/generate-schedule/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hours_4x2_normal_cell(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "work_time_code": regular.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 540)
        self.assertEqual(cell.scheduled_overtime_minutes, 120)
        self.assertEqual(str(cell.start_time), "08:30:00")
        self.assertEqual(str(cell.end_time), "20:35:00")
        self.assertEqual(cell.break_minutes, 65)
        self.assertFalse(cell.crosses_midnight)

    def test_hours_4x2_night_normal_cell(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="night")
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "work_time_code": regular.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 540)
        self.assertEqual(cell.scheduled_overtime_minutes, 120)
        self.assertEqual(str(cell.start_time), "20:30:00")
        self.assertEqual(str(cell.end_time), "08:35:00")
        self.assertEqual(cell.break_minutes, 65)
        self.assertTrue(cell.crosses_midnight)

    def test_hours_5x2_normal_cell(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2")
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "work_time_code": regular.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 480)
        self.assertEqual(cell.scheduled_overtime_minutes, 180)

    def test_hours_5x2_teiji(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="5x2", shift_type="day")
        work_status = AttendanceStatus.objects.get(code="work")
        teiji = OperationalCode.objects.get(code="teiji")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "operational_code": teiji.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 480)
        self.assertEqual(cell.scheduled_overtime_minutes, 0)

    def test_hours_special_codes_sunday_and_holiday_work(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2")
        off_status = AttendanceStatus.objects.get(code="off")
        sunday_code = OperationalCode.objects.get(code="sunday")
        holiday_code = OperationalCode.objects.get(code="holiday_work")
        CalendarDayCell.objects.create(
            calendar_id=calendar["id"],
            assignment_id=assignment["id"],
            date=date(2026, 5, 4),
            attendance_status=off_status,
            operational_code=sunday_code,
        )
        CalendarDayCell.objects.create(
            calendar_id=calendar["id"],
            assignment_id=assignment["id"],
            date=date(2026, 5, 5),
            attendance_status=off_status,
            operational_code=holiday_code,
        )
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {"start_assignment": assignment["id"], "start_date": "2026-05-04", "tsv": "日曜\t休日出勤"},
            format="json",
        )
        sunday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-04")
        holiday = CalendarDayCell.objects.get(assignment_id=assignment["id"], date="2026-05-05")
        self.assertEqual(sunday.scheduled_regular_minutes, 0)
        self.assertEqual(holiday.scheduled_regular_minutes, 0)
        self.assertEqual(sunday.scheduled_overtime_minutes, 660)
        self.assertEqual(holiday.scheduled_overtime_minutes, 660)

    def test_hours_non_working_status_is_zero(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])
        off_status = AttendanceStatus.objects.get(code="off")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {"assignment": assignment["id"], "date": "2026-05-01", "attendance_status": off_status.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 0)
        self.assertEqual(cell.scheduled_overtime_minutes, 0)

    def test_hours_paid_leave_absence_and_vaccine_are_zero(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")
        paid_leave = AttendanceStatus.objects.get(code="paid_leave")
        absence = AttendanceStatus.objects.get(code="absence")
        work_status = AttendanceStatus.objects.get(code="work")
        vaccine = OperationalCode.objects.get(code="vaccine")

        payloads = [
            {"date": "2026-05-01", "attendance_status": paid_leave.pk},
            {"date": "2026-05-02", "attendance_status": absence.pk},
            {"date": "2026-05-03", "attendance_status": work_status.pk, "operational_code": vaccine.pk},
        ]
        for payload in payloads:
            response = self.client.post(
                f"/api/operations/calendars/{calendar['id']}/cells/",
                {"assignment": assignment["id"], **payload},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        cells = CalendarDayCell.objects.filter(assignment_id=assignment["id"]).order_by("date")
        for cell in cells:
            self.assertEqual(cell.scheduled_regular_minutes, 0)
            self.assertEqual(cell.scheduled_overtime_minutes, 0)
            self.assertEqual(cell.actual_work_minutes, 0)
            self.assertEqual(cell.actual_overtime_minutes, 0)

    def test_hours_teiji_with_leave_time_adjusts_overtime(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")
        work_status = AttendanceStatus.objects.get(code="work")
        teiji = OperationalCode.objects.get(code="teiji")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "operational_code": teiji.pk,
                "leave_time": "17:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_overtime_minutes, 0)
        self.assertEqual(cell.actual_overtime_minutes, 0)
        self.assertEqual(cell.actual_work_minutes, 445)

    def test_hours_4x2_night_teiji(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="night")
        work_status = AttendanceStatus.objects.get(code="work")
        teiji = OperationalCode.objects.get(code="teiji")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "operational_code": teiji.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 540)
        self.assertEqual(cell.scheduled_overtime_minutes, 0)

    def test_hours_4x2_day_leave_time_reduces_overtime(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")
        work_status = AttendanceStatus.objects.get(code="work")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "leave_time": "18:30",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.actual_work_minutes, 535)
        self.assertEqual(cell.actual_overtime_minutes, 0)

    def test_hours_4x2_night_leave_time_after_midnight(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="night")
        work_status = AttendanceStatus.objects.get(code="work")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "leave_time": "03:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.actual_work_minutes, 325)
        self.assertEqual(cell.actual_overtime_minutes, 0)

    def test_hours_4x2_night_leave_time_0500(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="night")
        work_status = AttendanceStatus.objects.get(code="work")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "leave_time": "05:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.actual_work_minutes, 445)
        self.assertEqual(cell.actual_overtime_minutes, 0)

    def test_hours_sunday_with_leave_time_calculates_real_overtime(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")
        off_status = AttendanceStatus.objects.get(code="off")
        sunday = OperationalCode.objects.get(code="sunday")
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-04",
                "attendance_status": off_status.pk,
                "operational_code": sunday.pk,
                "leave_time": "12:30",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 0)
        self.assertEqual(cell.actual_overtime_minutes, 220)

    def test_assignment_totals_endpoint(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2")
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")
        for day in ("2026-05-01", "2026-05-02"):
            self.client.post(
                f"/api/operations/calendars/{calendar['id']}/cells/",
                {"assignment": assignment["id"], "date": day, "attendance_status": work_status.pk, "work_time_code": regular.pk},
                format="json",
            )
        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/assignment-totals/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        first = response.data[0]
        self.assertEqual(first["scheduled_regular_minutes_total"], 1080)
        self.assertEqual(first["scheduled_overtime_minutes_total"], 240)
        self.assertEqual(first["scheduled_regular_formatted"], "18:00")
        self.assertEqual(first["scheduled_overtime_formatted"], "04:00")

    def test_cell_recalculation_does_not_accumulate_on_multiple_saves(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2")
        work_status = AttendanceStatus.objects.get(code="work")
        regular = WorkTimeCode.objects.get(code="regular")

        create = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.pk,
                "work_time_code": regular.pk,
            },
            format="json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        cell_id = create.data["id"]

        for _ in range(3):
            patch = self.client.patch(
                f"/api/operations/calendars/{calendar['id']}/cells/{cell_id}/",
                {"memo": "saving again"},
                format="json",
            )
            self.assertEqual(patch.status_code, status.HTTP_200_OK)

        cell = CalendarDayCell.objects.get(pk=cell_id)
        self.assertEqual(cell.scheduled_regular_minutes, 540)
        self.assertEqual(cell.scheduled_overtime_minutes, 120)
        self.assertEqual(cell.actual_work_minutes, 540)
        self.assertEqual(cell.actual_overtime_minutes, 120)

    def test_vaccine_code_keeps_hours_zero_when_attendance_status_is_not_working(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2")
        off_status = AttendanceStatus.objects.get(code="off")
        vaccine = OperationalCode.objects.get(code="vaccine")

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-02",
                "attendance_status": off_status.pk,
                "operational_code": vaccine.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cell = CalendarDayCell.objects.get(pk=response.data["id"])
        self.assertEqual(cell.scheduled_regular_minutes, 0)
        self.assertEqual(cell.scheduled_overtime_minutes, 0)

    def test_import_employees_imports_all_active_department_employees(self):
        calendar = self._create_calendar()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"import_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], 0)
        employees = set(CalendarEmployeeAssignment.objects.values_list("employee_id", flat=True))
        self.assertEqual(employees, {self.employee.employee_id, self.second_employee.employee_id})

    def test_import_employees_imports_selected_employees(self):
        calendar = self._create_calendar()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"employee_ids": [self.second_employee.employee_id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)
        assignment = CalendarEmployeeAssignment.objects.get()
        self.assertEqual(assignment.employee_id, self.second_employee.employee_id)

    def test_import_employees_skips_duplicates(self):
        calendar = self._create_calendar()
        self._create_assignment(calendar["id"])

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"import_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["skipped"], 1)

    def test_import_employees_infers_4x2_and_5x2_patterns(self):
        self.second_employee.contract_type = "supervisor"
        self.second_employee.save()
        calendar = self._create_calendar()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"import_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        normal_assignment = CalendarEmployeeAssignment.objects.get(employee=self.employee)
        supervisor_assignment = CalendarEmployeeAssignment.objects.get(employee=self.second_employee)
        self.assertEqual(normal_assignment.work_pattern, "4x2")
        self.assertEqual(normal_assignment.rotation_group, "A")
        self.assertEqual(supervisor_assignment.work_pattern, "5x2")
        self.assertEqual(supervisor_assignment.operational_category, "supervisor")

    def test_import_employees_infers_default_position_by_process(self):
        position = self._create_position()
        calendar = self._create_calendar()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"employee_ids": [self.employee.employee_id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment = CalendarEmployeeAssignment.objects.get(employee=self.employee)
        self.assertEqual(assignment.default_position_id, position["id"])

    def test_import_employees_uses_employee_operational_defaults_when_present(self):
        self.employee.operational_category = "trainer"
        self.employee.work_pattern = "manual"
        self.employee.shift_type = "flexible"
        self.employee.rotation_group = "C"
        self.employee.five_two_off_days = [1, 2]
        self.employee.save()
        calendar = self._create_calendar()

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"employee_ids": [self.employee.employee_id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment = CalendarEmployeeAssignment.objects.get(employee=self.employee)
        self.assertEqual(assignment.operational_category, "trainer")
        self.assertEqual(assignment.work_pattern, "manual")
        self.assertEqual(assignment.shift_type, "flexible")
        self.assertEqual(assignment.rotation_group, "C")
        self.assertEqual(assignment.five_two_off_days, [1, 2])

    def test_import_employees_write_permission_is_required(self):
        calendar = self._create_calendar()
        self.client.force_authenticate(self.consulta_user)

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"import_all": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_import_employees_preview_returns_candidates_and_scope(self):
        calendar = self._create_calendar()
        self._create_assignment(calendar["id"], employee=self.employee.pk)

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/import-employees-preview/?import_all=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("scope", response.data)
        self.assertEqual(response.data["scope"]["department"], self.department.code)
        self.assertEqual(response.data["total_candidates"], 1)
        self.assertEqual(response.data["total_already_linked"], 1)

    def test_import_employees_respects_shift_scope(self):
        night_shift = Shift.objects.create(code="N", label_pt="Noite", label_jp="夜勤")
        self.second_employee.shift = night_shift
        self.second_employee.save()
        calendar = self._create_calendar()

        preview = self.client.get(f"/api/operations/calendars/{calendar['id']}/import-employees-preview/?import_all=true")
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["total_candidates"], 1)
        ignored_reasons = {item["reason"] for item in preview.data["ignored"]}
        self.assertIn("different_shift", ignored_reasons)

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/import-employees/",
            {"import_all": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)

    def test_import_employees_preview_lists_inactive_as_ignored(self):
        calendar = self._create_calendar()

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/import-employees-preview/?import_all=true")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ignored_reasons = {item["reason"] for item in response.data["ignored"]}
        self.assertIn("inactive", ignored_reasons)
        self.assertEqual(response.data["total_candidates"], 2)

    def test_sync_assignments_updates_from_master_without_touching_cells(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], rotation_group="A", work_pattern="4x2")
        cell_response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "raw_value": "manual",
            },
            format="json",
        )
        self.employee.rotation_group = "C"
        self.employee.work_pattern = "5x2"
        self.employee.save()

        response = self.client.post(f"/api/operations/calendars/{calendar['id']}/sync-assignments/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 1)
        assignment_obj = CalendarEmployeeAssignment.objects.get(pk=assignment["id"])
        self.assertEqual(assignment_obj.rotation_group, "C")
        self.assertEqual(assignment_obj.work_pattern, "5x2")
        self.assertEqual(CalendarDayCell.objects.get(pk=cell_response.data["id"]).raw_value, "manual")

    def test_assignment_patch_updates_manual_fields(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], rotation_group="A")

        response = self.client.patch(
            f"/api/operations/calendars/{calendar['id']}/assignments/{assignment['id']}/",
            {"rotation_group": "B", "shift_type": "night", "work_pattern": "manual"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment_obj = CalendarEmployeeAssignment.objects.get(pk=assignment["id"])
        self.assertEqual(assignment_obj.rotation_group, "B")
        self.assertEqual(assignment_obj.shift_type, "night")
        self.assertEqual(assignment_obj.work_pattern, "manual")

    def test_save_template_from_calendar(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "position": self._create_position()["id"],
                "operational_code": OperationalCode.objects.get(code="teiji").id,
                "raw_value": "ECII / E2棟4F",
            },
            format="json",
        )

        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/save-template/",
            {"name": "Template Maio", "description": "Base mensal", "scope_from_calendar": True, "include_base_cells": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        template = OperationCalendarTemplate.objects.get(pk=response.data["template_id"])
        self.assertEqual(template.name, "Template Maio")
        self.assertEqual(template.department_id, self.department.id)
        self.assertEqual(template.assignments.count(), 1)
        self.assertEqual(template.cells.count(), 1)

    def test_apply_template_requires_confirmation_when_target_has_data(self):
        source_calendar = self._create_calendar(year=2026, month=5)
        self._create_assignment(source_calendar["id"])
        self.client.post(
            f"/api/operations/calendars/{source_calendar['id']}/save-template/",
            {"name": "Template Base"},
            format="json",
        )
        template = OperationCalendarTemplate.objects.get(name="Template Base")

        target_calendar = self._create_calendar(year=2026, month=6)
        self._create_assignment(target_calendar["id"], employee=self.second_employee.pk, display_order=2)

        response = self.client.post(
            f"/api/operations/calendars/{target_calendar['id']}/apply-template/",
            {"template_id": template.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(response.data["requires_confirmation"])

    def test_apply_template_with_overwrite(self):
        source_calendar = self._create_calendar(year=2026, month=5)
        source_assignment = self._create_assignment(source_calendar["id"], display_order=1)
        position = self._create_position()
        self.client.post(
            f"/api/operations/calendars/{source_calendar['id']}/cells/",
            {
                "assignment": source_assignment["id"],
                "date": "2026-05-01",
                "position": position["id"],
                "operational_code": OperationalCode.objects.get(code="teiji").id,
                "raw_value": "ECII / E2棟4F",
            },
            format="json",
        )
        save_res = self.client.post(
            f"/api/operations/calendars/{source_calendar['id']}/save-template/",
            {"name": "Template Aplicacao"},
            format="json",
        )
        template_id = save_res.data["template_id"]

        target_calendar = self._create_calendar(year=2026, month=6)
        self._create_assignment(target_calendar["id"], employee=self.second_employee.pk, display_order=2)

        response = self.client.post(
            f"/api/operations/calendars/{target_calendar['id']}/apply-template/",
            {"template_id": template_id, "overwrite": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created_assignments"], 1)
        target_assignments = CalendarEmployeeAssignment.objects.filter(calendar_id=target_calendar["id"])
        self.assertEqual(target_assignments.count(), 1)
        applied_assignment = target_assignments.first()
        applied_cells = CalendarDayCell.objects.filter(assignment=applied_assignment)
        self.assertEqual(applied_cells.count(), 1)

    def test_export_excel_returns_xlsx_file(self):
        calendar = self._create_calendar()
        self._create_assignment(calendar["id"], work_pattern="4x2", shift_type="day")

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/export-excel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.content))
        sheet = workbook.active
        self.assertEqual(sheet.title, "Escala")
        self.assertTrue(str(sheet["A1"].value).startswith("Escala Operacional"))

    def test_export_excel_requires_authenticated_user(self):
        calendar = self._create_calendar()
        self.client.force_authenticate(None)

        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/export-excel/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cell_update_creates_history_entry(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])

        create_response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "raw_value": "ECII / E2棟4F",
                "history_source": "inline_edit",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OperationCalendarHistory.objects.filter(calendar_id=calendar["id"]).count(), 1)
        entry = OperationCalendarHistory.objects.filter(calendar_id=calendar["id"]).first()
        self.assertEqual(entry.source, OperationCalendarHistory.Source.INLINE_EDIT)
        self.assertEqual(entry.cell_date.isoformat(), "2026-05-01")

    def test_paste_endpoint_creates_history_entries(self):
        calendar = self._create_calendar()
        assignment = self._create_assignment(calendar["id"])
        response = self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/paste/",
            {
                "start_assignment": assignment["id"],
                "start_date": "2026-05-01",
                "tsv": "ECII / E2棟4F\t休",
                "history_source": "paste",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history_qs = OperationCalendarHistory.objects.filter(calendar_id=calendar["id"], source=OperationCalendarHistory.Source.PASTE)
        self.assertEqual(history_qs.count(), 2)

    def test_history_endpoint_requires_authentication(self):
        calendar = self._create_calendar()
        self.client.force_authenticate(None)
        response = self.client.get(f"/api/operations/calendars/{calendar['id']}/history/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_permissions_for_master_data_and_calendar_writes(self):
        self.client.force_authenticate(self.supervisor_user)
        position_response = self.client.post(
            "/api/operations/positions/",
            {
                "department": self.department.pk,
                "code": "NG",
                "name_pt": "Sem permissao",
                "name_jp": "権限なし",
            },
            format="json",
        )
        calendar_response = self.client.post(
            "/api/operations/calendars/",
            {
                "department": self.department.pk,
                "year": 2026,
                "month": 6,
                "title": "Supervisor pode criar calendario",
            },
            format="json",
        )

        self.assertEqual(position_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(calendar_response.status_code, status.HTTP_201_CREATED)

    def test_authenticated_read_and_consulta_write_denied(self):
        self._create_position()
        self.client.force_authenticate(self.consulta_user)

        read_response = self.client.get("/api/operations/positions/")
        write_response = self.client.post(
            "/api/operations/calendars/",
            {
                "department": self.department.pk,
                "year": 2026,
                "month": 7,
                "title": "Consulta nao pode escrever",
            },
            format="json",
        )

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(write_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_production_dashboard_returns_mock_when_empty(self):
        response = self.client.get("/api/operations/production-snapshots/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_mock"])
        self.assertIn("kpis", response.data)
        self.assertGreater(len(response.data["machines"]), 0)

    def test_production_dashboard_filters_by_status(self):
        source = ProductionMonitorSource.objects.create(name="Fonte Linha A", source_type=ProductionMonitorSource.SourceType.CSV)
        snapshot = ProductionSnapshot.objects.create(
            source=source,
            captured_at=timezone.make_aware(datetime(2026, 5, 27, 8, 0, 0)),
            process=self.process,
            shift=self.shift,
            area="Linha A",
        )
        ProductionMachineStatus.objects.create(
            snapshot=snapshot,
            machine_code="M1",
            equipment_name="Prensa",
            status=ProductionMachineStatus.MachineState.RUNNING,
            production_actual=100,
            production_target=120,
            run_minutes=80,
            stop_minutes=10,
            alarm_active=False,
        )
        ProductionMachineStatus.objects.create(
            snapshot=snapshot,
            machine_code="M2",
            equipment_name="Solda",
            status=ProductionMachineStatus.MachineState.STOPPED,
            production_actual=80,
            production_target=120,
            run_minutes=50,
            stop_minutes=40,
            alarm_active=True,
        )
        ProductionMetrics.objects.create(
            snapshot=snapshot,
            total_actual=180,
            total_target=240,
            average_kadouritsu=75,
            running_count=1,
            stopped_count=1,
            idle_count=0,
            error_count=0,
            alarms_active=1,
        )

        response = self.client.get("/api/operations/production-snapshots/dashboard/?status=stopped")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_mock"])
        self.assertEqual(len(response.data["machines"]), 1)
        self.assertEqual(response.data["machines"][0]["status"], "stopped")

    def test_attendance_dashboard_aggregation_and_filters(self):
        calendar = self._create_calendar(year=2026, month=5, title="Attendance test")
        assignment = self._create_assignment(calendar["id"])
        late_status = AttendanceStatus.objects.create(
            code="late_custom",
            label_pt="Atraso",
            label_jp="遅刻",
            is_working_day=True,
            is_absence=False,
        )
        absence_status = AttendanceStatus.objects.get(code="absence")
        work_status = AttendanceStatus.objects.get(code="work")

        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.id,
                "overtime_minutes": 120,
                "actual_work_minutes": 600,
            },
            format="json",
        )
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-02",
                "attendance_status": late_status.id,
                "overtime_minutes": 60,
                "actual_work_minutes": 540,
            },
            format="json",
        )
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-03",
                "attendance_status": absence_status.id,
                "overtime_minutes": 0,
                "actual_work_minutes": 0,
            },
            format="json",
        )

        response = self.client.get("/api/operations/attendance-dashboard/?month=2026-05")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kpis"]["total_scheduled_employees"], 1)
        self.assertEqual(response.data["kpis"]["absences"], 1)
        self.assertGreaterEqual(response.data["kpis"]["lates"], 1)
        self.assertIn("employee_rankings", response.data)

        filtered = self.client.get(f"/api/operations/attendance-dashboard/?month=2026-05&process={self.process.id}")
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)

    def test_operations_settings_endpoint_get_and_patch(self):
        get_response = self.client.get("/api/operations/settings/current/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(get_response.data["weekly_warning_hours"]), 50.0)

        patch_response = self.client.patch(
            "/api/operations/settings/current/",
            {
                "weekly_warning_hours": 40,
                "weekly_critical_hours": 55,
                "monthly_overtime_warning_hours": 30,
                "monthly_overtime_critical_hours": 50,
                "consecutive_absence_warning": 1,
                "recurrent_late_warning": 1,
            },
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(patch_response.data["weekly_warning_hours"]), 40.0)

    def test_attendance_dashboard_uses_configurable_thresholds(self):
        settings = OperationsSettings.load()
        settings.weekly_warning_hours = 1
        settings.weekly_critical_hours = 2
        settings.monthly_overtime_warning_hours = 1
        settings.monthly_overtime_critical_hours = 2
        settings.save()

        calendar = self._create_calendar(year=2026, month=5, title="Threshold test")
        assignment = self._create_assignment(calendar["id"])
        work_status = AttendanceStatus.objects.get(code="work")
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-01",
                "attendance_status": work_status.id,
                "overtime_minutes": 180,
                "actual_work_minutes": 300,
            },
            format="json",
        )
        response = self.client.get("/api/operations/attendance-dashboard/?month=2026-05")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["risk_alerts"]), 1)

    def test_attendance_dashboard_employee_detail_endpoint(self):
        calendar = self._create_calendar(year=2026, month=5, title="Employee detail test")
        assignment = self._create_assignment(calendar["id"])
        work_status = AttendanceStatus.objects.get(code="work")
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-10",
                "attendance_status": work_status.id,
                "overtime_minutes": 90,
                "actual_work_minutes": 540,
                "memo": "Observacao teste",
            },
            format="json",
        )
        response = self.client.get(f"/api/operations/attendance-dashboard/employees/{self.employee.employee_id}/?month=2026-05")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["employee"]["employee_id"], self.employee.employee_id)
        self.assertGreaterEqual(len(response.data["daily_history"]), 1)

    def test_employee_admin_notes_create_list_and_dashboard_detail(self):
        calendar = self._create_calendar(year=2026, month=5, title="Notes detail test")
        assignment = self._create_assignment(calendar["id"])
        work_status = AttendanceStatus.objects.get(code="work")
        self.client.post(
            f"/api/operations/calendars/{calendar['id']}/cells/",
            {
                "assignment": assignment["id"],
                "date": "2026-05-28",
                "attendance_status": work_status.id,
                "overtime_minutes": 30,
                "actual_work_minutes": 480,
            },
            format="json",
        )

        response = self.client.post(
            "/api/operations/employee-admin-notes/",
            {
                "employee": self.employee.pk,
                "date": "2026-05-28",
                "category": "horas_extras",
                "severity": "warning",
                "note": "Acúmulo de HE no período.",
                "related_period_start": "2026-05-01",
                "related_period_end": "2026-05-28",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get(f"/api/operations/employee-admin-notes/?employee={self.employee.employee_id}")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        items = list_response.data if isinstance(list_response.data, list) else list_response.data.get("results", [])
        self.assertGreaterEqual(len(items), 1)

        detail_response = self.client.get(f"/api/operations/attendance-dashboard/employees/{self.employee.employee_id}/?month=2026-05")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIn("administrative_notes", detail_response.data)

    def test_parse_production_csv_valid(self):
        source = ProductionMonitorSource.objects.create(name="Fonte CSV", source_type=ProductionMonitorSource.SourceType.CSV)
        with NamedTemporaryFile("w", suffix=".csv", delete=True) as fp:
            fp.write(
                "machine_code,equipment_name,status,production_count,target_count,running_minutes,stopped_minutes,alarm_code,timestamp\n"
                "M1,Prensa,running,120,150,80,10,0,2026-05-27 08:00:00\n"
            )
            fp.flush()
            parsed = parse_production_file(source, fp.name, encoding="utf-8", delimiter="auto")
        self.assertEqual(len(parsed["rows"]), 1)
        self.assertEqual(parsed["rows"][0]["machine_code"], "M1")
        self.assertEqual(parsed["rows"][0]["status"], "running")

    def test_parse_production_txt_tab_and_numeric_status(self):
        source = ProductionMonitorSource.objects.create(name="Fonte TXT", source_type=ProductionMonitorSource.SourceType.TXT)
        with NamedTemporaryFile("w", suffix=".txt", delete=True) as fp:
            fp.write(
                "machine_code\tequipment_name\tstatus\tproduction_count\ttarget_count\trunning_minutes\tstopped_minutes\talarm_code\ttimestamp\n"
                "M2\tSolda\t1\t88\t100\t50\t40\tE101\t2026/05/27 08:10:00\n"
            )
            fp.flush()
            parsed = parse_production_file(source, fp.name, encoding="utf-8", delimiter="tab")
        self.assertEqual(parsed["rows"][0]["status"], "stopped")
        self.assertTrue(parsed["rows"][0]["alarm_active"])

    def test_import_production_snapshot_dry_run_does_not_persist(self):
        source = ProductionMonitorSource.objects.create(name="Fonte DryRun", source_type=ProductionMonitorSource.SourceType.CSV)
        existing_count = ProductionSnapshot.objects.count()
        with NamedTemporaryFile("w", suffix=".csv", delete=True) as fp:
            fp.write(
                "machine_code,equipment_name,status,production_count,target_count,running_minutes,stopped_minutes,alarm_code,timestamp\n"
                "M3,Montagem,0,200,220,110,15,0,2026-05-27T08:20:00\n"
            )
            fp.flush()
            call_command(
                "import_production_snapshot",
                "--source",
                str(source.id),
                "--file",
                fp.name,
                "--dry-run",
            )
        self.assertEqual(ProductionSnapshot.objects.count(), existing_count)

    def test_import_production_snapshot_persists_snapshot_status_and_metrics(self):
        source = ProductionMonitorSource.objects.create(name="Fonte Import", source_type=ProductionMonitorSource.SourceType.CSV)
        existing_count = ProductionSnapshot.objects.count()
        with NamedTemporaryFile("w", suffix=".csv", delete=True) as fp:
            fp.write(
                "machine_code,equipment_name,status,production_count,target_count,running_minutes,stopped_minutes,alarm_code,timestamp\n"
                "M4,Linha 4,3,10,100,10,120,E401,2026-05-27 08:30:00\n"
                "M5,Linha 5,0,95,100,105,20,0,2026-05-27 08:30:00\n"
            )
            fp.flush()
            call_command(
                "import_production_snapshot",
                "--source",
                str(source.id),
                "--file",
                fp.name,
                "--encoding",
                "utf-8",
                "--delimiter",
                ",",
            )
        self.assertEqual(ProductionSnapshot.objects.count(), existing_count + 1)
        snapshot = ProductionSnapshot.objects.order_by("-id").first()
        self.assertEqual(snapshot.machine_statuses.count(), 2)
        self.assertTrue(hasattr(snapshot, "metrics"))
        self.assertEqual(snapshot.metrics.error_count, 1)
        self.assertEqual(snapshot.metrics.running_count, 1)
