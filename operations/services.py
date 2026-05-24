import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction

from .models import AttendanceStatus, CalendarDayCell, OperationalPosition, WorkTimeCode


PASTE_TOKEN_SEPARATOR_RE = re.compile(r"[\s+/・]+")
FOUR_TWO_GROUP_OFFSETS = {"A": 0, "B": 2, "C": 4}
DEFAULT_FIVE_TWO_OFF_DAYS = [5, 6]


@dataclass
class ParsedCalendarCellValue:
    position: OperationalPosition | None = None
    attendance_status: AttendanceStatus | None = None
    work_time_code: WorkTimeCode | None = None
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
                    cell.raw_value = "休"
                else:
                    position = assignment.default_position or last_position
                    cell.position = position
                    cell.attendance_status = work_status
                    cell.work_time_code = regular_work_time
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
    }


def parse_calendar_cell_value(value, context):
    raw_value = str(value or "").strip()
    if not raw_value:
        return ParsedCalendarCellValue(recognized=True)

    exact_key = _normalize_lookup_value(raw_value)
    exact_match = _match_token(exact_key, context)
    if exact_match:
        return ParsedCalendarCellValue(**exact_match, recognized=True)

    parsed = ParsedCalendarCellValue()
    memo_tokens = []
    for token in _tokenize_cell_value(raw_value):
        key = _normalize_lookup_value(token)
        match = _match_token(key, context)
        if match:
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
    parsed.recognized = bool(parsed.position or parsed.attendance_status or parsed.work_time_code)
    if not parsed.recognized:
        parsed.memo = raw_value

    return parsed


def _match_token(key, context):
    position = context["positions"].get(key)
    attendance_status = context["attendance_statuses"].get(key)
    work_time_code = context["work_time_codes"].get(key)
    if not position and not attendance_status and not work_time_code:
        return None

    return {
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
