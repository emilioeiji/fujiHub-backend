from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from common.models import BaseModel


class UniformCategory(BaseModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Uniform category"
        verbose_name_plural = "Uniform categories"

    def __str__(self):
        return self.name


class UniformItem(BaseModel):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        UniformCategory,
        on_delete=models.PROTECT,
        related_name="items",
    )
    size = models.CharField(max_length=30)
    color = models.CharField(max_length=50)
    stock_quantity = models.PositiveIntegerField(default=0)
    minimum_stock = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["category", "name", "size", "color"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["size"]),
            models.Index(fields=["color"]),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class UniformRequest(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        APPROVED = "approved", "Aprovado"
        SEPARATED = "separated", "Separado"
        DELIVERED = "delivered", "Entregue"
        CANCELLED = "cancelled", "Cancelado"

    employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.PROTECT,
        related_name="uniform_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uniform_requests_requested",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reason = models.CharField(max_length=255)
    request_date = models.DateField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uniform_requests_approved",
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    separated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uniform_requests_separated",
    )
    separated_at = models.DateTimeField(blank=True, null=True)
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uniform_requests_delivered",
    )
    delivered_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uniform_requests_cancelled",
    )
    cancelled_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-request_date", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["request_date"]),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.status}"


class UniformRequestItem(models.Model):
    request = models.ForeignKey(
        UniformRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item = models.ForeignKey(
        UniformItem,
        on_delete=models.PROTECT,
        related_name="request_items",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.item.sku} x {self.quantity}"


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Saida"
        ADJUSTMENT = "adjustment", "Ajuste"
        RESERVED = "reserved", "Reservado"
        CANCELLED = "cancelled", "Cancelado"

    item = models.ForeignKey(
        UniformItem,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    source_type = models.CharField(max_length=100, blank=True)
    source_id = models.CharField(max_length=100, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="stock_movements",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["movement_type"]),
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.item.sku} {self.movement_type} {self.quantity}"


class UniformRequestEvent(models.Model):
    request = models.ForeignKey(
        UniformRequest,
        on_delete=models.CASCADE,
        related_name="events",
    )
    status_from = models.CharField(
        max_length=20,
        choices=UniformRequest.Status.choices,
        blank=True,
    )
    status_to = models.CharField(max_length=20, choices=UniformRequest.Status.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uniform_request_events",
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
