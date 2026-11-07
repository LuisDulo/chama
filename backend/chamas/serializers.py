from rest_framework import serializers

from chamas import permissions
from chamas.models import Chama, ChamaMembership, ChamaRole


class ChamaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chama
        fields = ["id", "name", "description", "category", "currency", "location", "visibility",
                  "membership_type", "requires_approval", "maximum_members", "status",
                  "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def validate_maximum_members(self, value):
        if not 2 <= value <= 1000:
            raise serializers.ValidationError("A chama can have 2 to 1000 members")
        if self.instance and value < self.instance.memberships.filter(
            status__in=ChamaMembership.CURRENT
        ).count():
            raise serializers.ValidationError("The chama already has more members than that")
        return value


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChamaRole
        fields = ["id", "role_name", "description", "permissions", "is_system_role"]
        read_only_fields = ["id", "is_system_role"]

    def validate_permissions(self, value):
        unknown = set(value) - set(permissions.ALL)
        if unknown:
            raise serializers.ValidationError(f"Unknown permissions: {sorted(unknown)}")
        return sorted(set(value))


class MembershipSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name")
    role = serializers.CharField(source="role.role_name")
    role_id = serializers.IntegerField(source="role.id")
    phone_number = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = ChamaMembership
        fields = ["id", "name", "phone_number", "role", "role_id", "status", "joined_at", "is_me"]

    def get_is_me(self, membership):
        return membership.user_id == getattr(self.context.get("user"), "pk", None)

    def get_phone_number(self, membership):
        # Contact details are shown only to people who manage membership.
        if self.context.get("show_contacts"):
            return membership.user.phone_number
        return None


class MyChamaSerializer(serializers.ModelSerializer):
    """A chama as seen in the switcher, with the caller's own role."""

    role = serializers.CharField(source="role.role_name")
    permissions = serializers.ListField(source="role.permissions")
    chama = ChamaSerializer()

    class Meta:
        model = ChamaMembership
        fields = ["id", "chama", "role", "permissions", "status", "joined_at"]


class InvitationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    role_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone_number"):
            raise serializers.ValidationError("Give an email address or a phone number")
        return attrs
