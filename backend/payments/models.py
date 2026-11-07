import uuid

from django.conf import settings
from django.db import models

from audit.models import AppendOnly
from finance.models import MONEY


class Payment(models.Model):
    """A request for money and what came of it. Never deleted; only its status moves on."""

    class Status(models.TextChoices):
        PENDING = "pending"
        CONFIRMED = "confirmed"
        FAILED = "failed"
        EXPIRED = "expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chama = models.ForeignKey("chamas.Chama", on_delete=models.PROTECT, related_name="payments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name="payments")
    membership = models.ForeignKey("chamas.ChamaMembership", on_delete=models.PROTECT,
                                   related_name="payments")
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, default="KES")
    payment_method = models.CharField(max_length=20, default="mpesa_stk")
    provider = models.CharField(max_length=20, default="mpesa")
    merchant_reference = models.CharField(max_length=40, unique=True)
    checkout_request_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    provider_reference = models.CharField(max_length=80, unique=True, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    failure_reason = models.CharField(max_length=200, blank=True)
    contribution = models.OneToOneField("finance.Contribution", null=True, blank=True,
                                        on_delete=models.PROTECT, related_name="payment")
    initiated_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-initiated_at"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Payments cannot be deleted")


class PaymentCallback(AppendOnly):
    """Every callback received, kept as evidence. A repeat of the same body is recognised."""

    class Result(models.TextChoices):
        APPLIED = "applied"
        DUPLICATE = "duplicate"
        UNKNOWN_PAYMENT = "unknown_payment"
        IGNORED = "ignored"
        REJECTED = "rejected"

    payment = models.ForeignKey(Payment, null=True, on_delete=models.PROTECT,
                                related_name="callbacks")
    provider_event_id = models.CharField(max_length=80)
    payload_hash = models.CharField(max_length=64)
    result_code = models.IntegerField(null=True)
    processing_status = models.CharField(max_length=20, choices=Result.choices)
    received_at = models.DateTimeField(auto_now_add=True)
