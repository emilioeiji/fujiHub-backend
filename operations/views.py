import csv
from datetime import datetime, timedelta
from io import StringIO

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    AttendanceStatus,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    MonthlyOperationCalendar,
    OperationalPosition,
    PositionDailyRequirement,
    WorkTimeCode,
)
from .permissions import OperationsCalendarPermission, OperationsMasterDataPermission
from .serializers import (
    AttendanceStatusSerializer,
    CalendarDayCellSerializer,
    CalendarEmployeeAssignmentSerializer,
    MonthlyOperationCalendarSerializer,
    OperationalPositionSerializer,
    PositionDailyRequirementSerializer,
    WorkTimeCodeSerializer,
)
from .services import build_calendar_cell_parser_context, parse_calendar_cell_value


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


class MonthlyOperationCalendarViewSet(ActorMixin, viewsets.ModelViewSet):
    queryset = MonthlyOperationCalendar.objects.select_related("department", "process", "shift")
    serializer_class = MonthlyOperationCalendarSerializer
    permission_classes = [OperationsCalendarPermission]

    @action(detail=True, methods=["get", "post"])
    def assignments(self, request, pk=None):
        calendar = self.get_object()

        if request.method == "GET":
            queryset = calendar.assignments.select_related("employee").order_by("display_order", "employee_id")
            serializer = CalendarEmployeeAssignmentSerializer(queryset, many=True)
            return Response(serializer.data)

        serializer = CalendarEmployeeAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self._actor()
        assignment = serializer.save(calendar=calendar, created_by=user, updated_by=user)
        return Response(CalendarEmployeeAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"])
    def cells(self, request, pk=None):
        calendar = self.get_object()

        if request.method == "GET":
            queryset = self._calendar_cells(calendar)
            serializer = CalendarDayCellSerializer(queryset, many=True)
            return Response(serializer.data)

        serializer = CalendarDayCellSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.validated_data["assignment"]
        if assignment.calendar_id != calendar.id:
            return Response(
                {"assignment": "Assignment does not belong to this calendar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = self._actor()
        cell = serializer.save(calendar=calendar, created_by=user, updated_by=user)
        return Response(CalendarDayCellSerializer(cell).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"cells/(?P<cell_id>\d+)")
    def cell_detail(self, request, pk=None, cell_id=None):
        calendar = self.get_object()
        cell = get_object_or_404(CalendarDayCell, pk=cell_id, calendar=calendar)
        serializer = CalendarDayCellSerializer(cell, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        assignment = serializer.validated_data.get("assignment")
        if assignment and assignment.calendar_id != calendar.id:
            return Response(
                {"assignment": "Assignment does not belong to this calendar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(updated_by=self._actor())
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

        result = self._paste_tsv(calendar, assignments[start_index:], start_date, tsv)
        return Response(result, status=status.HTTP_200_OK)

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
        )
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        return queryset.order_by("assignment__display_order", "date")

    def _paste_tsv(self, calendar, assignments, start_date, tsv):
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

                    cell.calendar = calendar
                    cell.raw_value = value
                    cell.position = parsed.position
                    cell.attendance_status = parsed.attendance_status
                    cell.work_time_code = parsed.work_time_code
                    cell.memo = parsed.memo
                    cell.updated_by = actor
                    cell.save()

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
