from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Q
from django.db import transaction
from datetime import datetime
import csv
from .models import (
    Employee, EmployeeHousing, Gender, Shift, Nationality, BillingRate, Rejoined,
    Process, BuildingFloor, Department, EntryType, HireType
)
from .permissions import EmployeePermission
from .pagination import EmployeePagination
from .serializers import (
    EmployeeSerializer, EmployeeHousingSerializer, GenderSerializer, ShiftSerializer, NationalitySerializer, BillingRateSerializer,
    RejoinedSerializer, ProcessSerializer, BuildingFloorSerializer,
    DepartmentSerializer, EntryTypeSerializer, HireTypeSerializer
)
from .csv_import import (
    CSV_HEADERS,
    MAPPING_USED,
    commit_employee_import,
    parse_employee_rows,
    preview_employee_import,
    read_csv_rows,
)


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [EmployeePermission]
    pagination_class = EmployeePagination
    lookup_field = "employee_id"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("department", "process", "shift", "building_floor")
        )

        search = (self.request.query_params.get("search") or "").strip()
        department = (self.request.query_params.get("department") or "").strip()
        active = (self.request.query_params.get("active") or "").strip().lower()
        operational_category = (self.request.query_params.get("operational_category") or "").strip()
        work_pattern = (self.request.query_params.get("work_pattern") or "").strip()
        ordering = (self.request.query_params.get("ordering") or "").strip()

        if search:
            queryset = queryset.filter(
                Q(employee_id__icontains=search)
                | Q(name_en__icontains=search)
                | Q(name_jp__icontains=search)
                | Q(internal_name__icontains=search)
                | Q(nickname__icontains=search)
            )

        if department:
            queryset = queryset.filter(department_id=department)

        if active in {"true", "1", "yes", "sim"}:
            queryset = queryset.filter(active_end_month=True)
        elif active in {"false", "0", "no", "nao", "não"}:
            queryset = queryset.filter(active_end_month=False)

        if operational_category:
            queryset = queryset.filter(operational_category=operational_category)

        if work_pattern:
            queryset = queryset.filter(work_pattern=work_pattern)

        if ordering:
            allowed = {
                "employee_id",
                "-employee_id",
                "name_en",
                "-name_en",
                "joined_imc",
                "-joined_imc",
                "retired",
                "-retired",
            }
            if ordering in allowed:
                queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("employee_id")

        return queryset.distinct()

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        filename = f"employees_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # UTF-8 BOM for Excel compatibility.
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(
            [
                "employee_id",
                "name_en",
                "name_jp",
                "nickname",
                "department",
                "process",
                "shift",
                "building_floor",
                "organization_name",
                "operational_category",
                "work_pattern",
                "shift_type",
                "rotation_group",
                "five_two_off_days",
                "active_end_month",
                "admission_date",
                "termination_date",
                "operational_memo",
            ]
        )

        for employee in queryset.iterator():
            writer.writerow(
                [
                    employee.employee_id,
                    employee.name_en or "",
                    employee.name_jp or "",
                    employee.nickname or "",
                    getattr(employee.department, "label_pt", "") or getattr(employee.department, "label_jp", "") or "",
                    getattr(employee.process, "label_pt", "") or getattr(employee.process, "label_jp", "") or "",
                    getattr(employee.shift, "label_pt", "") or getattr(employee.shift, "label_jp", "") or "",
                    getattr(employee.building_floor, "label_pt", "") or getattr(employee.building_floor, "label_jp", "") or "",
                    employee.organization_name or "",
                    employee.operational_category or "",
                    employee.work_pattern or "",
                    employee.shift_type or "",
                    employee.rotation_group or "",
                    ",".join(str(day) for day in (employee.five_two_off_days or [])),
                    "1" if employee.active_end_month else "0",
                    employee.joined_imc.isoformat() if employee.joined_imc else "",
                    employee.retired.isoformat() if employee.retired else "",
                    employee.operational_memo or "",
                ]
            )

        return response

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="employees_import_template.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(CSV_HEADERS)
        return response

    @action(detail=False, methods=["post"], url_path="import-preview")
    def import_preview(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return Response({"detail": "CSV file is required."}, status=400)

        update_empty = str(request.data.get("update_empty", "false")).strip().lower() in {"1", "true", "yes", "sim"}

        try:
            rows, detected_headers = read_csv_rows(csv_file)
            parsed_rows = parse_employee_rows(rows, update_empty=update_empty)
            preview = preview_employee_import(parsed_rows)
        except UnicodeDecodeError:
            return Response({"detail": "Invalid encoding. Use UTF-8 or UTF-8 BOM."}, status=400)
        except Exception as exc:
            return Response({"detail": f"Failed to parse CSV: {exc}"}, status=400)

        return Response(
            {
                **preview,
                "mapping_used": MAPPING_USED,
                "update_empty": update_empty,
                "detected_headers": detected_headers,
                "first_error_samples": preview.get("errors", [])[:10],
                "first_warning_samples": preview.get("warnings", [])[:10],
            }
        )

    @action(detail=False, methods=["post"], url_path="import-commit")
    def import_commit(self, request):
        csv_file = request.FILES.get("file")
        if not csv_file:
            return Response({"detail": "CSV file is required."}, status=400)

        update_empty = str(request.data.get("update_empty", "false")).strip().lower() in {"1", "true", "yes", "sim"}

        try:
            rows, _detected_headers = read_csv_rows(csv_file)
            parsed_rows = parse_employee_rows(rows, update_empty=update_empty)
        except UnicodeDecodeError:
            return Response({"detail": "Invalid encoding. Use UTF-8 or UTF-8 BOM."}, status=400)
        except Exception as exc:
            return Response({"detail": f"Failed to parse CSV: {exc}"}, status=400)

        with transaction.atomic():
            result = commit_employee_import(parsed_rows)
            if result.get("errors"):
                transaction.set_rollback(True)

        status_code = 200 if result.get("committed") else 400
        return Response(result, status=status_code)


class EmployeeHousingViewSet(viewsets.ModelViewSet):
    queryset = EmployeeHousing.objects.all()
    serializer_class = EmployeeHousingSerializer
    permission_classes = [IsAuthenticated]


class GenderViewSet(viewsets.ModelViewSet):
    queryset = Gender.objects.all()
    serializer_class = GenderSerializer
    permission_classes = [IsAuthenticated]


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticated]


class NationalityViewSet(viewsets.ModelViewSet):
    queryset = Nationality.objects.all()
    serializer_class = NationalitySerializer
    permission_classes = [IsAuthenticated]


class BillingRateViewSet(viewsets.ModelViewSet):
    queryset = BillingRate.objects.all()
    serializer_class = BillingRateSerializer
    permission_classes = [IsAuthenticated]


class RejoinedViewSet(viewsets.ModelViewSet):
    queryset = Rejoined.objects.all()
    serializer_class = RejoinedSerializer
    permission_classes = [IsAuthenticated]


class ProcessViewSet(viewsets.ModelViewSet):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer
    permission_classes = [IsAuthenticated]


class BuildingFloorViewSet(viewsets.ModelViewSet):
    queryset = BuildingFloor.objects.all()
    serializer_class = BuildingFloorSerializer
    permission_classes = [IsAuthenticated]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


class EntryTypeViewSet(viewsets.ModelViewSet):
    queryset = EntryType.objects.all()
    serializer_class = EntryTypeSerializer
    permission_classes = [IsAuthenticated]


class HireTypeViewSet(viewsets.ModelViewSet):
    queryset = HireType.objects.all()
    serializer_class = HireTypeSerializer
    permission_classes = [IsAuthenticated]
