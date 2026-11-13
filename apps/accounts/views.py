from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.accounts.models import User
from apps.accounts.serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    AdminCreateUserSerializer,
    AuthResponseSerializer
)
from apps.audit.models import AuditLog
from apps.audit.utils import log_action

from common.schema import PAGE_PARAMS, paginated
from common.pagination import StandardPagination
from common.permissions import IsAdmin


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Create a new organization and its admin user",
        description="Creates a NEW organization. The registrant becomes its admin. "
                    "The slug must be unused; to add users to an existing organization, "
                    "an admin uses `POST /api/auth/users/`.",
        request=RegisterSerializer,
        responses={201: AuthResponseSerializer, 400: OpenApiTypes.OBJECT},
        auth=[],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            log_action(request, AuditLog.REGISTER, "user", user.id, user=user)
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "user": UserSerializer(user).data,
                    "tokens": tokens,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Log in and receive JWT tokens",
        request=LoginSerializer,
        responses={200: AuthResponseSerializer, 400: OpenApiTypes.OBJECT},
        auth=[],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            log_action(request, AuditLog.LOGIN, "user", user.id, user=user)
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "user": UserSerializer(user).data,
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK,
            )
        log_action(
            request,
            AuditLog.LOGIN_FAILED,
            metadata={"email": str(request.data.get("email", ""))[:255]},
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Auth"], summary="Current user", responses=UserSerializer)
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class OrganizationUserListCreateView(APIView):
    """Admins list and add users within their own organization."""
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="users_list",
        tags=["Auth"],
        summary="List users in your organization (admin)",
        parameters=PAGE_PARAMS,
        responses=paginated(UserSerializer),
    )
    def get(self, request):
        users = User.objects.filter(
            organization=request.user.organization
        ).select_related("organization").order_by("email")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(
            UserSerializer(page, many=True).data
        )

    @extend_schema(
        operation_id="users_create",
        tags=["Auth"],
        summary="Add a user to your organization (admin)",
        request=AdminCreateUserSerializer,
        responses={201: UserSerializer, 400: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = AdminCreateUserSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = serializer.save()
            log_action(
                request, AuditLog.USER_CREATE, "user", user.id,
                metadata={"role": user.role},
            )
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)