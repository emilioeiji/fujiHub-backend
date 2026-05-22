from django.contrib import admin

from .models import (
    MedicalDestination,
    MedicalReason,
    MedicalRequest,
    MedicalRequestEvent,
    MedicalRequestSymptom,
    SymptomType,
)


class MedicalRequestSymptomInline(admin.TabularInline):
    model = MedicalRequestSymptom
    extra = 0


class MedicalRequestEventInline(admin.TabularInline):
    model = MedicalRequestEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(MedicalReason)
class MedicalReasonAdmin(admin.ModelAdmin):
    list_display = ("code", "name_pt", "name_jp", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name_pt", "name_jp")


@admin.register(SymptomType)
class SymptomTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name_pt", "name_jp", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name_pt", "name_jp")


@admin.register(MedicalDestination)
class MedicalDestinationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "address", "phone")


@admin.register(MedicalRequest)
class MedicalRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee",
        "reason",
        "severity",
        "status",
        "requested_at",
        "assigned_to",
    )
    list_filter = ("status", "severity", "requested_at", "needs_transport", "has_vehicle")
    search_fields = (
        "employee__employee_id",
        "employee__name_en",
        "employee__name_jp",
        "description",
        "notes",
    )
    inlines = [MedicalRequestSymptomInline, MedicalRequestEventInline]


@admin.register(MedicalRequestSymptom)
class MedicalRequestSymptomAdmin(admin.ModelAdmin):
    list_display = ("request", "symptom")
    search_fields = ("request__employee__employee_id", "symptom__code", "symptom__name_pt")


@admin.register(MedicalRequestEvent)
class MedicalRequestEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "request", "status_from", "status_to", "user")
    list_filter = ("status_to", "created_at")
    search_fields = ("request__employee__employee_id", "user__username", "note")
    readonly_fields = ("created_at",)
