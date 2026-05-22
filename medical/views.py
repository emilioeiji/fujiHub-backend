from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import MedicalDestination, MedicalReason, MedicalRequest, MedicalRequestEvent, SymptomType
from .permissions import MedicalEventPermission, MedicalMasterDataPermission, MedicalRequestPermission
from .serializers import (
    MedicalDestinationSerializer,
    MedicalReasonSerializer,
    MedicalRequestEventSerializer,
    MedicalRequestSerializer,
    SymptomTypeSerializer,
)
from .services import (
    MedicalWorkflowError,
    cancel_medical_request,
    complete_medical_request,
    start_medical_service,
    triage_request,
)


class MedicalReasonViewSet(viewsets.ModelViewSet):
    queryset = MedicalReason.objects.all()
    serializer_class = MedicalReasonSerializer
    permission_classes = [MedicalMasterDataPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class SymptomTypeViewSet(viewsets.ModelViewSet):
    queryset = SymptomType.objects.all()
    serializer_class = SymptomTypeSerializer
    permission_classes = [MedicalMasterDataPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class MedicalDestinationViewSet(viewsets.ModelViewSet):
    queryset = MedicalDestination.objects.all()
    serializer_class = MedicalDestinationSerializer
    permission_classes = [MedicalMasterDataPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class MedicalRequestViewSet(viewsets.ModelViewSet):
    queryset = MedicalRequest.objects.select_related(
        "employee",
        "reason",
        "destination",
        "requested_by",
        "assigned_to",
        "completed_by",
    ).prefetch_related("symptoms", "symptoms__symptom")
    serializer_class = MedicalRequestSerializer
    permission_classes = [MedicalRequestPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(requested_by=user, created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    @action(detail=True, methods=["post"])
    def triage(self, request, pk=None):
        return self._run_workflow(triage_request, request)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._run_workflow(start_medical_service, request)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._run_workflow(complete_medical_request, request)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._run_workflow(cancel_medical_request, request)

    def _run_workflow(self, service, request):
        medical_request = self.get_object()
        note = request.data.get("note")

        try:
            updated_request = service(medical_request, self._actor(), note=note)
        except MedicalWorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(updated_request)
        return Response(serializer.data)

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class MedicalRequestEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MedicalRequestEvent.objects.select_related("request", "user")
    serializer_class = MedicalRequestEventSerializer
    permission_classes = [MedicalEventPermission]
