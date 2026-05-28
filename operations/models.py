from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel


class OperationalPosition(BaseModel):
    department = models.ForeignKey(
        "master.Department",
        on_delete=models.PROTECT,
        related_name="operational_positions",
    )
    code = models.CharField(max_length=50)
    name_pt = models.CharField(max_length=100)
    name_jp = models.CharField(max_length=100)
    building_floor = models.ForeignKey(
        "master.BuildingFloor",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operational_positions",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["department", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"],
                name="unique_operational_position_department_code",
            ),
        ]

    def __str__(self):
        return f"{self.department} - {self.code}"


class AttendanceStatus(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    label_pt = models.CharField(max_length=100)
    label_jp = models.CharField(max_length=100)
    color = models.CharField(max_length=20, blank=True)
    is_working_day = models.BooleanField(default=True)
    is_absence = models.BooleanField(default=False)
    is_paid_leave = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        verbose_name = "Attendance status"
        verbose_name_plural = "Attendance statuses"

    def __str__(self):
        return self.code


class WorkTimeCode(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    label_pt = models.CharField(max_length=100)
    label_jp = models.CharField(max_length=100)
    color = models.CharField(max_length=20, blank=True)
    affects_overtime = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class RotationGroupStyle(BaseModel):
    group_code = models.CharField(max_length=1, unique=True)
    label = models.CharField(max_length=50)
    background_color = models.CharField(max_length=20, blank=True)
    text_color = models.CharField(max_length=20, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "group_code"]

    def __str__(self):
        return self.group_code


class EmployeeVisualCategory(BaseModel):
    class TargetColumn(models.TextChoices):
        NAME = "name", "Name"
        KANA = "kana", "Kana"
        CODE = "code", "Code"
        ROW = "row", "Row"

    class PrintBehavior(models.TextChoices):
        SHOW = "show", "Show"
        SUPPRESS_ON_PRINT = "suppress_on_print", "Suppress on print"

    code = models.SlugField(max_length=50, unique=True)
    label_pt = models.CharField(max_length=100)
    label_jp = models.CharField(max_length=100)
    target_column = models.CharField(max_length=20, choices=TargetColumn.choices)
    background_color = models.CharField(max_length=20, blank=True)
    text_color = models.CharField(max_length=20, blank=True)
    print_behavior = models.CharField(
        max_length=30,
        choices=PrintBehavior.choices,
        default=PrintBehavior.SHOW,
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "code"]
        verbose_name = "Employee visual category"
        verbose_name_plural = "Employee visual categories"

    def __str__(self):
        return self.code


class OperationalCode(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    label_pt = models.CharField(max_length=100)
    label_jp = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True)
    attendance_status = models.ForeignKey(
        AttendanceStatus,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operational_codes",
    )
    work_time_code = models.ForeignKey(
        WorkTimeCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operational_codes",
    )
    background_color = models.CharField(max_length=20, blank=True)
    text_color = models.CharField(max_length=20, blank=True)
    affects_overtime = models.BooleanField(default=False)
    affects_holiday_work = models.BooleanField(default=False)

    class Meta:
        ordering = ["category", "code"]

    def __str__(self):
        return self.code


class MonthlyOperationCalendar(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    department = models.ForeignKey(
        "master.Department",
        on_delete=models.PROTECT,
        related_name="operation_calendars",
    )
    process = models.ForeignKey(
        "master.Process",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operation_calendars",
    )
    shift = models.ForeignKey(
        "master.Shift",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operation_calendars",
    )
    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    title = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-year", "-month", "department"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "process", "shift", "year", "month"],
                name="unique_operation_calendar_scope_month",
            ),
        ]

    def __str__(self):
        return f"{self.department} - {self.year:04d}-{self.month:02d}"

    def _duplicate_queryset(self):
        queryset = MonthlyOperationCalendar.objects.filter(
            department=self.department,
            year=self.year,
            month=self.month,
        )

        if self.process_id is None:
            queryset = queryset.filter(process__isnull=True)
        else:
            queryset = queryset.filter(process_id=self.process_id)

        if self.shift_id is None:
            queryset = queryset.filter(shift__isnull=True)
        else:
            queryset = queryset.filter(shift_id=self.shift_id)

        if self.pk:
            queryset = queryset.exclude(pk=self.pk)

        return queryset

    def clean(self):
        super().clean()

        if self.department_id and self.year and self.month and self._duplicate_queryset().exists():
            raise ValidationError(
                {
                    "__all__": (
                        "Ja existe um calendario para este departamento, processo, "
                        "turno, ano e mes."
                    )
                }
            )

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)

        excluded = set(exclude or [])
        calendar_scope_fields = {"department", "process", "shift", "year", "month"}
        if calendar_scope_fields.intersection(excluded):
            return

        if self.department_id and self.year and self.month and self._duplicate_queryset().exists():
            raise ValidationError(
                {
                    "__all__": (
                        "Ja existe um calendario para este departamento, processo, "
                        "turno, ano e mes."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class CalendarEmployeeAssignment(BaseModel):
    class OperationalCategory(models.TextChoices):
        NORMAL = "normal", "Normal"
        RELIEF = "relief", "Relief"
        TRAINER = "trainer", "Trainer"
        KOUTEI_LEADER = "koutei_leader", "Koutei leader"
        GL = "gl", "GL"
        SUPERVISOR = "supervisor", "Supervisor"
        MANAGER = "manager", "Manager"
        DIRECTOR = "director", "Director"

    class WorkPattern(models.TextChoices):
        FOUR_TWO = "4x2", "4x2"
        FIVE_TWO = "5x2", "5x2"
        MANUAL = "manual", "Manual"

    class RotationGroup(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"

    class ShiftType(models.TextChoices):
        DAY = "day", "Day"
        NIGHT = "night", "Night"
        FLEXIBLE = "flexible", "Flexible"

    calendar = models.ForeignKey(
        MonthlyOperationCalendar,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.PROTECT,
        related_name="operation_calendar_assignments",
    )
    operational_category = models.CharField(
        max_length=30,
        choices=OperationalCategory.choices,
        default=OperationalCategory.NORMAL,
    )
    work_pattern = models.CharField(
        max_length=10,
        choices=WorkPattern.choices,
        default=WorkPattern.FOUR_TWO,
    )
    rotation_group = models.CharField(
        max_length=1,
        choices=RotationGroup.choices,
        blank=True,
    )
    shift_type = models.CharField(
        max_length=10,
        choices=ShiftType.choices,
        default=ShiftType.DAY,
    )
    five_two_off_days = models.JSONField(default=list, blank=True)
    default_position = models.ForeignKey(
        OperationalPosition,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="default_assignments",
    )
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["calendar", "display_order", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "employee", "start_date"],
                name="unique_calendar_assignment_employee_start",
            ),
        ]

    def __str__(self):
        return f"{self.calendar} - {self.employee}"


class CalendarDayCell(BaseModel):
    calendar = models.ForeignKey(
        MonthlyOperationCalendar,
        on_delete=models.CASCADE,
        related_name="day_cells",
    )
    assignment = models.ForeignKey(
        CalendarEmployeeAssignment,
        on_delete=models.CASCADE,
        related_name="day_cells",
    )
    date = models.DateField()
    position = models.ForeignKey(
        OperationalPosition,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="day_cells",
    )
    attendance_status = models.ForeignKey(
        AttendanceStatus,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="day_cells",
    )
    work_time_code = models.ForeignKey(
        WorkTimeCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="day_cells",
    )
    operational_code = models.ForeignKey(
        OperationalCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="day_cells",
    )
    scheduled_regular_minutes = models.PositiveIntegerField(default=0)
    scheduled_overtime_minutes = models.PositiveIntegerField(default=0)
    actual_work_minutes = models.PositiveIntegerField(default=0)
    actual_overtime_minutes = models.PositiveIntegerField(default=0)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    break_minutes = models.PositiveIntegerField(default=0)
    crosses_midnight = models.BooleanField(default=False)
    manual_time_override = models.BooleanField(default=False)
    leave_time = models.TimeField(blank=True, null=True)
    time_note = models.TextField(blank=True)
    overtime_minutes = models.PositiveIntegerField(default=0)
    memo = models.TextField(blank=True)
    raw_value = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["calendar", "assignment", "date"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "date"],
                name="unique_calendar_day_cell_assignment_date",
            ),
        ]
        indexes = [
            models.Index(fields=["calendar", "date"]),
            models.Index(fields=["position", "date"]),
        ]

    def __str__(self):
        return f"{self.assignment} - {self.date}"


