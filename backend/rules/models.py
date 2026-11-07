from django.conf import settings
from django.db import models
from django.db.models import Q


class ChamaRule(models.Model):
    """One rule category of one chama. Its content lives in versions."""

    chama = models.ForeignKey("chamas.Chama", on_delete=models.PROTECT, related_name="rules")
    category = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chama", "category"], name="one_rule_per_category")
        ]


class RuleVersion(models.Model):
    """A proposed or approved configuration. Approved versions are never edited (BR-05)."""

    class Status(models.TextChoices):
        PROPOSED = "proposed"
        APPROVED = "approved"
        REJECTED = "rejected"
        WITHDRAWN = "withdrawn"

    rule = models.ForeignKey(ChamaRule, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    configuration = models.JSONField()
    previous_configuration = models.JSONField(null=True, blank=True)
    reason = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    effective_from = models.DateField()
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(fields=["rule", "version_number"], name="unique_version"),
            # Two approved versions cannot both start on the same day, or "which rule
            # applied that day" would have two answers.
            models.UniqueConstraint(fields=["rule", "effective_from"],
                                    condition=Q(status="approved"),
                                    name="one_approved_version_per_day"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk,
                                                 status=self.Status.APPROVED).exists():
            raise PermissionError("An approved rule version cannot be changed")
        super().save(*args, **kwargs)
