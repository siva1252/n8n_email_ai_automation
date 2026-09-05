from functools import wraps

from django.conf import settings
from django.http import JsonResponse


def require_internal_key(view_fn):
    @wraps(view_fn)
    def _wrapped(request, *args, **kwargs):
        expected = settings.INTERNAL_API_KEY
        if not expected:
            return JsonResponse({"error": "INTERNAL_API_KEY is not configured"}, status=500)
        provided = request.headers.get("X-Internal-API-Key") or request.META.get("HTTP_X_INTERNAL_API_KEY")
        if provided != expected:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return view_fn(request, *args, **kwargs)

    return _wrapped
