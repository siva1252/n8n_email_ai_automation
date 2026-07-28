# AI-Powered Email Negotiation System - Django Backend

## Overview
This Django backend integrates with n8n and Gmail to create a thread-based email negotiation system where each Gmail `thread_id` represents one business Deal.

## Core Concept
- **1 Gmail thread_id = 1 Deal**
- All emails (incoming/outgoing) in the same thread are grouped under the same Deal
- Dashboard displays Deals, not individual emails
- Fully automated via n8n with manual control via dashboard

## Models

### Client
- `email` (unique, required)
- `brand_name` (optional)
- `created_at`

### Deal
- `client` (ForeignKey → Client)
- `thread_id` (unique, required)
- `subject`
- `status` (choices):
  - `NEW`
  - `WAITING_FOR_CLIENT`
  - `PENDING_CREATOR`
  - `COMPLETED`
  - `REJECTED`
  - `AUTO_REJECTED`
- `ai_generated_reply` (optional)
- `created_at`, `updated_at`

### EmailMessage
- `deal` (ForeignKey → Deal, related_name="emails")
- `direction` (INCOMING / OUTGOING)
- `subject`
- `body`
- `from_email`
- `to_email`
- `created_at`

## API Endpoint: `/save-email/`

**Method:** POST  
**Content-Type:** application/json  
**CSRF:** Exempt (for n8n integration)

### Required Fields:
```json
{
  "thread_id": "19b885c070d16aaa",
  "subject": "Collaboration Proposal",
  "body": "Hi, I would like to collaborate...",
  "from_email": "client@example.com",
  "to_email": "you@example.com",
  "direction": "INCOMING"
}
```

### Optional Fields:
- `brand_name` - Will be saved to Client if provided

### Logic Flow:
1. Validates all required fields
2. Gets or creates Client using `from_email`
3. Gets or creates Deal using `thread_id`
   - If Deal is **created** → status set to `WAITING_FOR_CLIENT`
4. Creates EmailMessage linked to the Deal
5. If `direction = INCOMING` → updates Deal status to `PENDING_CREATOR`
6. Returns JSON response with `deal_id` and `success` status

### Response:
```json
{
  "status": "success",
  "deal_id": 1,
  "deal_created": true,
  "email_message_id": 1,
  "deal_status": "PENDING_CREATOR"
}
```

## Dashboard Features

### URL: `/dashboard/`
- **Authentication:** Required (login required)
- **Features:**
  - Status-wise counts (New, Waiting, Pending, Completed)
  - Deal list with:
    - Client email/brand
    - Subject
    - Status badge
    - Created date
  - Click "View Details" to see full conversation

### Deal Detail View

**URL:** `/deal/<deal_id>/`

**Features:**
- Shows all EmailMessage records ordered by `created_at`
- Displays conversation thread
- Shows Accept/Reject buttons **only if** Deal status is `PENDING_CREATOR`
- AI reply editor
- Accept/Reject actions trigger n8n webhook

## Accept/Reject Actions

### Accept Deal
**URL:** `/deal/<deal_id>/accept/`  
**Method:** POST

Updates Deal status to `COMPLETED` and triggers n8n webhook:
```json
{
  "action": "accept",
  "thread_id": "19b885c070d16aaa",
  "deal_id": 1,
  "ai_reply": "Thank you for your proposal..."
}
```

### Reject Deal
**URL:** `/deal/<deal_id>/reject/`  
**Method:** POST

Updates Deal status to `REJECTED` and triggers n8n webhook:
```json
{
  "action": "reject",
  "thread_id": "19b885c070d16aaa",
  "deal_id": 1,
  "ai_reply": "Thank you for your proposal..."
}
```

## n8n Webhook Configuration

Add to `settings.py`:
```python
N8N_WEBHOOK_URL = 'https://your-n8n-instance.com/webhook/deal-action'
```

The webhook will be called when Accept/Reject actions are performed from the dashboard.

## Admin Interface

**URL:** `/admin/`

Enhanced admin interface with:
- Client management with deal counts
- Deal management with status badges and email counts
- EmailMessage management with direction badges
- Search and filtering capabilities

## Authentication

- **Login:** `/login/`
- **Logout:** `/logout/`
- Create superuser: `python manage.py createsuperuser`

## Integration Rules

1. ✅ Django never assumes emails are standalone; all emails must belong to a Deal
2. ✅ n8n must always send proper JSON (no string blobs)
3. ✅ Dashboard relies only on Deal table for counts and lists
4. ✅ Thread-based organization (1 thread = 1 Deal)
5. ✅ Status-driven workflow

## Testing the API

### Using cURL:
```bash
curl -X POST http://127.0.0.1:8000/save-email/ \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "19b885c070d16aaa",
    "subject": "Test Email",
    "body": "This is a test email body",
    "from_email": "client@example.com",
    "to_email": "you@example.com",
    "direction": "INCOMING"
  }'
```

### Using Python requests:
```python
import requests

url = "http://127.0.0.1:8000/save-email/"
data = {
    "thread_id": "19b885c070d16aaa",
    "subject": "Test Email",
    "body": "This is a test email body",
    "from_email": "client@example.com",
    "to_email": "you@example.com",
    "direction": "INCOMING"
}

response = requests.post(url, json=data)
print(response.json())
```

## Status Flow

1. **New Deal Created** → `WAITING_FOR_CLIENT`
2. **Incoming Email Received** → `PENDING_CREATOR` (shows Accept/Reject buttons)
3. **Creator Accepts** → `COMPLETED`
4. **Creator Rejects** → `REJECTED`

## Notes

- All emails in the same thread are automatically grouped
- The system automatically determines client from `from_email`
- Status updates are automatic based on email direction
- Dashboard provides full visibility into all deals
- Admin interface allows full CRUD operations








