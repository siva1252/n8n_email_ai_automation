# Email AI Automation — current architecture

Single source of truth for agents. UI and setup: [README.md](README.md). Demo script: [IMPLEMENTATION_AND_DEMO.md](IMPLEMENTATION_AND_DEMO.md). The Word spec `INFLUENCER_EMAIL_AI_MASTER_CURSOR_SPEC.docx` is the acceptance contract.

| Item | Value |
|------|--------|
| Stack | Gmail → n8n → Django (SQLite) + Flask AI gateway → Ollama / optional free open-weight APIs |
| Rule | 1 Gmail `thread_id` = 1 Deal |
| AI | Ollama primary, then Mistral → Groq → Cerebras → OpenRouter `openrouter/free` |
| Auth | Django session for UI; `X-Internal-API-Key` for n8n write APIs |

## Pipeline

Inbound Gmail (or demo POST) → normalize → persist EmailMessage (idempotent on `gmail_message_id`) → spam/security → if NOT_SPAM: intent + extract + RAG negotiation → n8n sends only when `send_reply` is true → outgoing persisted. HUMAN_REQUIRED / REVIEW / SPAM do not auto-send. Accept/Reject are creator actions; Django stores the closing letter and webhooks n8n.

AI provider failure **never** becomes SPAM; status is REVIEW / HUMAN_REVIEW.

## Services

| Service | Host | Compose DNS |
|---------|------|-------------|
| Django | http://localhost:8000 | `django_backend:8000` |
| Flask | http://localhost:5000 | `flask_ai:5000` |
| n8n | http://localhost:5678 | `n8n:5678` |
| Ollama | host :11434 | `host.docker.internal:11434` |

## Main APIs

- `POST /api/emails/ingest/` — n8n ingest (internal key)
- `GET /api/deals/` and `GET /api/deals/<id>/` — session
- `POST /api/deals/<id>/accept|reject|human-action/` — session
- `POST /api/ai/reprocess/` — internal key
- `GET /health/` and `GET /api/ai/health/`

## Dashboard routes

`/dashboard/` `/inbox/` `/human-queue/` `/spam/` `/completed/` `/deal/<id>/`

## Do not

- Commit `.env`, Google client JSON, or API keys
- Treat `docs/` as current (stale)
- Auto-send on HUMAN_REQUIRED or REVIEW
- Invent missing phone/budget
