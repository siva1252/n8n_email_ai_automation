# Django Backend API Documentation

## 📋 API Endpoints Overview

### Base URL Structure
- Main URLs are under: `http://127.0.0.1:8000/`
- API endpoints: `http://127.0.0.1:8000/api/` or `http://127.0.0.1:8000/`

---

## 🔥 API Endpoints (n8n Integration)

### 1. **Save Email** (n8n Entry Point)
**Endpoint:** `POST /save-email/` or `POST /api/save-email/`

**Purpose:** n8n automation  main entry point.

**Authentication:** Not required (CSRF exempt)

**Request Body (JSON):**
```json
{
  "thread_id": "19ba740d2519c1e2",          // Required - Gmail thread ID
  "subject": "Collaboration mail",          // Required
  "body": "Hi, I want to collaborate...",   // Required - Email body
  "from_email": "client@gmail.com",         // Required - Sender email
  "to_email": "your@gmail.com",             // Required - Receiver email
  "direction": "INCOMING",                  // Required - "INCOMING" or "OUTGOING"
  "ai_generated_reply": "Thanks for...",    // Optional - AI generated reply text
  "brand_name": "Brand Name"                // Optional - Client brand name
}
```

**How it Works:**
1. ✅ Validates required fields (thread_id, subject, body, from_email, to_email, direction)
2. ✅ Creates or gets Client using `from_email`
3. ✅ Creates or gets Deal using `thread_id` (1 thread = 1 Deal)
4. ✅ Saves AI reply if provided
5. ✅ Creates EmailMessage record
6. ✅ **Status Update Logic:**
   - If `direction = "OUTGOING"` → Status = `WAITING_FOR_CLIENT` 
   - If `direction = "INCOMING"` and status is `WAITING_FOR_CLIENT` → Status = `PENDING_CREATOR` (Client 2nd reply)

**Response (Success - 201):**
```json
{
  "status": "success",
  "deal_id": 4,
  "deal_created": true,
  "email_message_id": 5,
  "deal_status": "WAITING_FOR_CLIENT"
}
```

**Response (Error - 400):**
```json
{
  "error": "Missing required fields: thread_id, subject"
}
```

**Response (Error - 500):**
```json
{
  "error": "Server error: [error details]"
}
```

---

### 2. **Save Dashboard Deal** (Manual Creation)
**Endpoint:** `POST /api/dashboard/deal/`

**Purpose:** Dashboard manually deal create 

**Authentication:** Not required (CSRF exempt)

**Request Body (JSON):**
```json
{
  "from_email": "client@gmail.com",         // Required
  "subject": "Test Deal",                   // Required
  "incoming_body": "Email body text",       // Required
  "ai_reply_body": "AI reply text",         // Optional
  "thread_id": "manual_123",                // Optional - auto-generated if not provided
  "status": "WAITING_FOR_CLIENT",           // Optional - defaults to WAITING_FOR_CLIENT
  "to_email": "your@gmail.com",             // Optional
  "brand_name": "Brand Name"                // Optional
}
```

**Response (Success - 201):**
```json
{
  "status": "success",
  "deal_id": 5,
  "thread_id": "manual_123"
}
```

---

## 🟢 Web Pages (HTML Views)

### 3. **Dashboard Page**
**Endpoint:** `GET /dashboard/`

**Purpose:** All deal dashboard.

**Authentication:** Required (login required)

**What it Shows:**
- 📊 Statistics cards: NEW, WAITING, PENDING, COMPLETED, REJECTED counts
- 📋 All deals list with status badges
- 🔗 "View Details" button for each deal

