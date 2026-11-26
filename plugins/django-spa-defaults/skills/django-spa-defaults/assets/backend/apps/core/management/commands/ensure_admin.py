"""Create the first administrator from ADMIN_* env vars if that user does not exist yet.

Runs on every container start; it never touches an existing user, so changing
ADMIN_PASSWORD later has no effect (use `manage.py set_password <username>`).
Defaults: admin / admin@example.com / administrator; ADMIN_USERNAME set empty skips it.
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from config.env import INSECURE_SECRET_VALUES


class Command(BaseCommand):
    help = "Create the initial superuser from ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin").strip()
        if not username:
            self.stdout.write("ADMIN_USERNAME not set, skipping admin creation.")
            return

        User = get_user_model()
        # Case-insensitive like the unique constraint: ADMIN_USERNAME=Admin finds "admin".
        if User.objects.filter(**{f"{User.USERNAME_FIELD}__iexact": username}).exists():
            self.stdout.write(f"Admin user {username!r} already exists.")
            return

        password = os.environ.get("ADMIN_PASSWORD", "administrator")
        if password in INSECURE_SECRET_VALUES and not settings.DEBUG:
            raise CommandError("Set ADMIN_PASSWORD to a real password before the first start.")

        User.objects.create_superuser(
            **{User.USERNAME_FIELD: username},
            email=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created admin user {username!r}."))
