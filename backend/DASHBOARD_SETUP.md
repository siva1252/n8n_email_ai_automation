# Django Client Dashboard - Setup Guide

## Overview
This Django dashboard allows influencers to manage brand collaboration emails. It provides a clean interface to view deals, review AI-generated replies, and accept/reject collaboration offers.

## Features
- **Dashboard View**: List all deals with status badges
- **Deal Detail**: View email conversation and AI-generated reply
- **Accept/Reject**: Make decisions on pending deals
- **Authentication**: Secure login/logout functionality
- **Webhook Integration**: Triggers n8n webhooks when deals are accepted/rejected

## Setup Instructions


###1. Install Dependencies
```bash
pip install -r requirements.txt
```

###2. Create Database Migrations
```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```


###3. Create a Superuser (for admin access)
```bash
python manage.py createsuperuser
```


###4. Configure n8n Webhook URL
Edit `backend/backend/settings.py` and set:
```python
N8N_WEBHOOK_URL = 'https://your-n8n-instance.com/webhook/deal-action'
```


### 5. Run the Development Server
```bash
python manage.py runserver
```


The dashboard will be available at:
- Dashboard: http://localhost:8000/dashboard/
- Login: http://localhost:8000/login/
- Admin: http://localhost:8000/admin/

## Usage


### Accessing the Dashboard
1. Navigate to http://localhost:8000/login/
2. Login with your Django user credentials
3. You'll be redirected to the dashboard showing all deals


### Viewing Deal Details
1. Click "View Details" on any deal from the dashboard
2. The detail page shows:
   - Email conversation history (left side)
   - AI-generated reply (right side, editable)
   - Accept/Reject buttons (if status is "Pending Creator Decision")


### Accepting/Rejecting Deals
1. Navigate to a deal detail page
2. Review the AI-generated reply (edit if needed)
3. Click "Save Reply" to update the reply
4. Click "Accept Deal" or "Reject Deal" to make your decision
5. The system will:
   - Update the deal status in the database
   - Trigger a webhook to n8n (if configured)
   - n8n will handle sending the email response


## Status Types
- **New**: Deal just created
- **Waiting for Client**: Awaiting client response
- **Pending Creator Decision**: Ready for accept/reject action
- **Completed**: Deal accepted
- **Rejected**: Deal rejected
- **Auto Rejected**: Automatically rejected by system


## Architecture
- **Django**: Server-rendered templates (no React/frontend framework)
- **Database**: SQLite (can be changed to PostgreSQL/MySQL in production)
- **Authentication**: Django's built-in authentication system
- **Webhooks**: HTTP POST requests to n8n when deals are accepted/rejected



## API Endpoints

- `POST /api/save-email/` - Save incoming email (used by n8n)
- `GET /dashboard/` - Main dashboard (requires login)
- `GET /deal/<id>/` - Deal detail page (requires login)
- `POST /deal/<id>/accept/` - Accept deal (requires login)
- `POST /deal/<id>/reject/` - Reject deal (requires login)
- `POST /deal/<id>/update-reply/` - Update AI reply (requires login)
- `GET /login/` - Login page
- `POST /login/` - Login submission
- `GET /logout/` - Logout




## Notes
- All dashboard views require authentication
- The system uses Django's template system (no REST APIs for frontend)
- Webhook calls to n8n are non-blocking (errors are logged but don't fail the request)
- The AI-generated reply field can be edited before accepting/rejecting