**Status Flow in Dashboard:**
- **NEW** → Blue card ( email)
- **WAITING_FOR_CLIENT** → Yellow card ( AI reply
- **PENDING_CREATOR** → Purple card (Client 2nd reply 
- **COMPLETED** → Green card (Accept 
- **REJECTED** → Red card (Reject 

---

### 4. **Deal Detail Page**
**Endpoint:** `GET /deal/<deal_id>/`

**Purpose:** Specific deal full details 

**Authentication:** Required

**What it Shows:**
- Deal information (client, subject, status)
- All email messages in the thread (INCOMING & OUTGOING)
- AI generated reply (editable)
- Accept/Reject buttons (only if status is `PENDING_CREATOR`)

---

### 5. **Accept Deal**
**Endpoint:** `POST /deal/<deal_id>/accept/`

**Purpose:** Deal accept 

**Authentication:** Required

**What it Does:**
1. ✅ Changes deal status to `COMPLETED`
2. ✅ Updates `updated_at` timestamp
3. ✅ Sends webhook to n8n (if `N8N_WEBHOOK_URL` configured)
4. ✅ Redirects to deal detail page

**n8n Webhook Data:**
```json
{
  "action": "accept",
  "thread_id": "19ba740d2519c1e2",
  "deal_id": 4,
  "ai_reply": "Thanks for collaboration..."
}
```

---

### 6. **Reject Deal**
**Endpoint:** `POST /deal/<deal_id>/reject/`

**Purpose:** Deal reject 

**Authentication:** Required

**What it Does:**
1. ✅ Changes deal status to `REJECTED`
2. ✅ Updates `updated_at` timestamp
3. ✅ Sends webhook to n8n (if configured)
4. ✅ Redirects to deal detail page

**n8n Webhook Data:**
```json
{
  "action": "reject",
  "thread_id": "19ba740d2519c1e2",
  "deal_id": 4,
  "ai_reply": "Thanks for collaboration..."
}
```

---

### 7. **Update AI Reply**
**Endpoint:** `POST /deal/<deal_id>/update-reply/`

**Purpose:** AI generated reply edit 

**Authentication:** Required

**Request Body (Form Data):**
```
ai_reply: "Updated AI reply text"
```

**What it Does:**
1. ✅ Updates `ai_generated_reply` field in Deal
2. ✅ Updates `updated_at` timestamp
3. ✅ Redirects to deal detail page

---

## 🔐 Authentication

### 8. **Login**
**Endpoint:** `GET /login/` (page) or `POST /login/` (submit)

**Purpose:** User login .

**POST Request Body (Form Data):**
```
username: "kavya"
password: "password123"
```

**What it Does:**
- Authenticates user
- Creates session
- Redirects to dashboard or `next` URL

---

### 9. **Logout**
**Endpoint:** `GET /logout/` or `POST /logout/`

**Purpose:** User logout చేయడానికి.

**Authentication:** Required

**What it Does:**
- Logs out user
- Destroys session
- Redirects to login page

---

### 10. **Home Page**
**Endpoint:** `GET /`

**Purpose:** Root URL - redirects based on authentication:
- If logged in → `/dashboard/`
- If not logged in → `/login/`

---

## 📊 Complete Status Flow

```
1. Client sends first email (INCOMING)
   ↓
   Deal created with status: NEW
   ↓
2. You send AI reply (OUTGOING)
   ↓
   Status changes to: WAITING_FOR_CLIENT
   ↓
3. Client replies again (INCOMING)
   ↓
   Status changes to: PENDING_CREATOR
   ↓
4. You click Accept
   ↓
   Status changes to: COMPLETED
```

---

## 🔄 n8n Integration Flow

### Incoming Email (Client → You):
```
Gmail Trigger (INCOMING email)
  ↓
n8n processes email
  ↓
POST /save-email/
  Body: {
    direction: "INCOMING",
    thread_id: "...",
    subject: "...",
    body: "...",
    from_email: "client@gmail.com",
    to_email: "your@gmail.com"
  }
  ↓
Backend:
  - Creates/updates Deal
  - Creates EmailMessage
  - Updates status based on current status
```

### Outgoing Email (You → Client):
```
After AI generates reply
  ↓
Send email via Gmail
  ↓
POST /save-email/
  Body: {
    direction: "OUTGOING",
    thread_id: "...",
    subject: "...",
    body: "...",
    from_email: "your@gmail.com",
    to_email: "client@gmail.com",
    ai_generated_reply: "AI reply text"
  }
  ↓
Backend:
  - Updates Deal status to WAITING_FOR_CLIENT
  - Saves EmailMessage
  - Sets our_reply_sent_at timestamp
```

### Accept/Reject Actions:
```
User clicks Accept/Reject in dashboard
  ↓
POST /deal/<id>/accept/ or /reject/
  ↓
Backend:
  - Updates Deal status
  - Sends webhook to n8n (if configured)
```

---

## 📝 Database Models

### Client Model:
- `email` (unique) - Client email address
- `brand_name` - Brand name (optional)
- `created_at` - Creation timestamp

### Deal Model:
- `client` - ForeignKey to Client
- `subject` - Email subject
- `thread_id` - Gmail thread ID (unique)
- `status` - One of: NEW, WAITING_FOR_CLIENT, PENDING_CREATOR, COMPLETED, REJECTED, AUTO_REJECTED
- `ai_generated_reply` - AI generated reply text
- `our_reply_sent_at` - Timestamp when we replied
- `client_replied_at` - Timestamp when client replied
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

### EmailMessage Model:
- `deal` - ForeignKey to Deal
- `direction` - "INCOMING" or "OUTGOING"
- `subject` - Email subject
- `body` - Email body
- `from_email` - Sender email
- `to_email` - Receiver email
- `created_at` - Creation timestamp

---

## ⚙️ Configuration

### Settings Required:
```python
# settings.py
N8N_WEBHOOK_URL = "https://your-n8n-webhook-url"  # Optional
```

---

## 🎯 Key Points:

1. **Main API:** `/save-email/` - n8n uses this to save all emails
2. **Status Logic:**
   - OUTGOING email → Always sets status to `WAITING_FOR_CLIENT`
   - INCOMING email → Only changes to `PENDING_CREATOR` if current status is `WAITING_FOR_CLIENT`
3. **Accept/Reject:** Only available when status is `PENDING_CREATOR`
4. **Thread ID:** Same thread_id = Same Deal (Gmail thread concept)
5. **Webhooks:** Accept/Reject actions trigger n8n webhooks (if configured)

---

## 🚀 Quick Reference

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/save-email/` | POST | No | n8n email save (main API) |
| `/api/dashboard/deal/` | POST | No | Manual deal creation |
| `/dashboard/` | GET | Yes | View all deals |
| `/deal/<id>/` | GET | Yes | View deal details |
| `/deal/<id>/accept/` | POST | Yes | Accept deal |
| `/deal/<id>/reject/` | POST | Yes | Reject deal |
| `/deal/<id>/update-reply/` | POST | Yes | Update AI reply |
| `/login/` | GET/POST | No | Login |
| `/logout/` | GET/POST | Yes | Logout |

---

## ✅ Testing Examples

### Test Save Email (INCOMING):
```bash
curl -X POST http://127.0.0.1:8000/save-email/ \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test123",
    "subject": "Test Email",
    "body": "Hello, I want to collaborate",
    "from_email": "client@test.com",
    "to_email": "you@test.com",
    "direction": "INCOMING"
  }'
```

### Test Save Email (OUTGOING):
```bash
curl -X POST http://127.0.0.1:8000/save-email/ \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test123",
    "subject": "Re: Test Email",
    "body": "Thanks for your interest",
    "from_email": "you@test.com",
    "to_email": "client@test.com",
    "direction": "OUTGOING",
    "ai_generated_reply": "Thanks for your interest in collaboration"
  }'
```

---

**Last Updated:** 2025-01-10
**Version:** 1.0