class PositionDailyRequirement(BaseModel):
    calendar = models.ForeignKey(
        MonthlyOperationCalendar,
        on_delete=models.CASCADE,
        related_name="position_requirements",
    )
    position = models.ForeignKey(
        OperationalPosition,
        on_delete=models.CASCADE,
        related_name="daily_requirements",
    )
    date = models.DateField()
    required_headcount = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["calendar", "date", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "position", "date"],
                name="unique_position_daily_requirement",
            ),
        ]

    def __str__(self):
        return f"{self.calendar} - {self.position} - {self.date}"


class CalendarPrintPreset(BaseModel):
    class PaperSize(models.TextChoices):
        A4 = "A4", "A4"
        A3 = "A3", "A3"

    class Orientation(models.TextChoices):
        PORTRAIT = "portrait", "Portrait"
        LANDSCAPE = "landscape", "Landscape"

    calendar = models.ForeignKey(
        MonthlyOperationCalendar,
        on_delete=models.CASCADE,
        related_name="print_presets",
    )
    paper_size = models.CharField(max_length=5, choices=PaperSize.choices, default=PaperSize.A4)
    orientation = models.CharField(
        max_length=20,
        choices=Orientation.choices,
        default=Orientation.LANDSCAPE,
    )
    scale_percent = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(10), MaxValueValidator(200)],
    )
    show_colors = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["calendar", "paper_size", "orientation"]

    def __str__(self):
        return f"{self.calendar} - {self.paper_size} {self.orientation}"


