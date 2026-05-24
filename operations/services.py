import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

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


@dataclass
class ParsedCalendarCellValue:
    position: OperationalPosition | None = None
    attendance_status: AttendanceStatus | None = None
    work_time_code: WorkTimeCode | None = None
    operational_code: OperationalCode | None = None
    memo: str = ""
    recognized: bool = False


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
                cell.save()

                if was_created:
                    result["created"] += 1
                else:
                    result["updated"] += 1

                current_date += timedelta(days=1)

    return result


def import_calendar_employees(calendar, user, import_all=False, employee_ids=None):
    month_start = date(calendar.year, calendar.month, 1)
    employee_ids = employee_ids or []
    existing_employee_ids = set(calendar.assignments.values_list("employee_id", flat=True))

    candidates = _calendar_employee_candidates(calendar, import_all=import_all, employee_ids=employee_ids)
    display_order = calendar.assignments.aggregate(max_order=Max("display_order"))["max_order"] or 0
    result = {
        "created": 0,
        "skipped": 0,
        "total_candidates": candidates.count(),
        "assignments": [],
    }

    with transaction.atomic():
        for employee in candidates:
            if employee.employee_id in existing_employee_ids:
                result["skipped"] += 1
                continue

            display_order += 1
            assignment = CalendarEmployeeAssignment.objects.create(
                calendar=calendar,
                employee=employee,
                operational_category=_infer_operational_category(employee),
                work_pattern=_infer_work_pattern(employee),
                rotation_group="A",
                five_two_off_days=DEFAULT_FIVE_TWO_OFF_DAYS.copy(),
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


def _calendar_employee_candidates(calendar, import_all=False, employee_ids=None):
    queryset = Employee.objects.filter(
        department=calendar.department,
        active_end_month=True,
        retired__isnull=True,
        end_work__isnull=True,
    ).select_related("process", "building_floor", "hire_type", "entry_type")

    if import_all:
        return queryset.order_by("employee_id")

    return queryset.filter(employee_id__in=employee_ids or []).order_by("employee_id")


def _infer_work_pattern(employee):
    return (
        CalendarEmployeeAssignment.WorkPattern.FIVE_TWO
        if employee.manager_flag or _employee_has_any_keyword(employee, FIVE_TWO_KEYWORDS)
        else CalendarEmployeeAssignment.WorkPattern.FOUR_TWO
    )


def _infer_operational_category(employee):
    if employee.manager_flag or _employee_has_any_keyword(employee, {"manager"}):
        return CalendarEmployeeAssignment.OperationalCategory.MANAGER
    if _employee_has_any_keyword(employee, {"supervisor"}):
        return CalendarEmployeeAssignment.OperationalCategory.SUPERVISOR
    if _employee_has_any_keyword(employee, {"gl"}):
        return CalendarEmployeeAssignment.OperationalCategory.GL
    return CalendarEmployeeAssignment.OperationalCategory.NORMAL


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
