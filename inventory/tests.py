from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from master.models import Employee

from .models import (
    StockMovement,
    UniformCategory,
    UniformItem,
    UniformRequest,
    UniformRequestEvent,
    UniformRequestItem,
)
from .services import (
    UniformWorkflowError,
    approve_request,
    cancel_request,
    deliver_request,
    separate_request,
)


class UniformWorkflowServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inventory-user",
            password="password",
        )
        self.employee = Employee.objects.create(
            employee_id="EMP100",
            name_jp="山田太郎",
            name_en="Taro Yamada",
        )
        self.category, _ = UniformCategory.objects.get_or_create(
            code="shirt",
            defaults={"name": "Camiseta"},
        )
        self.item = UniformItem.objects.create(
            sku="UNI-SHIRT-M-WHITE",
            name="Camiseta",
            category=self.category,
            size="M",
            color="White",
            stock_quantity=10,
            minimum_stock=2,
            unit_cost=Decimal("1200.50"),
        )
        self.uniform_request = UniformRequest.objects.create(
            employee=self.employee,
            requested_by=self.user,
            reason="Novo uniforme",
            request_date=timezone.localdate(),
        )
        self.request_item = UniformRequestItem.objects.create(
            request=self.uniform_request,
            item=self.item,
            quantity=3,
        )

    def test_approve_request_moves_pending_to_approved_and_creates_event(self):
        updated_request = approve_request(self.uniform_request, self.user, note="Aprovado")

        self.assertEqual(updated_request.status, UniformRequest.Status.APPROVED)
        self.assertEqual(updated_request.approved_by, self.user)
        self.assertIsNotNone(updated_request.approved_at)
        self.assertEqual(updated_request.events.count(), 1)
        event = updated_request.events.first()
        self.assertEqual(event.status_from, UniformRequest.Status.PENDING)
        self.assertEqual(event.status_to, UniformRequest.Status.APPROVED)
        self.assertEqual(event.note, "Aprovado")

    def test_separate_request_decreases_stock_and_creates_movement_and_event(self):
        approve_request(self.uniform_request, self.user)

        updated_request = separate_request(self.uniform_request, self.user, note="Separado")
        self.item.refresh_from_db()

        self.assertEqual(updated_request.status, UniformRequest.Status.SEPARATED)
        self.assertEqual(updated_request.separated_by, self.user)
        self.assertIsNotNone(updated_request.separated_at)
        self.assertEqual(self.item.stock_quantity, 7)
        self.assertEqual(StockMovement.objects.count(), 1)

        movement = StockMovement.objects.get()
        self.assertEqual(movement.item, self.item)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.OUT)
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.source_type, "uniform_request")
        self.assertEqual(movement.source_id, str(updated_request.pk))
        self.assertEqual(movement.user, self.user)

        self.assertTrue(
            UniformRequestEvent.objects.filter(
                request=updated_request,
                status_from=UniformRequest.Status.APPROVED,
                status_to=UniformRequest.Status.SEPARATED,
            ).exists()
        )

    def test_deliver_request_does_not_decrease_stock_again(self):
        approve_request(self.uniform_request, self.user)
        separate_request(self.uniform_request, self.user)
        self.item.refresh_from_db()
        stock_after_separation = self.item.stock_quantity

        updated_request = deliver_request(self.uniform_request, self.user, note="Entregue")
        self.item.refresh_from_db()

        self.assertEqual(updated_request.status, UniformRequest.Status.DELIVERED)
        self.assertEqual(updated_request.delivered_by, self.user)
        self.assertIsNotNone(updated_request.delivered_at)
        self.assertEqual(self.item.stock_quantity, stock_after_separation)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_cancel_request_moves_pending_to_cancelled_without_stock_movement(self):
        updated_request = cancel_request(self.uniform_request, self.user, note="Cancelado")
        self.item.refresh_from_db()

        self.assertEqual(updated_request.status, UniformRequest.Status.CANCELLED)
        self.assertEqual(updated_request.cancelled_by, self.user)
        self.assertIsNotNone(updated_request.cancelled_at)
        self.assertEqual(self.item.stock_quantity, 10)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertTrue(
            UniformRequestEvent.objects.filter(
                request=updated_request,
                status_from=UniformRequest.Status.PENDING,
                status_to=UniformRequest.Status.CANCELLED,
            ).exists()
        )

    def test_cancel_request_moves_approved_to_cancelled_without_stock_movement(self):
        approve_request(self.uniform_request, self.user)

        updated_request = cancel_request(self.uniform_request, self.user)
        self.item.refresh_from_db()

        self.assertEqual(updated_request.status, UniformRequest.Status.CANCELLED)
        self.assertEqual(self.item.stock_quantity, 10)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_invalid_transition_raises_error(self):
        with self.assertRaises(UniformWorkflowError):
            deliver_request(self.uniform_request, self.user)

        self.uniform_request.refresh_from_db()
        self.assertEqual(self.uniform_request.status, UniformRequest.Status.PENDING)
        self.assertEqual(UniformRequestEvent.objects.count(), 0)

    def test_separate_request_prevents_negative_stock(self):
        self.request_item.quantity = 11
        self.request_item.save()
        approve_request(self.uniform_request, self.user)

        with self.assertRaises(UniformWorkflowError):
            separate_request(self.uniform_request, self.user)

        self.item.refresh_from_db()
        self.uniform_request.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 10)
        self.assertEqual(self.uniform_request.status, UniformRequest.Status.APPROVED)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_cancel_after_separation_is_not_allowed(self):
        approve_request(self.uniform_request, self.user)
        separate_request(self.uniform_request, self.user)

        with self.assertRaises(UniformWorkflowError):
            cancel_request(self.uniform_request, self.user)

        self.uniform_request.refresh_from_db()
        self.assertEqual(self.uniform_request.status, UniformRequest.Status.SEPARATED)


