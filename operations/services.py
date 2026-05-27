import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, time, timedelta

from django.db import transaction
from django.db.models import Max

from master.models import Employee

from .models import (
    AttendanceStatus,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    OperationalCode,
    OperationalPosition,
    WorkTimeCode,
)


PASTE_TOKEN_SEPARATOR_RE = re.compile(r"[\s+/・]+")
FOUR_TWO_GROUP_OFFSETS = {"A": 0, "B": 2, "C": 4}
DEFAULT_FIVE_TWO_OFF_DAYS = [5, 6]
FIVE_TWO_KEYWORDS = {"supervisor", "manager", "staff", "管理", "スタッフ"}
SPECIAL_ALL_OT_CODES = {"sunday", "holiday_work", "sunday_teiji", "holiday_work_teiji"}


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
