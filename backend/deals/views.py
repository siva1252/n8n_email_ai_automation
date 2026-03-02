from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.utils import timezone
from django.conf import settings
import json
import requests

from .models import Deal, EmailMessage, Client

# Configure Flask AI URL
FLASK_AI_URL = getattr(settings, "FLASK_AI_URL", "http://127.0.0.1:5000")

# 🔥 SAVE EMAIL (n8n ENTRY POINT)
@csrf_exempt
def save_email(request):
    """
    API endpoint for n8n to save emails.
    Accepts JSON only with required fields:
    - thread_id (required)
    - subject (required)
    - body (required)
    - from_email (required)
    - to_email (required)
    - direction (required: INCOMING or OUTGOING)
    - ai_generated_reply (optional) - AI generated reply text
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    # Parse JSON body
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            # Try to parse as JSON anyway
            data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({
            "error": "Invalid JSON. Please send JSON data only."
        }, status=400)

    # Validate required fields
    required_fields = ['thread_id', 'subject', 'body', 'from_email', 'to_email', 'direction']
    missing_fields = [field for field in required_fields if not data.get(field)]
    
    if missing_fields:
        return JsonResponse({
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }, status=400)

    thread_id = data.get("thread_id")
    subject = data.get("subject")
    body = data.get("body")
    from_email = data.get("from_email")
    to_email = data.get("to_email")
    direction = data.get("direction", "INCOMING").upper()

    # Validate direction
    if direction not in ['INCOMING', 'OUTGOING']:
        return JsonResponse({
            "error": "direction must be either 'INCOMING' or 'OUTGOING'"
        }, status=400)

    try:
        # 1️⃣ Get or create Client using from_email
        client, client_created = Client.objects.get_or_create(
            email=from_email,
            defaults={'brand_name': data.get('brand_name', '')}
        )

        # 2️⃣ Get or create Deal using thread_id (1 thread = 1 Deal)
        # Initial status: NEW for new deals (don't set PENDING until we reply and client replies back)
        initial_status = "NEW"
        deal, deal_created = Deal.objects.get_or_create(
            thread_id=thread_id,
            defaults={
                "client": client,
                "subject": subject,
                "status": initial_status
            }
        )

        # Update subject if it changed
        if deal.subject != subject:
            deal.subject = subject
            deal.save()

        # 3️⃣ Save AI-generated reply if provided
        ai_reply = data.get("ai_generated_reply", "")
        if ai_reply:
            deal.ai_generated_reply = ai_reply
            deal.save()

        # 4️⃣ Create EmailMessage linked to the Deal
        email_message = EmailMessage.objects.create(
            deal=deal,
            direction=direction,
            subject=subject,
            body=body,
            from_email=from_email,
            to_email=to_email,
        )

        ai_decision = None

        # 5️⃣ Autonomous AI Logic
        if direction == "INCOMING":
            # Generate reply automatically using Flask AI
            chat_history_qs = EmailMessage.objects.filter(deal=deal).order_by("created_at")
            chat_history = []
            for msg in chat_history_qs:
                role = "client" if msg.direction == "INCOMING" else "ai"
                # Exclude the very last message we just saved so we can pass it as incoming_body
                if msg.id != email_message.id:
                    chat_history.append({"role": role, "content": msg.body})
            
            # Call Flask AI
            try:
                flask_resp = requests.post(f"{FLASK_AI_URL}/generate_reply", json={
                    "body": body,
                    "chat_history": chat_history,
                    "min_price": 4000,
                    "goal_price": 5000
                }, timeout=10)
                
                if flask_resp.status_code == 200:
                    ai_data = flask_resp.json()
                    ai_reply = ai_data.get("reply", "")
                    ai_decision = ai_data.get("decision", "negotiating")
                    
                    deal.ai_generated_reply = ai_reply
                    
                    # If AI decides it's ready to close, pause for human review
                    if ai_decision == "ready_to_close":
                        deal.status = "PENDING_CREATOR"
                    
                    deal.save()
            except Exception as e:
                print(f"Error calling Flask AI: {e}")

        # If it's outgoing (N8N just sent the AI reply)
        if direction == "OUTGOING":
            # We replied with AI, so now waiting for client response
            deal.status = "WAITING_FOR_CLIENT"
            deal.our_reply_sent_at = timezone.now()
            deal.updated_at = timezone.now()
            deal.save()

        return JsonResponse({
            "status": "success",
            "deal_id": deal.id,
            "deal_created": deal_created,
            "email_message_id": email_message.id,
            "deal_status": deal.status,
            "ai_decision": ai_decision,
            "ai_reply": deal.ai_generated_reply
        }, status=201)

    except Exception as e:
        return JsonResponse({
            "error": f"Server error: {str(e)}"
        }, status=500)


# 🟢 DASHBOARD
@login_required
def dashboard(request):
    deals = Deal.objects.all().order_by("-created_at")

    stats = {
        "NEW": deals.filter(status="NEW").count(),
        "WAITING_FOR_CLIENT": deals.filter(status="WAITING_FOR_CLIENT").count(),
        "PENDING_CREATOR": deals.filter(status="PENDING_CREATOR").count(),
        "COMPLETED": deals.filter(status="COMPLETED").count(),
        "REJECTED": deals.filter(status="REJECTED").count(),
        "AUTO_REJECTED": deals.filter(status="AUTO_REJECTED").count(),
    }
    
    # Status colors for badge styling
    status_colors = {
        "NEW": "bg-blue-500",
        "WAITING_FOR_CLIENT": "bg-yellow-500",
        "PENDING_CREATOR": "bg-purple-500",
        "COMPLETED": "bg-green-500",
        "REJECTED": "bg-red-500",
        "AUTO_REJECTED": "bg-gray-500",
    }

    return render(request, "deals/dashboard.html", {
        "deals": deals,
        "stats": stats,
        "status_colors": status_colors
    })


# 🟢 DEAL DETAIL
@login_required
def deal_detail(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    messages_qs = deal.emails.all().order_by("created_at")
    
    # Show Accept/Reject buttons only if status is PENDING_CREATOR
    can_accept_reject = deal.status == "PENDING_CREATOR"
    
    # Status colors for badge styling
    status_colors = {
        "NEW": "bg-blue-500",
        "WAITING_FOR_CLIENT": "bg-yellow-500",
        "PENDING_CREATOR": "bg-purple-500",
        "COMPLETED": "bg-green-500",
        "REJECTED": "bg-red-500",
        "AUTO_REJECTED": "bg-gray-500",
    }

    return render(request, "deals/deal_detail.html", {
        "deal": deal,
        "email_messages": messages_qs,
        "can_accept_reject": can_accept_reject,
        "status_colors": status_colors
    })


# ✅ ACCEPT DEAL
@login_required
@require_POST
def accept_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)

    # 1. Ask AI to generate an acceptance letter
    chat_history_qs = deal.emails.all().order_by("created_at")
    chat_history = []
    for msg in chat_history_qs:
        role = "client" if msg.direction == "INCOMING" else "ai"
        chat_history.append({"role": role, "content": msg.body})
        
    try:
        flask_resp = requests.post(f"{FLASK_AI_URL}/generate_reply", json={
            "body": "The creator has accepted the deal. Generate an acceptance email.",
            "chat_history": chat_history,
            "action": "accept"
        }, timeout=15)
        
        if flask_resp.status_code == 200:
            ai_data = flask_resp.json()
            deal.ai_generated_reply = ai_data.get("reply", deal.ai_generated_reply)
    except Exception as e:
        print(f"Error calling Flask AI for accept: {e}")

    # 2. Update Deal Status
    deal.status = "COMPLETED"
    deal.updated_at = timezone.now()
    deal.save()

    # Trigger n8n webhook
    if hasattr(settings, "N8N_WEBHOOK_URL") and settings.N8N_WEBHOOK_URL:
        try:
            requests.post(settings.N8N_WEBHOOK_URL, json={
                "action": "accept",
                "thread_id": deal.thread_id,
                "deal_id": deal.id,
                "ai_reply": deal.ai_generated_reply,
                "from_email": deal.client.email
            }, timeout=5)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to send webhook: {e}")

    messages.success(request, "Deal accepted")
    return redirect("deal_detail", deal_id=deal.id)


# ❌ REJECT DEAL
@login_required
@require_POST
def reject_deal(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)

    # 1. Ask AI to generate a rejection letter
    chat_history_qs = deal.emails.all().order_by("created_at")
    chat_history = []
    for msg in chat_history_qs:
        role = "client" if msg.direction == "INCOMING" else "ai"
        chat_history.append({"role": role, "content": msg.body})
        
    try:
        flask_resp = requests.post(f"{FLASK_AI_URL}/generate_reply", json={
            "body": "The creator has rejected the deal. Generate a polite rejection email.",
            "chat_history": chat_history,
            "action": "reject"
        }, timeout=15)
        
        if flask_resp.status_code == 200:
            ai_data = flask_resp.json()
            deal.ai_generated_reply = ai_data.get("reply", deal.ai_generated_reply)
    except Exception as e:
        print(f"Error calling Flask AI for reject: {e}")

    # 2. Update Deal Status
    deal.status = "REJECTED"
    deal.updated_at = timezone.now()
    deal.save()

    # Trigger n8n webhook
    if hasattr(settings, "N8N_WEBHOOK_URL") and settings.N8N_WEBHOOK_URL:
        try:
            requests.post(settings.N8N_WEBHOOK_URL, json={
                "action": "reject",
                "thread_id": deal.thread_id,
                "deal_id": deal.id,
                "ai_reply": deal.ai_generated_reply,
                "from_email": deal.client.email
            }, timeout=5)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to send webhook: {e}")

    messages.success(request, "Deal rejected")
    return redirect("deal_detail", deal_id=deal.id)


# 🔄 UPDATE AI REPLY
@login_required
@require_POST
def update_ai_reply(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    ai_reply = request.POST.get("ai_reply", "").strip()
    
    deal.ai_generated_reply = ai_reply
    deal.updated_at = timezone.now()
    deal.save()
    
    messages.success(request, "AI reply updated successfully")
    return redirect("deal_detail", deal_id=deal.id)


# 🔐 LOGIN VIEW
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next", "dashboard")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    
    return render(request, "deals/login.html")


# 🔐 LOGOUT VIEW
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("login")



# 🔍 CHECK DEAL EXISTS
@csrf_exempt
@require_GET
def check_deal_exists(request):
    """
    API endpoint to check if a deal exists based on thread_id.
    GET /api/deals/check/?thread_id=<thread_id>
    
    Returns:
        - {"exists": true} if deal exists
        - {"exists": false} if deal does not exist
        - {"error": "thread_id parameter is required"} if thread_id is missing
    """
    thread_id = request.GET.get("thread_id")
    
    if not thread_id:
        return JsonResponse({
            "error": "thread_id parameter is required"
        }, status=400)
    
    exists = Deal.objects.filter(thread_id=thread_id).exists()
    
    return JsonResponse({
        "exists": exists
    })


# 📝 SAVE DASHBOARD DEAL (Manual Deal Creation)
@csrf_exempt
def save_dashboard_deal(request):
    """
    API endpoint to manually create a deal from dashboard.
    Accepts JSON with:
    - from_email (required)
    - subject (required)
    - incoming_body (required) - will be saved as EmailMessage
    - ai_reply_body (optional) - will be saved as ai_generated_reply
    - thread_id (optional) - will be auto-generated if not provided
    - status (optional) - defaults to WAITING_FOR_CLIENT
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({
            "error": "Invalid JSON. Please send JSON data only."
        }, status=400)

    # Validate required fields
    required_fields = ['from_email', 'subject', 'incoming_body']
    missing_fields = [field for field in required_fields if not data.get(field)]
    
    if missing_fields:
        return JsonResponse({
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }, status=400)

    try:
        from_email = data.get("from_email")
        subject = data.get("subject")
        incoming_body = data.get("incoming_body")
        ai_reply_body = data.get("ai_reply_body", "")
        thread_id = data.get("thread_id") or f"manual_{timezone.now().timestamp()}"
        status = data.get("status", "WAITING_FOR_CLIENT")
        to_email = data.get("to_email", "")

        # Validate status
        valid_statuses = [choice[0] for choice in Deal.STATUS_CHOICES]
        if status not in valid_statuses:
            status = "WAITING_FOR_CLIENT"

        # Get or create Client
        client, _ = Client.objects.get_or_create(
            email=from_email,
            defaults={'brand_name': data.get('brand_name', '')}
        )

        # Create Deal
        deal = Deal.objects.create(
            client=client,
            subject=subject,
            thread_id=thread_id,
            status=status,
            ai_generated_reply=ai_reply_body
        )

        # Create EmailMessage for incoming email
        EmailMessage.objects.create(
            deal=deal,
            direction="INCOMING",
            subject=subject,
            body=incoming_body,
            from_email=from_email,
            to_email=to_email
        )

        return JsonResponse({
            "status": "success",
            "deal_id": deal.id,
            "thread_id": deal.thread_id
        }, status=201)

    except Exception as e:
        return JsonResponse({
            "error": f"Server error: {str(e)}"
        }, status=500)
