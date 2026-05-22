from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from master.models import Employee

from .models import MedicalReason, MedicalRequest, MedicalRequestEvent
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
