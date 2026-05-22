from rest_framework.routers import DefaultRouter

from .views import (
    MedicalDestinationViewSet,
    MedicalReasonViewSet,
    MedicalRequestEventViewSet,
    MedicalRequestViewSet,
    SymptomTypeViewSet,
)

app_name = "medical"

router = DefaultRouter()
router.register("reasons", MedicalReasonViewSet, basename="medical-reasons")
router.register("symptoms", SymptomTypeViewSet, basename="medical-symptoms")
router.register("destinations", MedicalDestinationViewSet, basename="medical-destinations")
router.register("requests", MedicalRequestViewSet, basename="medical-requests")
router.register("events", MedicalRequestEventViewSet, basename="medical-events")

urlpatterns = router.urls
