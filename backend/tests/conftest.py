import itertools

import pytest
from rest_framework.test import APIClient

from accounts.models import User

PASSWORD = "Correct-Horse-42"
_numbers = itertools.count(10)


@pytest.fixture(autouse=True)
def database(db):
    """Every test gets a clean database."""


def make_user(first_name="Asha", **fields):
    number = next(_numbers)
    return User.objects.create_user(
        email=fields.pop("email", f"{first_name.lower()}{number}@example.com"),
        phone_number=fields.pop("phone_number", f"2547000{number:05d}"),
        password=PASSWORD,
        first_name=first_name,
        last_name=fields.pop("last_name", "Test"),
        **fields,
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def user():
    return make_user()


@pytest.fixture
def api(user):
    return client_for(user)


@pytest.fixture
def anonymous():
    return APIClient()
