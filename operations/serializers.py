from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from master.serializers import DepartmentSerializer, EmployeeSerializer

from .models import (
    AttendanceStatus,
    CalendarDayCell,
    CalendarEmployeeAssignment,
    CalendarPrintPreset,
    EmployeeVisualCategory,
    MonthlyOperationCalendar,
    OperationalCode,
    OperationalPosition,
    PositionDailyRequirement,
    RotationGroupStyle,
    OperationCalendarTemplate,
    OperationCalendarTemplateAssignment,
    OperationCalendarHistory,
    HikitsuguiOccurrenceCategory,
    HikitsuguiReport,
    HikitsuguiItem,
    WorkTimeCode,
)
from .services import get_operational_rank, get_visual_category_from_master


class OperationalPositionSerializer(serializers.ModelSerializer):
    department_detail = DepartmentSerializer(source="department", read_only=True)

    class Meta:
        model = OperationalPosition
        fields = [
            "id",
            "department",
            "department_detail",
            "code",
            "name_pt",
            "name_jp",
            "building_floor",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "department_detail", "created_at", "updated_at"]


class AttendanceStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceStatus
        fields = [
            "id",
            "code",
            "label_pt",
            "label_jp",
            "color",
            "is_working_day",
            "is_absence",
            "is_paid_leave",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class WorkTimeCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkTimeCode
        fields = [
            "id",
            "code",
            "label_pt",
            "label_jp",
            "color",
            "affects_overtime",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RotationGroupStyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RotationGroupStyle
        fields = [
            "id",
            "group_code",
            "label",
            "background_color",
            "text_color",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EmployeeVisualCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeVisualCategory
        fields = [
            "id",
            "code",
            "label_pt",
            "label_jp",
            "target_column",
            "background_color",
            "text_color",
            "print_behavior",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OperationalCodeSerializer(serializers.ModelSerializer):
    attendance_status_detail = AttendanceStatusSerializer(source="attendance_status", read_only=True)
    work_time_code_detail = WorkTimeCodeSerializer(source="work_time_code", read_only=True)

    class Meta:
        model = OperationalCode
        fields = [
            "id",
            "code",
            "label_pt",
            "label_jp",
            "category",
            "attendance_status",
            "attendance_status_detail",
            "work_time_code",
            "work_time_code_detail",
            "background_color",
            "text_color",
            "affects_overtime",
            "affects_holiday_work",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "attendance_status_detail", "work_time_code_detail", "created_at", "updated_at"]


class MonthlyOperationCalendarSerializer(serializers.ModelSerializer):
    department_detail = DepartmentSerializer(source="department", read_only=True)
    process = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=MonthlyOperationCalendar._meta.get_field("process").remote_field.model.objects.all(),
        required=False,
    )
    shift = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        queryset=MonthlyOperationCalendar._meta.get_field("shift").remote_field.model.objects.all(),
        required=False,
    )

    class Meta:
        model = MonthlyOperationCalendar
        fields = [
            "id",
            "department",
            "department_detail",
            "process",
            "shift",
            "year",
            "month",
            "title",
            "status",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "department_detail", "created_at", "updated_at"]
        validators = []

    def validate(self, attrs):
        instance = self.instance or MonthlyOperationCalendar()
        for field, value in attrs.items():
            setattr(instance, field, value)

        try:
            instance.validate_unique()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)

        return attrs


class CalendarEmployeeAssignmentSerializer(serializers.ModelSerializer):
    employee_detail = EmployeeSerializer(source="employee", read_only=True)
    billing_rate = serializers.SerializerMethodField()
    process = serializers.SerializerMethodField()
    category_rank = serializers.SerializerMethodField()
    category_label = serializers.SerializerMethodField()
    visual_category = serializers.SerializerMethodField()

    class Meta:
        model = CalendarEmployeeAssignment
        fields = [
            "id",
            "calendar",
            "employee",
            "employee_detail",
            "operational_category",
            "billing_rate",
            "process",
            "category_rank",
            "category_label",
            "visual_category",
            "work_pattern",
            "rotation_group",
            "shift_type",
            "five_two_off_days",
            "default_position",
            "start_date",
            "end_date",
            "display_order",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "calendar", "employee_detail", "created_at", "updated_at"]

    def get_billing_rate(self, obj):
        billing = getattr(getattr(obj, "employee", None), "billing_rate", None)
        if not billing:
            return None
        return {"id": billing.id, "code": billing.code, "label_pt": billing.label_pt, "label_jp": billing.label_jp}

    def get_process(self, obj):
        process = getattr(getattr(obj, "employee", None), "process", None)
        if not process:
            return None
        return {"id": process.id, "code": process.code, "label_pt": process.label_pt, "label_jp": process.label_jp}

    def get_category_rank(self, obj):
        return get_operational_rank(obj)

    def get_category_label(self, obj):
        category = (obj.operational_category or "").strip().lower()
        labels = {
            "normal": "Normal",
            "koutei_leader": "Koutei Leader",
            "relief": "Relief",
            "trainer": "Trainer",
            "gl": "GL",
            "supervisor": "Supervisor",
            "manager": "Manager",
            "director": "Director",
        }
        return labels.get(category, "Outro")

    def get_visual_category(self, obj):
        employee = getattr(obj, "employee", None)
        if not employee:
            return "normal"
        return get_visual_category_from_master(employee)


class CalendarDayCellSerializer(serializers.ModelSerializer):
    position_detail = OperationalPositionSerializer(source="position", read_only=True)
    attendance_status_detail = AttendanceStatusSerializer(source="attendance_status", read_only=True)
    work_time_code_detail = WorkTimeCodeSerializer(source="work_time_code", read_only=True)
    operational_code_detail = OperationalCodeSerializer(source="operational_code", read_only=True)

    class Meta:
        model = CalendarDayCell
        fields = [
            "id",
            "calendar",
            "assignment",
            "date",
            "position",
            "position_detail",
            "attendance_status",
            "attendance_status_detail",
            "work_time_code",
            "work_time_code_detail",
            "operational_code",
            "operational_code_detail",
            "scheduled_regular_minutes",
            "scheduled_overtime_minutes",
            "actual_work_minutes",
            "actual_overtime_minutes",
            "start_time",
            "end_time",
            "break_minutes",
            "crosses_midnight",
            "manual_time_override",
            "leave_time",
            "time_note",
            "overtime_minutes",
            "memo",
            "raw_value",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "calendar",
            "position_detail",
            "attendance_status_detail",
            "work_time_code_detail",
            "operational_code_detail",
            "created_at",
            "updated_at",
        ]


class PositionDailyRequirementSerializer(serializers.ModelSerializer):
    position_detail = OperationalPositionSerializer(source="position", read_only=True)

    class Meta:
        model = PositionDailyRequirement
        fields = [
            "id",
            "calendar",
            "position",
            "position_detail",
            "date",
            "required_headcount",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "calendar", "position_detail", "created_at", "updated_at"]


class CalendarPrintPresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarPrintPreset
        fields = [
            "id",
            "calendar",
            "paper_size",
            "orientation",
            "scale_percent",
            "show_colors",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OperationCalendarTemplateAssignmentSerializer(serializers.ModelSerializer):
    employee_detail = EmployeeSerializer(source="employee", read_only=True)

    class Meta:
        model = OperationCalendarTemplateAssignment
        fields = [
            "id",
            "template",
            "employee",
            "employee_detail",
            "operational_category",
            "work_pattern",
            "rotation_group",
            "shift_type",
            "five_two_off_days",
            "default_position",
            "display_order",
        ]
        read_only_fields = ["id", "template", "employee_detail"]


class OperationCalendarTemplateSerializer(serializers.ModelSerializer):
    department_detail = DepartmentSerializer(source="department", read_only=True)
    process_detail = serializers.SerializerMethodField()
    shift_detail = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    assignments_count = serializers.SerializerMethodField()
    cells_count = serializers.SerializerMethodField()

    class Meta:
        model = OperationCalendarTemplate
        fields = [
            "id",
            "name",
            "description",
            "department",
            "department_detail",
            "process",
            "process_detail",
            "shift",
            "shift_detail",
            "created_by",
            "created_by_username",
            "is_active",
            "assignments_count",
            "cells_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "department_detail",
            "process_detail",
            "shift_detail",
            "created_by",
            "created_by_username",
            "assignments_count",
            "cells_count",
            "created_at",
            "updated_at",
        ]

    def get_process_detail(self, obj):
        process = getattr(obj, "process", None)
        if not process:
            return None
        return {"id": process.id, "code": process.code, "label_pt": process.label_pt, "label_jp": process.label_jp}

    def get_shift_detail(self, obj):
        shift = getattr(obj, "shift", None)
        if not shift:
            return None
        return {"id": shift.id, "code": shift.code, "label_pt": shift.label_pt, "label_jp": shift.label_jp}

    def get_created_by_username(self, obj):
        return getattr(obj.created_by, "username", None)

    def get_assignments_count(self, obj):
        return obj.assignments.count()

    def get_cells_count(self, obj):
        return obj.cells.count()


class OperationCalendarHistorySerializer(serializers.ModelSerializer):
    assignment_employee_id = serializers.SerializerMethodField()
    assignment_employee_name = serializers.SerializerMethodField()
    updated_by_username = serializers.SerializerMethodField()

    class Meta:
        model = OperationCalendarHistory
        fields = [
            "id",
            "calendar",
            "assignment",
            "assignment_employee_id",
            "assignment_employee_name",
            "cell_date",
            "source",
            "old_value",
            "new_value",
            "metadata",
            "updated_by",
            "updated_by_username",
            "created_at",
        ]
        read_only_fields = fields

    def get_assignment_employee_id(self, obj):
        employee = getattr(obj.assignment, "employee", None)
        return getattr(employee, "employee_id", None)

    def get_assignment_employee_name(self, obj):
        employee = getattr(obj.assignment, "employee", None)
        return getattr(employee, "name_en", None) or getattr(employee, "internal_name", None) or getattr(employee, "name_jp", None)

    def get_updated_by_username(self, obj):
        return getattr(obj.updated_by, "username", None)


class HikitsuguiOccurrenceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = HikitsuguiOccurrenceCategory
        fields = [
            "id",
            "code",
            "label_pt",
            "label_jp",
            "description",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class HikitsuguiItemSerializer(serializers.ModelSerializer):
    category_detail = HikitsuguiOccurrenceCategorySerializer(source="category", read_only=True)
    responsible_employee_detail = EmployeeSerializer(source="responsible_employee", read_only=True)

    class Meta:
        model = HikitsuguiItem
        fields = [
            "id",
            "report",
            "category",
            "category_detail",
            "title",
            "description",
            "action_taken",
            "pending_for_next_shift",
            "responsible_employee",
            "responsible_employee_detail",
            "status",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category_detail", "responsible_employee_detail", "created_at", "updated_at"]


class HikitsuguiReportSerializer(serializers.ModelSerializer):
    calendar_detail = MonthlyOperationCalendarSerializer(source="calendar", read_only=True)
    responsible_employee_detail = EmployeeSerializer(source="responsible_employee", read_only=True)
    responsible_assignment_detail = CalendarEmployeeAssignmentSerializer(source="responsible_assignment", read_only=True)
    items = HikitsuguiItemSerializer(many=True, read_only=True)
    open_items_count = serializers.SerializerMethodField()

    class Meta:
        model = HikitsuguiReport
        fields = [
            "id",
            "calendar",
            "calendar_detail",
            "report_date",
            "shift",
            "process",
            "area_equipment",
            "responsible_employee",
            "responsible_employee_detail",
            "responsible_assignment",
            "responsible_assignment_detail",
            "status",
            "priority",
            "description",
            "action_taken",
            "pending_for_next_shift",
            "items",
            "open_items_count",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "calendar_detail",
            "responsible_employee_detail",
            "responsible_assignment_detail",
            "items",
            "open_items_count",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        instance = self.instance
        calendar = attrs.get("calendar", getattr(instance, "calendar", None))
        responsible_assignment = attrs.get("responsible_assignment", getattr(instance, "responsible_assignment", None))
        responsible_employee = attrs.get("responsible_employee", getattr(instance, "responsible_employee", None))

        if responsible_assignment and calendar and responsible_assignment.calendar_id != calendar.id:
            raise serializers.ValidationError({"responsible_assignment": "Assignment não pertence ao calendário informado."})

        if responsible_assignment and responsible_employee and responsible_assignment.employee_id != responsible_employee.employee_id:
            raise serializers.ValidationError({"responsible_employee": "Funcionário precisa ser o mesmo do assignment selecionado."})

        return attrs

    def get_open_items_count(self, obj):
        return obj.items.exclude(status=HikitsuguiItem.Status.RESOLVED).count()
