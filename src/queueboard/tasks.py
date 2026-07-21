from typing import Protocol, cast

from sqlalchemy import select

from queueboard.celery_app import celery_app
from queueboard.database import SessionLocal
from queueboard.models import Activity, WorkItem


class ActivityTask(Protocol):
    def delay(self, work_item_id: int, message: str) -> object: ...


def _record_activity(work_item_id: int, message: str) -> None:
    """Persist an activity emitted by a web request in the worker process."""
    with SessionLocal.begin() as session:
        item = session.scalar(select(WorkItem).where(WorkItem.id == work_item_id))
        if item is None:
            return
        session.add(Activity(work_item_id=work_item_id, message=message))


record_activity = cast(
    ActivityTask, celery_app.task(name="queueboard.record_activity")(_record_activity)
)
