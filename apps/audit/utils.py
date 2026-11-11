from apps.audit.models import AuditLog


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, action, resource_type="", resource_id="", metadata=None, user=None):
    """Record one audit entry. Pass `user` explicitly for login/register,
    where request.user isn't authenticated yet."""
    user = user or (request.user if request.user.is_authenticated else None)
    return AuditLog.objects.create(
        user=user,
        user_email=user.email if user else (metadata or {}).get("email", ""),
        organization=user.organization if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else "",
        ip_address=get_client_ip(request),
        metadata=metadata or {},
    )