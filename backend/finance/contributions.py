from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit.log import record
from finance import ledger
from finance.models import Contribution, ContributionSchedule, FinancialAccount
from finance.schedules import outstanding_for
from rules.services import current_version

ACCOUNT_FOR_METHOD = {
    Contribution.Method.MPESA: FinancialAccount.MPESA,
    Contribution.Method.CASH: FinancialAccount.CASH,
    Contribution.Method.BANK: FinancialAccount.BANK,
}


def check_amount(membership, amount: Decimal):
    """At least the chama's minimum, unless it exactly clears what the member owes now."""
    if amount <= 0:
        raise ValidationError({"amount": "The amount must be positive"})
    rule = current_version(membership.chama, "contributions").configuration
    owed = sum((s.outstanding for s in outstanding_for(membership)), Decimal("0"))
    if amount < Decimal(rule["minimum_amount"]) and amount != owed:
        raise ValidationError(
            {"amount": f"The minimum contribution is {membership.chama.currency} "
                       f"{rule['minimum_amount']}"})


def allocate(membership, amount: Decimal):
    """Pay the oldest unpaid periods first, including future ones. Any surplus stays as savings."""
    remaining = amount
    for schedule in (ContributionSchedule.objects.select_for_update()
                     .filter(membership=membership).order_by("due_date")):
        if remaining <= 0:
            break
        share = min(schedule.outstanding, remaining)
        if share > 0:
            schedule.paid_amount += share
            schedule.save(update_fields=["paid_amount"])
            remaining -= share


@transaction.atomic
def record_contribution(membership, amount: Decimal, method, reference, recorded_by,
                        on=None) -> Contribution:
    """Post the money to the ledger, apply it to the schedule and keep the receipt."""
    chama = membership.chama
    on = on or timezone.localdate()
    try:
        with transaction.atomic():
            entry = ledger.post(chama, recorded_by, reference,
                                f"Contribution from {membership.user.full_name}", [
                                    ledger.Line(ACCOUNT_FOR_METHOD[method], debit=amount),
                                    ledger.Line(FinancialAccount.MEMBER_SAVINGS, credit=amount,
                                                membership=membership),
                                ], on=on)
            contribution = Contribution.objects.create(
                chama=chama, membership=membership, amount=amount, currency=chama.currency,
                method=method, reference_number=reference, transaction_date=on,
                journal_entry=entry, recorded_by=recorded_by)
    except IntegrityError as error:
        raise ValidationError({"reference": "That reference has already been recorded"}) from error
    allocate(membership, amount)
    record(recorded_by, "contribution.recorded", contribution, chama=chama,
           member=membership.user.full_name, amount=amount, method=method, reference=reference)
    return contribution
