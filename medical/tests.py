from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, UserProfile
from master.models import Employee

from .models import MedicalDestination, MedicalReason, MedicalRequest, MedicalRequestEvent, SymptomType
from .services import (
    MedicalWorkflowError,
    cancel_medical_request,
    complete_medical_request,
    start_medical_service,
    triage_request,
)


class MedicalWorkflowServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="medical-user",
            password="password",
        )
        self.employee = Employee.objects.create(
            employee_id="MED100",
            name_jp="田中太郎",
            name_en="Taro Tanaka",
        )
        self.reason = MedicalReason.objects.create(
            code="dor_teste",
            name_pt="Dor",
            name_jp="痛み",
        )
        self.medical_request = MedicalRequest.objects.create(
            employee=self.employee,
            reason=self.reason,
            description="Funcionario com dor de cabeca.",
            severity=MedicalRequest.Severity.MEDIUM,
            requested_by=self.user,
            requested_at=timezone.now(),
        )

    def test_triage_request_moves_requested_to_triaged_and_creates_event(self):
        updated_request = triage_request(self.medical_request, self.user, note="Triagem inicial")

        self.assertEqual(updated_request.status, MedicalRequest.Status.TRIAGED)
        self.assertEqual(updated_request.assigned_to, self.user)
        self.assertIsNotNone(updated_request.triaged_at)
        self.assertEqual(updated_request.events.count(), 1)

        event = updated_request.events.first()
        self.assertEqual(event.status_from, MedicalRequest.Status.REQUESTED)
        self.assertEqual(event.status_to, MedicalRequest.Status.TRIAGED)
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.note, "Triagem inicial")

    def test_start_medical_service_moves_triaged_to_in_progress(self):
        triage_request(self.medical_request, self.user)

        updated_request = start_medical_service(
            self.medical_request,
            self.user,
            note="Atendimento iniciado",
        )

        self.assertEqual(updated_request.status, MedicalRequest.Status.IN_PROGRESS)
        self.assertEqual(updated_request.assigned_to, self.user)
        self.assertIsNotNone(updated_request.started_service_at)
        self.assertTrue(
            MedicalRequestEvent.objects.filter(
                request=updated_request,
                status_from=MedicalRequest.Status.TRIAGED,
                status_to=MedicalRequest.Status.IN_PROGRESS,
                note="Atendimento iniciado",
            ).exists()
        )

    def test_complete_medical_request_moves_in_progress_to_completed(self):
        triage_request(self.medical_request, self.user)
        start_medical_service(self.medical_request, self.user)

        updated_request = complete_medical_request(
            self.medical_request,
            self.user,
            note="Atendimento concluido",
        )

        self.assertEqual(updated_request.status, MedicalRequest.Status.COMPLETED)
        self.assertEqual(updated_request.completed_by, self.user)
        self.assertIsNotNone(updated_request.completed_at)
        self.assertTrue(
            MedicalRequestEvent.objects.filter(
                request=updated_request,
                status_from=MedicalRequest.Status.IN_PROGRESS,
                status_to=MedicalRequest.Status.COMPLETED,
            ).exists()
        )

    def test_cancel_requested_request(self):
        updated_request = cancel_medical_request(
            self.medical_request,
            self.user,
            note="Cancelado antes da triagem",
        )

        self.assertEqual(updated_request.status, MedicalRequest.Status.CANCELLED)
        self.assertIsNotNone(updated_request.cancelled_at)
        self.assertTrue(
            MedicalRequestEvent.objects.filter(
                request=updated_request,
                status_from=MedicalRequest.Status.REQUESTED,
                status_to=MedicalRequest.Status.CANCELLED,
                note="Cancelado antes da triagem",
            ).exists()
        )

    def test_cancel_triaged_request(self):
        triage_request(self.medical_request, self.user)

        updated_request = cancel_medical_request(
            self.medical_request,
            self.user,
            note="Cancelado apos triagem",
        )

        self.assertEqual(updated_request.status, MedicalRequest.Status.CANCELLED)
        self.assertIsNotNone(updated_request.cancelled_at)
        self.assertTrue(
            MedicalRequestEvent.objects.filter(
                request=updated_request,
                status_from=MedicalRequest.Status.TRIAGED,
                status_to=MedicalRequest.Status.CANCELLED,
            ).exists()
        )

    def test_invalid_transition_raises_error(self):
        with self.assertRaises(MedicalWorkflowError):
            start_medical_service(self.medical_request, self.user)

        self.medical_request.refresh_from_db()
        self.assertEqual(self.medical_request.status, MedicalRequest.Status.REQUESTED)
        self.assertEqual(MedicalRequestEvent.objects.count(), 0)

    def test_cancel_after_in_progress_is_not_allowed(self):
        triage_request(self.medical_request, self.user)
        start_medical_service(self.medical_request, self.user)

        with self.assertRaises(MedicalWorkflowError):
            cancel_medical_request(self.medical_request, self.user)

        self.medical_request.refresh_from_db()
        self.assertEqual(self.medical_request.status, MedicalRequest.Status.IN_PROGRESS)
        self.assertIsNone(self.medical_request.cancelled_at)

    def test_completed_request_blocks_further_transitions(self):
        triage_request(self.medical_request, self.user)
        start_medical_service(self.medical_request, self.user)
        complete_medical_request(self.medical_request, self.user)

        with self.assertRaises(MedicalWorkflowError):
            triage_request(self.medical_request, self.user)

        with self.assertRaises(MedicalWorkflowError):
            cancel_medical_request(self.medical_request, self.user)

        self.medical_request.refresh_from_db()
        self.assertEqual(self.medical_request.status, MedicalRequest.Status.COMPLETED)
        self.assertEqual(self.medical_request.events.count(), 3)


