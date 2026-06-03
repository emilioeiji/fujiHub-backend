import re
import csv
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from master.models import Employee
from master.models import Process, Shift

from .models import (
    AttendanceStatus,
    AttendanceTimecardRecord,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    OperationalCode,
    OperationalPosition,
    ProductionMachineStatus,
    ProductionMetrics,
    ProductionSnapshot,
    ProductionMonitorSource,
    WorkTimeCode,
)


PASTE_TOKEN_SEPARATOR_RE = re.compile(r"[\s+/・]+")
FOUR_TWO_GROUP_OFFSETS = {"A": 0, "B": 2, "C": 4}
DEFAULT_FIVE_TWO_OFF_DAYS = [5, 6]
FIVE_TWO_KEYWORDS = {"supervisor", "manager", "staff", "管理", "スタッフ"}
SPECIAL_ALL_OT_CODES = {"sunday", "holiday_work", "sunday_teiji", "holiday_work_teiji"}
PRODUCTION_STATUS_MAP = {
    "running": ProductionMachineStatus.MachineState.RUNNING,
    "run": ProductionMachineStatus.MachineState.RUNNING,
    "rodando": ProductionMachineStatus.MachineState.RUNNING,
    "0": ProductionMachineStatus.MachineState.RUNNING,
    "stopped": ProductionMachineStatus.MachineState.STOPPED,
    "stop": ProductionMachineStatus.MachineState.STOPPED,
    "parado": ProductionMachineStatus.MachineState.STOPPED,
    "1": ProductionMachineStatus.MachineState.STOPPED,
    "idle": ProductionMachineStatus.MachineState.IDLE,
    "sem_producao": ProductionMachineStatus.MachineState.IDLE,
    "sem producao": ProductionMachineStatus.MachineState.IDLE,
    "2": ProductionMachineStatus.MachineState.IDLE,
    "error": ProductionMachineStatus.MachineState.ERROR,
    "erro": ProductionMachineStatus.MachineState.ERROR,
    "alarm": ProductionMachineStatus.MachineState.ERROR,
    "3": ProductionMachineStatus.MachineState.ERROR,
}
PRODUCTION_FIELD_ALIASES = {
    "machine_code": {"machine_code", "machine", "machineid", "maquina", "equipamento_codigo"},
    "equipment_name": {"equipment_name", "equipment", "equipamento", "machine_name"},
    "process": {"process", "processo"},
    "area": {"area", "linha", "setor"},
    "shift": {"shift", "turno"},
    "status": {"status", "machine_status", "estado"},
    "production_count": {"production_count", "production", "actual", "real", "producao", "production_actual"},
    "target_count": {"target_count", "target", "meta", "pedido", "production_target"},
    "running_minutes": {"running_minutes", "run_minutes", "tempo_rodando"},
    "stopped_minutes": {"stopped_minutes", "stop_minutes", "tempo_parado"},
    "alarm_code": {"alarm_code", "alarm", "alarme"},
    "timestamp": {"timestamp", "datetime", "datahora", "updated_at", "last_update"},
}
TIMECARD_FIELD_ALIASES = {
    "employee_code": {"社員cd", "社員_cd", "employee_code", "employeeid", "employee_id", "code"},
    "employee_name": {"社員氏名", "employee_name", "name", "氏名"},
    "work_date": {"年月日", "work_date", "date", "日付"},
    "work_type_code": {"勤務種類cd", "work_type_code", "worktypecode"},
    "work_type_name": {"勤務種類名", "work_type_name", "worktype", "worktypename"},
    "shift_code": {"就業時間帯cd", "shift_code", "shiftcode"},
    "shift_name": {"就業時間帯名", "shift_name", "shiftname"},
    "clock_in": {"出勤1時刻", "clock_in", "start_time", "in_time"},
    "clock_out": {"退勤1時刻", "clock_out", "end_time", "out_time"},
    "total_work_minutes": {"総労働時間", "total_work_time", "total_work_minutes"},
    "scheduled_work_minutes": {"就業時間", "scheduled_work_time", "scheduled_work_minutes"},
    "overtime_minutes": {"残業", "overtime", "overtime_minutes"},
    "late_minutes": {"遅刻時間1", "late_time", "late_minutes"},
    "early_leave_minutes": {"早退時間1", "early_leave_time", "early_leave_minutes"},
    "memo": {"備考", "memo", "notes"},
}


@dataclass
class ParsedCalendarCellValue:
    position: OperationalPosition | None = None
    attendance_status: AttendanceStatus | None = None
    work_time_code: WorkTimeCode | None = None
    operational_code: OperationalCode | None = None
    memo: str = ""
    recognized: bool = False


def get_group_rank(group_value):
    token = str(group_value or "").strip().upper()
    if token == "A":
        return 10
    if token == "B":
        return 20
    if token == "C":
        return 30
    return 90


def get_visual_category_from_master(employee):
    category = _employee_operational_category(employee)
    if category == CalendarEmployeeAssignment.OperationalCategory.NORMAL:
        return "normal"
    if category == CalendarEmployeeAssignment.OperationalCategory.KOUTEI_LEADER:
        return "koutei_leader"
    if category in {
        CalendarEmployeeAssignment.OperationalCategory.RELIEF,
        CalendarEmployeeAssignment.OperationalCategory.TRAINER,
    }:
        return "relief"
    if category in {
        CalendarEmployeeAssignment.OperationalCategory.GL,
        CalendarEmployeeAssignment.OperationalCategory.SUPERVISOR,
        CalendarEmployeeAssignment.OperationalCategory.MANAGER,
        CalendarEmployeeAssignment.OperationalCategory.DIRECTOR,
    }:
        return "trainer"
    return "normal"


def get_operational_rank(assignment):
    token = str(getattr(assignment, "operational_category", "") or "").strip().lower()
    if token == CalendarEmployeeAssignment.OperationalCategory.NORMAL:
        return 10
    if token == CalendarEmployeeAssignment.OperationalCategory.KOUTEI_LEADER:
        return 20
    if token in {
        CalendarEmployeeAssignment.OperationalCategory.RELIEF,
        CalendarEmployeeAssignment.OperationalCategory.TRAINER,
    }:
        return 30
    if token in {
        CalendarEmployeeAssignment.OperationalCategory.GL,
        CalendarEmployeeAssignment.OperationalCategory.SUPERVISOR,
        CalendarEmployeeAssignment.OperationalCategory.MANAGER,
        CalendarEmployeeAssignment.OperationalCategory.DIRECTOR,
    }:
        return 40
    return 90


def get_assignment_sort_key(assignment):
    employee = getattr(assignment, "employee", None)
    process_code = str(getattr(getattr(employee, "process", None), "code", "") or "").strip().casefold()
    employee_code = str(getattr(employee, "employee_cd", "") or getattr(employee, "employee_id", "") or "").strip().casefold()
    name = str(
        getattr(employee, "name_en", "")
        or getattr(employee, "internal_name", "")
        or getattr(employee, "name_jp", "")
        or ""
    ).strip().casefold()
    return (
        get_operational_rank(assignment),
        get_group_rank(getattr(assignment, "rotation_group", "")),
        process_code,
        int(getattr(assignment, "display_order", 0) or 0),
        employee_code,
        name,
        int(getattr(assignment, "id", 0) or 0),
    )


