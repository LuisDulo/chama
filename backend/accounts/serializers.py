from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User
from accounts.phone import normalise_phone


def phone_field(value):
    try:
        return normalise_phone(value)
    except ValueError as error:
        raise serializers.ValidationError(str(error)) from error


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "phone_number", "email_verified",
                  "phone_verified", "created_at"]
        read_only_fields = ["id", "email", "email_verified", "phone_verified", "created_at"]

    def validate_phone_number(self, value):
        phone = phone_field(value)
        if User.objects.exclude(pk=getattr(self.instance, "pk", None)).filter(
            phone_number=phone
        ).exists():
            raise serializers.ValidationError("That phone number is already registered")
        return phone


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "password"]

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("That email is already registered")
        return email

    def validate_phone_number(self, value):
        phone = phone_field(value)
        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError("That phone number is already registered")
        return phone

    def validate(self, attrs):
        candidate = User(**{k: v for k, v in attrs.items() if k != "password"})
        password_validation.validate_password(attrs["password"], candidate)
        return attrs

    def create(self, validated):
        return User.objects.create_user(**validated)


class LoginSerializer(TokenObtainPairSerializer):
    """Accepts an email address or a phone number in the same field."""

    username_field = "login"

    def validate(self, attrs):
        login = attrs.get("login", "").strip()
        user = User.objects.filter(email=login.lower()).first()
        if user is None:
            try:
                user = User.objects.filter(phone_number=normalise_phone(login)).first()
            except ValueError:
                user = None
        if user is None or not user.is_active or not user.check_password(attrs.get("password")):
            raise serializers.ValidationError("Wrong email, phone or password")
        refresh = self.get_token(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class PasswordChangeSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()
