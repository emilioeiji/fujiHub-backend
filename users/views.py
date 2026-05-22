from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        language = "pt-BR"
        try:
            language = request.user.profile.language
        except AttributeError:
            pass

        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "language": language,
        })
