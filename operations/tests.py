from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

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