def generate_calendar_schedule(calendar, user, overwrite=False, default_4x2_anchor_date=None):
    anchor_date = default_4x2_anchor_date or date(2026, 5, 30)
    if isinstance(anchor_date, str):
        anchor_date = date.fromisoformat(anchor_date)

    work_status = AttendanceStatus.objects.get(code="work")
    off_status = AttendanceStatus.objects.get(code="off")
    regular_work_time = WorkTimeCode.objects.get(code="regular")
    month_start = date(calendar.year, calendar.month, 1)
    month_end = date(calendar.year, calendar.month, monthrange(calendar.year, calendar.month)[1])

    result = {
        "created": 0,
        "skipped": 0,
        "updated": 0,
        "total_assignments": 0,
        "total_days": 0,
    }

    assignments = (
        calendar.assignments.filter(is_active=True)
        .select_related("default_position", "employee")
        .order_by("display_order", "employee_id", "id")
    )

    with transaction.atomic():
        for assignment in assignments:
            if assignment.work_pattern == assignment.WorkPattern.MANUAL:
                continue

            result["total_assignments"] += 1
            valid_start = max(month_start, assignment.start_date)
            valid_end = min(month_end, assignment.end_date or month_end)
            if valid_start > valid_end:
                continue

            last_position = assignment.default_position or _last_known_position(calendar, assignment, valid_start)
            current_date = valid_start
            while current_date <= valid_end:
                result["total_days"] += 1
                is_off_day = _is_off_day(assignment, current_date, anchor_date)
                cell_defaults = {
                    "calendar": calendar,
                    "created_by": user,
                }
                cell, was_created = CalendarDayCell.objects.get_or_create(
                    assignment=assignment,
                    date=current_date,
                    defaults=cell_defaults,
                )

                if not was_created and not overwrite:
                    if cell.position_id:
                        last_position = cell.position
                    result["skipped"] += 1
                    current_date += timedelta(days=1)
                    continue

                if is_off_day:
                    cell.position = None
                    cell.attendance_status = off_status
                    cell.work_time_code = None
                    cell.operational_code = None
                    cell.raw_value = "休"
                else:
                    position = assignment.default_position or last_position
                    cell.position = position
                    cell.attendance_status = work_status
                    cell.work_time_code = regular_work_time
                    cell.operational_code = None
                    cell.raw_value = position.code if position else ""
                    if position:
                        last_position = position

                cell.calendar = calendar
                cell.updated_by = user
                calculate_cell_work_minutes(cell, persist=False)
                cell.save()

                if was_created:
                    result["created"] += 1
                else:
                    result["updated"] += 1

                current_date += timedelta(days=1)

    return result


def calculate_cell_work_minutes(cell, persist=True):
    _apply_default_timing_fields(cell)
    scheduled_regular, scheduled_ot = _scheduled_minutes(cell)
    actual_work = scheduled_regular
    actual_ot = scheduled_ot

    effective_end_time = cell.leave_time or cell.end_time
    if effective_end_time and (scheduled_regular or scheduled_ot):
        actual_work, actual_ot = _actual_minutes_from_end_time(cell, scheduled_regular, scheduled_ot, effective_end_time)

    cell.scheduled_regular_minutes = scheduled_regular
    cell.scheduled_overtime_minutes = scheduled_ot
    cell.actual_work_minutes = actual_work
    cell.actual_overtime_minutes = actual_ot
    cell.overtime_minutes = actual_ot

    if persist:
        cell.save(update_fields=[
            "scheduled_regular_minutes",
            "scheduled_overtime_minutes",
            "actual_work_minutes",
            "actual_overtime_minutes",
            "overtime_minutes",
            "start_time",
            "end_time",
            "break_minutes",
            "crosses_midnight",
            "updated_at",
        ])

    return cell


def recalculate_calendar_totals(calendar):
    totals = {}
    queryset = calendar.day_cells.select_related("assignment").order_by("assignment_id")
    for cell in queryset:
        aid = cell.assignment_id
        if aid not in totals:
            totals[aid] = {
                "assignment": aid,
                "scheduled_regular_minutes_total": 0,
                "scheduled_overtime_minutes_total": 0,
                "actual_work_minutes_total": 0,
                "actual_overtime_minutes_total": 0,
                "overload_minutes": 0,
            }
        row = totals[aid]
        row["scheduled_regular_minutes_total"] += cell.scheduled_regular_minutes
        row["scheduled_overtime_minutes_total"] += cell.scheduled_overtime_minutes
        row["actual_work_minutes_total"] += cell.actual_work_minutes
        row["actual_overtime_minutes_total"] += cell.actual_overtime_minutes

    for row in totals.values():
        row["overload_minutes"] = row["actual_overtime_minutes_total"] - row["scheduled_overtime_minutes_total"]
        row["scheduled_regular_hours"] = _format_minutes(row["scheduled_regular_minutes_total"])
        row["scheduled_overtime_hours"] = _format_minutes(row["scheduled_overtime_minutes_total"])
        row["actual_work_hours"] = _format_minutes(row["actual_work_minutes_total"])
        row["actual_overtime_hours"] = _format_minutes(row["actual_overtime_minutes_total"])
        row["overload_hours"] = _format_minutes(row["overload_minutes"])
        # Alias fields kept for frontend compatibility in MVP iterations.
        row["scheduled_regular_formatted"] = row["scheduled_regular_hours"]
        row["scheduled_overtime_formatted"] = row["scheduled_overtime_hours"]
        row["actual_work_formatted"] = row["actual_work_hours"]
        row["actual_overtime_formatted"] = row["actual_overtime_hours"]
        row["overload_formatted"] = row["overload_hours"]
    return list(totals.values())


def import_calendar_employees(calendar, user, import_all=False, employee_ids=None):
    month_start = date(calendar.year, calendar.month, 1)
    employee_ids = employee_ids or []
    existing_employee_ids = set(calendar.assignments.values_list("employee_id", flat=True))

    preview = preview_calendar_employee_candidates(calendar, import_all=import_all, employee_ids=employee_ids)
    candidate_ids = [item["employee_id"] for item in preview["candidates"]]
    candidates = (
        Employee.objects.filter(employee_id__in=candidate_ids)
        .select_related("process", "building_floor", "hire_type", "entry_type", "shift")
        .order_by("employee_id")
    )
    display_order = calendar.assignments.aggregate(max_order=Max("display_order"))["max_order"] or 0
    result = {
        "created": 0,
        "skipped": len(preview["already_linked"]),
        "total_candidates": len(candidate_ids),
        "ignored_count": len(preview["ignored"]),
        "ignored": preview["ignored"],
        "already_linked_count": len(preview["already_linked"]),
        "already_linked": preview["already_linked"],
        "scope": preview["scope"],
        "assignments": [],
    }

    with transaction.atomic():
        for employee in candidates:
            display_order += 1
            assignment = CalendarEmployeeAssignment.objects.create(
                calendar=calendar,
                employee=employee,
                operational_category=_employee_operational_category(employee),
                work_pattern=_employee_work_pattern(employee),
                rotation_group=_employee_rotation_group(employee),
                shift_type=_employee_shift_type(employee),
                five_two_off_days=_employee_five_two_off_days(employee),
                default_position=_infer_default_position(calendar, employee),
                start_date=month_start,
                display_order=display_order,
                created_by=user,
                updated_by=user,
            )
            existing_employee_ids.add(employee.employee_id)
            result["created"] += 1
            result["assignments"].append(assignment.id)

    return result


