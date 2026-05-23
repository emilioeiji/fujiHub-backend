from datetime import date

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from master.models import BuildingFloor, Department, Employee, Process, Shift

from .models import (
    AttendanceStatus,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    CalendarPrintPreset,
    MonthlyOperationCalendar,
    OperationalPosition,
    PositionDailyRequirement,
    WorkTimeCode,
)


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
        )
        self.second_employee = Employee.objects.create(
            employee_id="EMP-OPS-API-002",
            name_jp="鈴木一郎",
            name_en="Ichiro Suzuki",
            department=self.department,
            process=self.process,
            shift=self.shift,
            building_floor=self.building_floor,
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

    def _create_calendar(self):
        response = self.client.post(
            "/api/operations/calendars/",
            {
                "department": self.department.pk,
                "process": self.process.pk,
                "shift": self.shift.pk,
                "year": 2026,
                "month": 5,
                "title": "54532 - Maio 2026",
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

    def _create_assignment(self, calendar_id):
        response = self.client.post(
            f"/api/operations/calendars/{calendar_id}/assignments/",
            {
                "employee": self.employee.pk,
                "operational_category": "normal",
                "start_date": "2026-05-01",
                "display_order": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data

    def _create_second_assignment(self, calendar_id):
        response = self.client.post(
            f"/api/operations/calendars/{calendar_id}/assignments/",
            {
                "employee": self.second_employee.pk,
                "operational_category": "normal",
                "start_date": "2026-05-01",
                "display_order": 2,
            },
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
        self.assertEqual(cell.memo, "ワクチン")

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
