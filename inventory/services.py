from django.db import transaction
from django.utils import timezone

from .models import StockMovement, UniformItem, UniformRequest, UniformRequestEvent


class UniformWorkflowError(ValueError):
    pass


def approve_request(request, user, note=None):
    return _transition_request(
        request=request,
        user=user,
        note=note,
        expected_status=UniformRequest.Status.PENDING,
        target_status=UniformRequest.Status.APPROVED,
        user_field="approved_by",
        timestamp_field="approved_at",
    )


def separate_request(request, user, note=None):
    with transaction.atomic():
        locked_request = _lock_request(request)
        _ensure_status(
            locked_request,
            UniformRequest.Status.APPROVED,
            UniformRequest.Status.SEPARATED,
        )

        items = list(locked_request.items.select_related("item"))
        if not items:
            raise UniformWorkflowError("Uniform request must have at least one item.")

        for request_item in items:
            item = UniformItem.objects.select_for_update().get(pk=request_item.item_id)
            if item.stock_quantity < request_item.quantity:
                raise UniformWorkflowError(
                    f"Insufficient stock for {item.sku}. "
                    f"Available: {item.stock_quantity}, requested: {request_item.quantity}."
                )

            item.stock_quantity -= request_item.quantity
            item.updated_by = user
            item.save(update_fields=["stock_quantity", "updated_by", "updated_at"])

            StockMovement.objects.create(
                item=item,
                movement_type=StockMovement.MovementType.OUT,
                quantity=request_item.quantity,
                source_type="uniform_request",
                source_id=str(locked_request.pk),
                user=user,
                notes=note or "",
            )

        return _apply_transition(
            request=locked_request,
            user=user,
            note=note,
            from_status=UniformRequest.Status.APPROVED,
            to_status=UniformRequest.Status.SEPARATED,
            user_field="separated_by",
            timestamp_field="separated_at",
        )


def deliver_request(request, user, note=None):
    return _transition_request(
        request=request,
        user=user,
        note=note,
        expected_status=UniformRequest.Status.SEPARATED,
        target_status=UniformRequest.Status.DELIVERED,
        user_field="delivered_by",
        timestamp_field="delivered_at",
    )


def cancel_request(request, user, note=None):
    allowed_statuses = {
        UniformRequest.Status.PENDING,
        UniformRequest.Status.APPROVED,
    }

    with transaction.atomic():
        locked_request = _lock_request(request)
        if locked_request.status not in allowed_statuses:
            raise UniformWorkflowError(
                f"Cannot transition uniform request from {locked_request.status} "
                f"to {UniformRequest.Status.CANCELLED}."
            )

        return _apply_transition(
            request=locked_request,
            user=user,
            note=note,
            from_status=locked_request.status,
            to_status=UniformRequest.Status.CANCELLED,
            user_field="cancelled_by",
            timestamp_field="cancelled_at",
        )


def _transition_request(
    *,
    request,
    user,
    note,
    expected_status,
    target_status,
    user_field,
    timestamp_field,
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
            user_field=user_field,
            timestamp_field=timestamp_field,
        )


def _lock_request(request):
    return UniformRequest.objects.select_for_update().get(pk=request.pk)


def _ensure_status(request, expected_status, target_status):
    if request.status != expected_status:
        raise UniformWorkflowError(
            f"Cannot transition uniform request from {request.status} to {target_status}."
        )


def _apply_transition(
    *,
    request,
    user,
    note,
    from_status,
    to_status,
    user_field,
    timestamp_field,
):
    setattr(request, user_field, user)
    setattr(request, timestamp_field, timezone.now())
    request.status = to_status
    request.updated_by = user
    request.save(update_fields=[user_field, timestamp_field, "status", "updated_by", "updated_at"])

    UniformRequestEvent.objects.create(
        request=request,
        status_from=from_status,
        status_to=to_status,
        user=user,
        note=note or "",
    )

    return request
