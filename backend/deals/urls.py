from django.urls import path
from django.shortcuts import redirect
from .views import (
    save_email, 
    dashboard, 
    deal_detail, 
    accept_deal, 
    reject_deal, 
    update_ai_reply,
    login_view,
    logout_view,
    save_dashboard_deal,
    check_deal_exists
)

def home(request):
    """Redirect to dashboard if authenticated, otherwise to login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


urlpatterns = [
    # Home page
    path("", home, name="home"),
    

    # API endpoints (under /api/)
    path("save-email/", save_email, name="save_email"),
    path("deals/check/", check_deal_exists, name="check_deal_exists"),
    

    # Dashboard views
    path("dashboard/", dashboard, name="dashboard"),
    path("deal/<int:deal_id>/", deal_detail, name="deal_detail"),
    path("deal/<int:deal_id>/accept/", accept_deal, name="accept_deal"),
    path("deal/<int:deal_id>/reject/", reject_deal, name="reject_deal"),
    path("deal/<int:deal_id>/update-reply/", update_ai_reply, name="update_ai_reply"),
    # urls.py
    path("api/dashboard/deal/", save_dashboard_deal, name="save_dashboard_deal"),

    
    
    
    # Authentication
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
]
