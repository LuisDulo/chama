from datetime import date
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.log import record
from chamas import permissions
from chamas.access import membership_for
from chamas.models import ChamaMembership
from finance import contributions, ledger, schedules
from finance.models import Contribution, ContributionSchedule


def money(value):
    return f"{value:.2f}"


def schedule_row(schedule, today):
    return {"id": schedule.id, "member": schedule.membership.user.full_name,
            "membership_id": schedule.membership_id, "due_date": schedule.due_date,
            "expected": money(schedule.expected_amount), "paid": money(schedule.paid_amount),
            "outstanding": money(schedule.outstanding), "status": schedule.status_on(today),
            "late_penalty": money(schedule.late_penalty),
            "rule_version": schedule.rule_version.version_number}


def contribution_row(contribution):
    return {"id": contribution.id, "member": contribution.membership.user.full_name,
            "amount": money(contribution.amount), "currency": contribution.currency,
            "method": contribution.method, "reference": contribution.reference_number,
            "date": contribution.transaction_date}


class ScheduleView(APIView):
    """A member sees their own schedule. Finance officers see everyone's."""

    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        rows = ContributionSchedule.objects.filter(chama=membership.chama).select_related(
            "membership__user", "rule_version")
        if request.query_params.get("scope") == "all":
            membership_for(request.user, chama_id, permissions.VIEW_FINANCES)
        else:
            rows = rows.filter(membership=membership)
        today = timezone.localdate()
        return Response([schedule_row(s, today) for s in rows.order_by("due_date", "id")])


class GenerateScheduleView(APIView):
    def post(self, request, chama_id):
        membership = membership_for(request.user, chama_id, permissions.RECORD_CONTRIBUTIONS)
        through = request.data.get("through")
        try:
            created = schedules.generate(membership.chama,
                                         date.fromisoformat(through) if through else None)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        record(request.user, "schedule.generated", membership.chama, chama=membership.chama,
               created=created)
        return Response({"created": created})


class CashContributionSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.ChoiceField([Contribution.Method.CASH, Contribution.Method.BANK])
    reference = serializers.CharField(max_length=40)
    date = serializers.DateField(required=False)


class ContributionView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        rows = Contribution.objects.filter(chama=membership.chama).select_related(
            "membership__user")
        if request.query_params.get("scope") == "all":
            membership_for(request.user, chama_id, permissions.VIEW_FINANCES)
        else:
            rows = rows.filter(membership=membership)
        return Response([contribution_row(c) for c in rows[:500]])

    def post(self, request, chama_id):
        """A finance officer records cash or a bank deposit that was received in person."""
        officer = membership_for(request.user, chama_id, permissions.RECORD_CONTRIBUTIONS)
        data = CashContributionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        member = get_object_or_404(ChamaMembership, pk=data.validated_data["membership_id"],
                                   chama=officer.chama, status=ChamaMembership.Status.ACTIVE)
        if data.validated_data.get("date", timezone.localdate()) > timezone.localdate():
            return Response({"date": "A payment cannot be recorded in the future"}, status=400)
        contributions.check_amount(member, data.validated_data["amount"])
        contribution = contributions.record_contribution(
            member, data.validated_data["amount"], data.validated_data["method"],
            data.validated_data["reference"], request.user, data.validated_data.get("date"))
        return Response(contribution_row(contribution), status=status.HTTP_201_CREATED)


class OverviewView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        chama = membership.chama
        today = timezone.localdate()
        owed = schedules.outstanding_for(membership, today)
        upcoming = membership.schedules.filter(due_date__gt=today).order_by("due_date").first()
        result = {
            "chama": chama.name, "currency": chama.currency,
            "my_savings": money(ledger.member_savings(membership)),
            "my_outstanding": money(sum((s.outstanding for s in owed), Decimal("0"))),
            "my_overdue_periods": sum(1 for s in owed if s.status_on(today) == "overdue"),
            "next_due": ({"date": upcoming.due_date, "amount": money(upcoming.outstanding)}
                         if upcoming and upcoming.outstanding > 0 else None),
        }
        if membership.role.allows(permissions.VIEW_FINANCES):
            members = chama.memberships.filter(status=ChamaMembership.Status.ACTIVE)
            result["group"] = {
                "members": members.count(),
                "accounts": [{**row, "debit": money(row["debit"]), "credit": money(row["credit"]),
                              "balance": money(row["balance"])}
                             for row in ledger.trial_balance(chama)],
                "members_overdue": sum(
                    1 for m in members
                    if any(s.status_on(today) == "overdue" for s in schedules.outstanding_for(m))),
            }
        return Response(result)
