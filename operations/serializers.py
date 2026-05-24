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
    WorkTimeCode,
)


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

    class Meta:
        model = CalendarEmployeeAssignment
        fields = [
            "id",
            "calendar",
            "employee",
            "employee_detail",
            "operational_category",
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
