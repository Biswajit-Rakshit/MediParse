from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers

_cache = {}


def paginated(serializer_class):
    """Builds (once) the response shape of StandardPagination around a serializer."""
    name = f"Paginated{serializer_class.__name__.replace('Serializer', '')}List"
    if name not in _cache:
        _cache[name] = type(
            name,
            (serializers.Serializer,),
            {
                "count": serializers.IntegerField(),
                "next": serializers.URLField(allow_null=True),
                "previous": serializers.URLField(allow_null=True),
                "results": serializer_class(many=True),
            },
        )
    return _cache[name]


PAGE_PARAMS = [
    OpenApiParameter("page", int, description="Page number (default 1)."),
    OpenApiParameter("page_size", int, description="Items per page (default 20, max 100)."),
]