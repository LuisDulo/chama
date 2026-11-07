import hmac
import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.log import record
from chamas import permissions
from chamas.access import membership_for
from payments import services
from payments.gateway import get_gateway
from payments.models import Payment

logger = logging.getLogger(__name__)


def payment_row(payment):
    return {"id": payment.id, "amount": f"{payment.amount:.2f}", "currency": payment.currency,
            "status": payment.status, "receipt": payment.provider_reference,
            "failure_reason": payment.failure_reason, "initiated_at": payment.initiated_at,
            "confirmed_at": payment.confirmed_at, "member": payment.user.full_name}


class StkPushSerializer(serializers.Serializer):
    chama_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class StkPushView(APIView):
    def post(self, request):
        data = StkPushSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        membership = membership_for(request.user, data.validated_data["chama_id"])
        payment = services.initiate(membership, data.validated_data["amount"])
        if payment.status == Payment.Status.FAILED:
            return Response({**payment_row(payment),
                             "detail": "M-Pesa is not available right now. Please try again."},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response({**payment_row(payment), "simulated": get_gateway().simulated},
                        status=status.HTTP_202_ACCEPTED)


class CallbackView(APIView):
    """Public endpoint for Safaricom. Daraja does not sign callbacks, so the URL holds a secret."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, secret):
        expected = settings.MPESA["CALLBACK_SECRET"]
        if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
            raise NotFound()
        try:
            data = json.loads(request.body)
            data["Body"]["stkCallback"]["CheckoutRequestID"]
        except (ValueError, KeyError, TypeError):
            return Response({"ResultCode": 1, "ResultDesc": "Not an STK callback"}, status=400)
        outcome = services.handle_callback(request.body, data)
        logger.info("M-Pesa callback: %s", outcome)
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PaymentDetailView(APIView):
    def get(self, request, payment_id):
        payment = get_object_or_404(Payment.objects.select_related("user"), pk=payment_id)
        membership = membership_for(request.user, payment.chama_id)
        if payment.user_id != request.user.pk and not membership.role.allows(
                permissions.VIEW_FINANCES):
            raise NotFound()
        return Response(payment_row(payment))


class PaymentListView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        payments = Payment.objects.filter(chama=membership.chama).select_related("user")
        if request.query_params.get("scope") == "all":
            membership_for(request.user, chama_id, permissions.VIEW_FINANCES)
        else:
            payments = payments.filter(user=request.user)
        return Response([payment_row(p) for p in payments[:200]])


class ReconcileView(APIView):
    def post(self, request):
        membership = membership_for(request.user, request.data.get("chama_id"),
                                    permissions.RECORD_CONTRIBUTIONS)
        summary = services.reconcile(membership.chama)
        record(request.user, "payment.reconciled", membership.chama, chama=membership.chama,
               **summary)
        return Response(summary)


class SimulateView(APIView):
    """Stands in for the member's phone when M-Pesa is simulated. The result goes through the
    real callback handler, exactly as Safaricom's would."""

    def post(self, request, payment_id):
        if not get_gateway().simulated:
            raise NotFound()
        payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
        accept = bool(request.data.get("accept"))
        stk = {"MerchantRequestID": "simulated", "CheckoutRequestID": payment.checkout_request_id,
               "ResultCode": 0 if accept else 1032,
               "ResultDesc": "Processed" if accept else "Request cancelled by user"}
        if accept:
            stk["CallbackMetadata"] = {"Item": [
                {"Name": "Amount", "Value": float(payment.amount)},
                {"Name": "MpesaReceiptNumber", "Value": f"SIM{payment.id.hex[:7].upper()}"},
                {"Name": "PhoneNumber", "Value": int(payment.user.phone_number)}]}
        body = {"Body": {"stkCallback": stk}}
        services.handle_callback(json.dumps(body).encode(), body)
        payment.refresh_from_db()
        return Response(payment_row(payment))
