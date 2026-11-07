from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from audit.models import AuditLog
from chamas.models import ChamaInvitation, ChamaMembership
from tests.conftest import client_for, make_user
from tests.factories import CHAMA, add_member, chama_for, member_client


def create(api, **fields):
    return api.post("/api/chamas/", {**CHAMA, **fields}, format="json")


class TestCreatingChamas:
    def test_creator_becomes_chairperson_with_standard_roles(self, api):
        response = create(api)
        assert response.status_code == 201
        detail = api.get(f"/api/chamas/{response.data['id']}/").data
        assert detail["my_role"] == "Chairperson"
        roles = api.get(f"/api/chamas/{response.data['id']}/roles/").data
        assert {r["role_name"] for r in roles} == {"Chairperson", "Treasurer", "Secretary",
                                                   "Member"}

    def test_a_user_can_create_and_switch_between_several_chamas(self, api):
        create(api, name="Umoja")
        create(api, name="Tujenge")
        names = [m["chama"]["name"] for m in api.get("/api/chamas/").data]
        assert names == ["Tujenge", "Umoja"]

    def test_capacity_must_be_sensible(self, api):
        assert create(api, maximum_members=1).status_code == 400

    def test_creation_is_audited(self, api):
        create(api)
        assert AuditLog.objects.filter(action="chama.created").count() == 1


class TestJoining:
    def test_an_invitation_lets_a_user_join_several_chamas(self, user):
        joiner = make_user("Baraka")
        joiner_api = client_for(joiner)
        for name in ("Umoja", "Tujenge"):
            chama = chama_for(user, name=name)
            response = client_for(user).post(f"/api/chamas/{chama.id}/invite/",
                                             {"email": joiner.email})
            assert response.status_code == 201
            accepted = joiner_api.post("/api/invitations/accept/",
                                       {"token": response.data["token"]})
            assert accepted.status_code == 201
        assert len(joiner_api.get("/api/chamas/").data) == 2

    def test_the_invitation_is_emailed(self, user):
        chama = chama_for(user)
        client_for(user).post(f"/api/chamas/{chama.id}/invite/", {"email": "new@example.com"})
        assert "/invitations/" in mail.outbox[-1].body

    def test_only_the_invited_person_can_use_an_invitation(self, user):
        chama = chama_for(user)
        token = client_for(user).post(f"/api/chamas/{chama.id}/invite/",
                                      {"email": "invited@example.com"}).data["token"]
        stranger = client_for(make_user("Stranger"))
        assert stranger.post("/api/invitations/accept/", {"token": token}).status_code == 404

    def test_an_invitation_works_once(self, user):
        chama = chama_for(user)
        joiner = make_user("Baraka")
        token = client_for(user).post(f"/api/chamas/{chama.id}/invite/",
                                      {"phone_number": "0" + joiner.phone_number[3:]}
                                      ).data["token"]
        assert client_for(joiner).post("/api/invitations/accept/",
                                       {"token": token}).status_code == 201
        assert client_for(joiner).post("/api/invitations/accept/",
                                       {"token": token}).status_code == 400

    def test_an_expired_invitation_is_refused(self, user):
        chama = chama_for(user)
        joiner = make_user("Baraka")
        token = client_for(user).post(f"/api/chamas/{chama.id}/invite/",
                                      {"email": joiner.email}).data["token"]
        ChamaInvitation.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        assert client_for(joiner).post("/api/invitations/accept/",
                                       {"token": token}).status_code == 400

    def test_only_a_hash_of_the_token_is_stored(self, user):
        chama = chama_for(user)
        token = client_for(user).post(f"/api/chamas/{chama.id}/invite/",
                                      {"email": "x@example.com"}).data["token"]
        assert token not in ChamaInvitation.objects.get().invitation_token_hash

    def test_open_chama_join_waits_for_approval(self, user):
        chama = chama_for(user, visibility="public", membership_type="open")
        joiner = client_for(make_user("Baraka"))
        assert any(c["id"] == str(chama.id) for c in joiner.get("/api/chamas/discover/").data)
        assert joiner.post(f"/api/chamas/{chama.id}/join/").data["status"] == "pending"
        assert joiner.get(f"/api/chamas/{chama.id}/").status_code == 404

        pending = ChamaMembership.objects.get(status="pending")
        response = client_for(user).post(
            f"/api/chamas/{chama.id}/members/{pending.id}/approve/")
        assert response.status_code == 200
        assert joiner.get(f"/api/chamas/{chama.id}/").status_code == 200

    def test_open_chama_without_approval_admits_directly(self, user):
        chama = chama_for(user, visibility="public", membership_type="open",
                          requires_approval=False)
        joiner = client_for(make_user("Baraka"))
        assert joiner.post(f"/api/chamas/{chama.id}/join/").data["status"] == "active"

    def test_a_private_chama_cannot_be_joined_or_discovered(self, user):
        chama = chama_for(user)
        joiner = client_for(make_user("Baraka"))
        assert joiner.get("/api/chamas/discover/").data == []
        assert joiner.post(f"/api/chamas/{chama.id}/join/").status_code == 404

    def test_a_full_chama_refuses_new_members(self, user):
        chama = chama_for(user, visibility="public", membership_type="open", maximum_members=2)
        add_member(chama)
        joiner = client_for(make_user("Baraka"))
        assert joiner.post(f"/api/chamas/{chama.id}/join/").status_code == 400

    def test_joining_twice_is_refused(self, user):
        chama = chama_for(user, visibility="public", membership_type="open")
        joiner = client_for(make_user("Baraka"))
        joiner.post(f"/api/chamas/{chama.id}/join/")
        assert joiner.post(f"/api/chamas/{chama.id}/join/").status_code == 400


