from celery import Celery

from queueboard.config import get_settings

settings = get_settings()

celery_app = Celery(
    "queueboard",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["queueboard.tasks"],
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
)
