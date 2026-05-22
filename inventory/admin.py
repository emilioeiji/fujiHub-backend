from django.contrib import admin

from .models import (
    StockMovement,
    UniformCategory,
    UniformItem,
    UniformRequest,
    UniformRequestEvent,
    UniformRequestItem,
)


class UniformRequestItemInline(admin.TabularInline):
    model = UniformRequestItem
    extra = 0


class UniformRequestEventInline(admin.TabularInline):
    model = UniformRequestEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(UniformCategory)
class UniformCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "description")


@admin.register(UniformItem)
class UniformItemAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "category",
        "size",
        "color",
        "stock_quantity",
        "minimum_stock",
        "is_active",
    )
    list_filter = ("category", "size", "color", "is_active")
    search_fields = ("sku", "name", "size", "color")


@admin.register(UniformRequest)
class UniformRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "status", "request_date", "requested_by")
    list_filter = ("status", "request_date")
    search_fields = ("employee__employee_id", "employee__name_en", "employee__name_jp", "reason")
    inlines = [UniformRequestItemInline, UniformRequestEventInline]


@admin.register(UniformRequestItem)
class UniformRequestItemAdmin(admin.ModelAdmin):
    list_display = ("request", "item", "quantity")
    search_fields = ("request__employee__employee_id", "item__sku", "item__name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "movement_type", "quantity", "user")
    list_filter = ("movement_type", "created_at")
    search_fields = ("item__sku", "item__name", "source_type", "source_id", "user__username")
    readonly_fields = ("created_at",)


@admin.register(UniformRequestEvent)
class UniformRequestEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "request", "status_from", "status_to", "user")
    list_filter = ("status_to", "created_at")
    search_fields = ("request__employee__employee_id", "user__username", "note")
    readonly_fields = ("created_at",)
