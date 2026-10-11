"""Build a live report from the requested user's work items without writes."""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, WorkItem, WorkItemStatus
from app.schemas import WeeklyReport, WorkItemRead


def generate_weekly_report(db: Session, user: User, week_start: date) -> WeeklyReport:
    items = db.scalars(
        select(WorkItem)
        .where(WorkItem.user_id == user.id, WorkItem.week_start == week_start)
        .order_by(WorkItem.category, WorkItem.id)
    ).all()
    counts = Counter(item.status for item in items)
    grouped: dict[str, list[WorkItemRead]] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(WorkItemRead.model_validate(item))

    total = len(items)
    completed = counts[WorkItemStatus.completed]
    return WeeklyReport(
        user_id=user.id,
        user_name=user.name,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        total_items=total,
        completed_count=completed,
        in_progress_count=counts[WorkItemStatus.in_progress],
        pending_count=counts[WorkItemStatus.pending],
        completion_percentage=round(completed / total * 100, 2) if total else 0,
        items_by_category=grouped,
    )
