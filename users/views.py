from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        language = "pt-BR"
        role_code = None
        try:
            language = request.user.profile.language
            if request.user.profile.role and request.user.profile.role.is_active:
                role_code = request.user.profile.role.code
        except AttributeError:
            pass

        if request.user.is_superuser and not role_code:
            role_code = "admin"

        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "language": language,
            "role_code": role_code,
        })