class InventoryAPITests(TestCase):
    # Contract coverage for:
    # /api/inventory/items/
    # /api/inventory/requests/
    # /api/inventory/requests/{id}/approve/
    # /api/inventory/requests/{id}/separate/
    # /api/inventory/requests/{id}/deliver/
    # /api/inventory/requests/{id}/cancel/
    # /api/inventory/movements/
    # /api/inventory/events/
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="inventory-api-user",
            password="password",
        )
        self._assign_role(self.user, "admin")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.employee = Employee.objects.create(
            employee_id="EMP200",
            name_jp="佐藤花子",
            name_en="Hanako Sato",
        )
        self.category, _ = UniformCategory.objects.get_or_create(
            code="pants",
            defaults={"name": "Calca"},
        )
        self.cap_category, _ = UniformCategory.objects.get_or_create(
            code="cap",
            defaults={"name": "Bone"},
        )
        self.other_category, _ = UniformCategory.objects.get_or_create(
            code="other",
            defaults={"name": "Outros"},
        )
        self.item = UniformItem.objects.create(
            sku="UNI-PANTS-L-BLACK",
            name="Calca",
            category=self.category,
            size="L",
            color="Black",
            stock_quantity=8,
            minimum_stock=2,
            unit_cost=Decimal("2500.75"),
        )

    def test_list_items(self):
        response = self.client.get("/api/inventory/items/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._results(response)
        self.assertEqual(results[0]["sku"], self.item.sku)
        self.assertEqual(results[0]["category"], self.category.pk)
        self.assertEqual(results[0]["category_detail"]["name"], self.category.name)
        self.assertEqual(results[0]["stock_quantity"], 8)

    def test_list_categories(self):
        response = self.client.get("/api/inventory/categories/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._results(response)
        self.assertEqual(results[0]["code"], self.cap_category.code)

    def test_create_category(self):
        payload = {
            "code": "gloves",
            "name": "Luvas",
            "description": "Categoria criada pela API",
        }

        response = self.client.post("/api/inventory/categories/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UniformCategory.objects.filter(code="gloves").exists())

    def test_create_item(self):
        payload = {
            "sku": "UNI-CAP-FREE-NAVY",
            "name": "Bone",
            "category": self.cap_category.pk,
            "size": "Free",
            "color": "Navy",
            "stock_quantity": 20,
            "minimum_stock": 5,
            "unit_cost": "780.25",
            "notes": "Estoque inicial",
        }

        response = self.client.post("/api/inventory/items/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UniformItem.objects.filter(sku="UNI-CAP-FREE-NAVY").exists())
        self.assertEqual(response.data["created_by"], self.user.pk)
        self.assertEqual(response.data["unit_cost"], "780.25")

    def test_create_request_with_nested_item(self):
        response = self._create_uniform_request()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["employee"], self.employee.pk)
        self.assertEqual(response.data["status"], UniformRequest.Status.PENDING)
        self.assertEqual(response.data["requested_by"], self.user.pk)
        self.assertEqual(response.data["request_type"], UniformRequest.RequestType.DONATION)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["item"], self.item.pk)
        self.assertEqual(response.data["items"][0]["quantity"], 2)
        self.assertEqual(response.data["items"][0]["unit_cost_snapshot"], "2500.75")
        self.assertEqual(response.data["items"][0]["total_cost"], "5001.50")
        self.assertEqual(response.data["total_cost"], Decimal("5001.50"))

    def test_create_purchase_request_without_reason_is_allowed(self):
        response = self._create_uniform_request(
            request_type=UniformRequest.RequestType.PURCHASE,
            reason="",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["request_type"], UniformRequest.RequestType.PURCHASE)
        self.assertEqual(response.data["reason"], "")

    def test_create_donation_request_without_reason_returns_error(self):
        response = self._create_uniform_request(reason="")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reason", response.data)

    def test_create_donation_request_with_reason_is_allowed(self):
        response = self._create_uniform_request(reason="Entrega sem custo")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reason"], "Entrega sem custo")

    def test_request_item_cost_snapshot_keeps_historical_item_cost(self):
        response = self._create_uniform_request()
        request_item = UniformRequestItem.objects.get(request_id=response.data["id"])

        self.item.unit_cost = Decimal("9999.99")
        self.item.save()
        request_item.refresh_from_db()

        self.assertEqual(request_item.unit_cost_snapshot, Decimal("2500.75"))
        self.assertEqual(request_item.total_cost, Decimal("5001.50"))

    def test_request_total_cost_sums_items(self):
        second_item = UniformItem.objects.create(
            sku="UNI-CAP-FREE-RED",
            name="Bone",
            category=self.cap_category,
            size="Free",
            color="Red",
            stock_quantity=3,
            minimum_stock=1,
            unit_cost=Decimal("300.00"),
        )
        response = self._create_uniform_request(
            items=[
                {"item": self.item.pk, "quantity": 2},
                {"item": second_item.pk, "quantity": 3},
            ]
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["total_cost"], Decimal("5901.50"))

    def test_approve_request(self):
        uniform_request = self._request_from_api()

        response = self.client.post(
            f"/api/inventory/requests/{uniform_request.pk}/approve/",
            {"note": "Aprovado pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], UniformRequest.Status.APPROVED)
        self.assertEqual(response.data["approved_by"], self.user.pk)
        self.assertTrue(
            UniformRequestEvent.objects.filter(
                request=uniform_request,
                status_to=UniformRequest.Status.APPROVED,
            ).exists()
        )

    def test_separate_request_decreases_stock(self):
        uniform_request = self._request_from_api()
        self.client.post(f"/api/inventory/requests/{uniform_request.pk}/approve/")

        response = self.client.post(
            f"/api/inventory/requests/{uniform_request.pk}/separate/",
            {"note": "Separado pela API"},
            format="json",
        )
        self.item.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], UniformRequest.Status.SEPARATED)
        self.assertEqual(self.item.stock_quantity, 6)
        self.assertEqual(StockMovement.objects.count(), 1)

        movements_response = self.client.get("/api/inventory/movements/")
        self.assertEqual(movements_response.status_code, status.HTTP_200_OK)
        movements = self._results(movements_response)
        self.assertEqual(movements[0]["movement_type"], StockMovement.MovementType.OUT)

    def test_deliver_request(self):
        uniform_request = self._request_from_api()
        self.client.post(f"/api/inventory/requests/{uniform_request.pk}/approve/")
        self.client.post(f"/api/inventory/requests/{uniform_request.pk}/separate/")

        response = self.client.post(
            f"/api/inventory/requests/{uniform_request.pk}/deliver/",
            {"note": "Entregue pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], UniformRequest.Status.DELIVERED)
        self.assertEqual(response.data["delivered_by"], self.user.pk)

        events_response = self.client.get("/api/inventory/events/")
        self.assertEqual(events_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(self._results(events_response)), 3)

    def test_cancel_request(self):
        uniform_request = self._request_from_api()

        response = self.client.post(
            f"/api/inventory/requests/{uniform_request.pk}/cancel/",
            {"note": "Cancelado pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], UniformRequest.Status.CANCELLED)
        self.assertEqual(response.data["cancelled_by"], self.user.pk)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_invalid_transition_returns_400(self):
        uniform_request = self._request_from_api()

        response = self.client.post(f"/api/inventory/requests/{uniform_request.pk}/deliver/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot transition uniform request", response.data["detail"])

    def test_authenticated_user_without_role_can_read_but_cannot_write_items(self):
        user = get_user_model().objects.create_user(username="inventory-no-role")
        self.client.force_authenticate(user=user)

        read_response = self.client.get("/api/inventory/items/")
        write_response = self.client.post(
            "/api/inventory/items/",
            {
                "sku": "UNI-NO-ROLE",
                "name": "Sem role",
                "category": self.other_category.pk,
                "size": "Free",
                "color": "Gray",
                "stock_quantity": 1,
                "minimum_stock": 0,
            },
            format="json",
        )

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(write_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_consulta_role_is_read_only_for_items_and_requests(self):
        self.client.force_authenticate(user=self._user_with_role("consulta-user", "consulta"))

        items_response = self.client.get("/api/inventory/items/")
        requests_response = self.client.get("/api/inventory/requests/")
        create_response = self._create_uniform_request()
        movements_response = self.client.get("/api/inventory/movements/")

        self.assertEqual(items_response.status_code, status.HTTP_200_OK)
        self.assertEqual(requests_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(movements_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_escritorio_can_approve_and_cancel_but_cannot_separate(self):
        uniform_request = self._request_from_api()
        self.client.force_authenticate(user=self._user_with_role("escritorio-user", "escritorio"))

        approve_response = self.client.post(f"/api/inventory/requests/{uniform_request.pk}/approve/")
        separate_response = self.client.post(f"/api/inventory/requests/{uniform_request.pk}/separate/")

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(separate_response.status_code, status.HTTP_403_FORBIDDEN)

        cancellable_request = self._request_from_api()
        cancel_response = self.client.post(f"/api/inventory/requests/{cancellable_request.pk}/cancel/")
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)

    def test_supervisor_can_create_and_approve_requests(self):
        self.client.force_authenticate(user=self._user_with_role("supervisor-user", "supervisor"))

        create_response = self._create_uniform_request()
        approve_response = self.client.post(
            f"/api/inventory/requests/{create_response.data['id']}/approve/"
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

    def test_almoxarifado_can_manage_items_separate_deliver_and_read_movements(self):
        uniform_request = self._request_from_api()
        self.client.force_authenticate(user=self._user_with_role("almox-user", "almoxarifado"))

        item_response = self.client.patch(
            f"/api/inventory/items/{self.item.pk}/",
            {"minimum_stock": 3},
            format="json",
        )
        approve_response = self.client.post(f"/api/inventory/requests/{uniform_request.pk}/approve/")

        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/inventory/requests/{uniform_request.pk}/approve/")

        self.client.force_authenticate(user=self._user_with_role("almox-user-2", "almoxarifado"))
        separate_response = self.client.post(f"/api/inventory/requests/{uniform_request.pk}/separate/")
        deliver_response = self.client.post(f"/api/inventory/requests/{uniform_request.pk}/deliver/")
        movements_response = self.client.get("/api/inventory/movements/")
        events_response = self.client.get("/api/inventory/events/")

        self.assertEqual(item_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(separate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(deliver_response.status_code, status.HTTP_200_OK)
        self.assertEqual(movements_response.status_code, status.HTTP_200_OK)
        self.assertEqual(events_response.status_code, status.HTTP_200_OK)

    def _create_uniform_request(self, *, request_type=None, reason="Troca de uniforme", items=None):
        payload = {
            "employee": self.employee.pk,
            "request_type": request_type or UniformRequest.RequestType.DONATION,
            "reason": reason,
            "request_date": timezone.localdate().isoformat(),
            "notes": "Solicitacao criada pela API",
            "items": items or [
                {
                    "item": self.item.pk,
                    "quantity": 2,
                }
            ],
        }
        return self.client.post("/api/inventory/requests/", payload, format="json")

    def _request_from_api(self):
        response = self._create_uniform_request()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return UniformRequest.objects.get(pk=response.data["id"])

    def _results(self, response):
        if isinstance(response.data, dict) and "results" in response.data:
            return response.data["results"]
        return response.data

    def _user_with_role(self, username, role_code):
        user = get_user_model().objects.create_user(username=username)
        self._assign_role(user, role_code)
        return user

    def _assign_role(self, user, role_code):
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": role_code.replace("_", " ").title()},
        )
        UserProfile.objects.create(user=user, role=role)
        return role
