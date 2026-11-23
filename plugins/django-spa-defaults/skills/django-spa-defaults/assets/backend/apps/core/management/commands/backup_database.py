"""Back up now, e.g. before an update: the database dump and, with uploads, a media archive.

    docker compose exec worker python manage.py backup_database

The worker does the same every night at ``BACKUP_TIME`` (``apps.core.tasks``).
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.services import backups


class Command(BaseCommand):
    help = (
        "Back up the database (and uploads) into BACKUP_DIR now"
        " and delete backups older than BACKUP_KEEP_DAYS."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        if not backups.available():
            raise CommandError(
                "Backups need PostgreSQL (DB_HOST); with SQLite copy the database file."
            )
        if not settings.BACKUP_DIR:
            raise CommandError("BACKUP_DIR is not set.")
        try:
            dump, media = backups.backup_all()
        except backups.BackupError as error:
            raise CommandError(f"backup failed: {error}") from error
        self.stdout.write(f"Database dumped to {dump}")
        self.stdout.write(
            f"Media archived to {media}" if media else "No uploaded media to archive."
        )
