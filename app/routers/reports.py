from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import Monday, WeeklyReport
from app.services.report_service import generate_weekly_report

router = APIRouter(prefix="/users/{user_id}", tags=["reports"])


@router.get("/weekly-report", response_model=WeeklyReport)
def get_weekly_report(
    user_id: int,
    week_start: Annotated[Monday, Query(le=date.max - timedelta(days=6))],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return generate_weekly_report(db, user, week_start)
