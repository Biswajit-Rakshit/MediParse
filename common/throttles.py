from rest_framework.throttling import SimpleRateThrottle


class OrganizationRateThrottle(SimpleRateThrottle):
    """Limits requests per organization, with a rate that depends on plan tier."""
    scope = "org"
    tier_rates = {
        "free": "100/min",
        "pro": "500/min",
        "enterprise": "2000/min",
    }

    def get_rate(self):
        return None  # chosen per request in allow_request

    def allow_request(self, request, view):
        user = request.user
        if not user.is_authenticated or not user.organization_id:
            return True  # anonymous traffic is handled by AnonRateThrottle

        self.rate = self.tier_rates.get(user.organization.plan_tier, self.tier_rates["free"])
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.organization_id),
        }


class UploadRateThrottle(OrganizationRateThrottle):
    """Tighter limit on uploads, since each one costs a Gemini call."""
    scope = "upload"
    tier_rates = {
        "free": "10/min",
        "pro": "10/min",
        "enterprise": "10/min",
    }