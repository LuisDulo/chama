import re

import pytest
from django.core import mail

from accounts.models import User
from accounts.phone import normalise_phone
from audit.models import AuditLog
from tests.conftest import PASSWORD, make_user

REGISTRATION = {
    "first_name": "Wanjiru",
    "last_name": "Kamau",
    "email": "Wanjiru@Example.com",
    "phone_number": "0712345678",
    "password": "Savings-Group-2026",
}


def register(anonymous, **changes):
    return anonymous.post("/api/auth/register/", {**REGISTRATION, **changes}, format="json")


def login(anonymous, login_name, password=PASSWORD):
    return anonymous.post("/api/auth/login/", {"login": login_name, "password": password},
                          format="json")


def link_from_email():
    return dict(re.findall(r"(uid|token)=([^&\s]+)", mail.outbox[-1].body))


@pytest.mark.parametrize("value", ["0712345678", "254712345678", "+254 712 345 678"])
def test_phone_numbers_are_normalised(value):
    assert normalise_phone(value) == "254712345678"


@pytest.mark.parametrize("value", ["12345", "0212345678", ""])
def test_invalid_phone_numbers_are_refused(value):
    with pytest.raises(ValueError):
        normalise_phone(value)


def test_registration_creates_an_unverified_user_and_sends_a_link(anonymous):
    response = register(anonymous)
    assert response.status_code == 201
    assert response.data["email"] == "wanjiru@example.com"
    assert response.data["phone_number"] == "254712345678"
    assert response.data["email_verified"] is False
    assert "password" not in response.data
    assert len(mail.outbox) == 1


def test_duplicate_email_or_phone_is_refused(anonymous):
    register(anonymous)
    assert register(anonymous, phone_number="0798765432").status_code == 400
    assert register(anonymous, email="other@example.com").status_code == 400


def test_weak_passwords_are_refused(anonymous):
    assert register(anonymous, password="12345678").status_code == 400
    assert register(anonymous, password="wanjiru").status_code == 400


def test_login_works_with_email_or_phone(anonymous):
    user = make_user()
    for login_name in (user.email.upper(), "0" + user.phone_number[3:]):
        response = login(anonymous, login_name)
        assert response.status_code == 200
        assert {"access", "refresh"} <= set(response.data)


def test_wrong_password_and_unknown_user_get_the_same_answer(anonymous):
    user = make_user()
    wrong = login(anonymous, user.email, "nope")
    unknown = login(anonymous, "nobody@example.com")
    assert wrong.status_code == unknown.status_code == 400
    assert wrong.data == unknown.data


def test_suspended_user_cannot_log_in(anonymous):
    user = make_user(account_status=User.Status.SUSPENDED)
    assert login(anonymous, user.email).status_code == 400


def test_api_requires_a_token(anonymous):
    assert anonymous.get("/api/auth/me/").status_code == 401


def test_profile_can_be_read_and_updated_but_not_the_email(api, user):
    response = api.patch("/api/auth/me/", {"first_name": "Akinyi", "email": "x@example.com"},
                         format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "Akinyi"
    assert user.email != "x@example.com"


def test_logout_revokes_the_refresh_token(anonymous):
    user = make_user()
    tokens = login(anonymous, user.email).data
    anonymous.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert anonymous.post("/api/auth/logout/", {"refresh": tokens["refresh"]}).status_code == 204
    refreshed = anonymous.post("/api/auth/refresh/", {"refresh": tokens["refresh"]})
    assert refreshed.status_code == 401


def test_a_user_cannot_revoke_someone_elses_token(anonymous):
    owner, other = make_user(), make_user("Baraka")
    tokens = login(anonymous, owner.email).data
    other_access = login(anonymous, other.email).data["access"]
    anonymous.credentials(HTTP_AUTHORIZATION=f"Bearer {other_access}")
    assert anonymous.post("/api/auth/logout/", {"refresh": tokens["refresh"]}).status_code == 400


def test_email_verification_link_works_once(anonymous):
    register(anonymous)
    link = link_from_email()
    assert anonymous.post("/api/auth/verify/", link).status_code == 200
    assert User.objects.get(email="wanjiru@example.com").email_verified
    assert anonymous.post("/api/auth/verify/", link).status_code == 400


def test_password_reset_changes_the_password(anonymous):
    user = make_user()
    anonymous.post("/api/auth/password-reset/", {"email": user.email})
    link = link_from_email()
    response = anonymous.post("/api/auth/password-reset/confirm/",
                              {**link, "new_password": "Brand-New-Pass-77"})
    assert response.status_code == 200
    assert login(anonymous, user.email, "Brand-New-Pass-77").status_code == 200
    assert login(anonymous, user.email).status_code == 400


def test_a_verification_link_cannot_reset_a_password(anonymous):
    register(anonymous)
    link = link_from_email()
    response = anonymous.post("/api/auth/password-reset/confirm/",
                              {**link, "new_password": "Brand-New-Pass-77"})
    assert response.status_code == 400


def test_password_reset_does_not_reveal_whether_an_email_exists(anonymous):
    make_user(email="known@example.com")
    known = anonymous.post("/api/auth/password-reset/", {"email": "known@example.com"})
    unknown = anonymous.post("/api/auth/password-reset/", {"email": "unknown@example.com"})
    assert known.data == unknown.data
    assert len(mail.outbox) == 1


def test_registration_is_audited(anonymous):
    register(anonymous)
    assert AuditLog.objects.filter(action="user.registered").count() == 1


def test_audit_entries_cannot_be_changed_or_deleted(anonymous):
    register(anonymous)
    entry = AuditLog.objects.get()
    entry.action = "something.else"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
