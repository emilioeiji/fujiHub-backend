# master/admin.py
from django.contrib import admin
from .models import (
    Gender, Shift, Nationality, BillingRate, Rejoined,
    Process, BuildingFloor, Department, EntryType, HireType,
    Employee, EmployeeHousing
)

# Inline para EmployeeHousing
class EmployeeHousingInline(admin.TabularInline):
    model = EmployeeHousing
    extra = 1
    fields = (
        "property_cd", "apartment_name", "room_number",
        "rent", "monthly_payment", "management_fee", "parking_fee",
        "move_in_date", "move_out_date",
        "phone_number", "postal_code", "address", "bus_stop", "bus_number"
    )


# Masters simples
@admin.register(Gender)
class GenderAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(Nationality)
class NationalityAdmin(admin.ModelAdmin):
    list_display = ("code", "name_pt", "name_jp")
    search_fields = ("code", "name_pt", "name_jp")


@admin.register(BillingRate)
class BillingRateAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(Rejoined)
class RejoinedAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(BuildingFloor)
class BuildingFloorAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(EntryType)
class EntryTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


@admin.register(HireType)
class HireTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "label_pt", "label_jp")
    search_fields = ("code", "label_pt", "label_jp")


# Employee com inline de Housing
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id", "name_en", "name_jp", "gender", "shift",
        "nationality", "department", "hire_type", "active_end_month"
    )
    list_filter = (
        "gender", "shift", "nationality", "department", "hire_type",
        "active_end_month", "manager_flag", "view_flag"
    )
    search_fields = ("employee_id", "name_en", "name_jp", "internal_name", "name_kana")
    ordering = ("employee_id",)

    inlines = [EmployeeHousingInline]
