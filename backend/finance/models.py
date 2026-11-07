import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from audit.models import AppendOnly

MONEY = {"max_digits": 14, "decimal_places": 2}
ZERO = Decimal("0.00")


class FinancialAccount(models.Model):
    """A logical account in one chama's books."""

    class Type(models.TextChoices):
        ASSET = "asset"
        LIABILITY = "liability"
        INCOME = "income"
        EXPENSE = "expense"

    MPESA = "mpesa"
    CASH = "cash"
    BANK = "bank"
    MEMBER_SAVINGS = "member_savings"

    STANDARD = [
        (MPESA, "M-Pesa collections", Type.ASSET),
        (CASH, "Cash on hand", Type.ASSET),
        (BANK, "Bank account", Type.ASSET),
        (MEMBER_SAVINGS, "Member savings", Type.LIABILITY),
    ]

    chama = models.ForeignKey("chamas.Chama", on_delete=models.PROTECT, related_name="accounts")
    code = models.CharField(max_length=30)
    account_name = models.CharField(max_length=80)
    account_type = models.CharField(max_length=10, choices=Type.choices)
    currency = models.CharField(max_length=3, default="KES")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["chama", "code"], name="unique_account")]


class JournalEntry(AppendOnly):
    """One balanced posting. Mistakes are corrected by a reversing entry, never by editing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chama = models.ForeignKey("chamas.Chama", on_delete=models.PROTECT, related_name="journal")
    transaction_reference = models.CharField(max_length=60)
    description = models.CharField(max_length=200)
    transaction_date = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["transaction_date", "created_at"]


class JournalLine(AppendOnly):
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="lines")
    account = models.ForeignKey(FinancialAccount, on_delete=models.PROTECT, related_name="lines")
    membership = models.ForeignKey("chamas.ChamaMembership", null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="ledger_lines")
    debit_amount = models.DecimalField(**MONEY, default=ZERO)
    credit_amount = models.DecimalField(**MONEY, default=ZERO)

    class Meta:
        constraints = [
            # Each line moves money one way only, by a positive amount.
            models.CheckConstraint(
                condition=(Q(debit_amount__gt=0, credit_amount=0)
                           | Q(debit_amount=0, credit_amount__gt=0)),
                name="one_sided_positive_line"),
        ]


class ContributionSchedule(models.Model):
    """What a member is expected to pay, and by when.

    `rule_version` records the rule that set the amount, so a later rule change never alters
    an existing obligation (BR-06, BR-11).
    """

    chama = models.ForeignKey("chamas.Chama", on_delete=models.PROTECT, related_name="schedules")
    membership = models.ForeignKey("chamas.ChamaMembership", on_delete=models.PROTECT,
                                   related_name="schedules")
    rule_version = models.ForeignKey("rules.RuleVersion", on_delete=models.PROTECT,
                                     related_name="+")
    due_date = models.DateField()
    expected_amount = models.DecimalField(**MONEY)
    paid_amount = models.DecimalField(**MONEY, default=ZERO)
    grace_period_days = models.PositiveIntegerField(default=0)
    late_penalty = models.DecimalField(**MONEY, default=ZERO)

    class Meta:
        ordering = ["due_date"]
        constraints = [
            models.UniqueConstraint(fields=["membership", "due_date"], name="one_due_per_day"),
            models.CheckConstraint(condition=Q(paid_amount__lte=models.F("expected_amount")),
                                   name="not_overpaid"),
        ]

    @property
    def outstanding(self):
        return self.expected_amount - self.paid_amount

    def status_on(self, today):
        if self.outstanding <= 0:
            return "paid"
        if today <= self.due_date:
            return "partial" if self.paid_amount else "upcoming"
        late = (today - self.due_date).days > self.grace_period_days
        return "overdue" if late else "due"


class Contribution(AppendOnly):
    """Money a member has actually paid in. Created only once payment is confirmed."""

    class Method(models.TextChoices):
        MPESA = "mpesa"
        CASH = "cash"
        BANK = "bank"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chama = models.ForeignKey("chamas.Chama", on_delete=models.PROTECT,
                              related_name="contributions")
    membership = models.ForeignKey("chamas.ChamaMembership", on_delete=models.PROTECT,
                                   related_name="contributions")
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, default="KES")
    method = models.CharField(max_length=10, choices=Method.choices)
    reference_number = models.CharField(max_length=80)
    transaction_date = models.DateField()
    journal_entry = models.OneToOneField(JournalEntry, on_delete=models.PROTECT, related_name="+")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["chama", "reference_number"],
                                    name="one_contribution_per_reference"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="positive_contribution"),
        ]
