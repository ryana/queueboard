from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from queueboard.api import get_item_or_404
from queueboard.database import get_db
from queueboard.markdown import render_markdown
from queueboard.models import WorkItem
from queueboard.schemas import Priority, WorkStatus
from queueboard.tasks import record_activity

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: DatabaseSession) -> HTMLResponse:
    items = list(session.scalars(select(WorkItem).order_by(WorkItem.created_at.desc())))
    counts = {
        row.status: row.count
        for row in session.execute(
            select(WorkItem.status, func.count(WorkItem.id).label("count")).group_by(
                WorkItem.status
            )
        )
    }
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"items": items, "counts": counts},
    )


@router.post("/work-items")
def create_work_item(
    session: DatabaseSession,
    title: Annotated[str, Form(min_length=1, max_length=160)],
    description: Annotated[str, Form(max_length=5000)] = "",
    priority: Annotated[Priority, Form()] = Priority.MEDIUM,
) -> RedirectResponse:
    item = WorkItem(title=title.strip(), description=description.strip(), priority=priority.value)
    session.add(item)
    session.commit()
    session.refresh(item)
    record_activity.delay(item.id, "Work item created")
    return RedirectResponse(url=f"/work-items/{item.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/work-items/{work_item_id}", response_class=HTMLResponse)
def work_item_detail(work_item_id: int, request: Request, session: DatabaseSession) -> HTMLResponse:
    item = session.scalar(
        select(WorkItem)
        .options(selectinload(WorkItem.activities))
        .where(WorkItem.id == work_item_id)
    )
    if item is None:
        get_item_or_404(session, work_item_id)
        raise AssertionError("unreachable")
    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "item": item,
            "rendered_description": render_markdown(item.description),
            "statuses": WorkStatus,
            "priorities": Priority,
        },
    )


@router.post("/work-items/{work_item_id}")
def update_work_item(
    work_item_id: int,
    session: DatabaseSession,
    title: Annotated[str, Form(min_length=1, max_length=160)],
    description: Annotated[str, Form(max_length=5000)] = "",
    item_status: Annotated[WorkStatus, Form(alias="status")] = WorkStatus.TODO,
    priority: Annotated[Priority, Form()] = Priority.MEDIUM,
) -> RedirectResponse:
    item = get_item_or_404(session, work_item_id)
    item.title = title.strip()
    item.description = description.strip()
    item.status = item_status.value
    item.priority = priority.value
    session.commit()
    record_activity.delay(item.id, "Work item updated")
    return RedirectResponse(url=f"/work-items/{item.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/work-items/{work_item_id}/delete")
def delete_work_item(work_item_id: int, session: DatabaseSession) -> RedirectResponse:
    item = get_item_or_404(session, work_item_id)
    session.delete(item)
    session.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
