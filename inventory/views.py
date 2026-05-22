from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import StockMovement, UniformCategory, UniformItem, UniformRequest, UniformRequestEvent
from .permissions import InventoryItemPermission, InventoryRequestPermission, InventoryStockReadPermission
from .serializers import (
    StockMovementSerializer,
    UniformCategorySerializer,
    UniformItemSerializer,
    UniformRequestEventSerializer,
    UniformRequestSerializer,
)
from .services import (
    UniformWorkflowError,
    approve_request,
    cancel_request,
    deliver_request,
    separate_request,
)


class UniformItemViewSet(viewsets.ModelViewSet):
    queryset = UniformItem.objects.select_related("category")
    serializer_class = UniformItemSerializer
    permission_classes = [InventoryItemPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class UniformCategoryViewSet(viewsets.ModelViewSet):
    queryset = UniformCategory.objects.all()
    serializer_class = UniformCategorySerializer
    permission_classes = [InventoryItemPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class UniformRequestViewSet(viewsets.ModelViewSet):
    queryset = UniformRequest.objects.select_related("employee").prefetch_related(
        "items",
        "items__item",
    )
    serializer_class = UniformRequestSerializer
    permission_classes = [InventoryRequestPermission]

    def perform_create(self, serializer):
        user = self._actor()
        serializer.save(requested_by=user, created_by=user, updated_by=user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._actor())

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._run_workflow(approve_request, request)

    @action(detail=True, methods=["post"])
    def separate(self, request, pk=None):
        return self._run_workflow(separate_request, request)

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        return self._run_workflow(deliver_request, request)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._run_workflow(cancel_request, request)

    def _run_workflow(self, service, request):
        uniform_request = self.get_object()
        note = request.data.get("note")

        try:
            updated_request = service(uniform_request, self._actor(), note=note)
        except UniformWorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(updated_request)
        return Response(serializer.data)

    def _actor(self):
        return self.request.user if self.request.user.is_authenticated else None


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("item", "user")
    serializer_class = StockMovementSerializer
    permission_classes = [InventoryStockReadPermission]


class UniformRequestEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UniformRequestEvent.objects.select_related("request", "user")
    serializer_class = UniformRequestEventSerializer
    permission_classes = [InventoryStockReadPermission]
