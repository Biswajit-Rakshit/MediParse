from rest_framework import serializers
from django.contrib.auth import authenticate
from apps.accounts.models import User, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "plan_tier"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    organization_name = serializers.CharField(write_only=True)
    organization_slug = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "role", "organization_name", "organization_slug"]

    def create(self, validated_data):
        org_name = validated_data.pop("organization_name")
        org_slug = validated_data.pop("organization_slug")

        organization, _ = Organization.objects.get_or_create(
            slug=org_slug,
            defaults={"name": org_name}
        )

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data.get("role", "viewer"),
            organization=organization,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        data["user"] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "role", "organization", "created_at"]