from chamas.models import ChamaMembership
from chamas.services import create_chama
from tests.conftest import client_for, make_user

CHAMA = {"name": "Umoja Savings", "description": "Monthly savings", "visibility": "private",
         "membership_type": "invitation", "maximum_members": 20}


def chama_for(owner, **fields):
    return create_chama(owner, {**CHAMA, **fields})


def add_member(chama, user=None, role_name="Member"):
    user = user or make_user("Member")
    membership = ChamaMembership(chama=chama, user=user, role=chama.roles.get(role_name=role_name))
    membership.activate(chama.created_by)
    membership.save()
    return membership


def member_client(chama, role_name="Member"):
    membership = add_member(chama, role_name=role_name)
    return membership, client_for(membership.user)
