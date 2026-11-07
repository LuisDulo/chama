import json
from datetime import timedelta
from decimal import Decimal

import pytest
import responses
from django.utils import timezone

from finance import ledger
from finance.models import Contribution
from payments import services
from payments.gateway import DarajaGateway, GatewayError, QueryResult
from payments.models import Payment, PaymentCallback
from tests.conftest import client_for
from tests.factories import add_member, chama_for

CALLBACK = "/api/payments/callback/test-callback-secret/"


@pytest.fixture
def chama(user):
    return chama_for(user)


@pytest.fixture
def member(chama):
    return add_member(chama)


def push(member, amount="1000"):
    return client_for(member.user).post("/api/payments/stk-push/",
                                        {"chama_id": str(member.chama_id), "amount": amount})


def paid_body(checkout, amount=1000, receipt="SGH12345"):
    return {"Body": {"stkCallback": {
        "MerchantRequestID": "m-1", "CheckoutRequestID": checkout, "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "CallbackMetadata": {"Item": [
            {"Name": "Amount", "Value": amount}, {"Name": "MpesaReceiptNumber", "Value": receipt},
            {"Name": "TransactionDate", "Value": 20260307101010},
            {"Name": "PhoneNumber", "Value": 254700000010}]}}}}


def cancelled_body(checkout):
    return {"Body": {"stkCallback": {"MerchantRequestID": "m-1", "CheckoutRequestID": checkout,
                                     "ResultCode": 1032,
                                     "ResultDesc": "Request cancelled by user"}}}


def callback(anonymous, body, url=CALLBACK):
    return anonymous.post(url, json.dumps(body), content_type="application/json")


def started(member, amount="1000"):
    response = push(member, amount)
    assert response.status_code == 202, response.data
    return Payment.objects.get(pk=response.data["id"])


class TestInitiating:
    def test_starting_a_payment_credits_nothing(self, member):
        payment = started(member)
        assert payment.status == "pending"
        assert payment.checkout_request_id
        assert len(payment.merchant_reference) <= 12
        assert Contribution.objects.count() == 0
        assert ledger.member_savings(member) == 0

    def test_amounts_must_be_whole_shillings_and_meet_the_minimum(self, member):
        assert push(member, "1000.50").status_code == 400
        assert push(member, "100").status_code == 400

    def test_a_second_prompt_waits_for_the_first(self, member):
        started(member)
        assert push(member).status_code == 400

    def test_an_outsider_cannot_pay_into_a_chama(self, chama):
        outsider = add_member(chama_for(chama.created_by, name="Other"))
        response = client_for(outsider.user).post("/api/payments/stk-push/",
                                                  {"chama_id": str(chama.id), "amount": "1000"})
        assert response.status_code == 404

    def test_an_mpesa_outage_is_reported_and_recorded(self, member, monkeypatch):
        class Down:
            simulated = False

            def stk_push(self, *args):
                raise GatewayError("down")

        monkeypatch.setattr(services, "get_gateway", lambda: Down())
        assert push(member).status_code == 502
        assert Payment.objects.get().status == "failed"


