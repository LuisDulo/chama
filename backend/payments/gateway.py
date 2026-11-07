"""Talking to M-Pesa. The rest of the app only sees the Gateway interface."""

import base64
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
NAIROBI = ZoneInfo("Africa/Nairobi")


class GatewayError(Exception):
    pass


@dataclass
class QueryResult:
    """None for result_code means M-Pesa is still processing the request."""

    result_code: int | None
    description: str = ""


class SimulatedGateway:
    """Used when no Daraja credentials are set. Results are sent through the real callback."""

    simulated = True

    def stk_push(self, phone, amount, reference, description) -> str:
        return f"ws_CO_SIMULATED_{uuid.uuid4().hex}"

    def query(self, checkout_request_id) -> QueryResult:
        return QueryResult(None, "Simulated payments are answered from the app")


class DarajaGateway:
    simulated = False
    timeout = 20

    def __init__(self, config):
        self.config = config
        self._token = None
        self._token_expiry = 0.0

    def _token_value(self):
        if time.monotonic() < self._token_expiry:
            return self._token
        response = requests.get(
            f"{self.config['BASE_URL']}/oauth/v1/generate?grant_type=client_credentials",
            auth=(self.config["CONSUMER_KEY"], self.config["CONSUMER_SECRET"]),
            timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        # Renew a minute early so a token cannot expire during a request.
        self._token_expiry = time.monotonic() + int(data["expires_in"]) - 60
        return self._token

    def _password(self, timestamp):
        raw = f"{self.config['SHORTCODE']}{self.config['PASSKEY']}{timestamp}"
        return base64.b64encode(raw.encode()).decode()

    def _post(self, path, body):
        try:
            response = requests.post(f"{self.config['BASE_URL']}{path}", json=body,
                                     headers={"Authorization": f"Bearer {self._token_value()}"},
                                     timeout=self.timeout)
            return response.status_code, response.json()
        except (requests.RequestException, ValueError, KeyError) as error:
            raise GatewayError("M-Pesa could not be reached") from error

    def _signed(self):
        timestamp = datetime.now(NAIROBI).strftime("%Y%m%d%H%M%S")
        return {"BusinessShortCode": self.config["SHORTCODE"],
                "Password": self._password(timestamp), "Timestamp": timestamp}

    def stk_push(self, phone, amount, reference, description) -> str:
        status, data = self._post("/mpesa/stkpush/v1/processrequest", {
            **self._signed(),
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.config["SHORTCODE"],
            "PhoneNumber": phone,
            "CallBackURL": f"{self.config['CALLBACK_BASE_URL']}/api/payments/callback/"
                           f"{self.config['CALLBACK_SECRET']}/",
            "AccountReference": reference,
            "TransactionDesc": description,
        })
        if status != 200 or str(data.get("ResponseCode")) != "0":
            logger.warning("STK push refused: %s", data.get("errorMessage") or data)
            raise GatewayError("M-Pesa did not accept the request")
        return data["CheckoutRequestID"]

    def query(self, checkout_request_id) -> QueryResult:
        status, data = self._post("/mpesa/stkpushquery/v1/query", {
            **self._signed(), "CheckoutRequestID": checkout_request_id})
        if "ResultCode" in data:
            return QueryResult(int(data["ResultCode"]), data.get("ResultDesc", ""))
        # Daraja answers with an error code while the customer has not finished.
        return QueryResult(None, data.get("errorMessage", "Still processing"))


@lru_cache
def get_gateway():
    config = settings.MPESA
    if config["CONSUMER_KEY"]:
        return DarajaGateway(config)
    logger.warning("No Daraja credentials set: M-Pesa payments are simulated")
    return SimulatedGateway()
