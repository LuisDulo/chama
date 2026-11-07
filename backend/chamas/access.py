"""The one place that decides whether a user may see or act on a chama (BR-03, section 5.3)."""

from rest_framework.exceptions import NotFound, PermissionDenied

from chamas.models import Chama, ChamaMembership


def membership_for(user, chama_id, permission=None) -> ChamaMembership:
    """The caller's active membership of the chama.

    A chama the user does not belong to is reported as missing, not forbidden, so its
    existence is not revealed. A missing permission inside the user's own chama is forbidden.
    """
    membership = (
        ChamaMembership.objects.select_related("chama", "role", "user")
        .filter(chama_id=chama_id, user=user, status=ChamaMembership.Status.ACTIVE,
                chama__status=Chama.Status.ACTIVE)
        .first()
    )
    if membership is None:
        raise NotFound("Chama not found")
    if permission and not membership.role.allows(permission):
        raise PermissionDenied("Your role in this chama does not allow that")
    return membership


def active_holders(chama, permission):
    return [
        m for m in chama.memberships.select_related("role").filter(
            status=ChamaMembership.Status.ACTIVE)
        if m.role.allows(permission)
    ]
