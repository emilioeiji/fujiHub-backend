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
    readonly_fields = ("unit_cost_snapshot", "total_cost")


class UniformRequestEventInline(admin.TabularInline):
    model = UniformRequestEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(UniformCategory)
class UniformCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "label_pt", "label_jp", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "label_pt", "label_jp", "description")


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
        "unit_cost",
        "average_cost",
        "average_price",
        "is_active",
    )
    list_filter = ("category", "size", "color", "is_active")
    search_fields = ("sku", "name", "size", "color")


@admin.register(UniformRequest)
class UniformRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "request_type", "status", "request_date", "total_cost", "requested_by")
    list_filter = ("request_type", "status", "request_date")
    search_fields = ("employee__employee_id", "employee__name_en", "employee__name_jp", "reason")
    inlines = [UniformRequestItemInline, UniformRequestEventInline]


@admin.register(UniformRequestItem)
class UniformRequestItemAdmin(admin.ModelAdmin):
    list_display = ("request", "item", "quantity", "unit_cost_snapshot", "total_cost")
    search_fields = ("request__employee__employee_id", "item__sku", "item__name")
    readonly_fields = ("total_cost",)


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