def sync_calendar_assignments_from_master(calendar, user):
    assignments = calendar.assignments.select_related("employee").order_by("display_order", "employee_id", "id")
    result = {"updated": 0, "unchanged": 0, "skipped": 0, "assignments": []}

    with transaction.atomic():
        for assignment in assignments:
            employee = assignment.employee
            if not employee or not employee.active_end_month or employee.retired or employee.end_work:
                result["skipped"] += 1
                result["assignments"].append({"assignment": assignment.id, "status": "skipped", "reason": "inactive"})
                continue

            updates = {
                "operational_category": _employee_operational_category(employee),
                "work_pattern": _employee_work_pattern(employee),
                "rotation_group": _employee_rotation_group(employee),
                "shift_type": _employee_shift_type(employee),
                "five_two_off_days": _employee_five_two_off_days(employee),
                "default_position": _infer_default_position(calendar, employee),
            }
            changed = False
            for field, value in updates.items():
                current = getattr(assignment, field)
                if field == "default_position":
                    if getattr(current, "id", None) != getattr(value, "id", None):
                        changed = True
                        setattr(assignment, field, value)
                elif current != value:
                    changed = True
                    setattr(assignment, field, value)

            if changed:
                assignment.updated_by = user
                assignment.save(
                    update_fields=[
                        "operational_category",
                        "work_pattern",
                        "rotation_group",
                        "shift_type",
                        "five_two_off_days",
                        "default_position",
                        "updated_by",
                        "updated_at",
                    ]
                )
                result["updated"] += 1
                result["assignments"].append({"assignment": assignment.id, "status": "updated"})
            else:
                result["unchanged"] += 1
                result["assignments"].append({"assignment": assignment.id, "status": "unchanged"})

    return result


def preview_calendar_employee_candidates(calendar, import_all=False, employee_ids=None):
    employee_ids = employee_ids or []
    existing_employee_ids = set(calendar.assignments.values_list("employee_id", flat=True))
    base_queryset = Employee.objects.filter(
        department=calendar.department,
    ).select_related("process", "building_floor", "hire_type", "entry_type", "shift")

    if not import_all:
        base_queryset = base_queryset.filter(employee_id__in=employee_ids)

    candidates = []
    ignored = []
    already_linked = []
    for employee in base_queryset.order_by("employee_id"):
        if employee.employee_id in existing_employee_ids:
            already_linked.append(
                {
                    "employee_id": employee.employee_id,
                    "name": employee.name_en or employee.internal_name or employee.name_jp or "",
                    "reason": "already_linked",
                }
            )
            continue
        valid, reason = _employee_matches_calendar_scope(employee, calendar)
        row = {
            "employee_id": employee.employee_id,
            "name": employee.name_en or employee.internal_name or employee.name_jp or "",
            "shift": getattr(employee.shift, "code", None),
            "process": getattr(employee.process, "code", None),
            "billing_rate": getattr(getattr(employee, "billing_rate", None), "code", None),
            "shift_type": _employee_shift_type(employee),
            "rotation_group": _employee_rotation_group(employee),
            "work_pattern": _employee_work_pattern(employee),
            "operational_category": _employee_operational_category(employee),
            "visual_category": get_visual_category_from_master(employee),
        }
        default_position = _infer_default_position(calendar, employee)
        if default_position:
            row["default_position"] = default_position.id
            row["default_position_code"] = default_position.code
        if valid:
            candidates.append(row)
        else:
            row["reason"] = reason
            ignored.append(row)

    return {
        "scope": {
            "department": getattr(calendar.department, "code", None) if calendar.department_id else None,
            "process": getattr(calendar.process, "code", None) if calendar.process_id else None,
            "shift": getattr(calendar.shift, "code", None) if calendar.shift_id else None,
        },
        "total_base": base_queryset.count(),
        "total_candidates": len(candidates),
        "total_already_linked": len(already_linked),
        "total_ignored": len(ignored),
        "candidates": candidates,
        "already_linked": already_linked,
        "ignored": ignored,
    }


def _employee_matches_calendar_scope(employee, calendar):
    if not employee.active_end_month or employee.retired or employee.end_work:
        return False, "inactive"

    if calendar.process_id:
        if not employee.process_id:
            return False, "missing_employee_process"
        if employee.process_id != calendar.process_id:
            return False, "different_process"

    if calendar.shift_id:
        if not employee.shift_id:
            return False, "missing_employee_shift"
        if employee.shift_id != calendar.shift_id:
            return False, "different_shift"

    return True, ""


def _infer_work_pattern(employee):
    return (
        CalendarEmployeeAssignment.WorkPattern.FIVE_TWO
        if employee.manager_flag or _employee_has_any_keyword(employee, FIVE_TWO_KEYWORDS)
        else CalendarEmployeeAssignment.WorkPattern.FOUR_TWO
    )


def _infer_shift_type(employee):
    shift_text = " ".join(
        str(value or "")
        for value in [
            getattr(employee.shift, "code", ""),
            getattr(employee.shift, "label_pt", ""),
            getattr(employee.shift, "label_jp", ""),
        ]
    ).casefold()
    if any(keyword in shift_text for keyword in {"night", "noite", "夜", "yakin"}):
        return CalendarEmployeeAssignment.ShiftType.NIGHT
    return CalendarEmployeeAssignment.ShiftType.DAY


