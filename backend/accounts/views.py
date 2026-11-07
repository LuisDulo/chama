from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    UserSerializer,
)
from audit.log import record


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """A separate salt, so a verification link can never be used to reset a password."""

    key_salt = "accounts.EmailVerification"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email_verified}{timestamp}"


verification_tokens = EmailVerificationTokenGenerator()


def link_parts(user, generator):
    return urlsafe_base64_encode(force_bytes(user.pk)), generator.make_token(user)


def user_from_uid(uid):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, ValidationError, TypeError):
        return None


def send_verification(user):
    uid, token = link_parts(user, verification_tokens)
    send_mail("Verify your CHAMA email",
              f"Confirm your email: {settings.FRONTEND_URL}/verify?uid={uid}&token={token}",
              None, [user.email])


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        record(user, "user.registered", user)
        send_verification(user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(UserSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutView(APIView):
    """Revokes the refresh token, so it cannot mint new access tokens."""

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh", ""))
            if str(token["user_id"]) != str(request.user.pk):
                raise TokenError("not yours")
            token.blacklist()
        except (TokenError, KeyError):
            return Response({"detail": "Invalid refresh token"}, status=400)
        return Response(status=204)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = user_from_uid(request.data.get("uid", ""))
        if user is None or not verification_tokens.check_token(user, request.data.get("token", "")):
            return Response({"detail": "This link is invalid or has expired"}, status=400)
        user.email_verified = True
        user.save(update_fields=["email_verified", "updated_at"])
        record(user, "user.email_verified", user)
        return Response({"detail": "Email verified"})


class PasswordResetView(APIView):
    """Always answers the same way, so it cannot reveal which emails are registered."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        user = User.objects.filter(email=str(request.data.get("email", "")).lower()).first()
        if user and user.is_active:
            uid, token = link_parts(user, default_token_generator)
            send_mail("Reset your CHAMA password",
                      f"Reset it here: {settings.FRONTEND_URL}/reset?uid={uid}&token={token}",
                      None, [user.email])
        return Response({"detail": "If that email is registered, a reset link is on its way"})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = user_from_uid(serializer.validated_data["uid"])
        if user is None or not default_token_generator.check_token(
            user, serializer.validated_data["token"]
        ):
            return Response({"detail": "This link is invalid or has expired"}, status=400)
        try:
            password_validation.validate_password(serializer.validated_data["new_password"], user)
        except ValidationError as error:
            return Response({"new_password": error.messages}, status=400)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        record(user, "user.password_reset", user)
        return Response({"detail": "Password changed. You can log in now."})
