from rest_framework import viewsets
from .models import (
    Employee, EmployeeHousing, Gender, Shift, Nationality, BillingRate, Rejoined,
    Process, BuildingFloor, Department, EntryType, HireType
)
from .serializers import (
    EmployeeSerializer, EmployeeHousingSerializer, GenderSerializer, ShiftSerializer, NationalitySerializer, BillingRateSerializer,
    RejoinedSerializer, ProcessSerializer, BuildingFloorSerializer,
    DepartmentSerializer, EntryTypeSerializer, HireTypeSerializer
)


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer


class EmployeeHousingViewSet(viewsets.ModelViewSet):
    queryset = EmployeeHousing.objects.all()
    serializer_class = EmployeeHousingSerializer


class GenderViewSet(viewsets.ModelViewSet):
    queryset = Gender.objects.all()
    serializer_class = GenderSerializer


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer


class NationalityViewSet(viewsets.ModelViewSet):
    queryset = Nationality.objects.all()
    serializer_class = NationalitySerializer


class BillingRateViewSet(viewsets.ModelViewSet):
    queryset = BillingRate.objects.all()
    serializer_class = BillingRateSerializer


class RejoinedViewSet(viewsets.ModelViewSet):
    queryset = Rejoined.objects.all()
    serializer_class = RejoinedSerializer


class ProcessViewSet(viewsets.ModelViewSet):
    queryset = Process.objects.all()
    serializer_class = ProcessSerializer


class BuildingFloorViewSet(viewsets.ModelViewSet):
    queryset = BuildingFloor.objects.all()
    serializer_class = BuildingFloorSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class EntryTypeViewSet(viewsets.ModelViewSet):
    queryset = EntryType.objects.all()
    serializer_class = EntryTypeSerializer


class HireTypeViewSet(viewsets.ModelViewSet):
    queryset = HireType.objects.all()
    serializer_class = HireTypeSerializer