def _infer_operational_category(employee):
    billing_text = " ".join(
        str(value or "")
        for value in [
            getattr(getattr(employee, "billing_rate", None), "code", ""),
            getattr(getattr(employee, "billing_rate", None), "label_pt", ""),
            getattr(getattr(employee, "billing_rate", None), "label_jp", ""),
            getattr(employee, "rank", ""),
        ]
    ).casefold()
    process_text = " ".join(
        str(value or "")
        for value in [
            getattr(getattr(employee, "process", None), "code", ""),
            getattr(getattr(employee, "process", None), "label_pt", ""),
            getattr(getattr(employee, "process", None), "label_jp", ""),
        ]
    ).casefold()

    if any(keyword in billing_text for keyword in {"kl", "koutei", "工程リーダ", "工程ﾘｰﾀﾞ"}):
        return CalendarEmployeeAssignment.OperationalCategory.KOUTEI_LEADER
    if any(keyword in billing_text for keyword in {"ririfu", "relief", "apoio"}):
        return CalendarEmployeeAssignment.OperationalCategory.RELIEF
    if any(keyword in process_text for keyword in {"ririfu", "relief", "apoio"}):
        return CalendarEmployeeAssignment.OperationalCategory.RELIEF
    if employee.manager_flag or _employee_has_any_keyword(employee, {"manager"}):
        return CalendarEmployeeAssignment.OperationalCategory.MANAGER
    if _employee_has_any_keyword(employee, {"supervisor"}):
        return CalendarEmployeeAssignment.OperationalCategory.SUPERVISOR
    if _employee_has_any_keyword(employee, {"gl"}):
        return CalendarEmployeeAssignment.OperationalCategory.GL
    return CalendarEmployeeAssignment.OperationalCategory.NORMAL


def _employee_work_pattern(employee):
    candidate = (getattr(employee, "work_pattern", "") or "").strip()
    allowed = {
        CalendarEmployeeAssignment.WorkPattern.FOUR_TWO,
        CalendarEmployeeAssignment.WorkPattern.FIVE_TWO,
        CalendarEmployeeAssignment.WorkPattern.MANUAL,
    }
    if candidate in allowed:
        return candidate
    return _infer_work_pattern(employee)


def _employee_shift_type(employee):
    candidate = (getattr(employee, "shift_type", "") or "").strip()
    allowed = {
        CalendarEmployeeAssignment.ShiftType.DAY,
        CalendarEmployeeAssignment.ShiftType.NIGHT,
        CalendarEmployeeAssignment.ShiftType.FLEXIBLE,
    }
    if candidate in allowed:
        return candidate
    return _infer_shift_type(employee)


def _employee_operational_category(employee):
    candidate = _normalize_operational_category_token(getattr(employee, "operational_category", ""))
    allowed = {choice for choice, _ in CalendarEmployeeAssignment.OperationalCategory.choices}
    if candidate in allowed:
        return candidate
    return _infer_operational_category(employee)


def _normalize_operational_category_token(value):
    token = str(value or "").strip().lower()
    if token == "kl":
        return CalendarEmployeeAssignment.OperationalCategory.KOUTEI_LEADER
    if token in {"koutei_leader", "kouteileader"}:
        return CalendarEmployeeAssignment.OperationalCategory.KOUTEI_LEADER
    if token in {"ririfu", "apoio"}:
        return CalendarEmployeeAssignment.OperationalCategory.RELIEF
    if token in {"leader", "lider", "lideranca", "supervisao"}:
        return CalendarEmployeeAssignment.OperationalCategory.SUPERVISOR
    return token


def _employee_rotation_group(employee):
    candidate = (getattr(employee, "rotation_group", "") or "").strip()
    if candidate in FOUR_TWO_GROUP_OFFSETS:
        return candidate
    return "A"


def _employee_five_two_off_days(employee):
    value = getattr(employee, "five_two_off_days", None)
    if not isinstance(value, list):
        return DEFAULT_FIVE_TWO_OFF_DAYS.copy()
    normalized = []
    for day in value:
        try:
            number = int(day)
        except (TypeError, ValueError):
            continue
        if 0 <= number <= 6:
            normalized.append(number)
    return normalized or DEFAULT_FIVE_TWO_OFF_DAYS.copy()


def _employee_has_any_keyword(employee, keywords):
    haystack = " ".join(
        str(value or "")
        for value in [
            employee.contract_type,
            employee.rank,
            employee.notes,
            getattr(employee.hire_type, "code", ""),
            getattr(employee.hire_type, "label_pt", ""),
            getattr(employee.hire_type, "label_jp", ""),
            getattr(employee.entry_type, "code", ""),
            getattr(employee.entry_type, "label_pt", ""),
            getattr(employee.entry_type, "label_jp", ""),
        ]
    ).casefold()
    return any(keyword.casefold() in haystack for keyword in keywords)


def _infer_default_position(calendar, employee):
    queryset = OperationalPosition.objects.filter(department=calendar.department, is_active=True)

    if employee.building_floor_id:
        floor_positions = list(queryset.filter(building_floor=employee.building_floor).order_by("code"))
        if len(floor_positions) == 1:
            return floor_positions[0]

    if employee.process:
        process_terms = {
            employee.process.code,
            employee.process.label_pt,
            employee.process.label_jp,
        }
        for position in queryset.order_by("code"):
            searchable = f"{position.code} {position.name_pt} {position.name_jp}".casefold()
            if any(term and term.casefold() in searchable for term in process_terms):
                return position

    return None


def _is_off_day(assignment, current_date, anchor_date):
    if assignment.work_pattern == assignment.WorkPattern.FIVE_TWO:
        off_days = assignment.five_two_off_days or DEFAULT_FIVE_TWO_OFF_DAYS
        return current_date.weekday() in {int(day) for day in off_days}

    group = assignment.rotation_group or "A"
    group_anchor = anchor_date + timedelta(days=FOUR_TWO_GROUP_OFFSETS.get(group, 0))
    return (current_date - group_anchor).days % 6 in {0, 1}


def _last_known_position(calendar, assignment, before_date):
    previous_cell = (
        CalendarDayCell.objects.filter(
            calendar=calendar,
            assignment=assignment,
            date__lt=before_date,
            position__isnull=False,
        )
        .select_related("position")
        .order_by("-date")
        .first()
    )
    return previous_cell.position if previous_cell else None


def _scheduled_minutes(cell):
    op_code = (getattr(cell.operational_code, "code", "") or "").casefold()
    work_pattern = getattr(cell.assignment, "work_pattern", "")
    regular_4x2 = 540
    regular_5x2 = 480
    overtime_4x2 = 120
    overtime_5x2 = 180

    if op_code in SPECIAL_ALL_OT_CODES:
        return 0, 660
    if op_code == "vaccine":
        return 0, 0

    is_working_day = bool(getattr(cell.attendance_status, "is_working_day", False))
    if not is_working_day:
        return 0, 0

    if work_pattern == CalendarEmployeeAssignment.WorkPattern.FIVE_TWO:
        regular = regular_5x2
        overtime = overtime_5x2
    else:
        regular = regular_4x2
        overtime = overtime_4x2

    if op_code.endswith("teiji") or op_code == "teiji":
        overtime = 0

    return regular, overtime


