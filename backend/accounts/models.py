import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, phone_number, password, **fields):
        user = self.model(email=self.normalize_email(email).lower(), phone_number=phone_number,
                          **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone_number, password, **fields):
        fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, phone_number, password, **fields)


class User(AbstractBaseUser, PermissionsMixin):
    """A platform identity. Chama roles live on memberships, not here."""

    class Status(models.TextChoices):
        ACTIVE = "active"
        SUSPENDED = "suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=12, unique=True)
    account_status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number", "first_name", "last_name"]

    @property
    def is_active(self):
        return self.account_status == self.Status.ACTIVE

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name
