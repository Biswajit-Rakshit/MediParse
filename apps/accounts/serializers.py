from rest_framework import serializers
from django.contrib.auth import authenticate, password_validation
from django.db import IntegrityError, transaction

from apps.accounts.models import User, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "plan_tier"]


class RegisterSerializer(serializers.ModelSerializer):
    """Public sign-up: creates a NEW organization; the registrant becomes its admin."""
    password = serializers.CharField(write_only=True, min_length=8)
    organization_name = serializers.CharField(write_only=True)
    organization_slug = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "role", "organization_name", "organization_slug"]

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def validate_organization_slug(self, value):
        value = value.lower()
        if Organization.objects.filter(slug=value).exists():
            raise serializers.ValidationError("This organization slug is already taken.")
        return value
    
    def create(self, validated_data):
        try:
            with transaction.atomic():
                organization = Organization.objects.create(
                    name=validated_data["organization_name"],
                    slug=validated_data["organization_slug"],
                )
                return User.objects.create_user(
                    email=validated_data["email"],
                    password=validated_data["password"],
                    role="admin",
                    organization=organization,
                )
        except IntegrityError:
            # two requests raced for the same slug or email
            raise serializers.ValidationError(
                "That organization slug or email is already registered."
            )

class AdminCreateUserSerializer(serializers.ModelSerializer):
    """Used by an org admin to add a user to THEIR OWN organization."""
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "role"]

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        request = self.context["request"]
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data.get("role", "viewer"),
            organization=request.user.organization,
        )

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        data["user"] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "role", "organization", "created_at"]