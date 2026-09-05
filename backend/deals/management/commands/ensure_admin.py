from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
import os


class Command(BaseCommand):
    help = "Create or update the demo admin user from environment variables."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("DJANGO_ADMIN_USER", "admin")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "DemoAdmin123!")
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "admin@localhost")
        user, created = User.objects.get_or_create(username=username, defaults={"email": email, "is_staff": True, "is_superuser": True})
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} admin user '{username}'"))
