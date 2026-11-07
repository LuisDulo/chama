from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.phone import normalise_phone
from audit.log import record
from audit.models import AuditLog
from chamas import permissions, services
from chamas.access import membership_for
from chamas.models import Chama, ChamaInvitation, ChamaMembership, ChamaRole, hash_token
from chamas.serializers import (
    ChamaSerializer,
    InvitationSerializer,
    MembershipSerializer,
    MyChamaSerializer,
    RoleSerializer,
)


class ChamaListView(APIView):
    def get(self, request):
        memberships = (
            ChamaMembership.objects.select_related("chama", "role")
            .filter(user=request.user, status=ChamaMembership.Status.ACTIVE,
                    chama__status=Chama.Status.ACTIVE)
            .order_by("chama__name")
        )
        return Response(MyChamaSerializer(memberships, many=True).data)

    def post(self, request):
        serializer = ChamaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        chama = services.create_chama(request.user, serializer.validated_data)
        return Response(ChamaSerializer(chama).data, status=status.HTTP_201_CREATED)


class ChamaDetailView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        return Response({**ChamaSerializer(membership.chama).data,
                         "my_role": membership.role.role_name,
                         "my_permissions": membership.role.permissions})

    def patch(self, request, chama_id):
        membership = membership_for(request.user, chama_id, permissions.MANAGE_CHAMA)
        serializer = ChamaSerializer(membership.chama, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(request.user, "chama.updated", membership.chama, chama=membership.chama,
               fields=",".join(sorted(serializer.validated_data)))
        return Response(serializer.data)


class DiscoverView(APIView):
    """Public, open chamas the caller has not joined."""

    def get(self, request):
        chamas = (
            Chama.objects.filter(visibility=Chama.Visibility.PUBLIC,
                                 membership_type=Chama.Membership.OPEN,
                                 status=Chama.Status.ACTIVE)
            .exclude(memberships__user=request.user,
                     memberships__status__in=ChamaMembership.CURRENT)
            .order_by("name")
        )
        return Response(ChamaSerializer(chamas, many=True).data)


class JoinView(APIView):
    def post(self, request, chama_id):
        chama = Chama.objects.filter(pk=chama_id, status=Chama.Status.ACTIVE).first()
        if chama is None or chama.visibility != Chama.Visibility.PUBLIC:
            raise NotFound("Chama not found")
        membership = services.request_to_join(request.user, chama)
        return Response({"status": membership.status}, status=status.HTTP_201_CREATED)


class LeaveView(APIView):
    def post(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        services.leave(request.user, membership)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberListView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        can_manage = membership.role.allows(permissions.MANAGE_MEMBERS)
        members = membership.chama.memberships.select_related("user", "role").order_by(
            "user__first_name")
        if can_manage:
            members = members.exclude(status=ChamaMembership.Status.REJECTED)
        else:
            members = members.filter(status=ChamaMembership.Status.ACTIVE)
        return Response(MembershipSerializer(members, many=True,
                                             context={"show_contacts": can_manage}).data)


def target_membership(actor_membership, membership_id):
    return get_object_or_404(ChamaMembership.objects.select_related("user", "role", "chama"),
                             pk=membership_id, chama=actor_membership.chama)


class MemberActionView(APIView):
    def post(self, request, chama_id, membership_id, action):
        actor = membership_for(request.user, chama_id, permissions.MANAGE_MEMBERS)
        updated = services.change_status(request.user, target_membership(actor, membership_id),
                                         action)
        return Response(MembershipSerializer(updated, context={"show_contacts": True}).data)


class MemberRoleView(APIView):
    def post(self, request, chama_id, membership_id):
        actor = membership_for(request.user, chama_id, permissions.MANAGE_ROLES)
        role = get_object_or_404(ChamaRole, pk=request.data.get("role_id"), chama=actor.chama)
        updated = services.assign_role(request.user, target_membership(actor, membership_id), role)
        return Response(MembershipSerializer(updated, context={"show_contacts": True}).data)


class RoleListView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id)
        return Response(RoleSerializer(membership.chama.roles.order_by("id"), many=True).data)

    def post(self, request, chama_id):
        membership = membership_for(request.user, chama_id, permissions.MANAGE_ROLES)
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                role = serializer.save(chama=membership.chama)
        except IntegrityError as error:
            raise ValidationError("A role with that name already exists") from error
        record(request.user, "role.created", role, chama=membership.chama, name=role.role_name)
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    def patch(self, request, chama_id, role_id):
        membership = membership_for(request.user, chama_id, permissions.MANAGE_ROLES)
        role = get_object_or_404(ChamaRole, pk=role_id, chama=membership.chama)
        if role.role_name == permissions.CHAIRPERSON and role.is_system_role:
            raise PermissionDenied("The Chairperson role always keeps every permission")
        if role.pk == membership.role_id:
            raise PermissionDenied("You cannot change the permissions of your own role")
        serializer = RoleSerializer(role, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(request.user, "role.updated", role, chama=membership.chama,
               permissions=",".join(role.permissions))
        return Response(serializer.data)


class InviteView(APIView):
    def post(self, request, chama_id):
        actor = membership_for(request.user, chama_id, permissions.MANAGE_MEMBERS)
        serializer = InvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phone = ""
        if data.get("phone_number"):
            try:
                phone = normalise_phone(data["phone_number"])
            except ValueError as error:
                raise ValidationError({"phone_number": str(error)}) from error
        role = (get_object_or_404(ChamaRole, pk=data["role_id"], chama=actor.chama)
                if data.get("role_id") else services.member_role(actor.chama))
        if role.allows(permissions.MANAGE_ROLES) and not actor.role.allows(
                permissions.MANAGE_ROLES):
            raise PermissionDenied("Only someone who manages roles can invite a leader")
        services.check_capacity(actor.chama)
        invitation, token = ChamaInvitation.issue(
            chama=actor.chama, invited_by=request.user, role=role,
            invited_email=data.get("email", "").lower(), invited_phone=phone)
        if invitation.invited_email:
            send_mail(f"Join {actor.chama.name} on CHAMA",
                      f"Accept here: {settings.FRONTEND_URL}/invitations/{token}",
                      None, [invitation.invited_email])
        record(request.user, "invitation.created", invitation, chama=actor.chama,
               email=invitation.invited_email, phone=invitation.invited_phone)
        # The token is shown once, so it can also be shared by message.
        return Response({"id": invitation.id, "token": token,
                         "expires_at": invitation.expires_at}, status=status.HTTP_201_CREATED)


class AcceptInvitationView(APIView):
    @transaction.atomic
    def post(self, request):
        invitation = (
            ChamaInvitation.objects.select_for_update().select_related("chama", "role")
            .filter(invitation_token_hash=hash_token(str(request.data.get("token", ""))))
            .first()
        )
        if invitation is None or not invitation.is_for(request.user):
            raise NotFound("Invitation not found")
        if invitation.status != ChamaInvitation.Status.PENDING:
            raise ValidationError("This invitation has already been used")
        if invitation.expires_at < timezone.now():
            raise ValidationError("This invitation has expired")
        chama = invitation.chama
        if chama.memberships.filter(user=request.user,
                                    status__in=ChamaMembership.CURRENT).exists():
            raise ValidationError("You are already a member of this chama")
        services.check_capacity(chama)
        membership = ChamaMembership(chama=chama, user=request.user, role=invitation.role)
        membership.activate(invitation.invited_by)
        membership.save()
        invitation.status = ChamaInvitation.Status.ACCEPTED
        invitation.save(update_fields=["status"])
        record(request.user, "invitation.accepted", membership, chama=chama)
        return Response({"chama_id": chama.id, "role": invitation.role.role_name},
                        status=status.HTTP_201_CREATED)


class AuditView(APIView):
    def get(self, request, chama_id):
        membership = membership_for(request.user, chama_id, permissions.VIEW_AUDIT)
        entries = AuditLog.objects.filter(chama_id=membership.chama_id).select_related(
            "actor")[:200]
        return Response([
            {"id": e.id, "actor": e.actor.full_name if e.actor else "System", "action": e.action,
             "resource_type": e.resource_type, "details": e.details, "created_at": e.created_at}
            for e in entries
        ])
