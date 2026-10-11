"""Validated input and ORM-compatible output schemas."""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import WorkItemStatus


def require_monday(value: date) -> date:
    if value.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    return value


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Monday = Annotated[date, AfterValidator(require_monday)]


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime


class WorkItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Name
    description: str = ""
    category: Category
    status: WorkItemStatus = WorkItemStatus.pending
    week_start: Monday


class WorkItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Name | None = None
    description: str | None = None
    category: Category | None = None
    status: WorkItemStatus | None = None
    week_start: Monday | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class WorkItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    title: str
    description: str
    category: str
    status: WorkItemStatus
    week_start: date
    created_at: datetime
    updated_at: datetime


class WeeklyReport(BaseModel):
    user_id: int
    user_name: str
    week_start: date
    week_end: date
    total_items: int
    completed_count: int
    in_progress_count: int
    pending_count: int
    completion_percentage: float
    items_by_category: dict[str, list[WorkItemRead]]