def _actual_minutes_from_end_time(cell, scheduled_regular, scheduled_overtime, end_time):
    total_planned = scheduled_regular + scheduled_overtime
    if total_planned <= 0:
        return 0, 0

    start_minutes = _minutes_of_day(cell.start_time or time(8, 30))
    end_minutes = _minutes_of_day(end_time)
    gross = _elapsed_minutes(start_minutes, end_minutes, bool(cell.crosses_midnight))
    if not cell.crosses_midnight and end_minutes < start_minutes:
        gross = _elapsed_minutes(start_minutes, end_minutes, True)

    break_applied = _break_deduction(gross, int(cell.break_minutes or 0))
    worked = max(0, gross - break_applied)

    op_code = (getattr(cell.operational_code, "code", "") or "").casefold()
    if op_code in SPECIAL_ALL_OT_CODES:
        return 0, worked

    if op_code.endswith("teiji") or op_code == "teiji":
        teiji_regular = 480 if cell.assignment.work_pattern == CalendarEmployeeAssignment.WorkPattern.FIVE_TWO else 540
        actual_work = min(worked, teiji_regular)
        actual_ot = max(0, worked - teiji_regular)
        return actual_work, actual_ot

    actual_work = min(worked, scheduled_regular)
    actual_ot = max(0, worked - scheduled_regular)
    return actual_work, actual_ot


def _format_minutes(minutes):
    sign = "-" if minutes < 0 else ""
    value = abs(int(minutes))
    return f"{sign}{value // 60:02d}:{value % 60:02d}"


def _apply_default_timing_fields(cell):
    if cell.manual_time_override:
        return

    work_pattern = getattr(cell.assignment, "work_pattern", "")
    shift_type = getattr(cell.assignment, "shift_type", CalendarEmployeeAssignment.ShiftType.DAY)

    if work_pattern == CalendarEmployeeAssignment.WorkPattern.FOUR_TWO and shift_type == CalendarEmployeeAssignment.ShiftType.NIGHT:
        cell.start_time = time(20, 30)
        cell.end_time = time(8, 35)
        cell.crosses_midnight = True
        cell.break_minutes = 65
        return

    if work_pattern == CalendarEmployeeAssignment.WorkPattern.FOUR_TWO:
        cell.start_time = time(8, 30)
        cell.end_time = time(20, 35)
        cell.crosses_midnight = False
        cell.break_minutes = 65
        return

    if work_pattern == CalendarEmployeeAssignment.WorkPattern.FIVE_TWO:
        cell.start_time = time(8, 30)
        cell.end_time = time(20, 35)
        cell.crosses_midnight = False
        cell.break_minutes = 65
        return

    if not cell.start_time:
        cell.start_time = time(8, 30)
    if cell.end_time is None:
        cell.end_time = time(20, 35)


def _minutes_of_day(value):
    return value.hour * 60 + value.minute


def _elapsed_minutes(start_minutes, end_minutes, crosses_midnight):
    if crosses_midnight:
        if end_minutes >= start_minutes:
            return end_minutes - start_minutes
        return (24 * 60 - start_minutes) + end_minutes
    return max(0, end_minutes - start_minutes)


def _break_deduction(gross_minutes, configured_break):
    if gross_minutes < 240:
        return 0
    if gross_minutes < 360:
        return min(20, configured_break)
    return min(configured_break, gross_minutes)


def build_calendar_cell_parser_context(calendar):
    return {
        "positions": _build_lookup(
            OperationalPosition.objects.filter(department=calendar.department, is_active=True),
            fields=("code", "name_pt", "name_jp"),
        ),
        "attendance_statuses": _build_lookup(
            AttendanceStatus.objects.filter(is_active=True),
            fields=("code", "label_pt", "label_jp"),
        ),
        "work_time_codes": _build_lookup(
            WorkTimeCode.objects.filter(is_active=True),
            fields=("code", "label_pt", "label_jp"),
        ),
        "operational_codes": _build_lookup(
            OperationalCode.objects.filter(is_active=True),
            fields=("code", "label_pt", "label_jp"),
        ),
    }


def parse_calendar_cell_value(value, context):
    raw_value = str(value or "").strip()
    if not raw_value:
        return ParsedCalendarCellValue(recognized=True)

    exact_key = _normalize_lookup_value(raw_value)
    exact_match = _match_token(exact_key, context)
    if exact_match:
        operational_code = exact_match.get("operational_code")
        attendance_status = exact_match.get("attendance_status")
        work_time_code = exact_match.get("work_time_code")
        if operational_code:
            attendance_status = attendance_status or operational_code.attendance_status
            work_time_code = work_time_code or operational_code.work_time_code
        return ParsedCalendarCellValue(
            position=exact_match.get("position"),
            attendance_status=attendance_status,
            work_time_code=work_time_code,
            operational_code=operational_code,
            recognized=True,
        )

    parsed = ParsedCalendarCellValue()
    memo_tokens = []
    for token in _tokenize_cell_value(raw_value):
        key = _normalize_lookup_value(token)
        match = _match_token(key, context)
        if match:
            if match["operational_code"] and parsed.operational_code is None:
                parsed.operational_code = match["operational_code"]
                if parsed.attendance_status is None and match["operational_code"].attendance_status:
                    parsed.attendance_status = match["operational_code"].attendance_status
                if parsed.work_time_code is None and match["operational_code"].work_time_code:
                    parsed.work_time_code = match["operational_code"].work_time_code
                continue
            if match["position"] and parsed.position is None:
                parsed.position = match["position"]
                continue
            if match["attendance_status"] and parsed.attendance_status is None:
                parsed.attendance_status = match["attendance_status"]
                continue
            if match["work_time_code"] and parsed.work_time_code is None:
                parsed.work_time_code = match["work_time_code"]
                continue

        memo_tokens.append(token)

    parsed.memo = " ".join(memo_tokens).strip()
    parsed.recognized = bool(parsed.position or parsed.attendance_status or parsed.work_time_code or parsed.operational_code)
    if not parsed.recognized:
        parsed.memo = raw_value

    return parsed


def _match_token(key, context):
    operational_code = context["operational_codes"].get(key)
    position = context["positions"].get(key)
    attendance_status = context["attendance_statuses"].get(key)
    work_time_code = context["work_time_codes"].get(key)
    if not position and not attendance_status and not work_time_code and not operational_code:
        return None

    return {
        "operational_code": operational_code,
        "position": position,
        "attendance_status": attendance_status,
        "work_time_code": work_time_code,
    }


def _tokenize_cell_value(value):
    return [token for token in PASTE_TOKEN_SEPARATOR_RE.split(value.replace("\r\n", "\n")) if token]


def _build_lookup(queryset, fields):
    lookup = {}
    for obj in queryset:
        for field in fields:
            value = getattr(obj, field, "")
            if value:
                lookup[_normalize_lookup_value(value)] = obj
    return lookup


def _normalize_lookup_value(value):
    return str(value or "").strip().casefold()


