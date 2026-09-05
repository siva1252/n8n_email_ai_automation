from django.contrib import admin

from .models import AIInteraction, Client, Deal, EmailMessage, HumanAction, NegotiationTurn


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["email", "brand_name", "contact_name", "phone", "created_at"]
    search_fields = ["email", "brand_name", "contact_name"]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "status", "priority", "intent", "thread_id", "updated_at"]
    list_filter = ["status", "priority", "intent"]
    search_fields = ["subject", "thread_id", "client__email"]


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "deal", "direction", "from_email", "gmail_message_id", "created_at"]
    search_fields = ["subject", "body", "gmail_message_id", "thread_id"]


@admin.register(AIInteraction)
class AIInteractionAdmin(admin.ModelAdmin):
    list_display = ["id", "deal", "task", "provider", "model", "success", "created_at"]
    list_filter = ["task", "provider", "success"]


@admin.register(NegotiationTurn)
class NegotiationTurnAdmin(admin.ModelAdmin):
    list_display = ["id", "deal", "round", "decision", "offer_amount", "created_at"]


@admin.register(HumanAction)
class HumanActionAdmin(admin.ModelAdmin):
    list_display = ["id", "deal", "action", "user", "created_at"]


admin.site.site_header = "Creator Deals Admin"
admin.site.site_title = "Deals Admin"
admin.site.index_title = "Deals"
