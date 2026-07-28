# Django Project - Complete Documentation 

## 📋 Table of Contents 
1. [Models Explanation (Models)](#models-explanation)
2. [API Endpoints (API ](#api-endpoints)
3. [Database Structure (Database )](#database-structure)
4. [How Data Saves to DB ](#how-data-saves-to-db)
5. [How to Test APIs (API)](#how-to-test-apis)
6. [URL Patterns (URL )](#url-patterns)
7. [Views Explanation (Views image.png)](#views-explanation)

---

## 1. Models Explanation (Models)

### 4 Models :

### 📧 **Model 1: Email**
**File:** `backend/deals/models.py` (Lines 4-12)

**Purpose:** Incoming emails ni store చేయడానికి

**Fields:**
- `subject` (CharField, max 255) - Email subject
- `body` (TextField) - Email body/content
- `thread_id` (CharField, max 255) - Email thread ID
- `category` (CharField, max 50, default="useful") - Email category
- `created_at` (DateTimeField, auto) - Email create ayina time

**Example:**
```python
Email.objects.create(
    subject="Brand Collaboration Request",
    body="We want to collaborate...",
    thread_id="thread_123",
    category="useful"
)
```

---

### 👤 **Model 2: Client**
**File:** `backend/deals/models.py` (Lines 15-21)

**Purpose:** Brand/Client information ni store 

**Fields:**
- `email` (EmailField, unique=True) - Client email (unique)
- `brand_name` (CharField, max 255, optional) - Brand name (null/blank allowed)
- `created_at` (DateTimeField, auto) - Client create ayina time

**Example:**
```python
Client.objects.create(
    email="brand@example.com",
    brand_name="Nike"
)
```

---

### 💼 **Model 3: Deal**
**File:** `backend/deals/models.py` (Lines 23-47)

**Purpose:** Main deal/collaboration information ni store చేయడానికి

**Fields:**
- `client` (ForeignKey → Client) - Which client ki deal
- `subject` (CharField, max 255) - Deal subject
- `thread_id` (CharField, max 255) - Email thread ID
- `status` (CharField, choices) - Deal status:
  - `NEW` - New deal
  - `WAITING_FOR_CLIENT` - Client response wait
  - `PENDING_CREATOR` - Creator decision pending
  - `COMPLETED` - Deal completed
  - `REJECTED` - Deal rejected
  - `AUTO_REJECTED` - Auto rejected
- `our_reply_sent_at` (DateTimeField, optional) - Our reply sent time
- `client_replied_at` (DateTimeField, optional) - Client reply time
- `ai_generated_reply` (TextField, optional) - AI generated reply
- `updated_at` (DateTimeField, auto) - Last update time
- `created_at` (DateTimeField, auto) - Deal create time

**Example:**
```python
Deal.objects.create(
    client=client_obj,
    subject="Collaboration Request",
    thread_id="thread_123",
    status="NEW"
)
```

---

### 📨 **Model 4: EmailMessage**
**File:** `backend/deals/models.py` (Lines 50-66)

**Purpose:** Deal related email messages ni store చేయడానికి

**Fields:**
- `deal` (ForeignKey → Deal, related_name="emails") - Which deal ki email
- `direction` (CharField, choices) - Email direction:
  - `INCOMING` - Client nunchi vachina email
  - `OUTGOING` - Memu pampina email
- `body` (TextField) - Email body
- `from_email` (EmailField) - Sender email
- `to_email` (EmailField) - Receiver email
- `created_at` (DateTimeField, auto) - Email create time

**Example:**
```python
EmailMessage.objects.create(
    deal=deal_obj,
    direction="INCOMING",
    body="Hello, we want to collaborate...",
    from_email="brand@example.com",
    to_email="creator@example.com"
)
```

---

## 2. API Endpoints (API )

###  1 API Endpoint :

### 🔵 **API 1: Save Email**
**URL:** `/save-email/` or `/api/save-email/`

**Method:** `POST`

**Authentication:** Not required (CSRF exempt)

**Purpose:** Email ni database lo save చేయడానికి

**Request Body (JSON):**
```json
{
    "subject": "Brand Collaboration Request",
    "body": "We want to collaborate with you...",
    "thread_id": "thread_12345",
    "category": "useful"
}
```

**Response (Success):**
```json
{
    "status": "success",
    "id": 1
}
```

**Response (Error):**
```json
{
    "error": "Invalid request"
}
```

**Code Location:** `backend/deals/views.py` (Lines 14-32)

**How it works:**
1. POST request vastundi
2. JSON data parse cheyadam
3. `Email.objects.create()` use chesi database lo save
4. Success response return

---

## 3. Database Structure 

### Relationship

```
Client (1) ──→ (Many) Deal
  ↓
  └── Each Client ki multiple Deals vachu

Deal (1) ──→ (Many) EmailMessage
  ↓
  └── Each Deal ki multiple EmailMessages vachu
```

**Example:**
- 1 Client (Nike) ki → 5 Deals vachu
- 1 Deal ki → 10 EmailMessages vachu (5 incoming + 5 outgoing)

### Database Tables:

1. **deals_email** - Email model data
2. **deals_client** - Client model data
3. **deals_deal** - Deal model data
4. **deals_emailmessage** - EmailMessage model data

---

## 4. How Data Saves to DB 

### Process Flow:

#### **Scenario 1: Email Save **

```
Step 1: External System → POST Request → /save-email/
        {
            "subject": "...",
            "body": "...",
            "thread_id": "...",
            "category": "..."
        }

Step 2: Django View (save_email) receives request
        ↓
        data = json.loads(request.body)

Step 3: Database Save
        ↓
        Email.objects.create(
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            thread_id=data.get("thread_id", ""),
            category=data.get("category", "useful")
        )

Step 4: Django ORM → SQL Query → SQLite Database
        ↓
        INSERT INTO deals_email (subject, body, thread_id, category, created_at)
        VALUES ('...', '...', '...', 'useful', '2024-01-01 10:00:00')

Step 5: Response sent back
        ↓
        {"status": "success", "id": 1}
```

#### **Scenario 2: Deal Accept/Reject ***

```
Step 1: User clicks "Accept" button
        ↓
        POST Request → /deal/1/accept/

Step 2: Django View (accept_deal) receives request
        ↓
        deal = get_object_or_404(Deal, id=deal_id)

Step 3: Update Deal Status
        ↓
        deal.status = 'COMPLETED'
        deal.updated_at = timezone.now()
        deal.save()

Step 4: Database Update
        ↓
        UPDATE deals_deal 
        SET status = 'COMPLETED', updated_at = '2024-01-01 10:00:00'
        WHERE id = 1

Step 5: Webhook to n8n (optional)
        ↓
        requests.post(webhook_url, json={...})

Step 6: Redirect to deal detail page
```

#### **Scenario 3: Update AI Reply**

```
Step 1: User edits AI reply and submits
        ↓
        POST Request → /deal/1/update-reply/
        ai_reply = "Thank you for..."

Step 2: Django View (update_ai_reply) receives request
        ↓
        deal.ai_generated_reply = ai_reply
        deal.save()

Step 3: Database Update
        ↓
        UPDATE deals_deal 
        SET ai_generated_reply = 'Thank you for...'
        WHERE id = 1
```

---

## 5. How to Test API

### Method 1: Using cURL (Terminal/Command Prompt)

```bash
# Save Email API Test
curl -X POST http://localhost:8000/save-email/ \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Test Email",
    "body": "This is a test email body",
    "thread_id": "test_thread_123",
    "category": "useful"
  }'
```

### Method 2: Using Python requests

```python
import requests
import json

url = "http://localhost:8000/save-email/"
data = {
    "subject": "Test Email",
    "body": "This is a test email body",
    "thread_id": "test_thread_123",
    "category": "useful"
}

response = requests.post(url, json=data)
print(response.json())
```

### Method 3: Using Postman

1. Open Postman
2. Method: `POST`
3. URL: `http://localhost:8000/save-email/`
4. Headers: `Content-Type: application/json`
5. Body (raw JSON):
```json
{
    "subject": "Test Email",
    "body": "This is a test email body",
    "thread_id": "test_thread_123",
    "category": "useful"
}
```
6. Click "Send"

### Method 4: Using Browser (JavaScript)

```javascript
fetch('http://localhost:8000/save-email/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        subject: "Test Email",
        body: "This is a test email body",
        thread_id: "test_thread_123",
        category: "useful"
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

### Check Database After API Call:

**Django Shell:**
```bash
python manage.py shell
```

```python
from deals.models import Email

# Check all emails
emails = Email.objects.all()
for email in emails:
    print(f"ID: {email.id}, Subject: {email.subject}, Created: {email.created_at}")

# Check specific email
email = Email.objects.get(id=1)
print(email.subject)
print(email.body)
```

**Django Admin:**
1. Go to: `http://localhost:8000/admin/`
2. Login
3. Click on "Emails"
4. See all saved emails

---

## 6. URL Patterns 

### All URLs in `backend/deals/urls.py`:

| URL Pattern | View Function | Purpose | Auth Required |
|------------|---------------|---------|---------------|
| `/` | `home` | Redirect to dashboard/login | No |
| `/save-email/` | `save_email` | Save email API | No |
| `/dashboard/` | `dashboard` | Show all deals | Yes |
| `/deal/<id>/` | `deal_detail` | Show deal details | Yes |
| `/deal/<id>/accept/` | `accept_deal` | Accept deal | Yes |
| `/deal/<id>/reject/` | `reject_deal` | Reject deal | Yes |
| `/deal/<id>/update-reply/` | `update_ai_reply` | Update AI reply | Yes |
| `/login/` | `login_view` | User login | No |
| `/logout/` | `logout_view` | User logout | Yes |

### URL Structure:

```
Main URLs (backend/backend/urls.py):
├── /admin/ → Django Admin
├── /api/ → Includes deals.urls (API endpoints)
└── / → Includes deals.urls (Dashboard & Auth)

Deals URLs (backend/deals/urls.py):
├── /save-email/ → API endpoint
├── /dashboard/ → Dashboard page
├── /deal/<id>/ → Deal detail page
├── /deal/<id>/accept/ → Accept deal
├── /deal/<id>/reject/ → Reject deal
├── /deal/<id>/update-reply/ → Update reply
├── /login/ → Login page
└── /logout/ → Logout
```

---

## 7. Views Explanation 

### All Views in `backend/deals/views.py`:

### **View 1: save_email** (Lines 14-32)
- **Purpose:** Email will be save in db
- **Method:** POST only
- **Auth:** Not required
- **Returns:** JSON response
- **Saves to:** `Email` model

###  **View 2: dashboard** (Lines 35-65)
- **Purpose:** All deals will be show in dashboard
- **Method:** GET
- **Auth:** Required (login_required)
- **Returns:** HTML page
- **Shows:** All deals with statistics

###  **View 3: deal_detail** (Lines 68-99)
- **Purpose:** Specific deal details will be shown
- **Method:** GET
- **Auth:** Required
- **Returns:** HTML page
- **Shows:** Deal info, email messages, AI reply

###  **View 4: accept_deal** (Lines 102-133)
- **Purpose:** Deal will be accept
- **Method:** POST only
- **Auth:** Required
- **Action:** 
  - Deal status → 'COMPLETED'
  - Webhook to n8n
- **Returns:** Redirect to deal detail

###  **View 5: reject_deal** (Lines 136-166)
- **Purpose:** Deal reject
- **Method:** POST only
- **Auth:** Required
- **Action:**
  - Deal status → 'REJECTED'
  - Webhook to n8n
- **Returns:** Redirect to deal detail

###  **View 6: update_ai_reply** (Lines 169-180)
- **Purpose:** AI generated reply
- **Method:** POST only
- **Auth:** Required
- **Action:** Deal's ai_generated_reply update
- **Returns:** Redirect to deal detail

###  **View 7: login_view** (Lines 184-204)
- **Purpose:** User login
- **Method:** GET, POST
- **Auth:** Not required (but redirects if already logged in)
- **Returns:** Login page or redirect to dashboard

###  **View 8: logout_view** (Lines 209-213)
- **Purpose:** User logout
- **Method:** GET
- **Auth:** Required
- **Returns:** Redirect to login

---

## 8. Database Queries Examples

### Create Records:

```python
# Create Client
client = Client.objects.create(
    email="nike@example.com",
    brand_name="Nike"
)

# Create Deal
deal = Deal.objects.create(
    client=client,
    subject="Collaboration Request",
    thread_id="thread_123",
    status="NEW"
)

# Create EmailMessage
email_msg = EmailMessage.objects.create(
    deal=deal,
    direction="INCOMING",
    body="Hello, we want to collaborate...",
    from_email="nike@example.com",
    to_email="creator@example.com"
)
```

### Read Records:

```python
# Get all deals
all_deals = Deal.objects.all()

# Get deals by status
pending_deals = Deal.objects.filter(status="PENDING_CREATOR")

# Get deal with client info
deal = Deal.objects.select_related('client').get(id=1)
print(deal.client.email)

# Get all emails for a deal
deal = Deal.objects.get(id=1)
emails = deal.emails.all()  # related_name="emails" use chesi
```

### Update Records:

```python
# Update deal status
deal = Deal.objects.get(id=1)
deal.status = "COMPLETED"
deal.save()

# Or in one line
Deal.objects.filter(id=1).update(status="COMPLETED")
```

### Delete Records:

```python
# Delete email
Email.objects.get(id=1).delete()

# Delete all emails
Email.objects.all().delete()
```

---

## 9. Important Notes 

###  **Database:**
- Using SQLite (default Django database)
- Database file: `backend/db.sqlite3`
- Migrations: `python manage.py migrate`

###  **Authentication:**
- Django's built-in authentication system
- Users must login to access dashboard
- API endpoint (`save_email`) doesn't require auth

###  **Webhooks:**
- When deal accepted/rejected, webhook sent to n8n
- Webhook URL set in settings: `N8N_WEBHOOK_URL`

###  **CSRF:**
- `save_email` API is CSRF exempt (external systems use cheyadaniki)
- Other views use Django's CSRF protection

### **Admin Panel:**
- Access at: `http://localhost:8000/admin/`
- All models registered in admin
- Can view/edit/delete all data

---

## 10. Quick Reference 

### Start Server:
```bash
cd backend
python manage.py runserver
```

### Create Superuser:
```bash
python manage.py createsuperuser
```

### Run Migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Access Points:
- **API:** `http://localhost:8000/save-email/`
- **Dashboard:** `http://localhost:8000/dashboard/`
- **Admin:** `http://localhost:8000/admin/`
- **Login:** `http://localhost:8000/login/`

---

## 📝 Summary 

**Models:** 4 models (Email, Client, Deal, EmailMessage)
**APIs:** 1 API endpoint (save_email)
**Views:** 8 views (1 API + 7 web views)
**Database:** SQLite
**Auth:** Django authentication
**Purpose:** Brand collaboration email management system

---

**Created:** Complete documentation for Django Deals project
**Last Updated:** 2024

