from django.conf import settings
from django.db import models

from common.models import BaseModel


class MedicalReason(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    name_pt = models.CharField(max_length=100)
    name_jp = models.CharField(max_length=100)

    class Meta:
        ordering = ["name_pt"]

    def __str__(self):
        return self.name_pt


class SymptomType(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    name_pt = models.CharField(max_length=100)
    name_jp = models.CharField(max_length=100)

    class Meta:
        ordering = ["name_pt"]

    def __str__(self):
        return self.name_pt


class MedicalDestination(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MedicalRequest(BaseModel):
    class Severity(models.TextChoices):
        LOW = "low", "Baixa"
        MEDIUM = "medium", "Media"
        URGENT = "urgent", "Urgente"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Solicitado"
        TRIAGED = "triaged", "Triado"
        IN_PROGRESS = "in_progress", "Em atendimento"
        COMPLETED = "completed", "Concluido"
        CANCELLED = "cancelled", "Cancelado"

    employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.PROTECT,
        related_name="medical_requests",
    )
    reason = models.ForeignKey(
        MedicalReason,
        on_delete=models.PROTECT,
        related_name="medical_requests",
    )
    description = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.LOW,
    )
    has_vehicle = models.BooleanField(default=False)
    needs_transport = models.BooleanField(default=False)
    destination = models.ForeignKey(
        MedicalDestination,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="medical_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="medical_requests_requested",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="medical_requests_assigned",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="medical_requests_completed",
    )
    requested_at = models.DateTimeField()
    triaged_at = models.DateTimeField(blank=True, null=True)
    started_service_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["requested_at"]),
            models.Index(fields=["employee"]),
            models.Index(fields=["assigned_to"]),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.status}"


class MedicalRequestSymptom(models.Model):
    request = models.ForeignKey(
        MedicalRequest,
        on_delete=models.CASCADE,
        related_name="symptoms",
    )
    symptom = models.ForeignKey(
        SymptomType,
        on_delete=models.PROTECT,
        related_name="request_symptoms",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "symptom"],
                name="unique_medical_request_symptom",
            )
        ]

    def __str__(self):
        return f"{self.request_id} - {self.symptom}"


class MedicalRequestEvent(models.Model):
    request = models.ForeignKey(
        MedicalRequest,
        on_delete=models.CASCADE,
        related_name="events",
    )
    status_from = models.CharField(
        max_length=20,
        choices=MedicalRequest.Status.choices,
        blank=True,
    )
    status_to = models.CharField(max_length=20, choices=MedicalRequest.Status.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="medical_request_events",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status_to"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.request_id}: {self.status_from} -> {self.status_to}"
