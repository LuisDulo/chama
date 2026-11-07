from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.log import record
from chamas import permissions
from chamas.access import active_holders
from chamas.models import Chama, ChamaMembership, ChamaRole


@transaction.atomic
def create_chama(user, data, rules=None) -> Chama:
    """Creates the chama, its standard roles and first rules, with the creator as chairperson.

    `rules` holds the wizard's financial and membership settings by category. Anything not
    given starts from the platform defaults, and every value can be changed later by a vote
    of the chama's own approvers.
    """
    from rules.services import install_defaults

    chama = Chama.objects.create(created_by=user, **data)
    roles = {
        name: ChamaRole.objects.create(chama=chama, role_name=name, description=description,
                                       permissions=list(perms), is_system_role=True)
        for name, (description, perms) in permissions.SYSTEM_ROLES.items()
    }
    membership = ChamaMembership(chama=chama, user=user, role=roles[permissions.CHAIRPERSON])
    membership.activate(user)
    membership.save()
    install_defaults(chama, user, rules)
    record(user, "chama.created", chama, chama=chama, name=chama.name)
    return chama


def member_role(chama) -> ChamaRole:
    return chama.roles.get(role_name="Member", is_system_role=True)


def check_capacity(chama):
    current = chama.memberships.filter(status__in=ChamaMembership.CURRENT).count()
    if current >= chama.maximum_members:
        raise ValidationError("This chama is full")


def keep_a_manager(chama, leaving: ChamaMembership):
    """A chama must never be left without someone who can manage roles."""
    managers = active_holders(chama, permissions.MANAGE_ROLES)
    if [m.pk for m in managers] == [leaving.pk]:
        raise ValidationError("Give another member the Chairperson role first")


@transaction.atomic
def request_to_join(user, chama) -> ChamaMembership:
    is_open = chama.membership_type == Chama.Membership.OPEN
    if chama.visibility != Chama.Visibility.PUBLIC or not is_open:
        raise PermissionDenied("This chama joins by invitation only")
    if chama.memberships.filter(user=user, status__in=ChamaMembership.CURRENT).exists():
        raise ValidationError("You are already a member or have asked to join")
    check_capacity(chama)
    membership = ChamaMembership(chama=chama, user=user, role=member_role(chama))
    if not chama.requires_approval:
        membership.activate(None)
    membership.save()
    record(user, "membership.requested", membership, chama=chama, status=membership.status)
    return membership


def change_status(actor, membership: ChamaMembership, action: str) -> ChamaMembership:
    status = ChamaMembership.Status
    allowed = {
        "approve": ([status.PENDING], status.ACTIVE),
        "reject": ([status.PENDING], status.REJECTED),
        "suspend": ([status.ACTIVE], status.SUSPENDED),
        "reinstate": ([status.SUSPENDED], status.ACTIVE),
        "remove": ([status.ACTIVE, status.SUSPENDED], status.EXITED),
    }
    if action not in allowed:
        raise ValidationError("Unknown action")
    sources, target = allowed[action]
    if membership.status not in sources:
        raise ValidationError(f"Cannot {action} a member who is {membership.status}")
    if membership.user_id == actor.pk:
        raise PermissionDenied("You cannot change your own membership this way")
    if target != status.ACTIVE:
        keep_a_manager(membership.chama, membership)
    if action == "approve":
        check_capacity_excluding(membership)
        membership.activate(actor)
    else:
        membership.status = target
        if target == status.EXITED:
            membership.exit_date = timezone.now()
    membership.save()
    record(actor, f"membership.{action}", membership, chama=membership.chama,
           member=membership.user.full_name)
    return membership


def check_capacity_excluding(membership):
    active = membership.chama.memberships.filter(status=ChamaMembership.Status.ACTIVE).count()
    if active >= membership.chama.maximum_members:
        raise ValidationError("This chama is full")


def assign_role(actor, membership: ChamaMembership, role: ChamaRole) -> ChamaMembership:
    if membership.user_id == actor.pk:
        raise PermissionDenied("You cannot change your own role")
    if role.chama_id != membership.chama_id:
        raise ValidationError("That role belongs to another chama")
    if not role.allows(permissions.MANAGE_ROLES):
        keep_a_manager(membership.chama, membership)
    previous = membership.role.role_name
    membership.role = role
    membership.save(update_fields=["role"])
    record(actor, "membership.role_changed", membership, chama=membership.chama,
           member=membership.user.full_name, previous=previous, role=role.role_name)
    return membership


def leave(user, membership: ChamaMembership):
    keep_a_manager(membership.chama, membership)
    membership.status = ChamaMembership.Status.EXITED
    membership.exit_date = timezone.now()
    membership.save()
    record(user, "membership.left", membership, chama=membership.chama)
