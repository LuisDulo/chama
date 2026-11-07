"""Expected contributions, generated from the rule version in force on each due date."""

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from chamas.models import ChamaMembership
from finance.models import ContributionSchedule
from rules.models import RuleVersion
from rules.schemas import WEEKDAYS


def _versions(chama):
    return list(
        RuleVersion.objects.filter(rule__chama=chama, rule__category="contributions",
                                   status=RuleVersion.Status.APPROVED)
        .order_by("effective_from", "version_number")
    )


def _in_force(versions, day):
    current = None
    for version in versions:
        if version.effective_from <= day:
            current = version
    return current


def _is_due(configuration, day: date) -> bool:
    if configuration["frequency"] == "monthly":
        return day.day == configuration["due_day"]
    return WEEKDAYS[day.weekday()] == configuration["due_weekday"]


def due_dates(chama, start: date, end: date):
    """(day, version) for every due date in the range, using the rule in force that day."""
    versions = _versions(chama)
    day = start
    while day <= end:
        version = _in_force(versions, day)
        if version and _is_due(version.configuration, day):
            yield day, version
        day += timedelta(days=1)


def end_of_next_month(today: date) -> date:
    first_of_next = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    return (first_of_next + timedelta(days=32)).replace(day=1) - timedelta(days=1)


@transaction.atomic
def generate(chama, through: date | None = None) -> int:
    """Create missing schedule rows up to a date. Safe to run again: returns how many are new."""
    through = through or end_of_next_month(timezone.localdate())
    if through > timezone.localdate() + timedelta(days=400):
        raise ValueError("Schedules can be generated at most about a year ahead")
    created = 0
    members = chama.memberships.filter(status=ChamaMembership.Status.ACTIVE)
    for membership in members:
        start = timezone.localtime(membership.joined_at).date()
        for day, version in due_dates(chama, start, through):
            config = version.configuration
            _, new = ContributionSchedule.objects.get_or_create(
                membership=membership, due_date=day,
                defaults={"chama": chama, "rule_version": version,
                          "expected_amount": Decimal(config["minimum_amount"]),
                          "grace_period_days": config["grace_period_days"],
                          "late_penalty": Decimal(config["late_penalty"])})
            created += new
    return created


def outstanding_for(membership, today=None):
    """Unpaid amounts that are already due, oldest first."""
    today = today or timezone.localdate()
    return [s for s in membership.schedules.filter(due_date__lte=today).order_by("due_date")
            if s.outstanding > 0]
