from django.contrib import admin
from django.utils.html import format_html
from .models import Client, Deal, EmailMessage


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['email', 'brand_name', 'created_at', 'deal_count']
    list_filter = ['created_at']
    search_fields = ['email', 'brand_name']
    readonly_fields = ['created_at']
    
    def deal_count(self, obj):
        count = obj.deal_set.count()
        return count
    deal_count.short_description = 'Deals'


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ['id', 'client_email', 'subject', 'status_badge', 'thread_id', 'created_at', 'updated_at', 'email_count']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['subject', 'thread_id', 'client__email', 'client__brand_name']
    readonly_fields = ['created_at', 'updated_at', 'thread_id']
    fieldsets = (
        ('Deal Information', {
            'fields': ('client', 'thread_id', 'subject', 'status')
        }),
        ('AI Reply', {
            'fields': ('ai_generated_reply',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def client_email(self, obj):
        return obj.client.email
    client_email.short_description = 'Client Email'
    
    def status_badge(self, obj):
        colors = {
            'NEW': 'blue',
            'WAITING_FOR_CLIENT': 'yellow',
            'PENDING_CREATOR': 'purple',
            'COMPLETED': 'green',
            'REJECTED': 'red',
            'AUTO_REJECTED': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def email_count(self, obj):
        count = obj.emails.count()
        return count
    email_count.short_description = 'Emails'


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'deal_link', 'direction_badge', 'from_email', 'to_email', 'subject_preview', 'created_at']
    list_filter = ['direction', 'created_at', 'deal__status']
    search_fields = ['subject', 'body', 'from_email', 'to_email', 'deal__thread_id']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Email Information', {
            'fields': ('deal', 'direction', 'subject', 'from_email', 'to_email')
        }),
        ('Content', {
            'fields': ('body',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def deal_link(self, obj):
        return format_html(
            '<a href="/admin/deals/deal/{}/change/">{}</a>',
            obj.deal.id,
            f"Deal #{obj.deal.id} - {obj.deal.subject[:30]}..."
        )
    deal_link.short_description = 'Deal'
    
    def direction_badge(self, obj):
        color = 'blue' if obj.direction == 'INCOMING' else 'green'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_direction_display()
        )
    direction_badge.short_description = 'Direction'
    
    def subject_preview(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject
    subject_preview.short_description = 'Subject'


admin.site.site_header = "Deals Admin"
admin.site.site_title = "Deals Admin Portal"
admin.site.index_title = "Welcome to Deals Admin Portal"
