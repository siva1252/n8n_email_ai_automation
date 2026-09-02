# Email AI Automation — Full Project Documentation

**Single source of truth for this repository.**  
Use this file when asking an agent to explain, fix, or improve anything. Older files in `docs/` are outdated and must not be treated as current.

| Item | Value |
|------|--------|
| Project name | Email AI Automation (n8n + Django + Flask) |
| Repo folder | `N8n_email_ai_automation` |
| Purpose | Auto-classify brand collaboration emails, negotiate price with AI, store every thread as a Deal, and let the creator accept/reject from a dashboard |
| Stack | Gmail → n8n (orchestrator) → Flask (Sarvam AI) → Django (SQLite + dashboard) |
| UI | Django server-rendered templates + Tailwind CDN (no React/SPA) |
| Database | SQLite (`backend/db.sqlite3`) |
| AI provider | Sarvam (`sarvam-30b` default, or `sarvam-105b`) |
| Last verified against code | 2026-08-31 |

---

## 1. What this project is

This is a **local brand-deal email negotiation system** for a creator / influencer.

A brand emails the creator’s Gmail about a collab, sponsorship, or paid promotion. The stack:

1. Watches Gmail (n8n).
2. Decides if the mail is a real business inquiry or spam (Flask + Sarvam).
3. Groups every message in the same Gmail thread into **one Deal**.
4. Drafts a negotiation reply (Flask + Sarvam).
5. Sends that reply back through Gmail (n8n).
6. Repeats until the AI thinks the price is ready to close.
7. Shows the Deal on a Django dashboard so the creator can **Accept** or **Reject**.
8. On accept/reject, Django asks the AI for a closing letter and notifies n8n so n8n can send it.

**Core rule:** `1 Gmail thread_id = 1 Deal`. Emails are never standalone records.

**Who uses it**

| Role | How they use it |
|------|-----------------|
| Brand / client | Sends normal Gmail. They never see this app. |
| n8n | Watches Gmail, calls Flask and Django, sends replies. |
| Flask AI | Classifies mail and writes negotiation / accept / reject text. |
| Django | Stores Clients, Deals, EmailMessages. Serves login + dashboard. |
| Creator | Logs into Django, reviews threads, edits the AI draft, Accept / Reject. |

---

## 2. What is already built vs what is not

### Built and working in this repo

- Flask AI microservice: classify email, generate negotiate / accept / reject replies.
- Django models: `Client`, `Deal`, `EmailMessage`.
- Django API used by n8n: `POST /save-email/`, `GET /deals/check/`, `POST /api/dashboard/deal/`.
- Django dashboard: stats, deal list, conversation thread, editable AI reply, Accept / Reject.
- Django login / logout / admin.
- Docker Compose for Django + Flask.
- Env template (`.env.example`).
- On incoming mail, Django itself calls Flask to generate a reply and can pause the deal when AI returns `ready_to_close`.
- On Accept / Reject, Django calls Flask for a closing letter, then POSTs a webhook to n8n.

### Not in this repo (exists only on the machine / n8n UI)

- The n8n workflow JSON is **not versioned**. n8n is started as a separate container (`n8n` on port 5678) with volume `n8n_data`.
- Gmail OAuth credentials live inside n8n, not in this repo.
- Real secrets live in `.env` (gitignored).

### Designed but unused / incomplete

| Thing | Status |
|-------|--------|
| `AUTO_REJECTED` deal status | In model + dashboard stats. Never set by any view. |
| `Deal.client_replied_at` | Field exists. Never written. |
| Flask `POST /classify_email` | Implemented. Django never calls it. n8n is supposed to. |
| `djangorestframework` | Installed. No serializers / DRF views. |
| Django reading `.env` | Compose injects env into the container, but `settings.py` does **not** read `FLASK_AI_URL`, `N8N_WEBHOOK_URL`, `DJANGO_SECRET_KEY`, or `DJANGO_DEBUG`. |
| Tests | `backend/deals/tests.py` is empty. |
| n8n in `docker-compose.yml` | Not included. Started separately. |

---

## 3. Repository map