class OperationCalendarTemplate(BaseModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        "master.Department",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operation_calendar_templates",
    )
    process = models.ForeignKey(
        "master.Process",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operation_calendar_templates",
    )
    shift = models.ForeignKey(
        "master.Shift",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="operation_calendar_templates",
    )

    class Meta:
        ordering = ["name", "-updated_at", "-id"]

    def __str__(self):
        return self.name


class OperationCalendarTemplateAssignment(BaseModel):
    template = models.ForeignKey(
        OperationCalendarTemplate,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.PROTECT,
        related_name="operation_calendar_template_assignments",
    )
    operational_category = models.CharField(
        max_length=30,
        choices=CalendarEmployeeAssignment.OperationalCategory.choices,
        default=CalendarEmployeeAssignment.OperationalCategory.NORMAL,
    )
    work_pattern = models.CharField(
        max_length=10,
        choices=CalendarEmployeeAssignment.WorkPattern.choices,
        default=CalendarEmployeeAssignment.WorkPattern.FOUR_TWO,
    )
    rotation_group = models.CharField(
        max_length=1,
        choices=CalendarEmployeeAssignment.RotationGroup.choices,
        blank=True,
    )
    shift_type = models.CharField(
        max_length=10,
        choices=CalendarEmployeeAssignment.ShiftType.choices,
        default=CalendarEmployeeAssignment.ShiftType.DAY,
    )
    five_two_off_days = models.JSONField(default=list, blank=True)
    default_position = models.ForeignKey(
        OperationalPosition,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="template_default_assignments",
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "employee_id", "id"]