def parse_production_file(source, file_path, *, encoding="utf-8", delimiter="auto"):
    file_content = Path(file_path).read_text(encoding=encoding)
    rows = [line for line in file_content.splitlines() if line.strip()]
    if not rows:
        raise ValueError("Arquivo vazio.")

    resolved_delimiter = _resolve_delimiter(rows[0], delimiter)
    reader = csv.DictReader(rows, delimiter=resolved_delimiter)
    if not reader.fieldnames:
        raise ValueError("Arquivo sem cabeçalho válido.")

    field_map = _build_production_field_map(reader.fieldnames)
    normalized_rows = []
    warnings = []
    captured_at = None

    for idx, row in enumerate(reader, start=2):
        normalized = _normalize_production_row(row, field_map, source=source)
        if not normalized:
            continue
        normalized_rows.append(normalized)
        row_timestamp = normalized.get("timestamp")
        if row_timestamp and (captured_at is None or row_timestamp > captured_at):
            captured_at = row_timestamp
        if normalized.get("status") == "unknown":
            warnings.append(f"Linha {idx}: status desconhecido, aplicado 'unknown'.")

    if not normalized_rows:
        raise ValueError("Nenhum registro válido encontrado no arquivo.")

    return {
        "rows": normalized_rows,
        "captured_at": captured_at or timezone.now(),
        "delimiter": resolved_delimiter,
        "warnings": warnings,
    }


def import_production_snapshot(
    *,
    source,
    file_path,
    encoding="utf-8",
    delimiter="auto",
    shift=None,
    process=None,
    area="",
    dry_run=False,
    user=None,
):
    parsed = parse_production_file(source, file_path, encoding=encoding, delimiter=delimiter)
    rows = parsed["rows"]
    captured_at = parsed["captured_at"]
    shift_obj = _resolve_shift(shift)
    process_obj = _resolve_process(process)
    area_value = area or (rows[0].get("area") if rows else "") or getattr(source, "area", "")

    normalized_rows = []
    for row in rows:
        row_process = process_obj or _resolve_process(row.get("process"))
        row_shift = shift_obj or _resolve_shift(row.get("shift"))
        normalized_rows.append(
            {
                **row,
                "process": row_process,
                "shift": row_shift,
            }
        )

    if dry_run:
        metrics = _calculate_production_metrics(normalized_rows)
        return {
            "dry_run": True,
            "created_snapshot_id": None,
            "rows_count": len(normalized_rows),
            "metrics": metrics,
            "captured_at": captured_at,
            "warnings": parsed["warnings"],
        }

    with transaction.atomic():
        duplicate_exists = ProductionSnapshot.objects.filter(
            source=source,
            captured_at=captured_at,
            process=process_obj,
            shift=shift_obj,
            area=area_value,
        ).exists()
        if duplicate_exists:
            captured_at = captured_at + timedelta(seconds=1)
            parsed["warnings"].append("Timestamp duplicado detectado; nova versão criada com +1s.")

        snapshot = ProductionSnapshot.objects.create(
            source=source,
            captured_at=captured_at,
            shift=shift_obj,
            process=process_obj,
            area=area_value,
            created_by=user,
            updated_by=user,
        )

        machine_objects = []
        for row in normalized_rows:
            target_count = row["target_count"]
            actual_count = row["production_count"]
            kadouritsu = round((actual_count / target_count) * 100, 2) if target_count > 0 else 0
            machine_objects.append(
                ProductionMachineStatus(
                    snapshot=snapshot,
                    machine_code=row["machine_code"],
                    equipment_name=row["equipment_name"],
                    status=row["status"],
                    production_actual=actual_count,
                    production_target=target_count,
                    kadouritsu=kadouritsu,
                    run_minutes=row["running_minutes"],
                    stop_minutes=row["stopped_minutes"],
                    last_update_at=row["timestamp"],
                    alarm_active=row["alarm_active"],
                    created_by=user,
                    updated_by=user,
                )
            )
        ProductionMachineStatus.objects.bulk_create(machine_objects)
        metrics_data = _calculate_production_metrics(normalized_rows)
        ProductionMetrics.objects.create(
            snapshot=snapshot,
            total_actual=metrics_data["production_total"],
            total_target=metrics_data["target_total"],
            average_kadouritsu=metrics_data["average_kadouritsu"],
            running_count=metrics_data["running_count"],
            stopped_count=metrics_data["stopped_count"],
            idle_count=metrics_data["idle_count"],
            error_count=metrics_data["error_count"],
            alarms_active=metrics_data["alarms_active"],
            created_by=user,
            updated_by=user,
        )

    return {
        "dry_run": False,
        "created_snapshot_id": snapshot.id,
        "rows_count": len(normalized_rows),
        "metrics": metrics_data,
        "captured_at": captured_at,
        "warnings": parsed["warnings"],
    }


def _resolve_delimiter(header_line, delimiter):
    if delimiter in {",", "tab", "semicolon"}:
        if delimiter == "tab":
            return "\t"
        if delimiter == "semicolon":
            return ";"
        return delimiter
    if delimiter not in {"auto", None, ""}:
        return delimiter
    candidates = [(",", header_line.count(",")), ("\t", header_line.count("\t")), (";", header_line.count(";"))]
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0][0] if candidates[0][1] > 0 else ","


def _build_production_field_map(fieldnames):
    mapping = {}
    normalized = {name: _normalize_lookup_value(name).replace("-", "_").replace(" ", "_") for name in fieldnames}
    for target_field, aliases in PRODUCTION_FIELD_ALIASES.items():
        for original, normalized_name in normalized.items():
            if normalized_name in aliases:
                mapping[target_field] = original
                break
    missing = [required for required in ("machine_code", "status", "production_count", "target_count") if required not in mapping]
    if missing:
        raise ValueError(f"Cabeçalho inválido. Campos obrigatórios ausentes: {', '.join(missing)}")
    return mapping


def _normalize_production_row(row, field_map, *, source):
    machine_code = _read_field(row, field_map, "machine_code")
    if not machine_code:
        return None
    equipment_name = _read_field(row, field_map, "equipment_name") or machine_code
    status_token = _read_field(row, field_map, "status")
    status = _normalize_production_status(status_token)
    production_count = _to_int(_read_field(row, field_map, "production_count"))
    target_count = _to_int(_read_field(row, field_map, "target_count"))
    running_minutes = _to_int(_read_field(row, field_map, "running_minutes"))
    stopped_minutes = _to_int(_read_field(row, field_map, "stopped_minutes"))
    alarm_code = _read_field(row, field_map, "alarm_code")
    timestamp_value = _read_field(row, field_map, "timestamp")

    return {
        "machine_code": machine_code,
        "equipment_name": equipment_name,
        "process": _read_field(row, field_map, "process") or getattr(getattr(source, "process", None), "code", ""),
        "area": _read_field(row, field_map, "area") or getattr(source, "area", ""),
        "shift": _read_field(row, field_map, "shift"),
        "status": status,
        "production_count": production_count,
        "target_count": target_count,
        "running_minutes": running_minutes,
        "stopped_minutes": stopped_minutes,
        "alarm_active": _normalize_alarm(alarm_code),
        "timestamp": _parse_timestamp(timestamp_value),
    }


def _read_field(row, field_map, target):
    source_key = field_map.get(target)
    if not source_key:
        return ""
    return str(row.get(source_key, "") or "").strip()