```
N8n_email_ai_automation/
├── PROJECT_DOCUMENTATION.md   ← this file (give this to an agent)
├── README.md                  ← short quick-start only
├── .env.example               ← copy to .env
├── .env                       ← local secrets (not committed)
├── .gitignore
├── docker-compose.yml         ← django_backend + flask_ai
├── Dockerfile.django
├── Dockerfile.flask
├── requirements.txt           ← Django + Flask + Sarvam + gunicorn
│
├── flask_ai/
│   └── app.py                 ← only AI service file
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt       ← Django-only subset
│   ├── db.sqlite3             ← created after migrate (gitignored)
│   ├── backend/               ← Django project package
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── deals/                 ← only Django app
│       ├── models.py
│       ├── views.py           ← APIs + dashboard + auth
│       ├── urls.py
│       ├── admin.py
│       ├── tests.py           ← empty
│       ├── templatetags/deals_extras.py
│       ├── templates/deals/
│       │   ├── base.html
│       │   ├── login.html
│       │   ├── dashboard.html
│       │   └── deal_detail.html
│       └── migrations/
│           ├── 0001_initial.py
│           ├── 0002_email.py                         ← Email model (later deleted)
│           ├── 0003_deal_ai_generated_reply_deal_updated_at.py
│           └── 0004_delete_email_emailmessage_subject_and_more.py
│
└── docs/                      ← STALE. Do not trust for current behavior.
    ├── DJANGO_COMPLETE_DOCUMENTATION.md   ← still talks about deleted Email model
    ├── DJANGO_API_DOCUMENTATION.md        ← status flow does not match views.py
    ├── EMAIL_NEGOTIATION_SYSTEM.md        ← same
    └── DASHBOARD_SETUP.md
```

When changing behavior, edit the code first, then update **this file**. Ignore or delete stale `docs/` later.

---

## 4. How to start the whole system (from zero)

### 4.1 Prerequisites

- Docker Desktop
- A Sarvam API key
- Gmail account for the creator (connected inside n8n)
- Optional: Python 3.10+ if running without Docker

### 4.2 Environment

```powershell
copy .env.example .env
```

Fill `.env`:

```env
SARVAM_API_KEY=...
SARVAM_MODEL=sarvam-30b
N8N_WEBHOOK_URL=http://localhost:5678/webhook/your_webhook_id_here
FLASK_AI_URL=http://flask_ai:5000
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,django_backend
```

**Important:** Django `settings.py` currently **ignores** most of these. Runtime values today:

| Setting | Actual source |
|---------|----------------|
| `SECRET_KEY` | Hardcoded in `settings.py` |
| `DEBUG` | Hardcoded `True` |
| `ALLOWED_HOSTS` | Hardcoded `["*"]` |
| `N8N_WEBHOOK_URL` | Hardcoded `http://localhost:5678/webhook-test/deal-action` |
| `FLASK_AI_URL` | **Not in settings.** Views default to `http://127.0.0.1:5000` |
| Flask `SARVAM_*` | Read from env / `.env` in `flask_ai/app.py` |

Inside Docker, Django calling `127.0.0.1:5000` talks to itself, not Flask. Flask is reachable as `http://flask_ai:5000`. This is a known gap.

### 4.3 Start Django + Flask

```powershell
docker compose up --build
```

| Service | Container | Host URL | Inside Docker |
|---------|-----------|----------|---------------|
| Django dashboard / API | `django_backend` | http://localhost:8000 | `http://django_backend:8000` |
| Flask AI | `flask_ai` | http://localhost:5000 | `http://flask_ai:5000` |

First time (and after model changes), run migrations and create a login user:

```powershell
docker exec -it django_backend python manage.py migrate
docker exec -it django_backend python manage.py createsuperuser
```

### 4.4 Start n8n (separate, not in compose)

```powershell
docker start n8n
```

If the container does not exist:

```powershell
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

n8n UI: http://localhost:5678

n8n must be able to reach:

- Flask: `http://host.docker.internal:5000` (n8n is not on the compose network)
- Django: `http://host.docker.internal:8000`

If you later add n8n to the same compose network, use `http://flask_ai:5000` and `http://django_backend:8000`.

### 4.5 Local URLs

| What | URL |
|------|-----|
| Django home | http://localhost:8000/ → login or dashboard |
| Dashboard | http://localhost:8000/dashboard/ |
| Login | http://localhost:8000/login/ |
| Admin | http://localhost:8000/admin/ |
| Save email API | http://localhost:8000/save-email/ or http://localhost:8000/api/save-email/ |
| Flask health | http://localhost:5000/health |
| n8n | http://localhost:5678 |

### 4.6 Run without Docker (dev)

```powershell
pip install -r requirements.txt
# terminal 1
cd flask_ai
python app.py
# terminal 2
cd backend
python manage.py migrate
python manage.py runserver
```

---

## 5. End-to-end process (how it starts, how it ends)