class TestCallbacks:
    def test_a_successful_callback_becomes_a_contribution_in_the_ledger(self, member, anonymous):
        payment = started(member)
        assert callback(anonymous, paid_body(payment.checkout_request_id)).status_code == 200
        payment.refresh_from_db()
        assert payment.status == "confirmed"
        assert payment.provider_reference == "SGH12345"
        assert payment.contribution.method == "mpesa"
        assert ledger.member_savings(member) == Decimal("1000")

    def test_a_repeated_callback_counts_once_and_is_kept_as_evidence(self, member, anonymous):
        payment = started(member)
        callback(anonymous, paid_body(payment.checkout_request_id))
        callback(anonymous, paid_body(payment.checkout_request_id))
        assert ledger.member_savings(member) == Decimal("1000")
        outcomes = list(PaymentCallback.objects.order_by("received_at")
                        .values_list("processing_status", flat=True))
        assert outcomes == ["applied", "duplicate"]

    def test_a_late_failure_cannot_undo_a_confirmed_payment(self, member, anonymous):
        payment = started(member)
        callback(anonymous, paid_body(payment.checkout_request_id))
        callback(anonymous, cancelled_body(payment.checkout_request_id))
        payment.refresh_from_db()
        assert payment.status == "confirmed"

    def test_a_cancelled_prompt_fails_without_crediting(self, member, anonymous):
        payment = started(member)
        callback(anonymous, cancelled_body(payment.checkout_request_id))
        payment.refresh_from_db()
        assert (payment.status, payment.failure_reason) == ("failed", "Request cancelled by user")
        assert ledger.member_savings(member) == 0

    def test_a_wrong_amount_is_rejected(self, member, anonymous):
        payment = started(member)
        callback(anonymous, paid_body(payment.checkout_request_id, amount=1))
        payment.refresh_from_db()
        assert payment.status == "failed"
        assert ledger.member_savings(member) == 0

    def test_a_receipt_cannot_be_used_twice(self, chama, member, anonymous):
        first = started(member)
        callback(anonymous, paid_body(first.checkout_request_id, receipt="SAME1"))
        other = add_member(chama)
        second = started(other)
        callback(anonymous, paid_body(second.checkout_request_id, receipt="SAME1"))
        second.refresh_from_db()
        assert second.status == "failed"
        assert ledger.member_savings(other) == 0

    def test_an_unknown_checkout_is_recorded_and_ignored(self, member, anonymous):
        started(member)
        assert callback(anonymous, paid_body("ws_CO_FORGED")).status_code == 200
        assert PaymentCallback.objects.get().processing_status == "unknown_payment"
        assert ledger.member_savings(member) == 0

    def test_the_wrong_secret_is_refused(self, member, anonymous):
        payment = started(member)
        response = callback(anonymous, paid_body(payment.checkout_request_id),
                            url="/api/payments/callback/guess/")
        assert response.status_code == 404
        payment.refresh_from_db()
        assert payment.status == "pending"

    def test_a_malformed_body_is_refused(self, anonymous):
        assert callback(anonymous, {"hello": "world"}).status_code == 400


class TestReconciliation:
    class Answers:
        simulated = False

        def __init__(self, result):
            self.result = result

        def query(self, checkout):
            return self.result

    def reconcile(self, user, chama):
        return client_for(user).post("/api/payments/reconcile/", {"chama_id": str(chama.id)})

    def age(self, payment, minutes):
        Payment.objects.filter(pk=payment.pk).update(
            initiated_at=timezone.now() - timedelta(minutes=minutes))

    def test_a_lost_callback_is_recovered_by_asking_mpesa(self, user, chama, member, monkeypatch):
        payment = started(member)
        self.age(payment, 5)
        monkeypatch.setattr(services, "get_gateway", lambda: self.Answers(QueryResult(0)))
        assert self.reconcile(user, chama).data["confirmed"] == 1
        assert ledger.member_savings(member) == Decimal("1000")

    def test_a_failed_result_is_recorded(self, user, chama, member, monkeypatch):
        payment = started(member)
        self.age(payment, 5)
        monkeypatch.setattr(services, "get_gateway",
                            lambda: self.Answers(QueryResult(1032, "Cancelled")))
        assert self.reconcile(user, chama).data["failed"] == 1

    def test_a_payment_with_no_answer_for_a_day_expires(self, user, chama, member, monkeypatch):
        payment = started(member)
        self.age(payment, 60 * 25)
        monkeypatch.setattr(services, "get_gateway", lambda: self.Answers(QueryResult(None)))
        assert self.reconcile(user, chama).data["expired"] == 1

    def test_recent_payments_are_left_alone(self, user, chama, member, monkeypatch):
        started(member)
        monkeypatch.setattr(services, "get_gateway", lambda: self.Answers(QueryResult(0)))
        assert self.reconcile(user, chama).data["checked"] == 0

    def test_only_finance_officers_can_reconcile(self, chama, member):
        response = client_for(member.user).post("/api/payments/reconcile/",
                                                {"chama_id": str(chama.id)})
        assert response.status_code == 403


