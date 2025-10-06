from rest_framework.routers import DefaultRouter
from .views import (
    EmployeeViewSet, EmployeeHousingViewSet, GenderViewSet, ShiftViewSet, NationalityViewSet, BillingRateViewSet,
    RejoinedViewSet, ProcessViewSet, BuildingFloorViewSet,
    DepartmentViewSet, EntryTypeViewSet, HireTypeViewSet
)

router = DefaultRouter()
router.register(r'employees/housing', EmployeeHousingViewSet)
router.register(r'employees', EmployeeViewSet)
router.register(r'genders', GenderViewSet)
router.register(r'shifts', ShiftViewSet)
router.register(r'nationalities', NationalityViewSet)
router.register(r'billingrates', BillingRateViewSet)
router.register(r'rejoined', RejoinedViewSet)
router.register(r'processes', ProcessViewSet)
router.register(r'buildingfloors', BuildingFloorViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'entrytypes', EntryTypeViewSet)
router.register(r'hiretypes', HireTypeViewSet)

urlpatterns = router.urls
