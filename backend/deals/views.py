import json

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .api_auth import require_internal_key
from .models import Deal, EmailMessage, HumanAction
from .pipeline import accept_or_reject, ingest_email, polish_creator_reply


def _json_body(request):
    try:
        return json.loads(request.body or "{}")
    except (json.JSONDecodeError, ValueError):
        return None


def _deal_queryset(request, extra_filter=None):
    qs = Deal.objects.select_related("client").order_by("-updated_at")
    if extra_filter:
        qs = qs.filter(**extra_filter)
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    priority = (request.GET.get("priority") or "").strip()
    intent = (request.GET.get("intent") or "").strip()
    if q:
        qs = qs.filter(
            Q(subject__icontains=q)
            | Q(client__email__icontains=q)
            | Q(client__brand_name__icontains=q)
            | Q(thread_id__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if intent:
        qs = qs.filter(intent=intent)
    return qs


def _paginate(request, qs, per_page=12):
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page") or 1)
    return page


STAT_LABELS = {
    "NEW": "New",
    "WAITING_FOR_CLIENT": "Waiting",
    "PENDING_CREATOR": "Needs you",
    "HUMAN_REQUIRED": "Call / human",
    "REVIEW": "Review",
    "SPAM": "Spam",
    "COMPLETED": "Accepted",
    "REJECTED": "Rejected",
    "AUTO_REJECTED": "Auto rejected",
    "NEED_INFORMATION": "Need details",
}


def _stats():
    deals = Deal.objects.all()
    counts = {key: deals.filter(status=key).count() for key in STAT_LABELS}
    counts["TOTAL"] = deals.count()
    return counts


def _stat_cards(stats):
    return [{"key": key, "label": STAT_LABELS[key], "count": stats.get(key, 0)} for key in STAT_LABELS]


STATUS_COLORS = {
    "NEW": "bg-sky-600",
    "WAITING_FOR_CLIENT": "bg-amber-500",
    "PENDING_CREATOR": "bg-violet-600",
    "HUMAN_REQUIRED": "bg-rose-600",
    "REVIEW": "bg-orange-500",
    "NEED_INFORMATION": "bg-cyan-600",
    "SPAM": "bg-slate-500",
    "COMPLETED": "bg-emerald-600",
    "REJECTED": "bg-red-600",
    "AUTO_REJECTED": "bg-slate-400",
}

PRIORITY_COLORS = {
    "HIGH": "bg-rose-100 text-rose-800",
    "MEDIUM": "bg-amber-100 text-amber-800",
    "LOW": "bg-slate-100 text-slate-700",
}


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next") or "dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "deals/login.html")


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")


@login_required
def dashboard(request):
    recent = Deal.objects.exclude(status="SPAM").select_related("client").order_by("-updated_at")[:8]
    high = Deal.objects.filter(priority="HIGH").exclude(status="SPAM").select_related("client").order_by("-updated_at")[:6]
    stats = _stats()
    return render(
        request,
        "deals/dashboard.html",
        {
            "stats": stats,
            "stat_cards": _stat_cards(stats),
            "recent": recent,
            "high": high,
            "status_colors": STATUS_COLORS,
            "priority_colors": PRIORITY_COLORS,
        },
    )


@login_required
def inbox(request):
    qs = _deal_queryset(request).exclude(status="SPAM")
    return render(
        request,
        "deals/inbox.html",
        {
            "page": _paginate(request, qs),
            "stats": _stats(),
            "status_colors": STATUS_COLORS,
            "priority_colors": PRIORITY_COLORS,
            "title": "Inbox / Leads",
            "filters": request.GET,
        },
    )


@login_required
def spam_box(request):
    qs = _deal_queryset(request, {"status": "SPAM"})
    return render(
        request,
        "deals/inbox.html",
        {
            "page": _paginate(request, qs),
            "stats": _stats(),
            "status_colors": STATUS_COLORS,
            "priority_colors": PRIORITY_COLORS,
            "title": "Spam",
            "filters": request.GET,
            "spam_view": True,
        },
    )


@login_required
def human_queue(request):
    qs = _deal_queryset(request).filter(Q(status="HUMAN_REQUIRED") | Q(human_required=True)).exclude(status="SPAM")
    return render(
        request,
        "deals/inbox.html",
        {
            "page": _paginate(request, qs),
            "stats": _stats(),
            "status_colors": STATUS_COLORS,
            "priority_colors": PRIORITY_COLORS,
            "title": "Needs a call",
            "filters": request.GET,
        },
    )


@login_required
def completed_box(request):
    qs = _deal_queryset(request).filter(status__in=["COMPLETED", "REJECTED", "AUTO_REJECTED"])
    return render(
        request,
        "deals/inbox.html",
        {
            "page": _paginate(request, qs),
            "stats": _stats(),
            "status_colors": STATUS_COLORS,
            "priority_colors": PRIORITY_COLORS,
            "title": "Completed",
            "filters": request.GET,
        },
    )


@login_required
def deal_detail(request, deal_id):
    deal = get_object_or_404(Deal.objects.select_related("client"), id=deal_id)
    return render(
        request,
        "deals/deal_detail.html",
        {
            "deal": deal,
            "email_messages": deal.emails.order_by("created_at"),
            "turns": deal.negotiation_turns.all(),
            "actions": deal.human_actions.all()[:10],
            "ai_logs": deal.ai_interactions.all()[:12],
            "can_accept_reject": deal.status in {"PENDING_CREATOR", "HUMAN_REQUIRED", "NEED_INFORMATION", "REVIEW", "NEW", "WAITING_FOR_CLIENT"},
            "status_colors": STATUS_COLORS,
            "priority_colors": PRIORITY_COLORS,
        },
    )


@login_required
@require_POST
def update_ai_reply(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    deal.ai_generated_reply = polish_creator_reply(request.POST.get("ai_reply", "").strip())
    deal.save(update_fields=["ai_generated_reply", "updated_at"])
    messages.success(request, "Reply saved")
    return redirect("deal_detail", deal_id=deal.id)


@login_required
@require_POST
def accept_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    accept_or_reject(deal, "accept", user=request.user, reason=request.POST.get("reason") or "")
    messages.success(request, "Deal accepted. Closing email queued.")
    return redirect("deal_detail", deal_id=deal.id)


@login_required
@require_POST
def reject_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    accept_or_reject(deal, "reject", user=request.user, reason=request.POST.get("reason") or "")
    messages.success(request, "Deal rejected. Closing email queued.")
    return redirect("deal_detail", deal_id=deal.id)


@login_required
@require_POST
def human_action(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    notes = request.POST.get("notes") or ""
    action = request.POST.get("action") or "note"
    HumanAction.objects.create(deal=deal, action=action, notes=notes, reason=request.POST.get("reason") or "", user=request.user)
    if action == "reopen" and deal.is_terminal:
        deal.status = "REVIEW"
        deal.human_required = True
        deal.save(update_fields=["status", "human_required", "updated_at"])
    messages.success(request, "Human action recorded")
    return redirect("deal_detail", deal_id=deal.id)


@login_required
@require_POST
def reclassify_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    if deal.status == "SPAM":
        deal.status = "REVIEW"
        deal.spam_decision = "REVIEW"
        deal.human_required = True
        deal.priority = "HIGH"
        deal.save()
        HumanAction.objects.create(deal=deal, action="reclassify_not_spam", user=request.user)
        messages.success(request, "Moved from spam to review")
    return redirect("deal_detail", deal_id=deal.id)


@csrf_exempt
@require_internal_key
@require_http_methods(["POST"])
def ingest_api(request):
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    result = ingest_email(data)
    code = result.pop("status_code", 400 if result.get("error") else 201)
    return JsonResponse(result, status=code)


@csrf_exempt
@require_internal_key
@require_http_methods(["POST"])
def save_email(request):
    return ingest_api(request)


@csrf_exempt
@require_internal_key
@require_GET
def check_deal_exists(request):
    thread_id = request.GET.get("thread_id")
    if not thread_id:
        return JsonResponse({"error": "thread_id parameter is required"}, status=400)
    return JsonResponse({"exists": Deal.objects.filter(thread_id=thread_id).exists()})


@login_required
@require_GET
def api_deal_list(request):
    qs = _deal_queryset(request)
    page = _paginate(request, qs)
    items = [
        {
            "id": d.id,
            "subject": d.subject,
            "status": d.status,
            "priority": d.priority,
            "intent": d.intent,
            "client": d.client.email,
            "brand": d.client.brand_name,
            "updated_at": d.updated_at.isoformat(),
        }
        for d in page.object_list
    ]
    return JsonResponse({"results": items, "count": page.paginator.count, "page": page.number})


@login_required
@require_GET
def api_deal_detail(request, deal_id):
    deal = get_object_or_404(Deal.objects.select_related("client"), id=deal_id)
    return JsonResponse(
        {
            "id": deal.id,
            "subject": deal.subject,
            "status": deal.status,
            "priority": deal.priority,
            "intent": deal.intent,
            "thread_id": deal.thread_id,
            "extracted": deal.extracted_json,
            "ai_reply": deal.ai_generated_reply,
            "decision": deal.last_ai_decision,
        }
    )


@csrf_exempt
@login_required
@require_POST
def api_accept(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    data = _json_body(request) or {}
    accept_or_reject(deal, "accept", user=request.user, reason=data.get("reason") or "")
    return JsonResponse({"status": deal.status, "deal_id": deal.id})


@csrf_exempt
@login_required
@require_POST
def api_reject(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    data = _json_body(request) or {}
    accept_or_reject(deal, "reject", user=request.user, reason=data.get("reason") or "")
    return JsonResponse({"status": deal.status, "deal_id": deal.id})


@csrf_exempt
@login_required
@require_POST
def api_human_action(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    data = _json_body(request) or {}
    HumanAction.objects.create(
        deal=deal,
        action=data.get("action") or "note",
        reason=data.get("reason") or "",
        notes=data.get("notes") or "",
        user=request.user,
    )
    return JsonResponse({"ok": True, "deal_id": deal.id})


@csrf_exempt
@require_internal_key
@require_POST
def api_reprocess(request):
    data = _json_body(request) or {}
    deal_id = data.get("deal_id")
    deal = get_object_or_404(Deal, id=deal_id)
    latest = deal.emails.filter(direction="INCOMING").order_by("-created_at").first()
    if not latest:
        return JsonResponse({"error": "No incoming email"}, status=400)
    payload = {
        "thread_id": deal.thread_id,
        "gmail_message_id": f"{latest.gmail_message_id or latest.id}-reprocess",
        "subject": latest.subject,
        "body": latest.body_text or latest.body,
        "from_email": latest.from_email,
        "to_email": latest.to_email,
        "direction": "INCOMING",
    }
    result = ingest_email(payload)
    code = result.pop("status_code", 201)
    return JsonResponse(result, status=code)


@csrf_exempt
@require_internal_key
@require_POST
def save_dashboard_deal(request):
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    data.setdefault("direction", "INCOMING")
    data.setdefault("thread_id", data.get("thread_id") or f"manual_{Deal.objects.count()+1}")
    result = ingest_email(data)
    code = result.pop("status_code", 201)
    return JsonResponse(result, status=code)


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "django",
            "flask_ai_url": settings.FLASK_AI_URL,
            "demo_mode": settings.DEMO_MODE,
        }
    )


def ai_health(request):
    try:
        r = requests.get(f"{settings.FLASK_AI_URL}/health", timeout=5)
        body = r.json()
    except Exception as exc:
        return JsonResponse({"status": "unreachable", "error": str(exc)}, status=503)
    return JsonResponse(body)
