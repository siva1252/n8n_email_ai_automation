# Email AI Automation (n8n + Django + Flask)

Local stack for email deal negotiation: **n8n** orchestrates Gmail flows, **Flask** classifies/replies with Sarvam AI, **Django** stores deals and serves the dashboard.

## Project structure

```
N8n_email_ai_automation/
├── backend/                 # Django API + deals dashboard
│   ├── backend/             # Django project settings
│   ├── deals/               # App (models, views, templates)
│   └── manage.py
├── flask_ai/                # AI microservice (Sarvam)
│   └── app.py
├── docs/                    # API & system documentation
├── docker-compose.yml       # Django + Flask services
├── Dockerfile.django
├── Dockerfile.flask
├── requirements.txt         # Full project dependencies
├── .env.example             # Copy to .env and fill values
└── .env                     # Local secrets (not committed)
```

## Quick start

1. Copy env file:
   ```powershell
   copy .env.example .env
   ```
2. Set `SARVAM_API_KEY` (and other values) in `.env`.
3. Start Django + Flask:
   ```powershell
   docker compose up --build
   ```
4. Start n8n (separate container with persistent volume):
   ```powershell
   docker start n8n
   ```
   If the container was removed:
   ```powershell
   docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
   ```

| Service | URL |
|---------|-----|
| Django dashboard | http://localhost:8000 |
| Flask AI | http://localhost:5000 |
| n8n | http://localhost:5678 |

## Docs

- [API documentation](docs/DJANGO_API_DOCUMENTATION.md)
- [Complete system docs](docs/DJANGO_COMPLETE_DOCUMENTATION.md)
- [Email negotiation flow](docs/EMAIL_NEGOTIATION_SYSTEM.md)
- [Dashboard setup](docs/DASHBOARD_SETUP.md)
