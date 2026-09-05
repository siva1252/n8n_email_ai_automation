# Implementation and demo handoff

This is what was implemented against `INFLUENCER_EMAIL_AI_MASTER_CURSOR_SPEC.docx`, plus how to demo it tomorrow.

## What changed

The old Sarvam-only Flask service is replaced by a **stateless AI gateway** with provider fallback:

Ollama (local, no key) → Mistral → Groq → Cerebras → OpenRouter `openrouter/free`.

Django is now the system of record for Clients, Deals, EmailMessages, AIInteraction, NegotiationTurn, and HumanAction. n8n is in Docker Compose. RAG documents live in `rag_data/` (placeholder rates). n8n workflows are versioned under `n8n/workflows/`.

Known gaps from the previous project that this upgrade addresses: env-driven Django settings, Flask URL `http://flask_ai:5000`, internal API key on write endpoints, Client identity from the brand (not the creator on outgoing), AI failures → REVIEW (never silent spam), prices in RAG/config, demo fixtures, tests, n8n in compose, closing emails persisted.

## Credentials actually present

| Item | Status |
| --- | --- |
| `creditinals.md` | Empty file. No Mistral/Groq/Cerebras/OpenRouter keys were supplied. |
| Google OAuth client JSON | Loaded into local `.env` only (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`). Not committed. |
| Ollama | Installed. `phi3:latest` was already on disk. `qwen3.5:2b` was started as a pull (better spec match, ~2.7 GB). Gateway uses whichever model Ollama actually has. |

Hardware on this machine is about **8 GB RAM**, so the spec’s 4B candidate was not installed. 2B Qwen or existing Phi-3 is the local path.

## 0-credit / open-weight model research (used in code)

- **Primary:** Ollama local weights. No API bill. Candidates: `qwen3.5:2b` (this laptop), `qwen3.5:4b` (if you later have 16+ GB RAM), `phi3`.
- **Mistral:** `open-mistral-nemo` (open weights, Experiment/free plan if a key is added).
- **Groq:** `openai/gpt-oss-20b` (open-weight, free-tier rate limits, no credits system).
- **Cerebras:** `llama3.1-8b` (open-weight, free daily token grant if a key is added).
- **OpenRouter:** **only** `openrouter/free` (dynamic free-model router). Not treated as unlimited.

No GPT/Claude/Gemini paid routes are wired.

## Demo tomorrow (no live Gmail required)

1. Start Docker Desktop and Ollama.
2. From the repo: `docker compose up --build`
3. Open http://localhost:8000/login/  
   User: `admin`  
   Password: `DemoAdmin123!`
4. Walk the dashboard:
   - **Inbox:** Northline collab, Glowbar promo (phone left missing on purpose), Bean&Co negotiation.
   - **Human queue:** Harbor Media asked for a phone call — autonomous send stopped.
   - **Spam:** crypto prize phishing, with reason/confidence.
   - **Peak Athletics:** `PENDING_CREATOR` at INR 8000 — click **Accept** or **Reject**.
5. Show deal detail: thread, extracted lead, RAG fact ids, provider/model, notes box.
6. Optional: n8n at http://localhost:5678 — import `n8n/workflows/*.json` if they are not already imported (`python scripts/import_n8n_workflows.py`).

## Connecting real Gmail (after the demo, or if OAuth is ready)

Google Cloud must include this redirect URI (the downloaded client currently only had `http://localhost`):

`http://localhost:5678/rest/oauth2-credential/callback`

In n8n, create **Gmail OAuth2** credentials using the client id/secret from `.env`, complete the consent screen, attach the credential to Gmail Trigger / Gmail Send, then activate:

- Incoming Email Pipeline
- Deal Action Webhook

Django already posts Accept/Reject to `http://n8n:5678/webhook/deal-action` with `X-Internal-API-Key`.

## What was tested vs not tested

| Check | Actual result this session |
| --- | --- |
| Unit tests | **24 passed** (`python -m pytest`) |
| Flask `/health` | 200, primary Ollama, external keys not configured |
| Django `/health/` | 200 |
| n8n `/healthz` | 200 |
| Dashboard login + demo pages | Northline, Harbor human queue, spam prize, Peak Athletics all present |
| Ingest without API key | **401** |
| Ingest with key (`skip_ai`) | **201**, Deal created |
| Live Ollama classify | `phi3:latest` returned **NOT_SPAM** for a short collab email (~90s) |
| n8n workflow import | 3 workflows imported via CLI |
| `docker compose up --build` | Python 3.11 image pull was still in progress on a slow network; **n8n + Django + Flask were started locally** so the demo is not blocked |
| Live Gmail send/receive | **Not tested.** Add n8n OAuth redirect in Google Cloud, then attach Gmail credentials. |
| Mistral/Groq/Cerebras/OpenRouter | **Not called.** `creditinals.md` was empty. |

## Files to look at

| Area | Path |
| --- | --- |
| Flask gateway | `flask_ai/` |
| Ingest pipeline | `backend/deals/pipeline.py` |
| Dashboard | `backend/deals/templates/deals/` |
| n8n | `n8n/workflows/` |
| RAG placeholders | `rag_data/README.md` |
| Demo emails | `demo_data/` |