This is the intended full lifecycle. n8n is the conductor. Django is the memory. Flask is the brain. Gmail is the pipe.

```
BRAND GMAIL
    │  (new message or reply in a thread)
    ▼
n8n Gmail Trigger
    │
    ▼
n8n → Flask POST /classify_email
    │
    ├─ category = "spam"  → STOP (do not save, do not reply)
    │
    └─ category = "useful"
            │
            ▼
       n8n → Django POST /save-email/   direction = INCOMING
            │
            ├─ get_or_create Client (from from_email)
            ├─ get_or_create Deal (from thread_id), first time status = NEW
            ├─ create EmailMessage
            └─ Django → Flask POST /generate_reply
                   │
                   ├─ decision = "negotiating"
                   │     Django stores ai_generated_reply
                   │     status stays NEW (first mail) or previous status
                   │
                   └─ decision = "ready_to_close"
                         Django stores reply
                         status = PENDING_CREATOR
            │
            ▼
       n8n reads JSON: ai_reply, ai_decision, deal_id, deal_status
            │
            ▼
       n8n sends Gmail reply in the SAME thread
            │
            ▼
       n8n → Django POST /save-email/   direction = OUTGOING
            │
            └─ status = WAITING_FOR_CLIENT
               our_reply_sent_at = now
            │
            ▼
       WAIT for brand to reply  ──────────────┐
            │                                 │
            └──── (loop: classify → save INCOMING → generate → send → save OUTGOING)
                                              │
                   when Flask returns ready_to_close
                                              ▼
                                   Deal status = PENDING_CREATOR
                                              │
                                              ▼
                              Creator opens http://localhost:8000
                              Login → Dashboard → View Details
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                   Edit + Save Reply     Accept Deal          Reject Deal
                         │                    │                    │
                         │              Flask action=accept   Flask action=reject
                         │              status=COMPLETED      status=REJECTED
                         │                    │                    │
                         │                    └────────┬───────────┘
                         │                             ▼
                         │              Django POST N8N_WEBHOOK_URL
                         │              { action, thread_id, deal_id, ai_reply, from_email }
                         │                             │
                         │                             ▼
                         │              n8n sends closing Gmail in that thread
                         │                             │
                         └─────────────────────────────┴──────────► END
```

### Happy path in words

1. **Start:** Brand writes “We want to collaborate, budget ₹3500.”
2. n8n fires. Flask marks it `useful`.
3. Django creates Client + Deal (`NEW`) + first EmailMessage.
4. Django asks Flask for a counter-offer (e.g. push toward ₹5000–₹6000).
5. n8n emails that counter-offer. Django records it as OUTGOING. Status → `WAITING_FOR_CLIENT`.
6. Brand replies with ₹4500. Same loop. AI keeps negotiating.
7. Brand holds at or above `min_price` (₹4000). Flask returns `ready_to_close`.
8. Deal → `PENDING_CREATOR`. Accept / Reject buttons appear.
9. **End (accept):** Creator clicks Accept. Flask writes an acceptance letter. Status → `COMPLETED`. n8n sends the letter.
10. **End (reject):** Same, but polite decline. Status → `REJECTED`.
11. **End (spam):** Classification says spam. Nothing is saved. Thread never becomes a Deal.

### What “end” means in the database

A Deal is finished when `status` is `COMPLETED`, `REJECTED`, or (intended, not implemented) `AUTO_REJECTED`.  
The Gmail thread can still receive more mail. Current code does **not** lock finished deals; a new INCOMING save will still append EmailMessages and may call the AI again.

---

## 6. Status machine (actual code, not old docs)

Statuses on `Deal.status`:

| Code | Label on UI | Who sets it | When |
|------|-------------|-------------|------|
| `NEW` | New | `save_email` on first `get_or_create` | First time this `thread_id` is seen |
| `WAITING_FOR_CLIENT` | Waiting for Client | `save_email` when `direction=OUTGOING` | We just sent a reply |
| `PENDING_CREATOR` | Pending Creator Decision | `save_email` when incoming AI `decision=ready_to_close` | Human must decide |
| `COMPLETED` | Completed | `accept_deal` | Creator accepted |
| `REJECTED` | Rejected | `reject_deal` | Creator rejected |
| `AUTO_REJECTED` | Auto Rejected | **Nobody** | Dead status |

Accept / Reject buttons show **only** when `status == PENDING_CREATOR`.

### What old docs get wrong

Old docs say:

- first incoming → `WAITING_FOR_CLIENT` or immediately `PENDING_CREATOR`
- second client reply → `PENDING_CREATOR`

