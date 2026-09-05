from django.db.models import Q


def header_alerts(request):
    user = getattr(request, "user", None)
    empty = {"header_alerts": {"needs_call": 0, "accepted": 0, "rejected": 0, "needs_you": 0}}
    if not user or not user.is_authenticated:
        return empty
    try:
        from .models import Deal

        unseen = Deal.objects.filter(header_unseen=True)
        needs_call = (
            unseen.filter(Q(status="HUMAN_REQUIRED") | Q(human_required=True)).exclude(status="SPAM").count()
        )
        return {
            "header_alerts": {
                "needs_call": needs_call,
                "accepted": unseen.filter(status="COMPLETED").count(),
                "rejected": unseen.filter(status__in=["REJECTED", "AUTO_REJECTED"]).count(),
                "needs_you": unseen.filter(status="PENDING_CREATOR").count(),
            }
        }
    except Exception:
        return empty
