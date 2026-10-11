from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, WorkItem, WorkItemStatus
from app.schemas import Category, Monday, WorkItemCreate, WorkItemRead, WorkItemUpdate

router = APIRouter(prefix="/users/{user_id}/work-items", tags=["work items"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def require_user(db: Session, user_id: int) -> None:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")


def require_item(db: Session, user_id: int, item_id: int) -> WorkItem:
    item = db.scalar(select(WorkItem).where(
        WorkItem.id == item_id, WorkItem.user_id == user_id,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return item


@router.post("", response_model=WorkItemRead, status_code=201)
def create_work_item(user_id: int, payload: WorkItemCreate, db: DatabaseSession):
    require_user(db, user_id)
    item = WorkItem(user_id=user_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[WorkItemRead])
def list_work_items(
    user_id: int,
    db: DatabaseSession,
    week_start: Monday | None = None,
    category: Category | None = None,
    status: WorkItemStatus | None = None,
):
    require_user(db, user_id)
    query = select(WorkItem).where(WorkItem.user_id == user_id)
    if week_start is not None:
        query = query.where(WorkItem.week_start == week_start)
    if category is not None:
        query = query.where(WorkItem.category == category)
    if status is not None:
        query = query.where(WorkItem.status == status)
    return db.scalars(query.order_by(WorkItem.id)).all()


@router.get("/{item_id}", response_model=WorkItemRead)
def get_work_item(user_id: int, item_id: int, db: DatabaseSession):
    return require_item(db, user_id, item_id)


@router.patch("/{item_id}", response_model=WorkItemRead)
def update_work_item(
    user_id: int, item_id: int, payload: WorkItemUpdate, db: DatabaseSession,
):
    item = require_item(db, user_id, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_work_item(user_id: int, item_id: int, db: DatabaseSession):
    item = require_item(db, user_id, item_id)
    db.delete(item)
    db.commit()
    return Response(status_code=204)
