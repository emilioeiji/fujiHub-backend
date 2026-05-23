import re
from dataclasses import dataclass

from .models import AttendanceStatus, OperationalPosition, WorkTimeCode


PASTE_TOKEN_SEPARATOR_RE = re.compile(r"[\s+/・]+")


@dataclass
class ParsedCalendarCellValue:
    position: OperationalPosition | None = None
    attendance_status: AttendanceStatus | None = None
    work_time_code: WorkTimeCode | None = None
    memo: str = ""
    recognized: bool = False


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
