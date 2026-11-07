"""Double-entry bookkeeping for one chama."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from finance.models import ZERO, FinancialAccount, JournalEntry, JournalLine


class UnbalancedEntry(ValueError):
    pass


@dataclass
class Line:
    account_code: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    membership: object = None


def install_accounts(chama):
    for code, name, account_type in FinancialAccount.STANDARD:
        FinancialAccount.objects.create(chama=chama, code=code, account_name=name,
                                        account_type=account_type, currency=chama.currency)


@transaction.atomic
def post(chama, user, reference, description, lines: list[Line], on=None) -> JournalEntry:
    """Write a journal entry. It must balance and use only this chama's accounts."""
    debits = sum((line.debit for line in lines), ZERO)
    credits = sum((line.credit for line in lines), ZERO)
    if len(lines) < 2 or debits != credits or debits <= 0:
        raise UnbalancedEntry(f"Debits {debits} and credits {credits} must be equal and positive")
    accounts = {a.code: a for a in FinancialAccount.objects.filter(chama=chama)}
    entry = JournalEntry.objects.create(chama=chama, transaction_reference=reference,
                                        description=description, created_by=user,
                                        **({"transaction_date": on} if on else {}))
    for line in lines:
        if line.account_code not in accounts:
            raise UnbalancedEntry(f"Unknown account {line.account_code}")
        if line.membership is not None and line.membership.chama_id != chama.pk:
            raise UnbalancedEntry("A line names a member of another chama")
        JournalLine.objects.create(entry=entry, account=accounts[line.account_code],
                                   membership=line.membership, debit_amount=line.debit,
                                   credit_amount=line.credit)
    return entry


def balance(account: FinancialAccount, membership=None) -> Decimal:
    """Natural balance: debits less credits for assets, credits less debits otherwise."""
    lines = account.lines.all()
    if membership is not None:
        lines = lines.filter(membership=membership)
    totals = lines.aggregate(debit=Sum("debit_amount"), credit=Sum("credit_amount"))
    debit, credit = totals["debit"] or ZERO, totals["credit"] or ZERO
    if account.account_type in (FinancialAccount.Type.ASSET, FinancialAccount.Type.EXPENSE):
        return debit - credit
    return credit - debit


def member_savings(membership) -> Decimal:
    account = FinancialAccount.objects.get(chama=membership.chama,
                                           code=FinancialAccount.MEMBER_SAVINGS)
    return balance(account, membership)


def trial_balance(chama):
    rows = []
    for account in FinancialAccount.objects.filter(chama=chama).order_by("code"):
        totals = account.lines.aggregate(debit=Sum("debit_amount"), credit=Sum("credit_amount"))
        rows.append({"code": account.code, "name": account.account_name,
                     "type": account.account_type,
                     "debit": totals["debit"] or ZERO, "credit": totals["credit"] or ZERO,
                     "balance": balance(account)})
    return rows
