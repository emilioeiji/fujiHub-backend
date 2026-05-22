from rest_framework import viewsets

from .models import Role, UserProfile
from .serializers import RoleSerializer, UserProfileSerializer


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.select_related("user", "role", "department")
    serializer_class = UserProfileSerializer
