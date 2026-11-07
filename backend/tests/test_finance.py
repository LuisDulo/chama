from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from chamas.models import ChamaMembership
from finance import ledger, schedules
from finance.models import ContributionSchedule, FinancialAccount, JournalLine
from rules.models import ChamaRule, RuleVersion
from tests.conftest import client_for
from tests.factories import add_member, chama_for, member_client

D = Decimal


def joined(membership, on: date):
    ChamaMembership.objects.filter(pk=membership.pk).update(
        joined_at=timezone.make_aware(datetime(on.year, on.month, on.day)))
    membership.refresh_from_db()
    return membership


def add_version(chama, config, effective_from, number):
    """An approved rule change, created directly so dates in the past can be tested."""
    rule = ChamaRule.objects.get(chama=chama, category="contributions")
    return RuleVersion.objects.create(rule=rule, version_number=number, configuration=config,
                                      status="approved", effective_from=effective_from,
                                      proposed_by=chama.created_by, decided_by=chama.created_by)


def set_first_rule_date(chama, on):
    RuleVersion.objects.filter(rule__chama=chama).update(effective_from=on)


def monthly(amount, due_day=5):
    return {"amount_type": "fixed", "minimum_amount": amount, "maximum_amount": amount,
            "frequency": "monthly", "due_day": due_day, "grace_period_days": 3,
            "late_penalty": "100.00"}


def record_cash(api, chama, membership, amount, reference):
    return api.post(f"/api/chamas/{chama.id}/contributions/", {
        "membership_id": str(membership.id), "amount": str(amount), "method": "cash",
        "reference": reference}, format="json")


@pytest.fixture
def chama(user):
    return chama_for(user)


class TestLedger:
    def test_a_balanced_entry_is_posted(self, chama, user):
        member = add_member(chama)
        ledger.post(chama, user, "R1", "Test", [
            ledger.Line("cash", debit=D("500")),
            ledger.Line("member_savings", credit=D("500"), membership=member)])
        assert ledger.member_savings(member) == D("500")

    @pytest.mark.parametrize("lines", [
        [ledger.Line("cash", debit=D("500")), ledger.Line("member_savings", credit=D("400"))],
        [ledger.Line("cash", debit=D("500"))],
        [ledger.Line("cash", debit=D("0")), ledger.Line("member_savings", credit=D("0"))],
        [ledger.Line("nowhere", debit=D("5")), ledger.Line("cash", credit=D("5"))],
    ])
    def test_unbalanced_or_invalid_entries_are_refused(self, chama, user, lines):
        with pytest.raises(ledger.UnbalancedEntry):
            ledger.post(chama, user, "R1", "Test", lines)
        assert JournalLine.objects.count() == 0

    def test_a_line_cannot_name_a_member_of_another_chama(self, chama, user):
        other = add_member(chama_for(add_member(chama).user, name="Other"))
        with pytest.raises(ledger.UnbalancedEntry):
            ledger.post(chama, user, "R1", "Test", [
                ledger.Line("cash", debit=D("5")),
                ledger.Line("member_savings", credit=D("5"), membership=other)])

    def test_the_database_refuses_a_two_sided_line(self, chama, user):
        entry = ledger.post(chama, user, "R1", "Test", [ledger.Line("cash", debit=D("5")),
                                                        ledger.Line("bank", credit=D("5"))])
        account = FinancialAccount.objects.get(chama=chama, code="cash")
        with pytest.raises(IntegrityError), transaction.atomic():
            JournalLine.objects.create(entry=entry, account=account, debit_amount=D("1"),
                                       credit_amount=D("1"))

    def test_posted_lines_cannot_be_edited_or_deleted(self, chama, user):
        ledger.post(chama, user, "R1", "Test", [ledger.Line("cash", debit=D("5")),
                                                ledger.Line("bank", credit=D("5"))])
        line = JournalLine.objects.first()
        line.debit_amount = D("50")
        with pytest.raises(PermissionError):
            line.save()
        with pytest.raises(PermissionError):
            line.delete()