def _normalize_production_status(value):
    token = _normalize_lookup_value(value).replace("-", "_")
    return PRODUCTION_STATUS_MAP.get(token, "unknown")


def _normalize_alarm(value):
    token = _normalize_lookup_value(value)
    if token in {"", "0", "ok", "none", "normal"}:
        return False
    return True


def _to_int(value):
    token = str(value or "").strip()
    if not token:
        return 0
    token = token.replace(",", "")
    try:
        return int(float(token))
    except ValueError:
        return 0


def _parse_timestamp(value):
    token = str(value or "").strip()
    if not token:
        return timezone.now()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(token, fmt)
            return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(token)
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except ValueError:
        return timezone.now()


def _resolve_shift(value):
    if not value:
        return None
    token = str(value).strip()
    if not token:
        return None
    if token.isdigit():
        return Shift.objects.filter(pk=int(token)).first()
    return Shift.objects.filter(code__iexact=token).first()


def _resolve_process(value):
    if not value:
        return None
    token = str(value).strip()
    if not token:
        return None
    if token.isdigit():
        return Process.objects.filter(pk=int(token)).first()
    return Process.objects.filter(code__iexact=token).first()


def _calculate_production_metrics(rows):
    production_total = sum(item["production_count"] for item in rows)
    target_total = sum(item["target_count"] for item in rows)
    kadouritsu_list = []
    running_count = 0
    stopped_count = 0
    idle_count = 0
    error_count = 0
    alarms_active = 0

    for item in rows:
        target = item["target_count"]
        actual = item["production_count"]
        kadouritsu_list.append((actual / target) * 100 if target > 0 else 0)
        status = item["status"]
        if status == ProductionMachineStatus.MachineState.RUNNING:
            running_count += 1
        elif status == ProductionMachineStatus.MachineState.STOPPED:
            stopped_count += 1
        elif status == ProductionMachineStatus.MachineState.IDLE:
            idle_count += 1
        elif status == ProductionMachineStatus.MachineState.ERROR:
            error_count += 1
        if item["alarm_active"]:
            alarms_active += 1

    average_kadouritsu = round(sum(kadouritsu_list) / len(kadouritsu_list), 2) if kadouritsu_list else 0
    return {
        "production_total": production_total,
        "target_total": target_total,
        "difference_total": production_total - target_total,
        "average_kadouritsu": average_kadouritsu,
        "running_count": running_count,
        "stopped_count": stopped_count,
        "idle_count": idle_count,
        "error_count": error_count,
        "alarms_active": alarms_active,
    }


def parse_timecard_csv(file_path, *, encoding="cp932", delimiter="auto", month=None):
    raw_text = Path(file_path).read_text(encoding=encoding)
    rows = [line for line in raw_text.splitlines() if line.strip()]
    if not rows:
        raise ValueError("Arquivo vazio.")

    resolved_delimiter = _resolve_delimiter(rows[0], delimiter)
    reader = csv.DictReader(rows, delimiter=resolved_delimiter)
    if not reader.fieldnames:
        raise ValueError("Arquivo sem cabeçalho válido.")

    field_map = _build_timecard_field_map(reader.fieldnames)
    expected_month = None
    if month:
        expected_month = date.fromisoformat(f"{month}-01").replace(day=1)

    normalized_rows = []
    warnings = []
    for idx, row in enumerate(reader, start=2):
        normalized = _normalize_timecard_row(row, field_map)
        if not normalized:
            continue
        if expected_month and normalized["work_date"].replace(day=1) != expected_month:
            warnings.append(f"Linha {idx}: registro fora do mês {month}, ignorado.")
            continue
        normalized_rows.append(normalized)

    if not normalized_rows:
        raise ValueError("Nenhum registro de cartão ponto válido encontrado.")

    return {
        "rows": normalized_rows,
        "delimiter": resolved_delimiter,
        "warnings": warnings,
    }


def import_timecard_csv(*, file_path, encoding="cp932", delimiter="auto", month=None, dry_run=False, source_file=None, user=None):
    parsed = parse_timecard_csv(file_path, encoding=encoding, delimiter=delimiter, month=month)
    rows = parsed["rows"]
    created = 0
    updated = 0
    duplicate_count = 0
    source_label = source_file or str(file_path)

    if dry_run:
        return {
            "dry_run": True,
            "created": 0,
            "updated": 0,
            "duplicate_count": 0,
            "rows_count": len(rows),
            "warnings": parsed["warnings"],
            "records": rows,
        }

    with transaction.atomic():
        for row in rows:
            defaults = {
                "employee_code_raw": row["employee_code_raw"],
                "employee_name": row["employee_name"],
                "work_type_code": row["work_type_code"],
                "work_type_name": row["work_type_name"],
                "shift_code": row["shift_code"],
                "shift_name": row["shift_name"],
                "clock_in": row["clock_in"],
                "clock_out": row["clock_out"],
                "total_work_minutes": row["total_work_minutes"],
                "scheduled_work_minutes": row["scheduled_work_minutes"],
                "overtime_minutes": row["overtime_minutes"],
                "late_minutes": row["late_minutes"],
                "early_leave_minutes": row["early_leave_minutes"],
                "memo": row["memo"],
                "source_file": source_label,
                "updated_by": user,
            }
            obj, is_created = AttendanceTimecardRecord.objects.update_or_create(
                employee_code_normalized=row["employee_code_normalized"],
                work_date=row["work_date"],
                defaults={**defaults, "created_by": user},
            )
            if is_created:
                created += 1
            else:
                updated += 1
        duplicate_count = len(rows) - created

    return {
        "dry_run": False,
        "created": created,
        "updated": updated,
        "duplicate_count": duplicate_count,
        "rows_count": len(rows),
        "warnings": parsed["warnings"],
    }


