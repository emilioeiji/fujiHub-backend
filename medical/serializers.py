from rest_framework import serializers

from .models import (
    MedicalDestination,
    MedicalReason,
    MedicalRequest,
    MedicalRequestEvent,
    MedicalRequestSymptom,
    SymptomType,
)


class MedicalReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalReason
        fields = [
            "id",
            "code",
            "name_pt",
            "name_jp",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class SymptomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SymptomType
        fields = [
            "id",
            "code",
            "name_pt",
            "name_jp",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class MedicalDestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalDestination
        fields = [
            "id",
            "code",
            "name",
            "address",
            "phone",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]


class MedicalRequestSymptomSerializer(serializers.ModelSerializer):
    symptom_detail = SymptomTypeSerializer(source="symptom", read_only=True)

    class Meta:
        model = MedicalRequestSymptom
        fields = ["id", "symptom", "symptom_detail"]
        read_only_fields = ["id", "symptom_detail"]


class MedicalRequestSerializer(serializers.ModelSerializer):
    symptoms = serializers.PrimaryKeyRelatedField(
        queryset=SymptomType.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    symptom_items = MedicalRequestSymptomSerializer(source="symptoms", many=True, read_only=True)
    employee_display = serializers.SerializerMethodField()
    reason_detail = MedicalReasonSerializer(source="reason", read_only=True)
    destination_detail = MedicalDestinationSerializer(source="destination", read_only=True)

    class Meta:
        model = MedicalRequest
        fields = [
            "id",
            "employee",
            "employee_display",
            "reason",
            "reason_detail",
            "description",
            "started_at",
            "severity",
            "has_vehicle",
            "needs_transport",
            "destination",
            "destination_detail",
            "status",
            "requested_by",
            "assigned_to",
            "completed_by",
            "requested_at",
            "triaged_at",
            "started_service_at",
            "completed_at",
            "cancelled_at",
            "notes",
            "symptoms",
            "symptom_items",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "employee_display",
            "reason_detail",
            "destination_detail",
            "status",
            "requested_by",
            "assigned_to",
            "completed_by",
            "triaged_at",
            "started_service_at",
            "completed_at",
            "cancelled_at",
            "symptom_items",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def get_employee_display(self, obj):
        employee = obj.employee
        return {
            "employee_id": employee.employee_id,
            "name_en": employee.name_en,
            "name_jp": employee.name_jp,
            "internal_name": employee.internal_name,
        }

    def create(self, validated_data):
        symptoms = validated_data.pop("symptoms", [])
        medical_request = MedicalRequest.objects.create(**validated_data)

        for symptom in symptoms:
            MedicalRequestSymptom.objects.create(
                request=medical_request,
                symptom=symptom,
            )

        return medical_request

    def update(self, instance, validated_data):
        if "symptoms" in validated_data:
            raise serializers.ValidationError(
                {"symptoms": "Medical request symptoms cannot be updated through this endpoint yet."}
            )

        return super().update(instance, validated_data)


class MedicalRequestEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRequestEvent
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