class TestSimulatorAndPrivacy:
    def test_the_simulator_goes_through_the_real_callback(self, member):
        payment = started(member)
        response = client_for(member.user).post(f"/api/payments/{payment.id}/simulate/",
                                                {"accept": True}, format="json")
        assert response.data["status"] == "confirmed"
        assert PaymentCallback.objects.get().processing_status == "applied"

    def test_only_the_payer_can_answer_their_prompt(self, chama, member):
        payment = started(member)
        other = add_member(chama)
        response = client_for(other.user).post(f"/api/payments/{payment.id}/simulate/",
                                               {"accept": True}, format="json")
        assert response.status_code == 404

    def test_a_payment_is_private_to_its_payer_and_finance_officers(self, user, chama, member):
        payment = started(member)
        other = add_member(chama)
        assert client_for(member.user).get(f"/api/payments/{payment.id}/").status_code == 200
        assert client_for(user).get(f"/api/payments/{payment.id}/").status_code == 200
        assert client_for(other.user).get(f"/api/payments/{payment.id}/").status_code == 404


class TestDarajaClient:
    CONFIG = {"BASE_URL": "https://daraja.test", "CONSUMER_KEY": "key",
              "CONSUMER_SECRET": "secret", "SHORTCODE": "174379", "PASSKEY": "pass",
              "CALLBACK_BASE_URL": "https://app.test", "CALLBACK_SECRET": "s" * 24}

    def token(self):
        responses.get("https://daraja.test/oauth/v1/generate?grant_type=client_credentials",
                      json={"access_token": "abc", "expires_in": "3599"})

    @responses.activate
    def test_stk_push_sends_a_well_formed_request(self):
        self.token()
        responses.post("https://daraja.test/mpesa/stkpush/v1/processrequest",
                       json={"ResponseCode": "0", "CheckoutRequestID": "ws_CO_1"})
        gateway = DarajaGateway(self.CONFIG)
        assert gateway.stk_push("254712345678", Decimal("1000"), "CH12345ABCDE",
                                "Contribution") == "ws_CO_1"
        sent = json.loads(responses.calls[1].request.body)
        assert sent["Amount"] == 1000
        assert sent["CallBackURL"] == "https://app.test/api/payments/callback/" + "s" * 24 + "/"
        assert responses.calls[1].request.headers["Authorization"] == "Bearer abc"
        assert len(sent["Timestamp"]) == 14

    @responses.activate
    def test_the_token_is_reused(self):
        self.token()
        responses.post("https://daraja.test/mpesa/stkpush/v1/processrequest",
                       json={"ResponseCode": "0", "CheckoutRequestID": "ws_CO_1"})
        gateway = DarajaGateway(self.CONFIG)
        gateway.stk_push("254712345678", Decimal("1"), "R", "D")
        gateway.stk_push("254712345678", Decimal("1"), "R", "D")
        assert len(responses.calls) == 3

    @responses.activate
    def test_a_refused_push_is_an_error(self):
        self.token()
        responses.post("https://daraja.test/mpesa/stkpush/v1/processrequest", status=400,
                       json={"errorCode": "400.002.02", "errorMessage": "Bad Request"})
        with pytest.raises(GatewayError):
            DarajaGateway(self.CONFIG).stk_push("254712345678", Decimal("1"), "R", "D")

    @responses.activate
    def test_query_reads_a_result_or_still_processing(self):
        self.token()
        responses.post("https://daraja.test/mpesa/stkpushquery/v1/query",
                       json={"ResultCode": "0", "ResultDesc": "Processed"})
        responses.post("https://daraja.test/mpesa/stkpushquery/v1/query", status=500,
                       json={"errorCode": "500.001.1001",
                             "errorMessage": "The transaction is being processed"})
        gateway = DarajaGateway(self.CONFIG)
        assert gateway.query("ws_CO_1").result_code == 0
        assert gateway.query("ws_CO_1").result_code is None
