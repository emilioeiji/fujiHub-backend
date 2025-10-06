from rest_framework import serializers
from .models import (
    Employee, EmployeeHousing,
    Gender, Shift, Nationality, BillingRate, Rejoined,
    Process, BuildingFloor, Department, EntryType, HireType
)

# Masters
class GenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gender
        fields = "__all__"

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = "__all__"

class NationalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Nationality
        fields = "__all__"

class BillingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingRate
        fields = "__all__"

class RejoinedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rejoined
        fields = "__all__"

class ProcessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = "__all__"

class BuildingFloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuildingFloor
        fields = "__all__"

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"

class EntryTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntryType
        fields = "__all__"

class HireTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HireType
        fields = "__all__"


# EmployeeHousing
class EmployeeHousingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeHousing
        fields = "__all__"
        extra_kwargs = {
            "move_in_date": {"allow_null": True, "required": False},
            "move_out_date": {"allow_null": True, "required": False},
        }


# Employee
class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = "__all__"
        extra_kwargs = {
            "end_work": {"allow_null": True, "required": False},
            "retired": {"allow_null": True, "required": False},
            "joined_imc": {"allow_null": True, "required": False},
            "joined_fa": {"allow_null": True, "required": False},
            "new_joined": {"allow_null": True, "required": False},
            "dispatch_start": {"allow_null": True, "required": False},
            "birth_date": {"allow_null": True, "required": False},
        }
