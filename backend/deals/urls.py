from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("inbox/", views.inbox, name="inbox"),
    path("spam/", views.spam_box, name="spam_box"),
    path("human-queue/", views.human_queue, name="human_queue"),
    path("completed/", views.completed_box, name="completed_box"),
    path("deal/<int:deal_id>/", views.deal_detail, name="deal_detail"),
    path("deal/<int:deal_id>/update-reply/", views.update_ai_reply, name="update_ai_reply"),
    path("deal/<int:deal_id>/accept/", views.accept_deal, name="accept_deal"),
    path("deal/<int:deal_id>/reject/", views.reject_deal, name="reject_deal"),
    path("deal/<int:deal_id>/human-action/", views.human_action, name="human_action"),
    path("deal/<int:deal_id>/reclassify/", views.reclassify_deal, name="reclassify_deal"),
    path("save-email/", views.save_email, name="save_email"),
    path("deals/check/", views.check_deal_exists, name="check_deal_exists"),
    path("api/emails/ingest/", views.ingest_api, name="ingest_api"),
    path("api/deals/", views.api_deal_list, name="api_deal_list"),
    path("api/deals/<int:deal_id>/", views.api_deal_detail, name="api_deal_detail"),
    path("api/deals/<int:deal_id>/accept/", views.api_accept, name="api_accept"),
    path("api/deals/<int:deal_id>/reject/", views.api_reject, name="api_reject"),
    path("api/deals/<int:deal_id>/human-action/", views.api_human_action, name="api_human_action"),
    path("api/ai/reprocess/", views.api_reprocess, name="api_reprocess"),
    path("api/ai/health/", views.ai_health, name="ai_health"),
    path("api/dashboard/deal/", views.save_dashboard_deal, name="save_dashboard_deal"),
]
