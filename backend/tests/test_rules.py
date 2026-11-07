from datetime import timedelta

import pytest
from django.utils import timezone

from rules.models import RuleVersion
from rules.services import version_on
from tests.conftest import client_for
from tests.factories import CHAMA, add_member, chama_for, member_client

WEEKLY = {"amount_type": "flexible", "minimum_amount": "200", "maximum_amount": "5000",
          "frequency": "weekly", "due_weekday": "friday", "grace_period_days": 1,
          "late_penalty": "50"}
MONTHLY_2000 = {"amount_type": "fixed", "minimum_amount": "2000", "maximum_amount": "2000",
                "frequency": "monthly", "due_day": 10, "grace_period_days": 5,
                "late_penalty": "200"}


def today():
    return timezone.localdate()


def contributions(api, chama_id):
    rules = api.get(f"/api/chamas/{chama_id}/rules/").data
    return next(r for r in rules if r["category"] == "contributions")


def propose(api, chama, config=MONTHLY_2000, days_ahead=7):
    return api.post(f"/api/chamas/{chama.id}/rules/", {
        "category": "contributions", "configuration": config,
        "effective_from": (today() + timedelta(days=days_ahead)).isoformat(),
        "reason": "Raise savings",
    }, format="json")


class TestSetup:
    def test_each_chama_starts_with_its_own_wizard_settings(self, api):
        weekly = api.post("/api/chamas/", {**CHAMA, "name": "Weekly",
                                           "rules": {"contributions": WEEKLY}}, format="json")
        monthly = api.post("/api/chamas/", {**CHAMA, "name": "Monthly",
                                            "rules": {"contributions": MONTHLY_2000}},
                           format="json")
        first = contributions(api, weekly.data["id"])["current"]["configuration"]
        second = contributions(api, monthly.data["id"])["current"]["configuration"]
        assert (first["frequency"], first["minimum_amount"]) == ("weekly", "200.00")
        assert (second["frequency"], second["minimum_amount"]) == ("monthly", "2000.00")

    def test_every_category_starts_at_version_one(self, api):
        chama = chama_for(api.handler._force_user)
        rules = api.get(f"/api/chamas/{chama.id}/rules/").data
        assert {r["category"] for r in rules} == {"contributions", "membership", "withdrawals"}
        assert all(r["current"]["version_number"] == 1 for r in rules)

    @pytest.mark.parametrize("bad", [
        {**MONTHLY_2000, "maximum_amount": "100"},
        {**MONTHLY_2000, "frequency": "daily"},
        {**WEEKLY, "due_weekday": None},
        {**MONTHLY_2000, "amount_type": "fixed", "maximum_amount": "3000"},
    ])
    def test_inconsistent_settings_are_refused_and_nothing_is_created(self, api, bad):
        response = api.post("/api/chamas/", {**CHAMA, "rules": {"contributions": bad}},
                            format="json")
        assert response.status_code == 400
        assert api.get("/api/chamas/").data == []


class TestChanges:
    def test_a_proposal_does_not_change_the_rule_in_force(self, user):
        chama = chama_for(user)
        api = client_for(user)
        assert propose(api, chama).status_code == 201
        rule = contributions(api, chama.id)
        assert rule["current"]["configuration"]["minimum_amount"] == "1000.00"
        assert rule["pending"]["version_number"] == 2

    def test_approval_takes_effect_on_its_date_and_history_is_kept(self, user):
        chama = chama_for(user)
        treasurer, treasurer_api = member_client(chama, "Treasurer")
        version_id = propose(client_for(user), chama).data["id"]
        response = treasurer_api.post(f"/api/chamas/{chama.id}/rules/{version_id}/approve/")
        assert response.status_code == 200

        assert version_on(chama, "contributions", today()).version_number == 1
        later = version_on(chama, "contributions", today() + timedelta(days=7))
        assert later.version_number == 2
        assert later.previous_configuration["minimum_amount"] == "1000.00"

        history = client_for(user).get(f"/api/chamas/{chama.id}/rules/history/").data
        numbers = [v["version_number"] for v in history if v["category"] == "contributions"]
        assert numbers == [2, 1]

    def test_the_proposer_cannot_approve_when_someone_else_can(self, user):
        chama = chama_for(user)
        add_member(chama, role_name="Treasurer")
        version_id = propose(client_for(user), chama).data["id"]
        response = client_for(user).post(f"/api/chamas/{chama.id}/rules/{version_id}/approve/")
        assert response.status_code == 403

    def test_a_sole_approver_can_approve_their_own_change(self, user):
        chama = chama_for(user)
        version_id = propose(client_for(user), chama).data["id"]
        response = client_for(user).post(f"/api/chamas/{chama.id}/rules/{version_id}/approve/")
        assert response.status_code == 200

    def test_ordinary_members_can_read_but_not_propose_or_approve(self, user):
        chama = chama_for(user)
        _, member_api = member_client(chama)
        assert member_api.get(f"/api/chamas/{chama.id}/rules/").status_code == 200
        assert propose(member_api, chama).status_code == 403
        version_id = propose(client_for(user), chama).data["id"]
        assert member_api.post(f"/api/chamas/{chama.id}/rules/{version_id}/approve/"
                               ).status_code == 403

    def test_only_one_change_can_wait_at_a_time(self, user):
        chama = chama_for(user)
        propose(client_for(user), chama)
        assert propose(client_for(user), chama, days_ahead=14).status_code == 400

    def test_a_change_cannot_start_in_the_past(self, user):
        chama = chama_for(user)
        assert propose(client_for(user), chama, days_ahead=-1).status_code == 400

    def test_a_rejected_change_never_applies(self, user):
        chama = chama_for(user)
        _, treasurer_api = member_client(chama, "Treasurer")
        version_id = propose(client_for(user), chama).data["id"]
        treasurer_api.post(f"/api/chamas/{chama.id}/rules/{version_id}/reject/")
        later = version_on(chama, "contributions", today() + timedelta(days=30))
        assert later.version_number == 1

    def test_a_decided_change_cannot_be_decided_again(self, user):
        chama = chama_for(user)
        _, treasurer_api = member_client(chama, "Treasurer")
        version_id = propose(client_for(user), chama).data["id"]
        treasurer_api.post(f"/api/chamas/{chama.id}/rules/{version_id}/approve/")
        assert treasurer_api.post(f"/api/chamas/{chama.id}/rules/{version_id}/reject/"
                                  ).status_code == 400

    def test_an_approved_version_cannot_be_edited(self, user):
        chama = chama_for(user)
        version = RuleVersion.objects.filter(rule__chama=chama).first()
        version.configuration = {"minimum_amount": "1"}
        with pytest.raises(PermissionError):
            version.save()

    def test_rule_changes_are_audited(self, user):
        chama = chama_for(user)
        version_id = propose(client_for(user), chama).data["id"]
        client_for(user).post(f"/api/chamas/{chama.id}/rules/{version_id}/approve/")
        actions = [e["action"] for e in
                   client_for(user).get(f"/api/chamas/{chama.id}/audit-logs/").data]
        assert {"rule.proposed", "rule.approved"} <= set(actions)

    def test_a_version_of_another_chama_cannot_be_approved(self, user):
        mine = chama_for(user)
        theirs = chama_for(add_member(mine).user, name="Theirs")
        their_version = RuleVersion.objects.filter(rule__chama=theirs).first()
        response = client_for(user).post(
            f"/api/chamas/{mine.id}/rules/{their_version.id}/approve/")
        assert response.status_code == 404
