from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "user", "ip_address")
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("entity_type", "entity_id", "user__username", "ip_address")
    readonly_fields = ("created_at",)