class TestSchedules:
    def test_monthly_schedule_runs_from_joining(self, chama):
        member = joined(add_member(chama), date(2026, 1, 20))
        set_first_rule_date(chama, date(2026, 1, 1))
        schedules.generate(chama, date(2026, 4, 30))
        dates = list(member.schedules.values_list("due_date", flat=True))
        assert dates == [date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)]

    def test_generating_twice_creates_nothing_new(self, chama):
        joined(add_member(chama), date(2026, 1, 1))
        set_first_rule_date(chama, date(2026, 1, 1))
        first = schedules.generate(chama, date(2026, 3, 31))
        assert first > 0
        assert schedules.generate(chama, date(2026, 3, 31)) == 0

    def test_each_due_date_uses_the_rule_in_force_that_day(self, chama):
        """BR-06: a rule change leaves earlier obligations exactly as they were."""
        member = joined(add_member(chama), date(2026, 1, 1))
        set_first_rule_date(chama, date(2026, 1, 1))
        schedules.generate(chama, date(2026, 2, 28))
        add_version(chama, monthly("2000.00", due_day=10), date(2026, 3, 1), 2)
        schedules.generate(chama, date(2026, 4, 30))

        rows = [(s.due_date, s.expected_amount, s.rule_version.version_number)
                for s in member.schedules.all()]
        assert rows == [
            (date(2026, 1, 5), D("1000.00"), 1),
            (date(2026, 2, 5), D("1000.00"), 1),
            (date(2026, 3, 10), D("2000.00"), 2),
            (date(2026, 4, 10), D("2000.00"), 2),
        ]

    def test_a_weekly_chama_gets_weekly_dates(self, user):
        weekly = {"amount_type": "flexible", "minimum_amount": "200", "maximum_amount": "5000",
                  "frequency": "weekly", "due_weekday": "friday", "grace_period_days": 1,
                  "late_penalty": "50"}
        chama = chama_for(user, name="Weekly")
        set_first_rule_date(chama, date(2025, 12, 1))
        add_version(chama, weekly, date(2026, 1, 1), 2)
        member = joined(add_member(chama), date(2026, 1, 1))
        schedules.generate(chama, date(2026, 1, 31))
        dates = list(member.schedules.values_list("due_date", flat=True))
        assert dates == [date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 16),
                         date(2026, 1, 23), date(2026, 1, 30)]
        assert all(d.weekday() == 4 for d in dates)

    def test_status_follows_the_due_date_and_grace_period(self, chama):
        member = add_member(chama)
        row = ContributionSchedule(chama=chama, membership=member, due_date=date(2026, 3, 5),
                                   expected_amount=D("1000"), grace_period_days=3)
        assert row.status_on(date(2026, 3, 1)) == "upcoming"
        assert row.status_on(date(2026, 3, 7)) == "due"
        assert row.status_on(date(2026, 3, 9)) == "overdue"
        row.paid_amount = D("400")
        assert row.status_on(date(2026, 3, 1)) == "partial"
        row.paid_amount = D("1000")
        assert row.status_on(date(2026, 3, 9)) == "paid"

    def test_generation_needs_permission(self, chama):
        _, member_api = member_client(chama)
        response = member_api.post(f"/api/chamas/{chama.id}/contribution-schedules/generate/")
        assert response.status_code == 403


