from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Full access — only org admins."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == "admin"
        )


class IsDoctor(BasePermission):
    """Doctors can upload documents and view extracted data."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ["admin", "doctor"]
        )


class IsNurse(BasePermission):
    """Nurses can view documents and extracted data but not upload."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ["admin", "doctor", "nurse"]
        )



