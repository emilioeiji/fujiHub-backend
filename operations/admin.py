from django.contrib import admin

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
    HikitsuguiOccurrenceCategory,
    HikitsuguiReport,
    HikitsuguiItem,
    RotationGroupStyle,
    WorkTimeCode,
)


@admin.register(OperationalPosition)
class OperationalPositionAdmin(admin.ModelAdmin):
    list_display = ("code", "department", "name_pt", "name_jp", "building_floor", "is_active")
    list_filter = ("department", "building_floor", "is_active")
    search_fields = ("code", "name_pt", "name_jp", "description")


@admin.register(AttendanceStatus)
class AttendanceStatusAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "label_pt",
        "label_jp",
        "is_working_day",
        "is_absence",
        "is_paid_leave",
        "is_active",
    )
    list_filter = ("is_working_day", "is_absence", "is_paid_leave", "is_active")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(WorkTimeCode)
class WorkTimeCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp", "affects_overtime", "is_active")
    list_filter = ("affects_overtime", "is_active")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(RotationGroupStyle)
class RotationGroupStyleAdmin(admin.ModelAdmin):
    list_display = ("group_code", "label", "background_color", "text_color", "display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("group_code", "label")


@admin.register(EmployeeVisualCategory)
class EmployeeVisualCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "label_pt",
        "label_jp",
        "target_column",
        "background_color",
        "print_behavior",
        "display_order",
        "is_active",
    )
    list_filter = ("target_column", "print_behavior", "is_active")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(OperationalCode)
class OperationalCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "label_pt",
        "label_jp",
        "category",
        "attendance_status",
        "work_time_code",
        "affects_overtime",
        "affects_holiday_work",
        "is_active",
    )
    list_filter = ("category", "affects_overtime", "affects_holiday_work", "is_active")
    search_fields = ("code", "label_pt", "label_jp")


class CalendarEmployeeAssignmentInline(admin.TabularInline):
    model = CalendarEmployeeAssignment
    fields = (
        "employee",
        "operational_category",
        "work_pattern",
        "rotation_group",
        "shift_type",
        "five_two_off_days",
        "default_position",
        "start_date",
        "end_date",
        "display_order",
        "is_active",
    )
    extra = 0


class PositionDailyRequirementInline(admin.TabularInline):
    model = PositionDailyRequirement
    extra = 0


class CalendarPrintPresetInline(admin.TabularInline):
    model = CalendarPrintPreset
    extra = 0


@admin.register(MonthlyOperationCalendar)
class MonthlyOperationCalendarAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "process", "shift", "year", "month", "status", "is_active")
    list_filter = ("status", "department", "process", "shift", "year", "month", "is_active")
    search_fields = ("title", "department__code", "department__label_pt", "department__label_jp")
    inlines = [CalendarEmployeeAssignmentInline, PositionDailyRequirementInline, CalendarPrintPresetInline]


@admin.register(CalendarEmployeeAssignment)
class CalendarEmployeeAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "calendar",
        "employee",
        "operational_category",
        "work_pattern",
        "rotation_group",
        "shift_type",
        "default_position",
        "start_date",
        "end_date",
        "display_order",
        "is_active",
    )
    list_filter = ("operational_category", "work_pattern", "rotation_group", "shift_type", "calendar", "start_date", "is_active")
    search_fields = ("employee__employee_id", "employee__name_en", "employee__name_jp", "notes")


@admin.register(CalendarDayCell)
class CalendarDayCellAdmin(admin.ModelAdmin):
    list_display = (
        "calendar",
        "assignment",
        "date",
        "position",
        "attendance_status",
        "work_time_code",
        "operational_code",
        "scheduled_regular_minutes",
        "scheduled_overtime_minutes",
        "start_time",
        "end_time",
        "break_minutes",
        "crosses_midnight",
        "manual_time_override",
        "overtime_minutes",
    )
    list_filter = ("calendar", "date", "position", "attendance_status", "work_time_code", "operational_code")
    search_fields = ("assignment__employee__employee_id", "raw_value", "memo")


@admin.register(PositionDailyRequirement)
class PositionDailyRequirementAdmin(admin.ModelAdmin):
    list_display = ("calendar", "position", "date", "required_headcount")
    list_filter = ("calendar", "position", "date")
    search_fields = ("position__code", "position__name_pt", "position__name_jp", "notes")


@admin.register(CalendarPrintPreset)
class CalendarPrintPresetAdmin(admin.ModelAdmin):
    list_display = ("calendar", "paper_size", "orientation", "scale_percent", "show_colors", "is_active")
    list_filter = ("paper_size", "orientation", "show_colors", "is_active")


@admin.register(HikitsuguiOccurrenceCategory)
class HikitsuguiOccurrenceCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp", "display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "label_pt", "label_jp")


class HikitsuguiItemInline(admin.TabularInline):
    model = HikitsuguiItem
    extra = 0


@admin.register(HikitsuguiReport)
class HikitsuguiReportAdmin(admin.ModelAdmin):
    list_display = ("report_date", "shift", "process", "area_equipment", "status", "priority", "responsible_employee", "is_active")
    list_filter = ("status", "priority", "shift", "process", "calendar", "is_active")
    search_fields = ("area_equipment", "description", "pending_for_next_shift", "responsible_employee__employee_id")
    inlines = [HikitsuguiItemInline]


@admin.register(HikitsuguiItem)
class HikitsuguiItemAdmin(admin.ModelAdmin):
    list_display = ("report", "title", "category", "status", "priority", "responsible_employee", "is_active")
    list_filter = ("status", "priority", "category", "is_active")
    search_fields = ("title", "description", "action_taken", "pending_for_next_shift")