**Actual `save_email` logic:**

- New deal always starts as `NEW`.
- Incoming does **not** set `PENDING_CREATOR` just because it is incoming.
- Incoming only sets `PENDING_CREATOR` if Flask returns `ready_to_close`.
- Outgoing always sets `WAITING_FOR_CLIENT`.
- Incoming does not currently set `client_replied_at`.

---

## 7. Architecture of the three services

```
┌─────────────┐     classify / generate      ┌──────────────────┐
│    n8n      │ ───────────────────────────► │  Flask :5000     │
│  :5678      │                              │  Sarvam AI       │
│  Gmail I/O  │ ◄─────────────────────────── │  flask_ai/app.py │
└──────┬──────┘                              └──────────────────┘
       │ save-email / check / webhook
       ▼
┌──────────────────────────────────────────┐
│  Django :8000                            │
│  deals.views + SQLite                    │
│  On INCOMING/accept/reject, Django also  │
│  calls Flask /generate_reply itself      │
└──────────────────────────────────────────┘
       │
       ▼
  Creator browser (login, dashboard, accept/reject)
```

### Why there are three pieces

| Service | Responsibility | Must not do |
|---------|----------------|-------------|
| n8n | Gmail trigger, routing, sending mail | Store deals (that is Django) |
| Flask | LLM calls only | Persist business data |
| Django | Source of truth + human UI | Talk to Gmail directly (it does not) |

Django **does** call Flask. n8n **also** calls Flask for classify. Both are true.

---

## 8. Flask AI service (`flask_ai/app.py`)

Loads `.env` from repo root, then process env. Creates `SarvamAI` only if `SARVAM_API_KEY` is set.

Model: `SARVAM_MODEL` or `sarvam-30b`. Temperature `0.2`. Responses must be JSON; helper `_extract_json` unwraps fenced blocks.

### `GET /`

```json
{ "message": "This is Flask AI Server (Sarvam Edition)" }
```

### `GET /health`

```json
{ "status": "Flask AI running with Sarvam", "model": "sarvam-30b", "api_key_configured": true }
```

### `POST /classify_email`

**Who calls it:** n8n (intended). Not Django.

```json
{ "body": "Hi, we want to collaborate on a paid promotion..." }
```

Returns:

```json
{ "category": "useful", "reason": "Paid promotion / collab inquiry" }
```

Categories: `useful` or `spam`.

Prompt bias: if in doubt, mark `useful` so the creator does not miss money. Newsletters / family / junk → `spam`.

On any exception (missing key, bad JSON, API down): **defaults to `spam`**. That can silently drop a real deal.

### `POST /generate_reply`

**Who calls it:** Django (`save_email`, `accept_deal`, `reject_deal`). n8n may also call it.

```json
{
  "body": "latest email or instruction",
  "chat_history": [
    { "role": "client", "content": "..." },
    { "role": "ai", "content": "..." }
  ],
  "min_price": 4000,
  "goal_price": 5000,
  "action": "negotiate"
}
```

`action` values:

| action | What the model writes | decision returned |
|--------|----------------------|-------------------|
| `negotiate` (default) | Counter-offer email | `negotiating` or `ready_to_close` |
| `accept` | Excited acceptance | `accepted` |
| `reject` | Polite “no time now, maybe later” | `rejected` |

Negotiation rules baked into the prompt:

- Low offer (e.g. ₹3500) → counter high (₹5000 / ₹6000).
- High first offer (e.g. ₹10000) → counter even higher (e.g. ₹15000).
- Near `min_price` → push toward `goal_price`, keep talking.
- Always negotiate the first offer.
- If they stand firm at or above `min_price` after back-and-forth → `ready_to_close`.

Django currently hardcodes `min_price=4000`, `goal_price=5000` in `save_email`. Those numbers are not per-user or in the database.

On error: generic “reviewing your inquiry…” reply and a safe decision.

---

## 9. Django data model

File: `backend/deals/models.py`

There is **no** `Email` model anymore. Migration `0004` deleted it.

```
Client 1 ──< Deal 1 ──< EmailMessage
```

### Client

| Field | Type | Notes |
|-------|------|--------|
| `email` | EmailField, unique | Brand contact |
| `brand_name` | CharField, optional | From `brand_name` on first create |
| `created_at` | auto | |

### Deal