class OperationCalendarTemplateCell(BaseModel):
    template = models.ForeignKey(
        OperationCalendarTemplate,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    template_assignment = models.ForeignKey(
        OperationCalendarTemplateAssignment,
        on_delete=models.CASCADE,
        related_name="cells",
    )
    day = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)])
    position = models.ForeignKey(
        OperationalPosition,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="template_cells",
    )
    attendance_status = models.ForeignKey(
        AttendanceStatus,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="template_cells",
    )
    work_time_code = models.ForeignKey(
        WorkTimeCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="template_cells",
    )
    operational_code = models.ForeignKey(
        OperationalCode,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="template_cells",
    )
    raw_value = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["template_assignment", "day", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["template_assignment", "day"],
                name="unique_template_assignment_day",
            ),
        ]


class OperationCalendarHistory(BaseModel):
    class Source(models.TextChoices):
        INLINE_EDIT = "inline_edit", "inline_edit"
        QUICK_APPLY = "quick_apply", "quick_apply"
        PASTE = "paste", "paste"
        FILL_HANDLE = "fill_handle", "fill_handle"
        PATTERN_4X2 = "pattern_4x2", "pattern_4x2"
        TEMPLATE = "template", "template"
        MONTH_DUPLICATION = "month_duplication", "month_duplication"
        NEXT_MONTH_GENERATION = "next_month_generation", "next_month_generation"
        SYSTEM = "system", "system"

    calendar = models.ForeignKey(
        MonthlyOperationCalendar,
        on_delete=models.CASCADE,
        related_name="history_entries",
    )
    assignment = models.ForeignKey(
        CalendarEmployeeAssignment,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="history_entries",
    )
    cell_date = models.DateField(blank=True, null=True)
    source = models.CharField(max_length=40, choices=Source.choices, default=Source.SYSTEM)
    old_value = models.JSONField(blank=True, null=True)
    new_value = models.JSONField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["calendar", "created_at"]),
            models.Index(fields=["calendar", "source"]),
            models.Index(fields=["calendar", "cell_date"]),
        ]


class HikitsuguiOccurrenceCategory(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    label_pt = models.CharField(max_length=100)
    label_jp = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "code"]

    def __str__(self):
        return self.label_pt or self.code


class HikitsuguiReport(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        IN_PROGRESS = "in_progress", "Em andamento"
        RESOLVED = "resolved", "Resolvido"
        PENDING = "pending", "Pendente"

    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        CRITICAL = "critical", "Crítica"

    calendar = models.ForeignKey(
        MonthlyOperationCalendar,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hikitsugui_reports",
    )
    report_date = models.DateField()
    shift = models.ForeignKey(
        "master.Shift",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hikitsugui_reports",
    )
    process = models.ForeignKey(
        "master.Process",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hikitsugui_reports",
    )
    area_equipment = models.CharField(max_length=150)
    responsible_employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hikitsugui_reports",
    )
    responsible_assignment = models.ForeignKey(
        CalendarEmployeeAssignment,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hikitsugui_reports",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    description = models.TextField()
    action_taken = models.TextField(blank=True)
    pending_for_next_shift = models.TextField(blank=True)

    class Meta:
        ordering = ["-report_date", "-updated_at", "-id"]
        indexes = [
            models.Index(fields=["report_date", "shift", "process"]),
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self):
        return f"{self.report_date} - {self.area_equipment}"


class HikitsuguiItem(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        IN_PROGRESS = "in_progress", "Em andamento"
        RESOLVED = "resolved", "Resolvido"
        PENDING = "pending", "Pendente"

    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        CRITICAL = "critical", "Crítica"

    report = models.ForeignKey(
        HikitsuguiReport,
        on_delete=models.CASCADE,
        related_name="items",
    )
    category = models.ForeignKey(
        HikitsuguiOccurrenceCategory,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="items",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    action_taken = models.TextField(blank=True)
    pending_for_next_shift = models.TextField(blank=True)
    responsible_employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="hikitsugui_items",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["report", "status", "priority"]),
        ]

    def __str__(self):
        return self.title


class ProductionMonitorSource(BaseModel):
    class SourceType(models.TextChoices):
        TXT = "txt", "TXT"
        CSV = "csv", "CSV"
        API = "api", "API"
        MANUAL = "manual", "Manual"

    name = models.CharField(max_length=120)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.MANUAL)
    process = models.ForeignKey(
        "master.Process",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="production_monitor_sources",
    )
    area = models.CharField(max_length=120, blank=True)
    poll_seconds = models.PositiveIntegerField(default=30)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class ProductionSnapshot(BaseModel):
    source = models.ForeignKey(
        ProductionMonitorSource,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="snapshots",
    )
    captured_at = models.DateTimeField()
    shift = models.ForeignKey(
        "master.Shift",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="production_snapshots",
    )
    process = models.ForeignKey(
        "master.Process",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="production_snapshots",
    )
    area = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-captured_at", "-id"]
        indexes = [
            models.Index(fields=["captured_at", "process", "shift"]),
        ]

    def __str__(self):
        return f"Snapshot {self.id} @ {self.captured_at}"


