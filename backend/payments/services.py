import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit.log import record
from finance.contributions import check_amount, record_contribution
from finance.models import Contribution
from payments.gateway import GatewayError, get_gateway
from payments.models import Payment, PaymentCallback

PROMPT_WAIT = timedelta(minutes=2)
GIVE_UP_AFTER = timedelta(hours=24)


def initiate(membership, amount: Decimal) -> Payment:
    """Ask M-Pesa to prompt the member's phone. Nothing is credited until it is confirmed.

    If M-Pesa cannot be reached the payment is returned as failed rather than raised, because
    raising would roll back the request's transaction and lose the record of the attempt.
    """
    if amount != amount.to_integral_value():
        raise ValidationError({"amount": "M-Pesa payments must be whole shillings"})
    check_amount(membership, amount)
    recent = Payment.objects.filter(membership=membership, status=Payment.Status.PENDING,
                                    initiated_at__gt=timezone.now() - PROMPT_WAIT)
    if recent.exists():
        raise ValidationError("Check your phone: a payment is already waiting for your PIN")
    payment = Payment.objects.create(
        chama=membership.chama, user=membership.user, membership=membership, amount=amount,
        currency=membership.chama.currency,
        # Daraja allows at most 12 characters here.
        merchant_reference=f"CH{secrets.token_hex(5).upper()}")
    try:
        # And at most 13 in the description.
        checkout = get_gateway().stk_push(membership.user.phone_number, amount,
                                          payment.merchant_reference, "Contribution")
    except GatewayError as error:
        _fail(payment, str(error))
        return payment
    payment.checkout_request_id = checkout
    payment.save(update_fields=["checkout_request_id"])
    record(membership.user, "payment.initiated", payment, chama=membership.chama, amount=amount)
    return payment


def _metadata(callback):
    items = (callback.get("CallbackMetadata") or {}).get("Item") or []
    return {item.get("Name"): item.get("Value") for item in items if "Value" in item}


def _confirm(payment: Payment, receipt: str):
    contribution = record_contribution(payment.membership, payment.amount,
                                       Contribution.Method.MPESA, receipt, payment.user)
    payment.status = Payment.Status.CONFIRMED
    payment.provider_reference = receipt
    payment.contribution = contribution
    payment.confirmed_at = timezone.now()
    payment.save()
    record(payment.user, "payment.confirmed", payment, chama=payment.chama, receipt=receipt)


def _fail(payment: Payment, reason: str, status=Payment.Status.FAILED):
    payment.status = status
    payment.failure_reason = reason[:200]
    payment.save(update_fields=["status", "failure_reason"])
    record(None, f"payment.{status}", payment, chama=payment.chama, reason=reason)


@transaction.atomic
def handle_callback(raw_body: bytes, data: dict) -> str:
    """Apply one Daraja result. Returns what happened, for the stored callback record."""
    stk = data["Body"]["stkCallback"]
    checkout = str(stk["CheckoutRequestID"])
    result_code = int(stk["ResultCode"])
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    payment = Payment.objects.select_for_update().filter(checkout_request_id=checkout).first()

    def store(outcome):
        PaymentCallback.objects.create(payment=payment, provider_event_id=checkout,
                                       payload_hash=payload_hash, result_code=result_code,
                                       processing_status=outcome)
        return outcome

    if PaymentCallback.objects.filter(payload_hash=payload_hash).exists():
        return store(PaymentCallback.Result.DUPLICATE)
    if payment is None:
        return store(PaymentCallback.Result.UNKNOWN_PAYMENT)
    if payment.status != Payment.Status.PENDING:
        return store(PaymentCallback.Result.IGNORED)
    if result_code != 0:
        _fail(payment, stk.get("ResultDesc", "Payment was not completed"))
        return store(PaymentCallback.Result.APPLIED)

    meta = _metadata(stk)
    receipt = str(meta.get("MpesaReceiptNumber") or "")
    try:
        amount = Decimal(str(meta.get("Amount")))
    except ArithmeticError:
        amount = None
    if not receipt or amount != payment.amount:
        _fail(payment, "M-Pesa reported a different amount or no receipt")
        return store(PaymentCallback.Result.REJECTED)
    try:
        with transaction.atomic():
            _confirm(payment, receipt)
    except (IntegrityError, ValidationError):
        _fail(payment, "This M-Pesa receipt has already been used")
        return store(PaymentCallback.Result.REJECTED)
    return store(PaymentCallback.Result.APPLIED)


def reconcile(chama) -> dict:
    """Ask M-Pesa about payments whose callback never arrived (NFR 4.3)."""
    gateway = get_gateway()
    now = timezone.now()
    summary = {"checked": 0, "confirmed": 0, "failed": 0, "expired": 0, "still_pending": 0}
    stale = Payment.objects.filter(chama=chama, status=Payment.Status.PENDING,
                                   initiated_at__lt=now - PROMPT_WAIT)
    for payment_id in stale.values_list("id", flat=True):
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment_id)
            if payment.status != Payment.Status.PENDING:
                continue
            summary["checked"] += 1
            try:
                result = gateway.query(payment.checkout_request_id) \
                    if payment.checkout_request_id else None
            except GatewayError:
                result = None
            if result is not None and result.result_code == 0:
                # The status query gives no receipt number, so the checkout ID stands in.
                _confirm(payment, payment.checkout_request_id)
                summary["confirmed"] += 1
            elif result is not None and result.result_code is not None:
                _fail(payment, result.description or "Payment was not completed")
                summary["failed"] += 1
            elif payment.initiated_at < now - GIVE_UP_AFTER:
                _fail(payment, "No result from M-Pesa", Payment.Status.EXPIRED)
                summary["expired"] += 1
            else:
                summary["still_pending"] += 1
    return summary
