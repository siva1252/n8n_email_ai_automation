# Email AI Automation

Local influencer/creator Gmail deal desk: **n8n** watches Gmail, **Django** stores every thread as one Deal, **Flask** runs a local-first AI gateway (Ollama, then optional free-tier open-weight fallbacks), and a dashboard lets the creator accept or reject.

## What you get

- Layered spam/security (Gmail signals + rules + AI). AI outages go to **REVIEW**, never silent spam.
- Intent, lead extraction, RAG-grounded negotiation.
- Human queue when a call is requested or rounds run out.
- Demo fixtures so the dashboard is usable without a live mailbox.
- Versioned n8n workflows in `n8n/workflows/`.

## URLs

| Service | URL |
| --- | --- |
| Django dashboard | http://localhost:8000 |
| Flask AI health | http://localhost:5000/health |
| n8n | http://localhost:5678 |

Local demo login (from `.env`): `admin` / `DemoAdmin123!`

## Prerequisites

- Docker Desktop
- Ollama on the host (`ollama list` should work). This laptop already had `phi3:latest`. Preferred small model is `qwen3.5:2b` if RAM allows; the gateway falls back to whatever is installed.
- Google OAuth client for Gmail (used inside n8n, not hard-coded in git)

## Start

```powershell
copy .env.example .env
# fill GOOGLE_CLIENT_ID / SECRET and any optional provider keys
docker compose up --build
```

First boot runs migrations, creates the admin user, and loads `demo_data/`.

Optional n8n import after n8n is healthy:

```powershell
python scripts/import_n8n_workflows.py
```

Then in n8n: create a Gmail OAuth2 credential with the Google client id/secret, add redirect URI `http://localhost:5678/rest/oauth2-credential/callback` in Google Cloud Console, attach it to the Gmail nodes, and activate the workflows.

## AI models (0-credit / open-weight)

| Priority | Provider | Model route | Key |
| --- | --- | --- | --- |
| 1 | Ollama (local) | `qwen3.5:2b` or installed fallback `phi3` | none |
| 2 | Mistral | `open-mistral-nemo` | `MISTRAL_API_KEY` |
| 3 | Groq | `openai/gpt-oss-20b` | `GROQ_API_KEY` |
| 4 | Cerebras | `llama3.1-8b` | `CEREBRAS_API_KEY` |
| 5 | OpenRouter | `openrouter/free` only | `OPENROUTER_API_KEY` |

No paid proprietary models are configured. Missing keys are skipped. `creditinals.md` was empty in this workspace, so only Ollama runs until keys are added.

## How to know if it is working

One command. Stack must already be up (`docker compose up` or the local Django/Flask/n8n processes).

```powershell
python scripts/verify_everything.py
```

That is the proper check. It reports PASS/FAIL for:

1. Flask, Django, n8n health (and ingest without a key is rejected)
2. Unit tests (`pytest` with `AI_MOCK=true`)
3. Dashboard login plus demo inbox / spam / human-queue mail
4. New inbound test mails appearing in Inbox and Dashboard
5. **Accept** and **Reject** from the deal page, including the closing email on the Done page
6. n8n `ingest-email` and `deal-action` automations

`OVERALL: WORKING` and exit code 0 means the product path is up. `OVERALL: NOT WORKING` means at least one required check failed — read the `[FAIL]` lines.

Optional real Gmail (needs n8n Gmail OAuth already connected). If Gmail is not connected, that check is skipped — it does not mark the stack as broken:

```powershell
python scripts/verify_everything.py --gmail
```

Unit tests only:

```powershell
pip install -r requirements.txt
$env:AI_MOCK="true"
pytest
```

## Demo without Gmail

Dashboard already has sample deals after `load_demo`. You can also POST a fake inbound message:

```powershell
curl -X POST http://localhost:8000/api/emails/ingest/ -H "Content-Type: application/json" -H "X-Internal-API-Key: YOUR_INTERNAL_API_KEY" -d "{\"thread_id\":\"demo-live-1\",\"gmail_message_id\":\"demo-live-1-m0\",\"subject\":\"Collab\",\"body\":\"Hi, we want a paid reel collaboration. Budget 3500.\",\"from_email\":\"brand@example.com\",\"to_email\":\"creator@example.com\",\"direction\":\"INCOMING\"}"
```

That does **not** send Gmail.

## Postgres later

Set `DATABASE_URL=postgres://user:pass@host:5432/dbname`. Schema is Django-managed, not SQLite-specific.

More detail: [IMPLEMENTATION_AND_DEMO.md](IMPLEMENTATION_AND_DEMO.md) and [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).