| Field | Type | Notes |
|-------|------|--------|
| `client` | FK Client, CASCADE | |
| `subject` | CharField 255 | Updated if later emails change subject |
| `thread_id` | CharField 255, **unique** | Gmail thread id. Manual deals use `manual_<timestamp>` |
| `status` | choices, default `NEW` | See status table |
| `ai_generated_reply` | Text, optional | Latest draft shown on detail page |
| `our_reply_sent_at` | DateTime, optional | Set on OUTGOING save |
| `client_replied_at` | DateTime, optional | **Never set** |
| `created_at` | auto | |
| `updated_at` | auto | |

### EmailMessage

| Field | Type | Notes |
|-------|------|--------|
| `deal` | FK Deal, `related_name="emails"` | |
| `direction` | `INCOMING` or `OUTGOING` | |
| `subject` | CharField, default `""` | |
| `body` | Text | |
| `from_email` | EmailField | |
| `to_email` | EmailField | |
| `created_at` | auto | |

Admin (`backend/deals/admin.py`) registers all three with badges, search, and counts.

---

## 10. Django URLs

`backend/backend/urls.py` mounts `deals.urls` **twice**:

- `""` → `/save-email/`, `/dashboard/`, …
- `"api/"` → `/api/save-email/`, `/api/dashboard/`, …

So every deals route exists with and without `/api/` prefix. That also means HTML pages are reachable under `/api/dashboard/`, which is accidental.

### All routes

| URL | Method | Auth | View | Purpose |
|-----|--------|------|------|---------|
| `/` | GET | No | `home` | Redirect: logged in → dashboard, else login |
| `/login/` | GET/POST | No | `login_view` | Session login |
| `/logout/` | GET | Yes | `logout_view` | Logout |
| `/dashboard/` | GET | Yes | `dashboard` | Deal list + counts |
| `/deal/<id>/` | GET | Yes | `deal_detail` | Thread + AI box + buttons |
| `/deal/<id>/update-reply/` | POST | Yes | `update_ai_reply` | Save edited draft |
| `/deal/<id>/accept/` | POST | Yes | `accept_deal` | Complete + webhook |
| `/deal/<id>/reject/` | POST | Yes | `reject_deal` | Reject + webhook |
| `/save-email/` | POST | **No, CSRF exempt** | `save_email` | n8n main write API |
| `/deals/check/?thread_id=` | GET | **No, CSRF exempt** | `check_deal_exists` | Does this thread already have a Deal? |
| `/api/dashboard/deal/` | POST | **No, CSRF exempt** | `save_dashboard_deal` | Manual deal create |
| `/admin/` | — | Superuser | Django admin | CRUD |

`LOGIN_URL = /login/`, `LOGIN_REDIRECT_URL = /dashboard/`.

---

## 11. API contracts (current)

### 11.1 `POST /save-email/` — main n8n entry

CSRF exempt. JSON only.

Required:

```json
{
  "thread_id": "19b885c070d16aaa",
  "subject": "Collaboration Proposal",
  "body": "Hi, we would like to collaborate...",
  "from_email": "brand@example.com",
  "to_email": "creator@example.com",
  "direction": "INCOMING"
}
```

Optional: `brand_name`, `ai_generated_reply`.

`direction` must be `INCOMING` or `OUTGOING`.

Success `201`:

```json
{
  "status": "success",
  "deal_id": 1,
  "deal_created": true,
  "email_message_id": 1,
  "deal_status": "NEW",
  "ai_decision": "negotiating",
  "ai_reply": "Thanks for reaching out, our standard rate is..."
}
```

Errors: `400` missing/invalid JSON, `405` not POST, `500` server error.

**Internal steps**

1. Validate JSON + required fields.
2. `Client.objects.get_or_create(email=from_email)`.
3. `Deal.objects.get_or_create(thread_id=..., defaults={status: NEW})`.
4. Update subject if it changed.
5. If `ai_generated_reply` provided, store it.
6. Create `EmailMessage`.
7. If INCOMING: build `chat_history` from prior messages, POST Flask `/generate_reply`, store reply; if `ready_to_close` → `PENDING_CREATOR`.
8. If OUTGOING: `WAITING_FOR_CLIENT` + `our_reply_sent_at`.
9. Return ids + `ai_reply` so n8n can send mail.

**Bug to know:** Client is always keyed by `from_email`. On OUTGOING, `from_email` is the creator. That can create / attach the Deal to the **creator as Client** if the Deal did not already exist. n8n must create the Deal on the first INCOMING before logging OUTGOING.

Flask timeout on this path is **10 seconds**.

### 11.2 `GET /deals/check/?thread_id=...`

```json
{ "exists": true }
```

or `{ "exists": false }`. Missing param → `400`.