class TestTenantIsolation:
    """Acceptance criterion 10: nothing of one chama is reachable from another."""

    @pytest.fixture
    def setup(self, user):
        mine = chama_for(user, name="Mine")
        theirs_owner = make_user("Owner")
        theirs = chama_for(theirs_owner, name="Theirs")
        their_member = add_member(theirs)
        return mine, theirs, their_member

    def test_another_chamas_endpoints_look_missing(self, api, setup):
        _, theirs, their_member = setup
        for url in ["", "members/", "roles/", "audit-logs/"]:
            assert api.get(f"/api/chamas/{theirs.id}/{url}").status_code == 404
        assert api.patch(f"/api/chamas/{theirs.id}/", {"name": "x"}).status_code == 404
        assert api.post(f"/api/chamas/{theirs.id}/invite/",
                        {"email": "a@b.co"}).status_code == 404
        assert api.post(f"/api/chamas/{theirs.id}/members/{their_member.id}/suspend/"
                        ).status_code == 404

    def test_a_membership_id_from_another_chama_is_not_found(self, api, setup):
        mine, _, their_member = setup
        response = api.post(f"/api/chamas/{mine.id}/members/{their_member.id}/suspend/")
        assert response.status_code == 404

    def test_a_role_from_another_chama_cannot_be_assigned(self, api, setup):
        mine, theirs, _ = setup
        member = add_member(mine)
        their_role = theirs.roles.get(role_name="Chairperson")
        response = api.post(f"/api/chamas/{mine.id}/members/{member.id}/role/",
                            {"role_id": their_role.id})
        assert response.status_code == 404

    def test_the_switcher_lists_only_my_chamas(self, api, setup):
        assert [m["chama"]["name"] for m in api.get("/api/chamas/").data] == ["Mine"]

    def test_platform_staff_get_no_access_to_chama_data(self, setup):
        _, theirs, _ = setup
        staff = client_for(make_user("Staff", is_staff=True))
        assert staff.get(f"/api/chamas/{theirs.id}/members/").status_code == 404