class TestContributions:
    @pytest.fixture
    def member(self, chama):
        member = joined(add_member(chama), timezone.localdate() - timedelta(days=70))
        set_first_rule_date(chama, timezone.localdate() - timedelta(days=100))
        schedules.generate(chama)
        return member

    def test_cash_is_posted_to_the_ledger_and_applied_oldest_first(self, chama, user, member):
        api = client_for(user)
        owed = schedules.outstanding_for(member)
        assert len(owed) >= 2
        response = record_cash(api, chama, member, "1500.00", "CASH-1")
        assert response.status_code == 201

        member_rows = list(member.schedules.order_by("due_date"))
        assert member_rows[0].paid_amount == D("1000.00")
        assert member_rows[1].paid_amount == D("500.00")
        assert ledger.member_savings(member) == D("1500.00")
        cash = FinancialAccount.objects.get(chama=chama, code="cash")
        assert ledger.balance(cash) == D("1500.00")

    def test_the_books_always_balance(self, chama, user, member):
        api = client_for(user)
        record_cash(api, chama, member, "1000.00", "CASH-1")
        record_cash(api, chama, member, "2500.00", "CASH-2")
        rows = ledger.trial_balance(chama)
        assert sum(r["debit"] for r in rows) == sum(r["credit"] for r in rows)

    def test_a_surplus_stays_as_savings(self, chama, user, member):
        total_expected = sum(s.expected_amount for s in member.schedules.all())
        record_cash(client_for(user), chama, member, total_expected + D("700"), "CASH-1")
        assert all(s.outstanding == 0 for s in member.schedules.all())
        assert ledger.member_savings(member) == total_expected + D("700")

    def test_a_reference_can_only_be_recorded_once(self, chama, user, member):
        api = client_for(user)
        record_cash(api, chama, member, "1000.00", "CASH-1")
        assert record_cash(api, chama, member, "1000.00", "CASH-1").status_code == 400
        assert ledger.member_savings(member) == D("1000.00")

    def test_the_chamas_minimum_applies(self, chama, user, member):
        assert record_cash(client_for(user), chama, member, "300.00", "CASH-1").status_code == 400

    def test_an_amount_that_exactly_clears_arrears_is_allowed(self, chama, user, member):
        api = client_for(user)
        owed = sum(s.outstanding for s in schedules.outstanding_for(member))
        record_cash(api, chama, member, owed - D("300"), "CASH-1")
        assert record_cash(api, chama, member, "300.00", "CASH-2").status_code == 201

    def test_ordinary_members_cannot_record_cash(self, chama, member):
        _, member_api = member_client(chama)
        assert record_cash(member_api, chama, member, "1000.00", "CASH-1").status_code == 403

    def test_a_member_of_another_chama_cannot_be_credited(self, chama, user, member):
        other = add_member(chama_for(member.user, name="Other"))
        assert record_cash(client_for(user), chama, other, "1000.00", "X").status_code == 404

    def test_members_see_only_their_own_money(self, chama, user, member):
        record_cash(client_for(user), chama, member, "1000.00", "CASH-1")
        _, other_api = member_client(chama)
        assert other_api.get(f"/api/chamas/{chama.id}/contributions/").data == []
        assert other_api.get(f"/api/chamas/{chama.id}/contributions/?scope=all"
                             ).status_code == 403
        mine = client_for(member.user).get(f"/api/chamas/{chama.id}/contributions/").data
        assert [c["reference"] for c in mine] == ["CASH-1"]

    def test_overview_shows_savings_and_arrears_and_group_totals_only_to_officers(
            self, chama, user, member):
        record_cash(client_for(user), chama, member, "1000.00", "CASH-1")
        mine = client_for(member.user).get(f"/api/chamas/{chama.id}/reports/overview/").data
        assert mine["my_savings"] == "1000.00"
        assert D(mine["my_outstanding"]) > 0
        assert "group" not in mine
        officer = client_for(user).get(f"/api/chamas/{chama.id}/reports/overview/").data
        savings = next(a for a in officer["group"]["accounts"] if a["code"] == "member_savings")
        assert savings["balance"] == "1000.00"

    def test_contributions_are_audited(self, chama, user, member):
        record_cash(client_for(user), chama, member, "1000.00", "CASH-1")
        actions = [e["action"] for e in
                   client_for(user).get(f"/api/chamas/{chama.id}/audit-logs/").data]
        assert "contribution.recorded" in actions