n8n can use this to decide “new thread vs existing negotiation.”

### 11.3 `POST /api/dashboard/deal/` — manual create

Required: `from_email`, `subject`, `incoming_body`.  
Optional: `ai_reply_body`, `thread_id`, `status`, `to_email`, `brand_name`.

If `thread_id` omitted: `manual_<unix_timestamp>`.  
Default status: `WAITING_FOR_CLIENT`.  
Creates Client + Deal + one INCOMING EmailMessage. Does **not** call Flask.

### 11.4 Accept / Reject webhooks (Django → n8n)

If `settings.N8N_WEBHOOK_URL` is set (it is, hardcoded):

```json
{
  "action": "accept",
  "thread_id": "19b885c070d16aaa",
  "deal_id": 1,
  "ai_reply": "We are excited to accept...",
  "from_email": "brand@example.com"
}
```

`action` is `accept` or `reject`. Timeout 5s. Failures are printed, they do **not** roll back the Deal.

Today the URL is n8n **test** webhook (`/webhook-test/...`), which is not a durable production webhook.

---

## 12. Dashboard (creator UX)

Templates: Tailwind via CDN. Base nav, flash messages, login.

### Login (`/login/`)

Django auth username + password. Invalid credentials → error message. Already logged in → dashboard.

### Dashboard (`/dashboard/`)

- Stat cards: NEW, WAITING, PENDING, COMPLETED (REJECTED / AUTO_REJECTED counted in view but not shown as cards).
- List: avatar initial, subject, client email / brand, status badge, last updated, “View Details”.
- Empty state: “No Deals Yet”.
- No search, filter, pagination, or create-deal form in the UI (manual API exists).

### Deal detail (`/deal/<id>/`)

Left: full thread, INCOMING blue / OUTGOING green.  
Right: textarea for `ai_generated_reply` + Save Reply.  
Accept / Reject only if `PENDING_CREATOR`.

Accept:

1. Flask `action=accept` (15s timeout).
2. `status=COMPLETED`.
3. Webhook n8n.
4. Flash “Deal accepted”.

Reject: same with `action=reject` and `REJECTED`.

---

## 13. Docker and runtime details

`docker-compose.yml`

- `django_backend` depends on `flask_ai`.
- Both load `.env`.
- Django mounts `./backend:/app` so SQLite and code persist.
- Flask mounts `./flask_ai:/app`.
- Images: `python:3.10-slim`, start with **gunicorn** (not `runserver` / Flask debug).
- Django CMD: `gunicorn --bind 0.0.0.0:8000 backend.wsgi:application`
- Flask CMD: `gunicorn --bind 0.0.0.0:5000 app:app`
- **No migrate / collectstatic on container start.**
- n8n is not a compose service.

Root `requirements.txt`: Django>=6.0, djangorestframework, Flask, sarvamai, python-dotenv, requests, gunicorn.

---

## 14. How n8n should be wired (for an agent that will build or fix the workflow)

The workflow is not in git. Rebuild it like this.

### Workflow A — Incoming Gmail (main loop)

1. **Gmail Trigger** — new message in inbox.
2. Normalize fields: `thread_id`, `subject`, `body`, `from`, `to`.
3. **HTTP Request** `POST http://host.docker.internal:5000/classify_email` body `{ "body": "<email body>" }`.
4. **IF** `category != useful` → stop.
5. Optional: `GET http://host.docker.internal:8000/deals/check/?thread_id=...` (existing vs new).
6. **HTTP Request** `POST http://host.docker.internal:8000/save-email/`

```json
{
  "thread_id": "{{gmail.threadId}}",
  "subject": "{{gmail.subject}}",
  "body": "{{gmail.text}}",
  "from_email": "{{gmail.from}}",
  "to_email": "{{gmail.to}}",
  "direction": "INCOMING"
}
```

7. Read `ai_reply` and `ai_decision` from Django.
8. **Gmail Send** reply in the same thread, body = `ai_reply`.
9. **HTTP Request** `POST /save-email/` again with `direction: OUTGOING`, swapped from/to, `body` = sent text, optional `ai_generated_reply`.
10. If you do **not** want to auto-send when `ai_decision == ready_to_close`, skip step 8–9 and wait for the dashboard.

### Workflow B — Deal action webhook (Accept / Reject)

1. **Webhook** node path `deal-action` (production URL, not `/webhook-test/`).
2. Receive `{ action, thread_id, deal_id, ai_reply, from_email }`.
3. **Gmail Send** to `from_email`, thread `thread_id`, body `ai_reply`.
4. Optional: call `/save-email/` with `direction: OUTGOING` so the closing letter is stored.

