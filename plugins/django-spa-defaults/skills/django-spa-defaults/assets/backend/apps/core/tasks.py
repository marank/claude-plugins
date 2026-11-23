"""Background jobs, run by ``manage.py procrastinate worker`` (the worker container).

Defer jobs from services inside the transaction that causes them, always through
``apps.core.jobs.defer(some_task, ...)``: with PostgreSQL the job exists only once the
change is committed; with SQLite (native development) it runs in-process after the
commit. Mails and other side effects go through here, never straight from a request.
The periodic jobs below only run where there is a worker, i.e. with PostgreSQL.
"""

from datetime import UTC, datetime

from django.conf import settings
from django.utils import timezone
from procrastinate import JobContext
from procrastinate.contrib.django import app

from apps.core.services import backups


@app.periodic(cron=f"{settings.BACKUP_TIME.minute} * * * *")
@app.task(queueing_lock="backup_database")
def backup_database(timestamp: int) -> None:
    """Daily at ``BACKUP_TIME``. Procrastinate's cron runs in UTC, so this job comes every
    hour and dumps only in the hour that is ``BACKUP_TIME``'s hour in ``TIME_ZONE``."""
    scheduled = timezone.localtime(datetime.fromtimestamp(timestamp, UTC))
    if settings.BACKUP_DIR and scheduled.hour == settings.BACKUP_TIME.hour:
        backups.backup_all()


@app.periodic(cron="30 3 * * *")
@app.task(pass_context=True)
async def remove_old_jobs(context: JobContext, timestamp: int) -> None:
    """Finished jobs may hold recipients and texts; keep them only briefly."""
    manager = context.app.job_manager
    await manager.delete_old_jobs(nb_hours=24)
    await manager.delete_old_jobs(
        nb_hours=14 * 24, include_failed=True, include_cancelled=True, include_aborted=True
    )
