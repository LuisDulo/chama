import uuid

from django.conf import settings
from django.db import models


class AppendOnly(models.Model):
    """A record that can be written once. Corrections are new records, never edits (BR-07)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError(f"{type(self).__name__} records cannot be changed")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError(f"{type(self).__name__} records cannot be deleted")


class AuditLog(AppendOnly):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chama_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
                              related_name="+")
    action = models.CharField(max_length=60)
    resource_type = models.CharField(max_length=40)
    resource_id = models.CharField(max_length=64)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