Point `N8N_WEBHOOK_URL` in Django at the **production** webhook URL.

n8n must send real JSON objects, not stringified blobs.

---

## 15. History of what was done (from code + git)

Migrations tell the build order:

1. **0001** — Client, Deal, EmailMessage. Statuses including AUTO_REJECTED. `client_replied_at` / `our_reply_sent_at` already there. `thread_id` not unique yet.
2. **0002** — Added standalone `Email` (subject, body, thread_id, category). Used by an early `/save-email/` that only dumped raw mail.
3. **0003** — `Deal.ai_generated_reply`, `Deal.updated_at`.
4. **0004** — Deleted `Email`. Added `EmailMessage.subject`. Made `thread_id` unique.

Git messages (oldest → newest):

- `negotation is start` — negotiation loop introduced.
- `Email_checking` / `uodate` — Gmail / n8n integration.
- `testing of mail intergation` — mail path testing.
- `checking ai stuff` — Sarvam / Flask work.

Product evolved from “save emails in a table” → “thread = Deal + dashboard” → “Django calls Flask and auto-negotiates until `ready_to_close`.”

---

## 16. Known bugs, gaps, and inconsistencies

Any improvement agent should treat these as real, verified against current code.

1. **Django ignores `.env` for its own settings.** `FLASK_AI_URL` in compose never reaches `views.py` (defaults to `127.0.0.1:5000`). In Docker, AI calls from Django fail unless that default is changed.
2. **`N8N_WEBHOOK_URL` is a test webhook** and uses `localhost`, which from inside the Django container is not the n8n container.
3. **Client identity bug on OUTGOING** — `get_or_create(email=from_email)` uses the sender. Outgoing sender is the creator.
4. **`client_replied_at` never set.** `AUTO_REJECTED` never set.
5. **Finished deals are not protected.** Another incoming mail can keep negotiating a COMPLETED/REJECTED deal.
6. **Classify-on-error = spam** can drop real inquiries.
7. **Prices hardcoded** (4000 / 5000) in `save_email`, not stored per creator or per deal.
8. **Open write APIs** — `/save-email/`, `/deals/check/`, `/api/dashboard/deal/` have no auth token.
9. **SECRET_KEY committed**, `DEBUG=True`, `ALLOWED_HOSTS=["*"]`.
10. **Duplicate URL include** (`/` and `/api/`) duplicates every route.
11. **No migrate on Docker start.** Fresh container has empty tables until someone runs migrate.
12. **No tests.**
13. **n8n workflow not in git** — cannot reproduce the system from the repo alone.
14. **Dashboard has no filter/search/pagination** and no in-UI create form.
15. **DRF unused.**
16. **Old `docs/` contradict `views.py`.** Agents must follow this file + code.
17. **Accept/Reject do not write an OUTGOING EmailMessage.** Thread on the detail page misses the closing letter until n8n calls `/save-email/` again.
18. **Webhook payload `from_email` is `deal.client.email`**, which is wrong if the Client row was created from an OUTGOING sender (bug 3).
19. **No per-user / multi-creator support.** One Django auth user sees every Deal.
20. **SQLite** is fine locally; not for concurrent production writes.

---

## 17. Suggested improvements (for the next agent)

Work in this order unless the user asks otherwise.

### P0 — make the running stack correct

- Read `FLASK_AI_URL`, `N8N_WEBHOOK_URL`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` from environment in `settings.py`.
- Default Docker Flask URL to `http://flask_ai:5000`.
- Add `migrate` to Django container startup (or an entrypoint).
- Put n8n on the same compose network (or document `host.docker.internal` clearly in n8n nodes).
- Export and commit the n8n workflow JSON under something like `n8n/workflows/`.

### P1 — correct business logic

- Resolve Client from the **brand** address: INCOMING `from_email`, OUTGOING `to_email`.
- Set `client_replied_at` on INCOMING.
- Do not mutate COMPLETED / REJECTED / AUTO_REJECTED except via an explicit reopen.
- After accept/reject, create an OUTGOING EmailMessage (or require n8n to save it).
- Add a shared API key / header that n8n must send to `/save-email/`.
- Persist `min_price` / `goal_price` (settings or Deal fields).

### P2 — product

- Search / filter / pagination on dashboard.
- Show REJECTED and AUTO_REJECTED cards or a filter.
- Classification result stored on the Deal or EmailMessage.
- Use `/classify_email` from Django as a fallback if n8n skips it.
- Multi-creator or at least Deal ownership.
- Replace CDN Tailwind with a built stylesheet if going to production.

