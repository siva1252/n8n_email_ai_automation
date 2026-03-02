from django.db import models


class Client(models.Model):
    email = models.EmailField(unique=True)
    brand_name = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.brand_name or self.email


class Deal(models.Model):
    STATUS_CHOICES = [
        ("NEW", "New"),
        ("WAITING_FOR_CLIENT", "Waiting for Client"),
        ("PENDING_CREATOR", "Pending Creator Decision"),
        ("COMPLETED", "Completed"),
        ("REJECTED", "Rejected"),
        ("AUTO_REJECTED", "Auto Rejected"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    thread_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="NEW")

    ai_generated_reply = models.TextField(blank=True, null=True)

    our_reply_sent_at = models.DateTimeField(blank=True, null=True)
    client_replied_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client.email} - {self.subject}"


class EmailMessage(models.Model):
    DIRECTION_CHOICES = [
        ("INCOMING", "Incoming"),
        ("OUTGOING", "Outgoing"),
    ]

    deal = models.ForeignKey(
        Deal,
        related_name="emails",
        on_delete=models.CASCADE
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    subject = models.CharField(max_length=255, default='')
    body = models.TextField()

    from_email = models.EmailField()
    to_email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.direction} - Deal {self.deal.id}"
