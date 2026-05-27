import csv
from calendar import monthrange
from datetime import datetime, timedelta
from io import StringIO

from django.http import HttpResponse
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    AttendanceStatus,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    EmployeeVisualCategory,
    MonthlyOperationCalendar,
    OperationalCode,
    OperationalPosition,
    OperationCalendarTemplate,
    OperationCalendarTemplateAssignment,
    OperationCalendarTemplateCell,
    OperationCalendarHistory,
    PositionDailyRequirement,
    HikitsuguiOccurrenceCategory,
    HikitsuguiReport,
    HikitsuguiItem,
    RotationGroupStyle,
    WorkTimeCode,
)
from .permissions import OperationsCalendarPermission, OperationsMasterDataPermission
from .serializers import (
    AttendanceStatusSerializer,
    CalendarDayCellSerializer,
    CalendarEmployeeAssignmentSerializer,
    EmployeeVisualCategorySerializer,
    MonthlyOperationCalendarSerializer,
    OperationalCodeSerializer,
    OperationalPositionSerializer,
    OperationCalendarTemplateSerializer,
    OperationCalendarHistorySerializer,
    PositionDailyRequirementSerializer,
    HikitsuguiOccurrenceCategorySerializer,
    HikitsuguiReportSerializer,
    HikitsuguiItemSerializer,
    RotationGroupStyleSerializer,
    WorkTimeCodeSerializer,
)
from .services import (
    build_calendar_cell_parser_context,
    calculate_cell_work_minutes,
    generate_calendar_schedule,
    get_assignment_sort_key,
    import_calendar_employees,
    preview_calendar_employee_candidates,
    parse_calendar_cell_value,
    recalculate_calendar_totals,
    sync_calendar_assignments_from_master,
)


class ActorMixin:
    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())


class OperationalPositionViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = OperationalPosition.objects.select_related("department", "building_floor")
    serializer_class = OperationalPositionSerializer
    permission_classes = [OperationsMasterDataPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        department = self.request.query_params.get("department")
        if department:
            queryset = queryset.filter(department_id=department)
        return queryset


class AttendanceStatusViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = AttendanceStatus.objects.all()
    serializer_class = AttendanceStatusSerializer
    permission_classes = [OperationsMasterDataPermission]


class WorkTimeCodeViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = WorkTimeCode.objects.all()
    serializer_class = WorkTimeCodeSerializer
    permission_classes = [OperationsMasterDataPermission]


class RotationGroupStyleViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = RotationGroupStyle.objects.all()
    serializer_class = RotationGroupStyleSerializer
    permission_classes = [OperationsMasterDataPermission]


class EmployeeVisualCategoryViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = EmployeeVisualCategory.objects.all()
    serializer_class = EmployeeVisualCategorySerializer
    permission_classes = [OperationsMasterDataPermission]


class OperationalCodeViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = OperationalCode.objects.select_related("attendance_status", "work_time_code")
    serializer_class = OperationalCodeSerializer
    permission_classes = [OperationsMasterDataPermission]


class OperationCalendarTemplateViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = OperationCalendarTemplate.objects.select_related("department", "process", "shift", "created_by")
    serializer_class = OperationCalendarTemplateSerializer
    permission_classes = [OperationsCalendarPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        department = self.request.query_params.get("department")
        process = self.request.query_params.get("process")
        shift = self.request.query_params.get("shift")
        if department:
            queryset = queryset.filter(department_id=department)
        if process:
            queryset = queryset.filter(process_id=process)
        if shift:
            queryset = queryset.filter(shift_id=shift)
        return queryset


class HikitsuguiOccurrenceCategoryViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = HikitsuguiOccurrenceCategory.objects.all()
    serializer_class = HikitsuguiOccurrenceCategorySerializer
    permission_classes = [OperationsCalendarPermission]


class HikitsuguiReportViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = HikitsuguiReport.objects.select_related(
        "calendar",
        "shift",
        "process",
        "responsible_employee",
        "responsible_assignment",
    ).prefetch_related("items", "items__category")
    serializer_class = HikitsuguiReportSerializer
    permission_classes = [OperationsCalendarPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        calendar = params.get("calendar")
        shift = params.get("shift")
        process = params.get("process")
        status_param = params.get("status")
        priority = params.get("priority")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        responsible_employee = params.get("responsible_employee")
        if calendar:
            queryset = queryset.filter(calendar_id=calendar)
        if shift:
            queryset = queryset.filter(shift_id=shift)
        if process:
            queryset = queryset.filter(process_id=process)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if priority:
            queryset = queryset.filter(priority=priority)
        if date_from:
            queryset = queryset.filter(report_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(report_date__lte=date_to)
        if responsible_employee:
            queryset = queryset.filter(responsible_employee_id=responsible_employee)
        return queryset


class HikitsuguiItemViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = HikitsuguiItem.objects.select_related("report", "category", "responsible_employee")
    serializer_class = HikitsuguiItemSerializer
    permission_classes = [OperationsCalendarPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        report = params.get("report")
        status_param = params.get("status")
        priority = params.get("priority")
        if report:
            queryset = queryset.filter(report_id=report)
        if status_param:
            queryset = queryset.filter(status=status_param)
        if priority:
            queryset = queryset.filter(priority=priority)
        return queryset


class MonthlyOperationCalendarViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = MonthlyOperationCalendar.objects.select_related("department", "process", "shift")
    serializer_class = MonthlyOperationCalendarSerializer
    permission_classes = [OperationsCalendarPermission]

    def _ordered_assignments_queryset(self, calendar):
        queryset = calendar.assignments.select_related(
            "employee",
            "employee__process",
            "employee__billing_rate",
        )
        return sorted(queryset, key=get_assignment_sort_key)

    @action(detail=True, methods=["get", "post"])
    def assignments(self, request, pk=None):
        calendar = self.get_object()

        if request.method == "GET":
            queryset = self._ordered_assignments_queryset(calendar)
            serializer = CalendarEmployeeAssignmentSerializer(queryset, many=True)
            return Response(serializer.data)

        serializer = CalendarEmployeeAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._actor()
        assignment = serializer.save(calendar=calendar, created_by=user, updated_by=user)
        return Response(CalendarEmployeeAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"assignments/(?P<assignment_id>\d+)")
    def assignment_detail(self, request, pk=None, assignment_id=None):
        calendar = self.get_object()
        assignment = get_object_or_404(CalendarEmployeeAssignment, pk=assignment_id, calendar=calendar)
        serializer = CalendarEmployeeAssignmentSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=self._actor())
        return Response(CalendarEmployeeAssignmentSerializer(assignment).data)

    @action(detail=True, methods=["get", "post"])
    def cells(self, request, pk=None):
        calendar = self.get_object()
        history_source = self._normalize_history_source(request.data.get("history_source"))

        if request.method == "GET":
            queryset = self._calendar_cells(calendar)
            serializer = CalendarDayCellSerializer(queryset, many=True)
            return Response(serializer.data)

        payload = request.data.copy()
        payload.pop("history_source", None)
        serializer = CalendarDayCellSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.validated_data["assignment"]
        if assignment.calendar_id != calendar.id:
            return Response(
                {"assignment": "Assignment does not belong to this calendar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = self._actor()
        old_payload = None
        cell = serializer.save(calendar=calendar, created_by=user, updated_by=user)
        calculate_cell_work_minutes(cell)
        self._log_cell_history(
            calendar=calendar,
            assignment=cell.assignment,
            cell_date=cell.date,
            source=history_source,
            old_value=old_payload,
            new_value=self._snapshot_cell(cell),
            metadata={"origin": "cells_create"},
        )
        return Response(CalendarDayCellSerializer(cell).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"cells/(?P<cell_id>\d+)")
    def cell_detail(self, request, pk=None, cell_id=None):
        calendar = self.get_object()
        cell = get_object_or_404(CalendarDayCell, pk=cell_id, calendar=calendar)
        old_payload = self._snapshot_cell(cell)
        history_source = self._normalize_history_source(request.data.get("history_source"))
        payload = request.data.copy()
        payload.pop("history_source", None)
        serializer = CalendarDayCellSerializer(cell, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)

        assignment = serializer.validated_data.get("assignment")
        if assignment and assignment.calendar_id != calendar.id:
            return Response(
                {"assignment": "Assignment does not belong to this calendar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(updated_by=self._actor())
        calculate_cell_work_minutes(cell)
        self._log_cell_history(
            calendar=calendar,
            assignment=cell.assignment,
            cell_date=cell.date,
            source=history_source,
            old_value=old_payload,
            new_value=self._snapshot_cell(cell),
            metadata={"origin": "cells_patch", "cell_id": cell.id},
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="cells/paste")
    def paste_cells(self, request, pk=None):
        calendar = self.get_object()
        start_assignment_id = request.data.get("start_assignment")
        start_date_raw = request.data.get("start_date")
        tsv = request.data.get("tsv", "")

        if not start_assignment_id or not start_date_raw or not isinstance(tsv, str):
            return Response(
                {"detail": "start_assignment, start_date and tsv are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        except ValueError:
            return Response({"start_date": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)

        if start_date.year != calendar.year or start_date.month != calendar.month:
            return Response(
                {"start_date": "Start date must be inside the calendar month."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignments = list(calendar.assignments.order_by("display_order", "employee_id", "id"))
        start_index = next(
            (index for index, assignment in enumerate(assignments) if assignment.id == int(start_assignment_id)),
            None,
        )
        if start_index is None:
            return Response(
                {"start_assignment": "Assignment does not belong to this calendar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = self._paste_tsv(
            calendar,
            assignments[start_index:],
            start_date,
            tsv,
            source=self._normalize_history_source(request.data.get("history_source")) or OperationCalendarHistory.Source.PASTE,
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="assignment-totals")
    def assignment_totals(self, request, pk=None):
        calendar = self.get_object()
        return Response(recalculate_calendar_totals(calendar))

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        calendar = self.get_object()
        queryset = calendar.history_entries.select_related("assignment__employee", "updated_by")
        assignment_id = request.query_params.get("assignment")
        cell_date = request.query_params.get("date")
        source = request.query_params.get("source")
        user_id = request.query_params.get("user")
        if assignment_id:
            queryset = queryset.filter(assignment_id=assignment_id)
        if cell_date:
            queryset = queryset.filter(cell_date=cell_date)
        if source:
            queryset = queryset.filter(source=source)
        if user_id:
            queryset = queryset.filter(updated_by_id=user_id)
        serializer = OperationCalendarHistorySerializer(queryset[:200], many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="export-excel")
    def export_excel(self, request, pk=None):
        calendar = self.get_object()
        assignments = list(calendar.assignments.select_related("employee").order_by("display_order", "employee_id", "id"))
        cells = list(
            calendar.day_cells.select_related(
                "assignment",
                "position",
                "attendance_status",
                "work_time_code",
                "operational_code",
            ).order_by("assignment__display_order", "date")
        )
        totals = {row["assignment"]: row for row in recalculate_calendar_totals(calendar)}
        cell_map = {(c.assignment_id, c.date): c for c in cells}
        days = self._month_days(calendar.year, calendar.month)

        wb = Workbook()
        ws = wb.active
        ws.title = "Escala"

        title = f"Escala Operacional {calendar.year}-{str(calendar.month).zfill(2)}"
        scope = f"Depto: {getattr(calendar.department, 'code', calendar.department_id)} | Proc: {getattr(calendar.process, 'code', '-') if calendar.process_id else '-'} | Turno: {getattr(calendar.shift, 'code', '-') if calendar.shift_id else '-'}"
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8 + len(days))
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=8 + len(days))
        ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
        ws.cell(row=2, column=1, value=scope).font = Font(bold=False, size=10)

        header_row = 4
        headers = ["SCD", "Nome", "和名", "Código", "Categoria", "Horas Normais", "Horas Extras", "Acumulado"]
        for idx, label in enumerate(headers, start=1):
            cell = ws.cell(row=header_row, column=idx, value=label)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill(fill_type="solid", fgColor="D9E8EF")

        for day_idx, day in enumerate(days, start=9):
            weekday = day.strftime("%a")
            label = f"{day.day}\n{weekday}"
            cell = ws.cell(row=header_row, column=day_idx, value=label)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            fill_color = "FFE9EF" if day.weekday() == 6 else ("EEF2FF" if day.weekday() == 5 else "D9E8EF")
            cell.fill = PatternFill(fill_type="solid", fgColor=fill_color)

        start_data_row = 5
        for row_offset, assignment in enumerate(assignments):
            row_no = start_data_row + row_offset
            employee = assignment.employee
            total = totals.get(assignment.id, {})
            ws.cell(row=row_no, column=1, value=assignment.display_order)
            ws.cell(row=row_no, column=2, value=getattr(employee, "name_en", "") or getattr(employee, "internal_name", "") or getattr(employee, "name_jp", ""))
            ws.cell(row=row_no, column=3, value=getattr(employee, "name_jp", ""))
            ws.cell(row=row_no, column=4, value=getattr(employee, "employee_cd", "") or getattr(employee, "employee_id", ""))
            ws.cell(row=row_no, column=5, value=assignment.operational_category)
            ws.cell(row=row_no, column=6, value=total.get("scheduled_regular_formatted", "0:00"))
            ws.cell(row=row_no, column=7, value=total.get("actual_overtime_formatted", "0:00"))
            ws.cell(row=row_no, column=8, value=total.get("overload_formatted", "0:00"))

            for day_idx, day in enumerate(days, start=9):
                source_cell = cell_map.get((assignment.id, day))
                excel_cell = ws.cell(row=row_no, column=day_idx, value=self._cell_export_text(source_cell))
                excel_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                fill = self._cell_export_fill(source_cell)
                if fill:
                    excel_cell.fill = PatternFill(fill_type="solid", fgColor=fill)

        # Widths
        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 18
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 12
        ws.column_dimensions["F"].width = 12
        ws.column_dimensions["G"].width = 12
        ws.column_dimensions["H"].width = 12
        for idx in range(9, 9 + len(days)):
            ws.column_dimensions[get_column_letter(idx)].width = 12

        filename_scope = (getattr(calendar.shift, "code", "") or getattr(calendar.process, "code", "") or "scope").replace(" ", "_")
        filename = f"escala_{calendar.year}_{str(calendar.month).zfill(2)}_{filename_scope}.xlsx"
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    @action(detail=True, methods=["post"], url_path="save-template")
    def save_template(self, request, pk=None):
        calendar = self.get_object()
        name = str(request.data.get("name") or "").strip()
        if not name:
            return Response({"name": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)

        description = str(request.data.get("description") or "").strip()
        scope_from_calendar = self._parse_bool(request.data.get("scope_from_calendar", True))
        include_base_cells = self._parse_bool(request.data.get("include_base_cells", True))

        with transaction.atomic():
            template = OperationCalendarTemplate.objects.create(
                name=name,
                description=description,
                department=calendar.department if scope_from_calendar else None,
                process=calendar.process if scope_from_calendar else None,
                shift=calendar.shift if scope_from_calendar else None,
                created_by=self._actor(),
                updated_by=self._actor(),
            )
            assignment_map = self._clone_assignments_to_template(calendar, template)
            created_cells = self._clone_cells_to_template_conservative(
                calendar=calendar,
                template=template,
                assignment_map=assignment_map,
                include_base_cells=include_base_cells,
            )
        self._log_operation_history(
            calendar=calendar,
            source=OperationCalendarHistory.Source.TEMPLATE,
            metadata={
                "event": "save_template",
                "template_id": template.id,
                "created_assignments": len(assignment_map),
                "created_cells": created_cells,
            },
        )

        return Response(
            {
                "detail": "Template salvo com sucesso.",
                "template_id": template.id,
                "template_name": template.name,
                "created_assignments": len(assignment_map),
                "created_cells": created_cells,
                "conservative_rules": "Absências, notas e exceções manuais não são replicadas.",
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="apply-template")
    def apply_template(self, request, pk=None):
        calendar = self.get_object()
        template_id = request.data.get("template_id")
        overwrite = self._parse_bool(request.data.get("overwrite", False))
        if not template_id:
            return Response({"template_id": "This field is required."}, status=status.HTTP_400_BAD_REQUEST)

        template = OperationCalendarTemplate.objects.filter(pk=template_id, is_active=True).first()
        if not template:
            return Response({"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND)

        target_assignment_count = calendar.assignments.count()
        target_cell_count = calendar.day_cells.count()
        target_has_data = target_assignment_count > 0 or target_cell_count > 0
        if target_has_data and not overwrite:
            return Response(
                {
                    "detail": "O calendário de destino já possui dados.",
                    "target_assignment_count": target_assignment_count,
                    "target_cell_count": target_cell_count,
                    "requires_confirmation": True,
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            if target_has_data and overwrite:
                calendar.position_requirements.all().delete()
                calendar.day_cells.all().delete()
                calendar.assignments.all().delete()
            assignment_map = self._clone_template_assignments_to_calendar(template, calendar)
            created_cells = self._clone_template_cells_to_calendar(template, calendar, assignment_map)
        self._log_operation_history(
            calendar=calendar,
            source=OperationCalendarHistory.Source.TEMPLATE,
            metadata={
                "event": "apply_template",
                "template_id": template.id,
                "created_assignments": len(assignment_map),
                "created_cells": created_cells,
                "overwrite": overwrite,
            },
        )

        return Response(
            {
                "detail": "Template aplicado com sucesso.",
                "template_id": template.id,
                "template_name": template.name,
                "target_calendar_id": calendar.id,
                "created_assignments": len(assignment_map),
                "created_cells": created_cells,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="duplicate-from-previous")
    def duplicate_from_previous(self, request, pk=None):
        target = self.get_object()
        overwrite = self._parse_bool(request.data.get("overwrite", False))
        copy_base_cells = self._parse_bool(request.data.get("copy_base_cells", True))

        prev_year, prev_month = self._previous_period(target.year, target.month)
        source = MonthlyOperationCalendar.objects.filter(
            department=target.department,
            process=target.process,
            shift=target.shift,
            year=prev_year,
            month=prev_month,
            is_active=True,
        ).first()
        if not source:
            return Response(
                {"detail": "Nenhum calendário do mês anterior encontrado para o mesmo escopo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        target_assignment_count = target.assignments.count()
        target_cell_count = target.day_cells.count()
        target_has_data = target_assignment_count > 0 or target_cell_count > 0
        if target_has_data and not overwrite:
            return Response(
                {
                    "detail": "O calendário de destino já possui dados.",
                    "target_assignment_count": target_assignment_count,
                    "target_cell_count": target_cell_count,
                    "requires_confirmation": True,
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            if target_has_data and overwrite:
                target.position_requirements.all().delete()
                target.day_cells.all().delete()
                target.assignments.all().delete()

            assignment_map = self._clone_assignments(source, target)
            created_cells = self._clone_cells_conservative(
                source=source,
                target=target,
                assignment_map=assignment_map,
                copy_base_cells=copy_base_cells,
            )
        self._log_operation_history(
            calendar=target,
            source=OperationCalendarHistory.Source.MONTH_DUPLICATION,
            metadata={
                "source_calendar_id": source.id,
                "target_calendar_id": target.id,
                "created_assignments": len(assignment_map),
                "created_cells": created_cells,
            },
        )

        return Response(
            {
                "detail": "Duplicação concluída.",
                "source_calendar_id": source.id,
                "target_calendar_id": target.id,
                "created_assignments": len(assignment_map),
                "created_cells": created_cells,
                "copy_base_cells": copy_base_cells,
                "conservative_rules": "Absências, notas e exceções manuais não são replicadas.",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="generate-next-month")
    def generate_next_month(self, request, pk=None):
        source = self.get_object()
        copy_assignments = self._parse_bool(request.data.get("copy_assignments", True))
        copy_base_cells = self._parse_bool(request.data.get("copy_base_cells", False))
        overwrite_existing = self._parse_bool(request.data.get("overwrite_existing", False))

        next_year, next_month = self._next_period(source.year, source.month)
        target = MonthlyOperationCalendar.objects.filter(
            department=source.department,
            process=source.process,
            shift=source.shift,
            year=next_year,
            month=next_month,
            is_active=True,
        ).first()

        created_calendar = False
        if not target:
            target = MonthlyOperationCalendar.objects.create(
                department=source.department,
                process=source.process,
                shift=source.shift,
                year=next_year,
                month=next_month,
                title=f"{next_year}-{str(next_month).zfill(2)}",
                status=MonthlyOperationCalendar.Status.DRAFT,
                notes="",
                created_by=self._actor(),
                updated_by=self._actor(),
            )
            created_calendar = True

        target_assignment_count = target.assignments.count()
        target_cell_count = target.day_cells.count()
        target_has_data = target_assignment_count > 0 or target_cell_count > 0
        if target_has_data and not overwrite_existing:
            return Response(
                {
                    "detail": "O calendário do próximo mês já existe e possui dados.",
                    "target_calendar_id": target.id,
                    "target_assignment_count": target_assignment_count,
                    "target_cell_count": target_cell_count,
                    "requires_confirmation": True,
                },
                status=status.HTTP_409_CONFLICT,
            )

        created_assignments = 0
        created_cells = 0
        with transaction.atomic():
            if target_has_data and overwrite_existing:
                target.position_requirements.all().delete()
                target.day_cells.all().delete()
                target.assignments.all().delete()

            assignment_map = {}
            if copy_assignments:
                assignment_map = self._clone_assignments(source, target)
                created_assignments = len(assignment_map)
                created_cells = self._clone_cells_conservative(
                    source=source,
                    target=target,
                    assignment_map=assignment_map,
                    copy_base_cells=copy_base_cells,
                )
        self._log_operation_history(
            calendar=target,
            source=OperationCalendarHistory.Source.NEXT_MONTH_GENERATION,
            metadata={
                "source_calendar_id": source.id,
                "target_calendar_id": target.id,
                "created_assignments": created_assignments,
                "created_cells": created_cells,
            },
        )

        return Response(
            {
                "detail": "Próximo mês gerado com sucesso.",
                "source_calendar_id": source.id,
                "target_calendar_id": target.id,
                "target_year": target.year,
                "target_month": target.month,
                "created_calendar": created_calendar,
                "created_assignments": created_assignments,
                "created_cells": created_cells,
                "copy_assignments": copy_assignments,
                "copy_base_cells": copy_base_cells,
                "conservative_rules": "Absências, notas e exceções manuais não são replicadas.",
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="generate-schedule")
    def generate_schedule(self, request, pk=None):
        calendar = self.get_object()
        overwrite = self._parse_bool(request.data.get("overwrite", False))
        anchor_date_raw = request.data.get("default_4x2_anchor_date")

        try:
            result = generate_calendar_schedule(
                calendar,
                user=self._actor(),
                overwrite=overwrite,
                default_4x2_anchor_date=anchor_date_raw,
            )
        except ValueError:
            return Response(
                {"default_4x2_anchor_date": "Invalid date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self._log_operation_history(
            calendar=calendar,
            source=OperationCalendarHistory.Source.PATTERN_4X2,
            metadata={"result": result},
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="import-employees")
    def import_employees(self, request, pk=None):
        calendar = self.get_object()
        import_all = self._parse_bool(request.data.get("import_all", False))
        employee_ids = request.data.get("employee_ids") or []

        if not import_all and not employee_ids:
            return Response(
                {"detail": "import_all or employee_ids is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if employee_ids and not isinstance(employee_ids, list):
            return Response({"employee_ids": "Expected a list."}, status=status.HTTP_400_BAD_REQUEST)

        result = import_calendar_employees(
            calendar,
            user=self._actor(),
            import_all=import_all,
            employee_ids=employee_ids,
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="import-employees-preview")
    def import_employees_preview(self, request, pk=None):
        calendar = self.get_object()
        employee_ids = request.query_params.getlist("employee_ids")
        import_all = self._parse_bool(request.query_params.get("import_all", "true"))
        result = preview_calendar_employee_candidates(
            calendar=calendar,
            import_all=import_all,
            employee_ids=employee_ids,
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="sync-assignments")
    def sync_assignments(self, request, pk=None):
        calendar = self.get_object()
        result = sync_calendar_assignments_from_master(calendar, user=self._actor())
        self._log_operation_history(
            calendar=calendar,
            source=OperationCalendarHistory.Source.SYSTEM,
            metadata={"event": "sync_assignments", "result": result},
        )
        return Response(result, status=status.HTTP_200_OK)

    def _parse_bool(self, value):
        if isinstance(value, bool):
            return value
        return str(value or "").strip().casefold() in {"1", "true", "yes", "sim"}

    def _month_days(self, year, month):
        from calendar import monthrange
        from datetime import date

        total = monthrange(year, month)[1]
        return [date(year, month, day) for day in range(1, total + 1)]

    def _cell_export_text(self, cell):
        if not cell:
            return ""

        status = getattr(cell, "attendance_status", None)
        if status and (status.is_absence or not status.is_working_day):
            return status.code or status.label_jp or status.label_pt or ""

        position = getattr(cell, "position", None)
        if position:
            floor = getattr(position, "building_floor", None)
            floor_text = getattr(floor, "code", "") or getattr(floor, "label_jp", "") or getattr(floor, "label_pt", "")
            pos_text = getattr(position, "code", "") or getattr(position, "name_jp", "") or getattr(position, "name_pt", "")
            if pos_text and floor_text and floor_text not in pos_text:
                return f"{pos_text} / {floor_text}"
            if pos_text:
                return pos_text

        if getattr(cell, "operational_code", None):
            op = cell.operational_code
            return op.code or op.label_jp or op.label_pt or ""
        if getattr(cell, "work_time_code", None):
            wt = cell.work_time_code
            return wt.code or wt.label_jp or wt.label_pt or ""
        return (cell.raw_value or "").strip()

    def _cell_export_fill(self, cell):
        if not cell:
            return None
        status = getattr(cell, "attendance_status", None)
        op = getattr(cell, "operational_code", None)

        if status:
            if status.is_absence:
                return "FEE2E2"
            if not status.is_working_day:
                return "F3F4F6"
        if op and getattr(op, "category", ""):
            category = str(op.category).lower()
            if "alert" in category or "warn" in category:
                return "FFF3C8"
            if "special" in category or "exception" in category:
                return "EDE9FE"
        return "EDF9EE" if status and status.is_working_day else None

    def _previous_period(self, year, month):
        if month == 1:
            return year - 1, 12
        return year, month - 1

    def _next_period(self, year, month):
        if month == 12:
            return year + 1, 1
        return year, month + 1

    def _clone_assignments(self, source, target):
        user = self._actor()
        assignment_map = {}
        source_assignments = source.assignments.order_by("display_order", "employee_id", "id")
        for source_assignment in source_assignments:
            cloned = CalendarEmployeeAssignment.objects.create(
                calendar=target,
                employee=source_assignment.employee,
                operational_category=source_assignment.operational_category,
                work_pattern=source_assignment.work_pattern,
                rotation_group=source_assignment.rotation_group,
                shift_type=source_assignment.shift_type,
                five_two_off_days=source_assignment.five_two_off_days,
                default_position=source_assignment.default_position,
                start_date=source_assignment.start_date.replace(year=target.year, month=target.month, day=1),
                end_date=None,
                display_order=source_assignment.display_order,
                notes=source_assignment.notes or "",
                created_by=user,
                updated_by=user,
            )
            assignment_map[source_assignment.id] = cloned
        return assignment_map

    def _clone_cells_conservative(self, source, target, assignment_map, copy_base_cells):
        if not copy_base_cells or not assignment_map:
            return 0

        user = self._actor()
        created_count = 0
        source_cells = source.day_cells.select_related("attendance_status").order_by("assignment_id", "date")
        for source_cell in source_cells:
            target_assignment = assignment_map.get(source_cell.assignment_id)
            if not target_assignment:
                continue

            # Conservative copy: skip absences and manually overridden / exception-like entries.
            if source_cell.attendance_status and source_cell.attendance_status.is_absence:
                continue
            if source_cell.memo or source_cell.time_note or source_cell.manual_time_override:
                continue

            if source_cell.date.day > 28:
                try:
                    target_date = source_cell.date.replace(year=target.year, month=target.month)
                except ValueError:
                    continue
            else:
                target_date = source_cell.date.replace(year=target.year, month=target.month)

            CalendarDayCell.objects.update_or_create(
                assignment=target_assignment,
                date=target_date,
                defaults={
                    "calendar": target,
                    "position": source_cell.position,
                    "attendance_status": source_cell.attendance_status,
                    "work_time_code": source_cell.work_time_code,
                    "operational_code": source_cell.operational_code,
                    "scheduled_regular_minutes": source_cell.scheduled_regular_minutes,
                    "scheduled_overtime_minutes": source_cell.scheduled_overtime_minutes,
                    "actual_work_minutes": 0,
                    "actual_overtime_minutes": 0,
                    "start_time": source_cell.start_time,
                    "end_time": source_cell.end_time,
                    "break_minutes": source_cell.break_minutes,
                    "crosses_midnight": source_cell.crosses_midnight,
                    "manual_time_override": False,
                    "leave_time": None,
                    "time_note": "",
                    "overtime_minutes": 0,
                    "memo": "",
                    "raw_value": "",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            created_count += 1
        return created_count

    def _clone_assignments_to_template(self, calendar, template):
        user = self._actor()
        assignment_map = {}
        source_assignments = calendar.assignments.order_by("display_order", "employee_id", "id")
        for source_assignment in source_assignments:
            cloned = OperationCalendarTemplateAssignment.objects.create(
                template=template,
                employee=source_assignment.employee,
                operational_category=source_assignment.operational_category,
                work_pattern=source_assignment.work_pattern,
                rotation_group=source_assignment.rotation_group,
                shift_type=source_assignment.shift_type,
                five_two_off_days=source_assignment.five_two_off_days,
                default_position=source_assignment.default_position,
                display_order=source_assignment.display_order,
                created_by=user,
                updated_by=user,
            )
            assignment_map[source_assignment.id] = cloned
        return assignment_map

    def _clone_cells_to_template_conservative(self, calendar, template, assignment_map, include_base_cells):
        if not include_base_cells or not assignment_map:
            return 0
        user = self._actor()
        created_count = 0
        source_cells = calendar.day_cells.select_related("attendance_status").order_by("assignment_id", "date")
        for source_cell in source_cells:
            target_assignment = assignment_map.get(source_cell.assignment_id)
            if not target_assignment:
                continue
            if source_cell.attendance_status and source_cell.attendance_status.is_absence:
                continue
            if source_cell.memo or source_cell.time_note or source_cell.manual_time_override:
                continue
            OperationCalendarTemplateCell.objects.update_or_create(
                template=template,
                template_assignment=target_assignment,
                day=source_cell.date.day,
                defaults={
                    "position": source_cell.position,
                    "attendance_status": source_cell.attendance_status,
                    "work_time_code": source_cell.work_time_code,
                    "operational_code": source_cell.operational_code,
                    "raw_value": source_cell.raw_value or "",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            created_count += 1
        return created_count

    def _clone_template_assignments_to_calendar(self, template, calendar):
        user = self._actor()
        assignment_map = {}
        source_assignments = template.assignments.order_by("display_order", "employee_id", "id")
        for source_assignment in source_assignments:
            cloned = CalendarEmployeeAssignment.objects.create(
                calendar=calendar,
                employee=source_assignment.employee,
                operational_category=source_assignment.operational_category,
                work_pattern=source_assignment.work_pattern,
                rotation_group=source_assignment.rotation_group,
                shift_type=source_assignment.shift_type,
                five_two_off_days=source_assignment.five_two_off_days,
                default_position=source_assignment.default_position,
                start_date=datetime(calendar.year, calendar.month, 1).date(),
                end_date=None,
                display_order=source_assignment.display_order,
                notes="",
                created_by=user,
                updated_by=user,
            )
            assignment_map[source_assignment.id] = cloned
        return assignment_map

    def _clone_template_cells_to_calendar(self, template, calendar, assignment_map):
        if not assignment_map:
            return 0
        user = self._actor()
        created_count = 0
        template_cells = template.cells.select_related("template_assignment").order_by("template_assignment_id", "day")
        for template_cell in template_cells:
            target_assignment = assignment_map.get(template_cell.template_assignment_id)
            if not target_assignment:
                continue
            try:
                target_date = datetime(calendar.year, calendar.month, template_cell.day).date()
            except ValueError:
                continue
            CalendarDayCell.objects.update_or_create(
                assignment=target_assignment,
                date=target_date,
                defaults={
                    "calendar": calendar,
                    "position": template_cell.position,
                    "attendance_status": template_cell.attendance_status,
                    "work_time_code": template_cell.work_time_code,
                    "operational_code": template_cell.operational_code,
                    "raw_value": template_cell.raw_value or "",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            created_count += 1
        return created_count

    @action(detail=True, methods=["get", "post"])
    def requirements(self, request, pk=None):
        calendar = self.get_object()

        if request.method == "GET":
            queryset = calendar.position_requirements.select_related("position").order_by("date", "position__code")
            serializer = PositionDailyRequirementSerializer(queryset, many=True)
            return Response(serializer.data)

        serializer = PositionDailyRequirementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._actor()
        requirement = serializer.save(calendar=calendar, created_by=user, updated_by=user)
        return Response(
            PositionDailyRequirementSerializer(requirement).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"], url_path=r"requirements/(?P<requirement_id>\d+)")
    def requirement_detail(self, request, pk=None, requirement_id=None):
        calendar = self.get_object()
        requirement = get_object_or_404(PositionDailyRequirement, pk=requirement_id, calendar=calendar)
        serializer = PositionDailyRequirementSerializer(requirement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=self._actor())
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="requirements/replicate")
    def replicate_requirements(self, request, pk=None):
        calendar = self.get_object()
        try:
            position_id = int(request.data.get("position"))
            required_headcount = int(request.data.get("required_headcount", 0))
        except (TypeError, ValueError):
            return Response({"detail": "position e required_headcount são obrigatórios."}, status=status.HTTP_400_BAD_REQUEST)

        mode = str(request.data.get("mode") or "remaining").strip().lower()
        base_date_raw = request.data.get("date")
        notes = str(request.data.get("notes") or "")
        weekdays_only = bool(request.data.get("weekdays_only", False))
        if not base_date_raw:
            return Response({"detail": "date é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            base_date = datetime.fromisoformat(str(base_date_raw)).date()
        except ValueError:
            return Response({"detail": "date inválida."}, status=status.HTTP_400_BAD_REQUEST)

        if base_date.year != calendar.year or base_date.month != calendar.month:
            return Response({"detail": "A data base deve pertencer ao mês do calendário."}, status=status.HTTP_400_BAD_REQUEST)

        _, total_days = monthrange(calendar.year, calendar.month)
        month_start = datetime(calendar.year, calendar.month, 1).date()
        month_end = datetime(calendar.year, calendar.month, total_days).date()
        if mode not in {"remaining", "all"}:
            return Response({"detail": "mode inválido. Use remaining ou all."}, status=status.HTTP_400_BAD_REQUEST)

        start_date = base_date if mode == "remaining" else month_start
        target_dates = []
        current = start_date
        while current <= month_end:
            if not weekdays_only or current.weekday() < 5:
                target_dates.append(current)
            current += timedelta(days=1)

        position = get_object_or_404(OperationalPosition, pk=position_id)
        user = self._actor()
        created = 0
        updated = 0
        with transaction.atomic():
            for current_date in target_dates:
                obj, was_created = PositionDailyRequirement.objects.update_or_create(
                    calendar=calendar,
                    position=position,
                    date=current_date,
                    defaults={
                        "required_headcount": required_headcount,
                        "notes": notes,
                        "updated_by": user,
                        "created_by": user,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        return Response(
            {
                "created": created,
                "updated": updated,
                "affected_days": len(target_dates),
                "mode": mode,
                "weekdays_only": weekdays_only,
            }
        )

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        calendar = self.get_object()
        requirements = calendar.position_requirements.select_related("position").order_by("date", "position__code")

        requirement_map = {
            (requirement.date, requirement.position_id): {
                "date": requirement.date,
                "position": requirement.position,
                "requirement_id": requirement.id,
                "required_headcount": requirement.required_headcount,
            }
            for requirement in requirements
        }

        assigned_counts = (
            CalendarDayCell.objects.filter(
                calendar=calendar,
                position__isnull=False,
                attendance_status__is_working_day=True,
            )
            .values("date", "position_id")
            .annotate(assigned_headcount=Count("id"))
        )

        for row in assigned_counts:
            key = (row["date"], row["position_id"])
            if key not in requirement_map:
                position = OperationalPosition.objects.get(pk=row["position_id"])
                requirement_map[key] = {
                    "date": row["date"],
                    "position": position,
                    "required_headcount": 0,
                }
            requirement_map[key]["assigned_headcount"] = row["assigned_headcount"]

        summary = []
        for item in requirement_map.values():
            assigned_headcount = item.get("assigned_headcount", 0)
            required_headcount = item["required_headcount"]
            position = item["position"]
            summary.append(
                {
                    "date": item["date"],
                    "position": position.id,
                    "requirement_id": item.get("requirement_id"),
                    "position_code": position.code,
                    "position_name_pt": position.name_pt,
                    "position_name_jp": position.name_jp,
                    "required_headcount": required_headcount,
                    "assigned_headcount": assigned_headcount,
                    "difference": assigned_headcount - required_headcount,
                }
            )

        summary.sort(key=lambda item: (item["date"], item["position_code"]))
        return Response(summary)

    def _calendar_cells(self, calendar):
        queryset = calendar.day_cells.select_related(
            "assignment",
            "assignment__employee",
            "position",
            "attendance_status",
            "work_time_code",
            "operational_code",
        )
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset.order_by("assignment__display_order", "date")

    def _snapshot_cell(self, cell):
        if not cell:
            return None
        return {
            "position": cell.position_id,
            "attendance_status": cell.attendance_status_id,
            "work_time_code": cell.work_time_code_id,
            "operational_code": cell.operational_code_id,
            "raw_value": cell.raw_value or "",
            "overtime_minutes": cell.overtime_minutes or 0,
            "memo": cell.memo or "",
        }

    def _normalize_history_source(self, raw):
        normalized = str(raw or "").strip().lower().replace("-", "_")
        aliases = {
            "inline_edit": OperationCalendarHistory.Source.INLINE_EDIT,
            "batch_apply": OperationCalendarHistory.Source.QUICK_APPLY,
            "batch_status": OperationCalendarHistory.Source.QUICK_APPLY,
            "batch_op_code": OperationCalendarHistory.Source.QUICK_APPLY,
            "batch_clear": OperationCalendarHistory.Source.QUICK_APPLY,
            "paste": OperationCalendarHistory.Source.PASTE,
            "fill_handle": OperationCalendarHistory.Source.FILL_HANDLE,
            "pattern_4x2": OperationCalendarHistory.Source.PATTERN_4X2,
            "template": OperationCalendarHistory.Source.TEMPLATE,
            "month_duplication": OperationCalendarHistory.Source.MONTH_DUPLICATION,
            "next_month_generation": OperationCalendarHistory.Source.NEXT_MONTH_GENERATION,
        }
        return aliases.get(normalized, OperationCalendarHistory.Source.SYSTEM)

    def _log_cell_history(self, calendar, assignment, cell_date, source, old_value, new_value, metadata=None):
        try:
            OperationCalendarHistory.objects.create(
                calendar=calendar,
                assignment=assignment,
                cell_date=cell_date,
                source=source or OperationCalendarHistory.Source.SYSTEM,
                old_value=old_value,
                new_value=new_value,
                metadata=metadata or {},
                created_by=self._actor(),
                updated_by=self._actor(),
            )
        except Exception:
            return

    def _log_operation_history(self, calendar, source, metadata=None):
        try:
            OperationCalendarHistory.objects.create(
                calendar=calendar,
                source=source,
                metadata=metadata or {},
                created_by=self._actor(),
                updated_by=self._actor(),
            )
        except Exception:
            return

    def _paste_tsv(self, calendar, assignments, start_date, tsv, source=OperationCalendarHistory.Source.PASTE):
        parser_context = build_calendar_cell_parser_context(calendar)

        rows = list(csv.reader(StringIO(tsv), delimiter="\t"))
        if rows and rows[-1] == [""]:
            rows.pop()

        created = 0
        updated = 0
        affected_cells = []
        unrecognized_values = []
        actor = self._actor()

        with transaction.atomic():
            for row_index, row_values in enumerate(rows):
                if row_index >= len(assignments):
                    break

                assignment = assignments[row_index]
                for column_index, raw_value in enumerate(row_values):
                    cell_date = start_date + timedelta(days=column_index)
                    if cell_date.year != calendar.year or cell_date.month != calendar.month:
                        break

                    value = raw_value.strip()
                    parsed = parse_calendar_cell_value(value, parser_context)
                    cell, was_created = CalendarDayCell.objects.get_or_create(
                        assignment=assignment,
                        date=cell_date,
                        defaults={
                            "calendar": calendar,
                            "created_by": actor,
                        },
                    )
                    old_snapshot = None if was_created else self._snapshot_cell(cell)

                    cell.calendar = calendar
                    cell.raw_value = value
                    cell.position = parsed.position
                    cell.attendance_status = parsed.attendance_status
                    cell.work_time_code = parsed.work_time_code
                    cell.operational_code = parsed.operational_code
                    cell.memo = parsed.memo
                    cell.updated_by = actor
                    calculate_cell_work_minutes(cell, persist=False)
                    cell.save()
                    self._log_cell_history(
                        calendar=calendar,
                        assignment=assignment,
                        cell_date=cell_date,
                        source=source,
                        old_value=old_snapshot,
                        new_value=self._snapshot_cell(cell),
                        metadata={"origin": "paste_endpoint"},
                    )

                    if was_created:
                        created += 1
                    else:
                        updated += 1

                    affected_cells.append(
                        {
                            "id": cell.id,
                            "assignment": assignment.id,
                            "date": cell_date,
                            "raw_value": value,
                            "created": was_created,
                        }
                    )

                    if value and not parsed.recognized:
                        unrecognized_values.append(
                            {
                                "assignment": assignment.id,
                                "date": cell_date,
                                "value": value,
                            }
                        )

        return {
            "created": created,
            "updated": updated,
            "unrecognized_values": unrecognized_values,
            "affected_cells": affected_cells,
        }