### P3 — quality

- Tests for `save_email` status transitions and Client assignment.
- Remove unused DRF or actually use it.
- Delete or rewrite stale `docs/`.
- Structured logging instead of `print`.
- Health endpoint on Django.

Do not “clean up” by deleting models or statuses the user still wants (e.g. `AUTO_REJECTED`) unless they ask. Implement them or leave them and document.

---

## 18. How an agent should work on this repo

### Before changing anything

1. Read this file.
2. Confirm behavior in `backend/deals/views.py`, `backend/deals/models.py`, `flask_ai/app.py`, `docker-compose.yml`, `backend/backend/settings.py`.
3. Do not trust `docs/*.md` if it conflicts with those files.

### Safe change map

| User asks about… | Touch these files |
|------------------|-------------------|
| Classification / negotiation wording / prices in the prompt | `flask_ai/app.py` |
| Saving mail, statuses, AI call from Django | `backend/deals/views.py` |
| Fields / relationships | `backend/deals/models.py` + new migration |
| Routes | `backend/deals/urls.py`, `backend/backend/urls.py` |
| Dashboard look / Accept UI | `backend/deals/templates/deals/*.html` |
| Admin columns | `backend/deals/admin.py` |
| Secrets / service URLs | `.env.example`, `settings.py`, `docker-compose.yml` |
| How to run | `README.md` + this file |

### Invariants (do not break)

- One `thread_id` → one Deal.
- Every stored mail is an `EmailMessage` on a Deal.
- Dashboard lists Deals, not raw emails.
- Flask stays stateless.
- Django does not send Gmail itself.
- Accept / Reject stay human actions unless the user asks for full auto-close.
- Do not commit `.env`.

### How to talk to an agent (copy/paste prompts)

```
Read PROJECT_DOCUMENTATION.md first. Then:

1) Fix Django so FLASK_AI_URL and N8N_WEBHOOK_URL come from environment,
   with Docker default http://flask_ai:5000.

2) Fix Client assignment so OUTGOING emails do not create a Client
   from the creator's address.

3) Do not change the negotiation prompt unless I ask.
```

```
Read PROJECT_DOCUMENTATION.md. Propose a production-ready n8n workflow
JSON that matches section 14, and add n8n to docker-compose on the same
network. Do not invent Gmail credentials.
```

```
Read PROJECT_DOCUMENTATION.md section 16. Implement P0 only.
Keep the current dashboard UI.
```

---

## 19. Quick test without Gmail

Flask:

```powershell
curl http://localhost:5000/health
```

```powershell
curl -X POST http://localhost:5000/classify_email -H "Content-Type: application/json" -d "{\"body\": \"Hi, we want a paid collab and sponsorship for our brand launch\"}"
```

Django incoming:

```powershell
curl -X POST http://localhost:8000/save-email/ -H "Content-Type: application/json" -d "{\"thread_id\": \"test-thread-1\", \"subject\": \"Collab\", \"body\": \"We can offer 3500 for one reel\", \"from_email\": \"brand@test.com\", \"to_email\": \"creator@test.com\", \"direction\": \"INCOMING\"}"
```

Expect `201`, a `deal_id`, and `ai_reply`. Then open `/dashboard/` after login.

Outgoing:

```powershell
curl -X POST http://localhost:8000/save-email/ -H "Content-Type: application/json" -d "{\"thread_id\": \"test-thread-1\", \"subject\": \"Re: Collab\", \"body\": \"Thanks, our rate starts at 5000\", \"from_email\": \"creator@test.com\", \"to_email\": \"brand@test.com\", \"direction\": \"OUTGOING\"}"
```

Expect `deal_status` = `WAITING_FOR_CLIENT`.

Check thread:

```powershell
curl "http://localhost:8000/deals/check/?thread_id=test-thread-1"
```

---

## 20. One-page mental model

```
Gmail in → n8n → classify (Flask)
                 → save INCOMING (Django) → generate reply (Flask)
                 → send Gmail (n8n) → save OUTGOING (Django)
                 → repeat until ready_to_close
                 → human Accept/Reject (Django)
                 → closing letter (Flask) → webhook (n8n) → Gmail out
                 → Deal COMPLETED or REJECTED
```

That is the entire product.

---

**For humans:** start with section 4 (run) and section 5 (flow).  
**For agents:** start with sections 2, 8–11, 16–18, then edit code and update this file.
