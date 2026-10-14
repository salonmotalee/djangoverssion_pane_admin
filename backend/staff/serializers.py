from rest_framework import serializers

from portal.serializers import PortalProfileSerializer

from .permissions import authorized_halls


def account_payload(account):
    return {
        "id": account.pk,
        "supervisor_id": account.supervisor_id,
        "phone": account.phone,
        "username": account.phone,
        "enabled": account.is_active,
        "first_name": account.supervisor.first_name,
        "last_name": account.supervisor.last_name,
        "created_at": account.created_at,
        "halls": list(authorized_halls(account).values("id", "name")),
        "organization": PortalProfileSerializer(account.organization).data,
    }


class StrictSerializer(serializers.Serializer):
    def validate(self, attrs):
        extras = set(self.initial_data) - set(self.fields)
        if extras:
            raise serializers.ValidationError({key: "این فیلد قابل تغییر نیست." for key in extras})
        return attrs


class ProvisionSerializer(StrictSerializer):
    enabled = serializers.BooleanField()
    password = serializers.CharField(required=False, max_length=4096, trim_whitespace=False, write_only=True)


class SupervisorCredentials(StrictSerializer):
    username = serializers.CharField(max_length=32)
    password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


class PasswordChangeSerializer(StrictSerializer):
    current_password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)
