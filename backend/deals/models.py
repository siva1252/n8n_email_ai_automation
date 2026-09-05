from django.db import models
from django.conf import settings


class Client(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    brand_name = models.CharField(max_length=255, null=True, blank=True)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.brand_name or self.email


class Deal(models.Model):
    STATUS_CHOICES = [
        ("NEW", "New"),
        ("WAITING_FOR_CLIENT", "Waiting for Client"),
        ("PENDING_CREATOR", "Pending Creator Decision"),
        ("HUMAN_REQUIRED", "Human Required"),
        ("REVIEW", "Review"),
        ("NEED_INFORMATION", "Need Information"),
        ("SPAM", "Spam"),
        ("COMPLETED", "Completed"),
        ("REJECTED", "Rejected"),
        ("AUTO_REJECTED", "Auto Rejected"),
    ]
    PRIORITY_CHOICES = [
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
    ]
    TERMINAL_STATUSES = {"COMPLETED", "REJECTED", "AUTO_REJECTED"}

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    thread_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="NEW", db_index=True)
    intent = models.CharField(max_length=40, blank=True, default="")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="MEDIUM", db_index=True)
    spam_decision = models.CharField(max_length=20, blank=True, default="")
    confidence = models.FloatField(null=True, blank=True)
    budget_offered = models.FloatField(null=True, blank=True)
    currency = models.CharField(max_length=12, blank=True, default="")
    min_price = models.FloatField(null=True, blank=True)
    target_price = models.FloatField(null=True, blank=True)
    negotiation_round = models.PositiveIntegerField(default=0)
    human_required = models.BooleanField(default=False)
    human_required_reason = models.TextField(blank=True, default="")
    extracted_json = models.JSONField(default=dict, blank=True)
    rag_facts_json = models.JSONField(default=list, blank=True)
    ai_summary = models.TextField(blank=True, default="")
    ai_generated_reply = models.TextField(blank=True, null=True)
    last_ai_provider = models.CharField(max_length=40, blank=True, default="")
    last_ai_model = models.CharField(max_length=120, blank=True, default="")
    last_ai_decision = models.CharField(max_length=40, blank=True, default="")
    send_reply = models.BooleanField(default=False)
    our_reply_sent_at = models.DateTimeField(blank=True, null=True)
    client_replied_at = models.DateTimeField(blank=True, null=True)
    header_unseen = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["-updated_at"]),
            models.Index(fields=["header_unseen", "status"]),
        ]

    def __str__(self):
        return f"{self.client.email} - {self.subject}"

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    def mark_header_seen(self):
        if not self.header_unseen:
            return
        self.header_unseen = False
        self.save(update_fields=["header_unseen"])


class EmailMessage(models.Model):
    DIRECTION_CHOICES = [
        ("INCOMING", "Incoming"),
        ("OUTGOING", "Outgoing"),
    ]

    deal = models.ForeignKey(Deal, related_name="emails", on_delete=models.CASCADE)
    gmail_message_id = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    thread_id = models.CharField(max_length=255, db_index=True, blank=True, default="")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    subject = models.CharField(max_length=255, default="")
    body = models.TextField(blank=True, default="")
    body_text = models.TextField(blank=True, default="")
    body_html = models.TextField(blank=True, default="")
    from_email = models.EmailField()
    to_email = models.EmailField(blank=True, default="")
    reply_to = models.EmailField(blank=True, default="")
    headers_json = models.JSONField(default=dict, blank=True)
    labels_json = models.JSONField(default=list, blank=True)
    attachment_metadata_json = models.JSONField(default=list, blank=True)
    urls_json = models.JSONField(default=list, blank=True)
    idempotency_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.body_text and not self.body:
            self.body = self.body_text
        elif self.body and not self.body_text:
            self.body_text = self.body
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.direction} - Deal {self.deal_id}"


class AIInteraction(models.Model):
    deal = models.ForeignKey(Deal, related_name="ai_interactions", on_delete=models.CASCADE, null=True, blank=True)
    email = models.ForeignKey(EmailMessage, related_name="ai_interactions", on_delete=models.SET_NULL, null=True, blank=True)
    task = models.CharField(max_length=40)
    provider = models.CharField(max_length=40, blank=True, default="")
    model = models.CharField(max_length=120, blank=True, default="")
    prompt_version = models.CharField(max_length=40, blank=True, default="")
    success = models.BooleanField(default=True)
    confidence = models.FloatField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    error_type = models.CharField(max_length=80, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class NegotiationTurn(models.Model):
    deal = models.ForeignKey(Deal, related_name="negotiation_turns", on_delete=models.CASCADE)
    round = models.PositiveIntegerField(default=1)
    client_message = models.TextField(blank=True, default="")
    ai_reply = models.TextField(blank=True, default="")
    decision = models.CharField(max_length=40, blank=True, default="")
    offer_amount = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class HumanAction(models.Model):
    deal = models.ForeignKey(Deal, related_name="human_actions", on_delete=models.CASCADE)
    action = models.CharField(max_length=40)
    reason = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
