import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import BuildingFloor, Department, Employee, Gender, Process, Shift


CSV_HEADERS = [
    "社員番号",
    "和名",
    "アルファベット名",
    "IMC入社日",
    "就労終了日",
    "退職日",
    "備考",
    "性別",
    "シフト",
    "統合職場CD",
    "統合職場名",
    "単価ランク",
    "職場コード",
    "職場略名",
    "国籍",
    "時給",
    "新異入社日",
    "請求単価",
    "再入",
    "FA入社日",
    "生年月日",
    "社内名",
    "カナ名",
    "工程",
    "氏名CD(村田用)",
    "月末在職",
    "勤務棟-階",
    "契約区分",
    "管理者区分",
    "所属",
    "ORDIA番号",
    "派遣就業開始日",
    "社員CD",
    "事業所CD",
    "総時給",
    "入社区分",
    "閲覧",
    "採用区分",
    "ICカード",
    "IMCカード",
]


@dataclass
class ParsedRow:
    row_number: int
    employee_id: str
    payload: dict[str, Any]
    warnings: list[str]
    errors: list[str]


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _parse_date(value: str):
    value = _norm(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return "__INVALID_DATE__"


def _parse_int(value: str):
    value = _norm(value)
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return "__INVALID_INT__"


def _parse_bool(value: str):
    value = _norm(value).lower()
    if not value:
        return None
    truthy = {"1", "true", "yes", "sim", "y", "有", "在職", "on"}
    falsy = {"0", "false", "no", "nao", "não", "off", "無", "退職"}
    if value in truthy:
        return True
    if value in falsy:
        return False
    return "__INVALID_BOOL__"


def _build_lookup(model):
    lookup = {}
    for obj in model.objects.all():
        for attr in ("code", "label_pt", "label_jp", "name_pt", "name_jp"):
            if hasattr(obj, attr):
                normalized = _norm(getattr(obj, attr))
                if normalized:
                    lookup[normalized.casefold()] = obj
    return lookup


def read_csv_rows(uploaded_file):
    raw = uploaded_file.read()
    if isinstance(raw, str):
        text = raw
    else:
        text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [{_norm(k): _norm(v) for k, v in row.items()} for row in reader]


def _set_if_allowed(payload, field, value, source_value, update_empty):
    if source_value == "" and not update_empty:
        return
    payload[field] = value


def parse_employee_rows(rows, update_empty=False):
    gender_lookup = _build_lookup(Gender)
    shift_lookup = _build_lookup(Shift)
    process_lookup = _build_lookup(Process)
    floor_lookup = _build_lookup(BuildingFloor)
    department_lookup = _build_lookup(Department)

    parsed_rows: list[ParsedRow] = []

    for index, row in enumerate(rows, start=2):
        warnings = []
        errors = []
        payload: dict[str, Any] = {}

        employee_id = _norm(row.get("社員番号"))
        if not employee_id:
            errors.append("社員番号 (employee_id) é obrigatório.")

        name_jp = _norm(row.get("和名"))
        name_en = _norm(row.get("アルファベット名"))
        if name_jp:
            payload["name_jp"] = name_jp
        if name_en:
            payload["name_en"] = name_en

        _set_if_allowed(payload, "employee_cd", _norm(row.get("社員CD")), row.get("社員CD", ""), update_empty)
        _set_if_allowed(payload, "internal_name", _norm(row.get("社内名")), row.get("社内名", ""), update_empty)
        _set_if_allowed(payload, "name_kana", _norm(row.get("カナ名")), row.get("カナ名", ""), update_empty)
        _set_if_allowed(payload, "workplace_cd", _norm(row.get("職場コード")), row.get("職場コード", ""), update_empty)
        _set_if_allowed(payload, "workplace_name", _norm(row.get("職場略名")), row.get("職場略名", ""), update_empty)
        _set_if_allowed(payload, "site_cd", _norm(row.get("統合職場CD")), row.get("統合職場CD", ""), update_empty)
        _set_if_allowed(payload, "site_abbr", _norm(row.get("統合職場名")), row.get("統合職場名", ""), update_empty)
        _set_if_allowed(payload, "rank", _norm(row.get("単価ランク")), row.get("単価ランク", ""), update_empty)
        _set_if_allowed(payload, "contract_type", _norm(row.get("契約区分")), row.get("契約区分", ""), update_empty)
        _set_if_allowed(payload, "ordia_number", _norm(row.get("ORDIA番号")), row.get("ORDIA番号", ""), update_empty)
        _set_if_allowed(payload, "office_cd", _norm(row.get("事業所CD")), row.get("事業所CD", ""), update_empty)
        _set_if_allowed(payload, "ic_card", _norm(row.get("ICカード")), row.get("ICカード", ""), update_empty)
        _set_if_allowed(payload, "imc_card", _norm(row.get("IMCカード")), row.get("IMCカード", ""), update_empty)
        _set_if_allowed(payload, "notes", _norm(row.get("備考")), row.get("備考", ""), update_empty)

        for csv_name, model_field in [
            ("IMC入社日", "joined_imc"),
            ("就労終了日", "end_work"),
            ("退職日", "retired"),
            ("新異入社日", "new_joined"),
            ("FA入社日", "joined_fa"),
            ("生年月日", "birth_date"),
            ("派遣就業開始日", "dispatch_start"),
        ]:
            source = row.get(csv_name, "")
            parsed_date = _parse_date(source)
            if parsed_date == "__INVALID_DATE__":
                errors.append(f"{csv_name}: data inválida ({source}).")
                continue
            _set_if_allowed(payload, model_field, parsed_date, source, update_empty)

        for csv_name, model_field in [
            ("時給", "hourly_rate"),
            ("総時給", "total_hourly"),
        ]:
            source = row.get(csv_name, "")
            parsed_int = _parse_int(source)
            if parsed_int == "__INVALID_INT__":
                errors.append(f"{csv_name}: número inválido ({source}).")
                continue
            _set_if_allowed(payload, model_field, parsed_int, source, update_empty)

        for csv_name, model_field in [
            ("管理者区分", "manager_flag"),
            ("月末在職", "active_end_month"),
            ("閲覧", "view_flag"),
        ]:
            source = row.get(csv_name, "")
            parsed_bool = _parse_bool(source)
            if parsed_bool == "__INVALID_BOOL__":
                warnings.append(f"{csv_name}: valor não reconhecido ({source}), mantendo valor atual.")
                continue
            _set_if_allowed(payload, model_field, parsed_bool, source, update_empty)

        for csv_name, model_field, lookup in [
            ("性別", "gender", gender_lookup),
            ("シフト", "shift", shift_lookup),
            ("工程", "process", process_lookup),
            ("勤務棟-階", "building_floor", floor_lookup),
        ]:
            source = row.get(csv_name, "")
            normalized = _norm(source)
            if not normalized:
                if update_empty:
                    payload[model_field] = None
                continue
            found = lookup.get(normalized.casefold())
            if found:
                payload[model_field] = found
            else:
                warnings.append(f"{csv_name}: referência não encontrada ({source}), campo ficará sem atualização.")

        department_source = row.get("所属", "")
        department_norm = _norm(department_source)
        if department_norm:
            found_department = department_lookup.get(department_norm.casefold())
            if found_department:
                payload["department"] = found_department
            else:
                warnings.append(f"所属: departamento não encontrado ({department_source}), usando organization_name.")
                payload["organization_name"] = department_norm
        elif update_empty:
            payload["department"] = None

        parsed_rows.append(
            ParsedRow(
                row_number=index,
                employee_id=employee_id,
                payload=payload,
                warnings=warnings,
                errors=errors,
            )
        )

    return parsed_rows


def preview_employee_import(parsed_rows):
    employee_ids = [row.employee_id for row in parsed_rows if row.employee_id]
    existing = Employee.objects.in_bulk(employee_ids, field_name="employee_id")

    creates = updates = unchanged = 0
    errors = []
    warnings = []
    sample_rows = []

    for row in parsed_rows:
        row_warnings = list(row.warnings)
        row_errors = list(row.errors)
        if not row.employee_id:
            row_errors.append("employee_id ausente.")
        existing_obj = existing.get(row.employee_id)

        action = "create"
        changed_fields = []
        if existing_obj:
            action = "unchanged"
            for key, value in row.payload.items():
                current = getattr(existing_obj, key)
                if hasattr(current, "pk"):
                    current = current.pk
                new_value = value.pk if hasattr(value, "pk") else value
                if current != new_value:
                    changed_fields.append(key)
            if changed_fields:
                action = "update"

        if action == "create" and (not row.payload.get("name_jp") or not row.payload.get("name_en")):
            row_errors.append("Linhas novas exigem 和名 e アルファベット名.")

        if row_errors:
            errors.append({"row": row.row_number, "employee_id": row.employee_id, "messages": row_errors})
        if row_warnings:
            warnings.append({"row": row.row_number, "employee_id": row.employee_id, "messages": row_warnings})

        if not row_errors:
            if action == "create":
                creates += 1
            elif action == "update":
                updates += 1
            else:
                unchanged += 1

        if len(sample_rows) < 20:
            sample_rows.append(
                {
                    "row": row.row_number,
                    "employee_id": row.employee_id,
                    "action": "error" if row_errors else action,
                    "changed_fields": changed_fields,
                    "warnings": row_warnings,
                    "errors": row_errors,
                }
            )

    return {
        "total_rows": len(parsed_rows),
        "creates": creates,
        "updates": updates,
        "unchanged": unchanged,
        "errors": errors,
        "warnings": warnings,
        "sample_rows": sample_rows,
    }


def commit_employee_import(parsed_rows):
    preview = preview_employee_import(parsed_rows)
    if preview["errors"]:
        return {**preview, "committed": False, "created_ids": [], "updated_ids": []}

    employee_ids = [row.employee_id for row in parsed_rows if row.employee_id]
    existing = Employee.objects.in_bulk(employee_ids, field_name="employee_id")
    created_ids = []
    updated_ids = []

    for row in parsed_rows:
        current = existing.get(row.employee_id)
        payload = dict(row.payload)

        if current:
            changed = False
            for key, value in payload.items():
                current_value = getattr(current, key)
                if hasattr(current_value, "pk"):
                    current_value = current_value.pk
                if current_value != value:
                    setattr(current, key, value)
                    changed = True
            if changed:
                current.save()
                updated_ids.append(current.employee_id)
        else:
            new_data = {"employee_id": row.employee_id, **payload}
            employee = Employee.objects.create(**new_data)
            created_ids.append(employee.employee_id)

    return {
        **preview,
        "committed": True,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
    }
