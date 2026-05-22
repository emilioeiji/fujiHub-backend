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
        fields = ["id", "item", "item_detail", "quantity"]
        read_only_fields = ["id", "item_detail"]


class UniformRequestSerializer(serializers.ModelSerializer):
    items = UniformRequestItemSerializer(many=True)

    class Meta:
        model = UniformRequest
        fields = [
            "id",
            "employee",
            "requested_by",
            "status",
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
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        uniform_request = UniformRequest.objects.create(**validated_data)

        for item_data in items_data:
            UniformRequestItem.objects.create(request=uniform_request, **item_data)

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
