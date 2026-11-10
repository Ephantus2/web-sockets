import os
import secrets

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from rest_framework import status

User = get_user_model()

class AdminBootstrapView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        #Get the bootstrap secret from environment variables

        bootstrap_token = os.getenv("ADMIN_BOOTSTRAP_TOKEN")

        if not bootstrap_token:
            return Response(
                {
                    "error":"Administrator setup is disabled."
                }
            )

        # verify the supplied token
        supplied_token = request.headers.get(
            "X-Admin-Bootstrap-Token", ""
        )
        if not secrets.compare_digest(
            bootstrap_token,
            supplied_token
        ):
            return Response({"error": "Invalid authorization Token"}, status=status.HTTP_403_FORBIDDEN)

        # prevent creation of duplicate administrators
        if User.objects.filter(is_superuser=True).exists():
            return Response(
                {
                    "error": "An administrator already exists."
                }, status=status.HTTP_409_CONFLICT
            )
        username = request.data.get("username")
        email = request.data.get("email", "")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status = status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 12:
            return Response(
                {
                    "error": "Password must contain atleast 12 characters."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists."},
                status=status.HTTP_409_CONFLICT
            )
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        return Response(
            {"message": "Administrator created successfully."},
            status=status.HTTP_201_CREATED
        )