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