class ProductionMachineStatus(BaseModel):
    class MachineState(models.TextChoices):
        RUNNING = "running", "Running"
        STOPPED = "stopped", "Stopped"
        IDLE = "idle", "Idle"
        ERROR = "error", "Error"

    snapshot = models.ForeignKey(
        ProductionSnapshot,
        on_delete=models.CASCADE,
        related_name="machine_statuses",
    )
    machine_code = models.CharField(max_length=80)
    equipment_name = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=MachineState.choices, default=MachineState.IDLE)
    production_actual = models.IntegerField(default=0)
    production_target = models.IntegerField(default=0)
    kadouritsu = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    run_minutes = models.PositiveIntegerField(default=0)
    stop_minutes = models.PositiveIntegerField(default=0)
    last_update_at = models.DateTimeField(blank=True, null=True)
    alarm_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["machine_code", "id"]
        indexes = [
            models.Index(fields=["snapshot", "status"]),
            models.Index(fields=["machine_code"]),
        ]

    def __str__(self):
        return f"{self.machine_code} ({self.status})"


class ProductionMetrics(BaseModel):
    snapshot = models.OneToOneField(
        ProductionSnapshot,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    total_actual = models.IntegerField(default=0)
    total_target = models.IntegerField(default=0)
    average_kadouritsu = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    running_count = models.PositiveIntegerField(default=0)
    stopped_count = models.PositiveIntegerField(default=0)
    idle_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    alarms_active = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-snapshot__captured_at", "-id"]

    def __str__(self):
        return f"Metrics snapshot {self.snapshot_id}"


class OperationsSettings(BaseModel):
    singleton_key = models.CharField(max_length=20, default="default", unique=True)
    weekly_warning_hours = models.DecimalField(max_digits=6, decimal_places=2, default=50)
    weekly_critical_hours = models.DecimalField(max_digits=6, decimal_places=2, default=60)
    monthly_overtime_warning_hours = models.DecimalField(max_digits=6, decimal_places=2, default=45)
    monthly_overtime_critical_hours = models.DecimalField(max_digits=6, decimal_places=2, default=60)
    consecutive_absence_warning = models.PositiveSmallIntegerField(default=2)
    recurrent_late_warning = models.PositiveSmallIntegerField(default=3)
    enable_kajuuroudou_alerts = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Operations settings"
        verbose_name_plural = "Operations settings"

    def __str__(self):
        return "Operations settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(singleton_key="default")
        return obj


class EmployeeAdministrativeNote(BaseModel):
    class Category(models.TextChoices):
        ASSIDUIDADE = "assiduidade", "Assiduidade"
        ATRASO = "atraso", "Atraso"
        FALTA = "falta", "Falta"
        HORAS_EXTRAS = "horas_extras", "Horas extras"
        KAJUUROUDOU = "kajuuroudou", "Kajuuroudou"
        ORIENTACAO = "orientacao", "Orientação"
        OUTROS = "outros", "Outros"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.CASCADE,
        related_name="administrative_notes",
    )
    date = models.DateField()
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OUTROS)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO)
    note = models.TextField()
    related_period_start = models.DateField(blank=True, null=True)
    related_period_end = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ["-date", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["employee", "date"]),
            models.Index(fields=["category", "severity"]),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.category} - {self.date}"
