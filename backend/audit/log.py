from audit.models import AuditLog


def record(actor, action, resource, chama=None, **details):
    """Write one audit entry naming who did what to which record (FR-12)."""
    return AuditLog.objects.create(
        actor=actor,
        chama_id=getattr(chama, "pk", chama),
        action=action,
        resource_type=type(resource).__name__.lower(),
        resource_id=str(resource.pk),
        details={key: str(value) for key, value in details.items()},
    )
