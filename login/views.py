from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    # Remove SessionAuthentication so CSRF is not enforced by DRF
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Usuário e senha são obrigatórios'}, status=400)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({'error': 'Credenciais inválidas'}, status=400)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
        })

@csrf_exempt
def ping(request):
    return JsonResponse({'ok': True})