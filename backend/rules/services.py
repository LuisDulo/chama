from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.log import record
from chamas import permissions
from chamas.access import active_holders
from rules import schemas
from rules.models import ChamaRule, RuleVersion


def version_on(chama, category, on: date) -> RuleVersion | None:
    """The approved version in force on a date: the latest one that had started by then."""
    return (
        RuleVersion.objects.filter(rule__chama=chama, rule__category=category,
                                   status=RuleVersion.Status.APPROVED, effective_from__lte=on)
        .order_by("-effective_from", "-version_number")
        .first()
    )


def current_version(chama, category):
    return version_on(chama, category, timezone.localdate())


@transaction.atomic
def install_defaults(chama, user, overrides=None):
    """Version 1 of every category, approved from today, when a chama is created."""
    for category, default in schemas.DEFAULTS.items():
        configuration = schemas.clean(category, (overrides or {}).get(category, default))
        rule = ChamaRule.objects.create(chama=chama, category=category)
        RuleVersion.objects.create(
            rule=rule, version_number=1, configuration=configuration,
            status=RuleVersion.Status.APPROVED, effective_from=timezone.localdate(),
            proposed_by=user, decided_by=user, decided_at=timezone.now(),
            reason="Set when the chama was created")


@transaction.atomic
def propose(user, chama, category, configuration, effective_from: date, reason=""):
    if effective_from < timezone.localdate():
        raise ValidationError("A rule change cannot take effect in the past")
    cleaned = schemas.clean(category, configuration)
    rule = ChamaRule.objects.select_for_update().filter(chama=chama, category=category).first()
    if rule is None:
        raise ValidationError({"category": f"Unknown rule category {category!r}"})
    if rule.versions.filter(status=RuleVersion.Status.PROPOSED).exists():
        raise ValidationError("This rule already has a change waiting for a decision")
    latest = rule.versions.order_by("-version_number").first()
    current = current_version(chama, category)
    version = RuleVersion.objects.create(
        rule=rule, version_number=latest.version_number + 1, configuration=cleaned,
        previous_configuration=current.configuration if current else None,
        effective_from=effective_from, proposed_by=user, reason=reason)
    record(user, "rule.proposed", version, chama=chama, category=category,
           version=version.version_number, effective_from=effective_from)
    return version


@transaction.atomic
def decide(user, chama, version: RuleVersion, approve: bool):
    version = RuleVersion.objects.select_for_update().get(pk=version.pk)
    if version.status != RuleVersion.Status.PROPOSED:
        raise ValidationError("This change has already been decided")
    approvers = active_holders(chama, permissions.APPROVE_RULES)
    if version.proposed_by_id == user.pk and len(approvers) > 1:
        raise PermissionDenied("Someone else must approve a change you proposed")
    if approve and version.effective_from < timezone.localdate():
        raise ValidationError("Its effective date has passed. Propose it again.")
    version.status = RuleVersion.Status.APPROVED if approve else RuleVersion.Status.REJECTED
    version.decided_by = user
    version.decided_at = timezone.now()
    try:
        with transaction.atomic():
            version.save()
    except IntegrityError as error:
        raise ValidationError("Another approved change already starts that day") from error
    record(user, "rule.approved" if approve else "rule.rejected", version, chama=chama,
           category=version.rule.category, version=version.version_number)
    return version