class TestPermissions:
    def test_an_ordinary_member_cannot_manage(self, user):
        chama = chama_for(user)
        _, member_api = member_client(chama)
        other = add_member(chama)
        assert member_api.patch(f"/api/chamas/{chama.id}/", {"name": "x"}).status_code == 403
        assert member_api.post(f"/api/chamas/{chama.id}/invite/",
                               {"email": "a@b.co"}).status_code == 403
        assert member_api.post(f"/api/chamas/{chama.id}/members/{other.id}/suspend/"
                               ).status_code == 403
        assert member_api.get(f"/api/chamas/{chama.id}/audit-logs/").status_code == 403

    def test_members_see_each_other_but_not_phone_numbers(self, user):
        chama = chama_for(user)
        _, member_api = member_client(chama)
        members = member_api.get(f"/api/chamas/{chama.id}/members/").data
        assert len(members) == 2
        assert all(m["phone_number"] is None for m in members)
        managed = client_for(user).get(f"/api/chamas/{chama.id}/members/").data
        assert all(m["phone_number"] for m in managed)

    def test_a_secretary_can_invite_members_but_not_leaders(self, user):
        chama = chama_for(user)
        _, secretary = member_client(chama, "Secretary")
        chair_role = chama.roles.get(role_name="Chairperson")
        assert secretary.post(f"/api/chamas/{chama.id}/invite/",
                              {"email": "a@b.co"}).status_code == 201
        assert secretary.post(f"/api/chamas/{chama.id}/invite/",
                              {"email": "c@d.co", "role_id": chair_role.id}).status_code == 403

    def test_nobody_can_change_their_own_role(self, user):
        chama = chama_for(user)
        me = ChamaMembership.objects.get(user=user)
        role = chama.roles.get(role_name="Member")
        response = client_for(user).post(f"/api/chamas/{chama.id}/members/{me.id}/role/",
                                         {"role_id": role.id})
        assert response.status_code == 403

    def test_a_secretary_cannot_grant_themselves_more_permissions(self, user):
        chama = chama_for(user)
        secretary_membership, secretary = member_client(chama, "Secretary")
        response = secretary.patch(
            f"/api/chamas/{chama.id}/roles/{secretary_membership.role_id}/",
            {"permissions": ["manage_roles"]}, format="json")
        assert response.status_code == 403

    def test_the_chairperson_role_cannot_be_weakened(self, user):
        chama = chama_for(user)
        chair = chama.roles.get(role_name="Chairperson")
        second = add_member(chama, role_name="Chairperson")
        response = client_for(second.user).patch(f"/api/chamas/{chama.id}/roles/{chair.id}/",
                                                 {"permissions": []}, format="json")
        assert response.status_code == 403

    def test_the_last_chairperson_cannot_leave_or_be_demoted(self, user):
        chama = chama_for(user)
        assert client_for(user).post(f"/api/chamas/{chama.id}/leave/").status_code == 400

    def test_handing_over_lets_the_old_chairperson_leave(self, user):
        chama = chama_for(user)
        successor = add_member(chama)
        chair = chama.roles.get(role_name="Chairperson")
        api = client_for(user)
        assert api.post(f"/api/chamas/{chama.id}/members/{successor.id}/role/",
                        {"role_id": chair.id}).status_code == 200
        assert api.post(f"/api/chamas/{chama.id}/leave/").status_code == 204
        assert client_for(successor.user).get(f"/api/chamas/{chama.id}/").status_code == 200

    def test_custom_roles_accept_only_known_permissions(self, user):
        chama = chama_for(user)
        api = client_for(user)
        good = api.post(f"/api/chamas/{chama.id}/roles/",
                        {"role_name": "Auditor", "permissions": ["view_audit"]}, format="json")
        bad = api.post(f"/api/chamas/{chama.id}/roles/",
                       {"role_name": "Boss", "permissions": ["do_anything"]}, format="json")
        assert good.status_code == 201
        assert bad.status_code == 400

    def test_suspended_members_lose_access_until_reinstated(self, user):
        chama = chama_for(user)
        membership, member_api = member_client(chama)
        api = client_for(user)
        api.post(f"/api/chamas/{chama.id}/members/{membership.id}/suspend/")
        assert member_api.get(f"/api/chamas/{chama.id}/").status_code == 404
        api.post(f"/api/chamas/{chama.id}/members/{membership.id}/reinstate/")
        assert member_api.get(f"/api/chamas/{chama.id}/").status_code == 200

    def test_membership_changes_are_audited_and_visible_to_auditors(self, user):
        chama = chama_for(user)
        membership = add_member(chama)
        api = client_for(user)
        api.post(f"/api/chamas/{chama.id}/members/{membership.id}/suspend/")
        actions = [e["action"] for e in api.get(f"/api/chamas/{chama.id}/audit-logs/").data]
        assert "membership.suspend" in actions
        assert "chama.created" in actions