class MedicalAPITests(TestCase):
    # Contract coverage for:
    # /api/medical/reasons/
    # /api/medical/symptoms/
    # /api/medical/destinations/
    # /api/medical/requests/
    # /api/medical/requests/{id}/triage/
    # /api/medical/requests/{id}/start/
    # /api/medical/requests/{id}/complete/
    # /api/medical/requests/{id}/cancel/
    # /api/medical/events/
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="medical-api-user",
            password="password",
        )
        self._assign_role(self.user, "admin")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.employee = Employee.objects.create(
            employee_id="MED200",
            name_jp="佐藤太郎",
            name_en="Taro Sato",
        )
        self.reason = MedicalReason.objects.create(
            code="api_dor",
            name_pt="Dor",
            name_jp="痛み",
        )
        self.symptom = SymptomType.objects.create(
            code="api_dor_de_cabeca",
            name_pt="Dor de cabeca",
            name_jp="頭痛",
        )
        self.destination = MedicalDestination.objects.create(
            code="api_clinica",
            name="Clinica parceira",
            address="Endereco teste",
            phone="000-0000",
        )

    def test_list_master_data(self):
        reasons_response = self.client.get("/api/medical/reasons/")
        symptoms_response = self.client.get("/api/medical/symptoms/")
        destinations_response = self.client.get("/api/medical/destinations/")

        self.assertEqual(reasons_response.status_code, status.HTTP_200_OK)
        self.assertEqual(symptoms_response.status_code, status.HTTP_200_OK)
        self.assertEqual(destinations_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(self._results(reasons_response)), 1)
        self.assertGreaterEqual(len(self._results(symptoms_response)), 1)
        self.assertGreaterEqual(len(self._results(destinations_response)), 1)

    def test_create_request_with_symptoms(self):
        response = self._create_medical_request()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["employee"], self.employee.pk)
        self.assertEqual(response.data["reason"], self.reason.pk)
        self.assertEqual(response.data["status"], MedicalRequest.Status.REQUESTED)
        self.assertEqual(response.data["requested_by"], self.user.pk)
        self.assertEqual(response.data["employee_display"]["name_en"], self.employee.name_en)
        self.assertEqual(response.data["reason_detail"]["name_pt"], self.reason.name_pt)
        self.assertEqual(response.data["destination_detail"]["name"], self.destination.name)
        self.assertEqual(len(response.data["symptom_items"]), 1)
        self.assertEqual(response.data["symptom_items"][0]["symptom"], self.symptom.pk)

    def test_triage_request(self):
        medical_request = self._request_from_api()

        response = self.client.post(
            f"/api/medical/requests/{medical_request.pk}/triage/",
            {"note": "Triado pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], MedicalRequest.Status.TRIAGED)
        self.assertEqual(response.data["assigned_to"], self.user.pk)
        self.assertTrue(
            MedicalRequestEvent.objects.filter(
                request=medical_request,
                status_to=MedicalRequest.Status.TRIAGED,
                note="Triado pela API",
            ).exists()
        )

    def test_start_request(self):
        medical_request = self._request_from_api()
        self.client.post(f"/api/medical/requests/{medical_request.pk}/triage/")

        response = self.client.post(
            f"/api/medical/requests/{medical_request.pk}/start/",
            {"note": "Atendimento iniciado pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], MedicalRequest.Status.IN_PROGRESS)
        self.assertIsNotNone(response.data["started_service_at"])

    def test_complete_request(self):
        medical_request = self._request_from_api()
        self.client.post(f"/api/medical/requests/{medical_request.pk}/triage/")
        self.client.post(f"/api/medical/requests/{medical_request.pk}/start/")

        response = self.client.post(
            f"/api/medical/requests/{medical_request.pk}/complete/",
            {"note": "Atendimento concluido pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], MedicalRequest.Status.COMPLETED)
        self.assertEqual(response.data["completed_by"], self.user.pk)

    def test_cancel_request(self):
        medical_request = self._request_from_api()

        response = self.client.post(
            f"/api/medical/requests/{medical_request.pk}/cancel/",
            {"note": "Cancelado pela API"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], MedicalRequest.Status.CANCELLED)
        self.assertIsNotNone(response.data["cancelled_at"])

    def test_invalid_transition_returns_400(self):
        medical_request = self._request_from_api()

        response = self.client.post(f"/api/medical/requests/{medical_request.pk}/start/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot transition medical request", response.data["detail"])

    def test_permissions_basic_roles(self):
        consulta = self._user_with_role("medical-consulta", "consulta")
        self.client.force_authenticate(user=consulta)

        read_response = self.client.get("/api/medical/requests/")
        create_response = self._create_medical_request()
        events_response = self.client.get("/api/medical/events/")

        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(events_response.status_code, status.HTTP_403_FORBIDDEN)

        supervisor = self._user_with_role("medical-supervisor", "supervisor")
        self.client.force_authenticate(user=supervisor)
        supervisor_create_response = self._create_medical_request()
        supervisor_triage_response = self.client.post(
            f"/api/medical/requests/{supervisor_create_response.data['id']}/triage/"
        )

        self.assertEqual(supervisor_create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(supervisor_triage_response.status_code, status.HTTP_403_FORBIDDEN)

        saude = self._user_with_role("medical-saude", "saude")
        self.client.force_authenticate(user=saude)
        reason_create_response = self.client.post(
            "/api/medical/reasons/",
            {
                "code": "api_teste_saude",
                "name_pt": "Teste saude",
                "name_jp": "テスト",
            },
            format="json",
        )
        triage_response = self.client.post(
            f"/api/medical/requests/{supervisor_create_response.data['id']}/triage/"
        )
        events_allowed_response = self.client.get("/api/medical/events/")

        self.assertEqual(reason_create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(triage_response.status_code, status.HTTP_200_OK)
        self.assertEqual(events_allowed_response.status_code, status.HTTP_200_OK)

    def _create_medical_request(self):
        payload = {
            "employee": self.employee.pk,
            "reason": self.reason.pk,
            "description": "Funcionario relatou dor de cabeca.",
            "started_at": timezone.now().isoformat(),
            "severity": MedicalRequest.Severity.MEDIUM,
            "has_vehicle": False,
            "needs_transport": True,
            "destination": self.destination.pk,
            "requested_at": timezone.now().isoformat(),
            "notes": "Solicitacao criada pela API",
            "symptoms": [self.symptom.pk],
        }
        return self.client.post("/api/medical/requests/", payload, format="json")

    def _request_from_api(self):
        response = self._create_medical_request()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return MedicalRequest.objects.get(pk=response.data["id"])

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