def compare_timecard_to_calendar(calendar, records=None):
    if records is None:
        records = AttendanceTimecardRecord.objects.all()

    day_cells = (
        CalendarDayCell.objects.filter(calendar=calendar)
        .select_related("assignment", "assignment__employee", "attendance_status", "work_time_code")
    )
    relevant_employee_codes = {
        _normalize_employee_code(
            getattr(cell.assignment.employee, "employee_cd", "") or getattr(cell.assignment.employee, "employee_id", "")
        )
        for cell in day_cells
        if getattr(cell.assignment, "employee", None)
    }
    records = [
        record
        for record in records
        if record.employee_code_normalized in relevant_employee_codes
        and record.work_date.year == calendar.year
        and record.work_date.month == calendar.month
    ]
    record_map = {
        (record.employee_code_normalized, record.work_date): record
        for record in records
    }

    divergences = []
    matched_keys = set()
    for cell in day_cells:
        employee = getattr(cell.assignment, "employee", None)
        employee_code = _normalize_employee_code(getattr(employee, "employee_cd", "") or getattr(employee, "employee_id", ""))
        employee_name = (
            getattr(employee, "name_en", None)
            or getattr(employee, "internal_name", None)
            or getattr(employee, "name_jp", None)
            or ""
        )
        record = record_map.get((employee_code, cell.date))
        planned_minutes = int(cell.scheduled_regular_minutes or 0) + int(cell.scheduled_overtime_minutes or 0)
        planned_overtime = int(cell.scheduled_overtime_minutes or 0)

        if not record:
            if getattr(cell.attendance_status, "is_working_day", False):
                divergences.append(
                    {
                        "employee_code": employee_code,
                        "employee_name": employee_name,
                        "date": cell.date,
                        "type": "missing_timecard",
                        "severity": "warning",
                        "expected": "Registro de ponto",
                        "actual": "Sem registro",
                        "message": "Escala marcou trabalho, mas nao existe registro de ponto.",
                    }
                )
            continue
        matched_keys.add((employee_code, cell.date))

        actual_work = int(record.total_work_minutes or 0)
        actual_overtime = int(record.overtime_minutes or 0)
        record_name = record.employee_name or employee_name

        if not getattr(cell.attendance_status, "is_working_day", False) and actual_work > 0:
            divergences.append(
                {
                    "employee_code": employee_code,
                    "employee_name": record_name,
                    "date": cell.date,
                    "type": "worked_on_day_off",
                    "severity": "warning",
                    "expected": "Folga",
                    "actual": "Trabalho registrado",
                    "message": "Escala marcou folga, mas o ponto mostra trabalho.",
                }
            )

        if int(record.late_minutes or 0) > 0:
            divergences.append(
                {
                    "employee_code": employee_code,
                    "employee_name": record_name,
                    "date": cell.date,
                    "type": "late",
                    "severity": "warning",
                    "expected": "Sem atraso",
                    "actual": f"{int(record.late_minutes or 0)} min",
                    "message": "Registro aponta atraso.",
                }
            )

        if int(record.early_leave_minutes or 0) > 0:
            divergences.append(
                {
                    "employee_code": employee_code,
                    "employee_name": record_name,
                    "date": cell.date,
                    "type": "early_leave",
                    "severity": "warning",
                    "expected": "Sem saída antecipada",
                    "actual": f"{int(record.early_leave_minutes or 0)} min",
                    "message": "Registro aponta saida antecipada.",
                }
            )

        if planned_minutes and actual_work != planned_minutes:
            divergences.append(
                {
                    "employee_code": employee_code,
                    "employee_name": record_name,
                    "date": cell.date,
                    "type": "work_minutes_mismatch",
                    "severity": "warning",
                    "expected": f"{planned_minutes} min",
                    "actual": f"{actual_work} min",
                    "message": "Jornada real difere da prevista.",
                    "planned_minutes": planned_minutes,
                    "actual_minutes": actual_work,
                }
            )

        if planned_overtime != actual_overtime:
            divergences.append(
                {
                    "employee_code": employee_code,
                    "employee_name": record_name,
                    "date": cell.date,
                    "type": "overtime_mismatch",
                    "severity": "warning",
                    "expected": f"{planned_overtime} min",
                    "actual": f"{actual_overtime} min",
                    "message": "Hora extra real difere da planejada.",
                    "planned_overtime_minutes": planned_overtime,
                    "actual_overtime_minutes": actual_overtime,
                }
            )

    for record in records:
        key = (record.employee_code_normalized, record.work_date)
        if key in matched_keys:
            continue
        divergences.append(
            {
                "employee_code": record.employee_code_normalized,
                "employee_name": record.employee_name or "",
                "date": record.work_date,
                "type": "timecard_without_calendar_cell",
                "severity": "warning",
                "expected": "Célula de escala correspondente",
                "actual": "Registro sem célula",
                "message": "Registro de ponto sem célula correspondente no calendário.",
            }
        )

    return divergences


def _build_timecard_field_map(fieldnames):
    mapping = {}
    normalized = {name: _normalize_lookup_value(name).replace("-", "_").replace(" ", "_") for name in fieldnames}
    for target_field, aliases in TIMECARD_FIELD_ALIASES.items():
        for original, normalized_name in normalized.items():
            if normalized_name in aliases:
                mapping[target_field] = original
                break

    missing = [
        required
        for required in ("employee_code", "employee_name", "work_date", "clock_in", "clock_out", "total_work_minutes")
        if required not in mapping
    ]
    if missing:
        raise ValueError(f"Cabeçalho inválido. Campos obrigatórios ausentes: {', '.join(missing)}")
    return mapping


def _normalize_timecard_row(row, field_map):
    raw_code = _read_field(row, field_map, "employee_code")
    normalized_code = _normalize_employee_code(raw_code)
    if not normalized_code:
        return None

    work_date = _parse_date(_read_field(row, field_map, "work_date"))
    if not work_date:
        return None

    return {
        "employee_code_raw": raw_code,
        "employee_code_normalized": normalized_code,
        "employee_name": _read_field(row, field_map, "employee_name"),
        "work_date": work_date,
        "work_type_code": _read_field(row, field_map, "work_type_code"),
        "work_type_name": _read_field(row, field_map, "work_type_name"),
        "shift_code": _read_field(row, field_map, "shift_code"),
        "shift_name": _read_field(row, field_map, "shift_name"),
        "clock_in": _parse_time(_read_field(row, field_map, "clock_in")),
        "clock_out": _parse_time(_read_field(row, field_map, "clock_out")),
        "total_work_minutes": _parse_duration_minutes(_read_field(row, field_map, "total_work_minutes")),
        "scheduled_work_minutes": _parse_duration_minutes(_read_field(row, field_map, "scheduled_work_minutes")),
        "overtime_minutes": _parse_duration_minutes(_read_field(row, field_map, "overtime_minutes")),
        "late_minutes": _parse_duration_minutes(_read_field(row, field_map, "late_minutes")),
        "early_leave_minutes": _parse_duration_minutes(_read_field(row, field_map, "early_leave_minutes")),
        "memo": _read_field(row, field_map, "memo"),
    }


def _normalize_employee_code(value):
    token = str(value or "").strip()
    if not token:
        return ""
    if token[-1:].upper() in {"A", "B", "C"} and token[:-1].isdigit():
        return token[:-1]
    return token


def _parse_date(value):
    token = str(value or "").strip()
    if not token:
        return None
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(token, fmt)
            return parsed.date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(token).date()
    except ValueError:
        return None


def _parse_time(value):
    token = str(value or "").strip()
    if not token:
        return None
    if token in {"-","--"}:
        return None
    formats = ["%H:%M", "%H:%M:%S", "%H%M", "%H.%M"]
    for fmt in formats:
        try:
            return datetime.strptime(token, fmt).time()
        except ValueError:
            continue
    return None


def _parse_duration_minutes(value):
    token = str(value or "").strip()
    if not token:
        return 0
    if token in {"-", "--"}:
        return 0
    if ":" in token:
        parts = token.split(":")
        try:
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            return hours * 60 + minutes
        except ValueError:
            return 0
    token = token.replace(",", "")
    try:
        return int(float(token))
    except ValueError:
        return 0
