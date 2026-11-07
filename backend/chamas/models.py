import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Chama(models.Model):
    """One savings group, and the tenant that its records belong to."""

    class Category(models.TextChoices):
        SAVINGS = "savings"
        INVESTMENT = "investment"
        MERRY_GO_ROUND = "merry_go_round"
        WELFARE = "welfare"
        OTHER = "other"

    class Visibility(models.TextChoices):
        PUBLIC = "public"
        PRIVATE = "private"

    class Membership(models.TextChoices):
        OPEN = "open"
        INVITATION = "invitation"

    class Status(models.TextChoices):
        ACTIVE = "active"
        SUSPENDED = "suspended"
        CLOSED = "closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SAVINGS)
    currency = models.CharField(max_length=3, default="KES")
    location = models.CharField(max_length=120, blank=True)
    visibility = models.CharField(max_length=10, choices=Visibility.choices,
                                  default=Visibility.PRIVATE)
    membership_type = models.CharField(max_length=12, choices=Membership.choices,
                                       default=Membership.INVITATION)
    requires_approval = models.BooleanField(default=True)
    maximum_members = models.PositiveIntegerField(default=50)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ChamaRole(models.Model):
    chama = models.ForeignKey(Chama, on_delete=models.CASCADE, related_name="roles")
    role_name = models.CharField(max_length=40)
    description = models.CharField(max_length=200, blank=True)
    permissions = models.JSONField(default=list)
    is_system_role = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chama", "role_name"], name="unique_role_name")
        ]

    def allows(self, permission):
        return permission in self.permissions


class ChamaMembership(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACTIVE = "active"
        SUSPENDED = "suspended"
        REJECTED = "rejected"
        EXITED = "exited"

    CURRENT = [Status.PENDING, Status.ACTIVE, Status.SUSPENDED]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chama = models.ForeignKey(Chama, on_delete=models.PROTECT, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="memberships")
    role = models.ForeignKey(ChamaRole, on_delete=models.PROTECT, related_name="memberships")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    joined_at = models.DateTimeField(null=True, blank=True)
    exit_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # A user can rejoin after leaving, but never hold two live memberships at once.
            models.UniqueConstraint(fields=["chama", "user"],
                                    condition=Q(status__in=["pending", "active", "suspended"]),
                                    name="one_current_membership")
        ]

    def activate(self, approver):
        self.status = self.Status.ACTIVE
        self.joined_at = timezone.now()
        self.approved_by = approver


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ChamaInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        REVOKED = "revoked"

    LIFETIME = timedelta(days=7)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chama = models.ForeignKey(Chama, on_delete=models.CASCADE, related_name="invitations")
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    invited_email = models.EmailField(blank=True)
    invited_phone = models.CharField(max_length=12, blank=True)
    role = models.ForeignKey(ChamaRole, on_delete=models.PROTECT, related_name="+")
    invitation_token_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, **fields):
        """Returns the invitation and its token. Only the hash is stored."""
        token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(invitation_token_hash=hash_token(token),
                                        expires_at=timezone.now() + cls.LIFETIME, **fields)
        return invitation, token

    def is_for(self, user):
        return (self.invited_email and self.invited_email == user.email) or (
            self.invited_phone and self.invited_phone == user.phone_number
        )
