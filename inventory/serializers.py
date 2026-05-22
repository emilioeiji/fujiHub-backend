from rest_framework import serializers

from .models import (
    StockMovement,
    UniformCategory,
    UniformItem,
    UniformRequest,
    UniformRequestEvent,
    UniformRequestItem,
)


class UniformCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UniformCategory
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class UniformItemSerializer(serializers.ModelSerializer):
    category_detail = UniformCategorySerializer(source="category", read_only=True)

    class Meta:
        model = UniformItem
        fields = [
            "id",
            "sku",
            "name",
            "category",
            "category_detail",
            "size",
            "color",
            "stock_quantity",
            "minimum_stock",
            "unit_cost",
            "average_cost",
            "average_price",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "category_detail",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]


class UniformRequestItemSerializer(serializers.ModelSerializer):
    item_detail = UniformItemSerializer(source="item", read_only=True)

    class Meta:
        model = UniformRequestItem
        fields = [
            "id",
            "item",
            "item_detail",
            "quantity",
            "unit_cost_snapshot",
            "total_cost",
        ]
        read_only_fields = ["id", "item_detail", "unit_cost_snapshot", "total_cost"]


class UniformRequestSerializer(serializers.ModelSerializer):
    items = UniformRequestItemSerializer(many=True)

    class Meta:
        model = UniformRequest
        fields = [
            "id",
            "employee",
            "requested_by",
            "status",
            "request_type",
            "reason",
            "request_date",
            "approved_by",
            "approved_at",
            "separated_by",
            "separated_at",
            "delivered_by",
            "delivered_at",
            "cancelled_by",
            "cancelled_at",
            "notes",
            "items",
            "total_cost",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "requested_by",
            "status",
            "approved_by",
            "approved_at",
            "separated_by",
            "separated_at",
            "delivered_by",
            "delivered_at",
            "cancelled_by",
            "cancelled_at",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "total_cost",
        ]

    def validate(self, attrs):
        request_type = attrs.get(
            "request_type",
            getattr(self.instance, "request_type", UniformRequest.RequestType.DONATION),
        )
        reason = attrs.get("reason", getattr(self.instance, "reason", ""))

        if request_type == UniformRequest.RequestType.DONATION and not reason:
            raise serializers.ValidationError(
                {"reason": "Reason is required for donation uniform requests."}
            )

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        uniform_request = UniformRequest.objects.create(**validated_data)

        for item_data in items_data:
            item = item_data["item"]
            UniformRequestItem.objects.create(
                request=uniform_request,
                unit_cost_snapshot=item.unit_cost,
                **item_data,
            )

        return uniform_request

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        if items_data is not None:
            raise serializers.ValidationError(
                {"items": "Uniform request items cannot be updated through this endpoint yet."}
            )

        instance = super().update(instance, validated_data)
        return instance


class StockMovementSerializer(serializers.ModelSerializer):
    item_detail = UniformItemSerializer(source="item", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "item",
            "item_detail",
            "movement_type",
            "quantity",
            "source_type",
            "source_id",
            "user",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class UniformRequestEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = UniformRequestEvent
        fields = [
            "id",
            "request",
            "status_from",
            "status_to",
            "user",
            "note",
            "created_at",
        ]
        read_only_fields = fields
