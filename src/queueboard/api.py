from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from queueboard.bulk_csv import (
    MAX_UPLOAD_BYTES,
    csv_download_name,
    export_work_items_csv,
    import_result,
    import_work_items_csv,
)
from queueboard.database import get_db
from queueboard.models import WorkItem
from queueboard.schemas import WorkItemCreate, WorkItemDetail, WorkItemRead, WorkItemUpdate
from queueboard.tasks import record_activity

router = APIRouter(prefix="/api/work-items", tags=["work items"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_item_or_404(session: Session, work_item_id: int) -> WorkItem:
    item = session.scalar(
        select(WorkItem)
        .options(selectinload(WorkItem.activities))
        .where(WorkItem.id == work_item_id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    return item


@router.get("", response_model=list[WorkItemRead])
def list_work_items(
    session: DatabaseSession,
    item_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[WorkItem]:
    statement = select(WorkItem).order_by(WorkItem.created_at.desc()).limit(limit).offset(offset)
    if item_status is not None:
        statement = statement.where(WorkItem.status == item_status)
    return list(session.scalars(statement))


@router.post("", response_model=WorkItemRead, status_code=status.HTTP_201_CREATED)
def create_work_item(payload: WorkItemCreate, session: DatabaseSession) -> WorkItem:
    item = WorkItem(**payload.model_dump(mode="json"))
    session.add(item)
    session.commit()
    session.refresh(item)
    record_activity.delay(item.id, "Work item created")
    return item


@router.get("/export.csv", response_class=Response)
def export_work_items(session: DatabaseSession) -> Response:
    items = list(session.scalars(select(WorkItem).order_by(WorkItem.id)))
    return Response(
        content=export_work_items_csv(items),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{csv_download_name()}"'},
    )


@router.post("/import.csv", status_code=status.HTTP_201_CREATED, response_model=None)
async def import_work_items(
    session: DatabaseSession, upload: Annotated[UploadFile, File()]
) -> Response | dict[str, object]:
    contents = await upload.read(MAX_UPLOAD_BYTES + 1)
    items, errors = import_work_items_csv(session, contents)
    if errors:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors}
        )
    return import_result(items)


@router.get("/{work_item_id}", response_model=WorkItemDetail)
def get_work_item(work_item_id: int, session: DatabaseSession) -> WorkItem:
    return get_item_or_404(session, work_item_id)


@router.patch("/{work_item_id}", response_model=WorkItemRead)
def update_work_item(
    work_item_id: int, payload: WorkItemUpdate, session: DatabaseSession
) -> WorkItem:
    item = get_item_or_404(session, work_item_id)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    for field, value in changes.items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    if changes:
        record_activity.delay(item.id, f"Updated {', '.join(sorted(changes))}")
    return item


@router.delete("/{work_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_item(work_item_id: int, session: DatabaseSession) -> Response:
    item = get_item_or_404(session, work_item_id)
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
