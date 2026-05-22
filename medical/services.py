from django.db import transaction
from django.utils import timezone

from .models import MedicalRequest, MedicalRequestEvent


class MedicalWorkflowError(ValueError):
    pass


def triage_request(request, user, note=None):
    return _transition_request(
        request=request,
        user=user,
        note=note,
        expected_status=MedicalRequest.Status.REQUESTED,
        target_status=MedicalRequest.Status.TRIAGED,
        timestamp_field="triaged_at",
        assign_user=True,
    )


def start_medical_service(request, user, note=None):
    return _transition_request(
        request=request,
        user=user,
        note=note,
        expected_status=MedicalRequest.Status.TRIAGED,
        target_status=MedicalRequest.Status.IN_PROGRESS,
        timestamp_field="started_service_at",
        assign_user=True,
    )


def complete_medical_request(request, user, note=None):
    return _transition_request(
        request=request,
        user=user,
        note=note,
        expected_status=MedicalRequest.Status.IN_PROGRESS,
        target_status=MedicalRequest.Status.COMPLETED,
        timestamp_field="completed_at",
        completed_by=user,
    )


def cancel_medical_request(request, user, note=None):
    allowed_statuses = {
        MedicalRequest.Status.REQUESTED,
        MedicalRequest.Status.TRIAGED,
    }

    with transaction.atomic():
        locked_request = _lock_request(request)
        if locked_request.status not in allowed_statuses:
            raise MedicalWorkflowError(
                f"Cannot transition medical request from {locked_request.status} "
                f"to {MedicalRequest.Status.CANCELLED}."
            )

        return _apply_transition(
            request=locked_request,
            user=user,
            note=note,
            from_status=locked_request.status,
            to_status=MedicalRequest.Status.CANCELLED,
            timestamp_field="cancelled_at",
        )


def _transition_request(
    *,
    request,
    user,
    note,
    expected_status,
    target_status,
    timestamp_field,
    assign_user=False,
    completed_by=None,
):
    with transaction.atomic():
        locked_request = _lock_request(request)
        _ensure_status(locked_request, expected_status, target_status)
        return _apply_transition(
            request=locked_request,
            user=user,
            note=note,
            from_status=expected_status,
            to_status=target_status,
            timestamp_field=timestamp_field,
            assign_user=assign_user,
            completed_by=completed_by,
        )


def _lock_request(request):
    return MedicalRequest.objects.select_for_update().get(pk=request.pk)


def _ensure_status(request, expected_status, target_status):
    if request.status != expected_status:
        raise MedicalWorkflowError(
            f"Cannot transition medical request from {request.status} to {target_status}."
        )


def _apply_transition(
    *,
    request,
    user,
    note,
    from_status,
    to_status,
    timestamp_field,
    assign_user=False,
    completed_by=None,
):
    update_fields = [timestamp_field, "status", "updated_by", "updated_at"]

    setattr(request, timestamp_field, timezone.now())
    request.status = to_status
    request.updated_by = user

    if assign_user and request.assigned_to_id is None:
        request.assigned_to = user
        update_fields.append("assigned_to")

    if completed_by is not None:
        request.completed_by = completed_by
        update_fields.append("completed_by")

    request.save(update_fields=update_fields)

    MedicalRequestEvent.objects.create(
        request=request,
        status_from=from_status,
        status_to=to_status,
        user=user,
        note=note or "",
    )

    return request
