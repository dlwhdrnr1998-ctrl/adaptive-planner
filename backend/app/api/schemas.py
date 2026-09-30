from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


FrequencyType = Literal["daily", "weekly", "biweekly", "monthly"]
TaskStatus = Literal["pending", "completed", "partial", "failed", "cancelled"]
ProgressResult = Literal["completed", "partial", "failed"]
ProjectStatus = Literal["planned", "active", "paused", "completed", "archived"]


class RoutineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = "general"
    description: str = ""
    frequency_type: FrequencyType = "weekly"
    frequency_interval: int = Field(1, ge=1)
    target_count: int = Field(1, ge=0)
    preferred_weekdays: list[int] = Field(default_factory=list)
    default_duration_minutes: int = Field(gt=0)
    min_duration_minutes: int = Field(gt=0)
    max_duration_minutes: int = Field(gt=0)
    default_target_value: float | None = Field(None, ge=0)
    default_target_unit: str | None = None
    priority: int = Field(50, ge=0, le=100)
    active: bool = True
    active_from: date | None = None
    active_until: date | None = None

    @model_validator(mode="after")
    def validate_duration_and_weekdays(self):
        if self.min_duration_minutes > self.default_duration_minutes:
            raise ValueError("minimum duration cannot exceed default duration")
        if self.default_duration_minutes > self.max_duration_minutes:
            raise ValueError("default duration cannot exceed maximum duration")
        if any(day < 0 or day > 6 for day in self.preferred_weekdays):
            raise ValueError("weekdays must be between 0 (Monday) and 6 (Sunday)")
        return self


class RoutineUpdate(RoutineCreate):
    pass


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    deadline: date | None = None
    status: ProjectStatus = "active"
    priority: int = Field(50, ge=0, le=100)
    next_action: str = ""
    estimated_remaining_minutes: int | None = Field(None, ge=0)
    weekly_target_minutes: int | None = Field(None, ge=0)


class ProjectUpdate(ProjectCreate):
    pass


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    scheduled_date: date
    expected_minutes: int = Field(gt=0)
    target_value: float | None = Field(None, ge=0)
    target_unit: str | None = None
    detail: str = ""
    priority: int = Field(50, ge=0, le=100)
    routine_id: int | None = None
    project_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=160)
    scheduled_date: date | None = None
    expected_minutes: int | None = Field(None, gt=0)
    target_value: float | None = Field(None, ge=0)
    target_unit: str | None = None
    detail: str | None = None
    status: TaskStatus | None = None
    priority: int | None = Field(None, ge=0, le=100)
    confirm_reschedule: bool = False


class ProgressCreate(BaseModel):
    task_id: int
    actual_minutes: int = Field(ge=0)
    actual_value: float | None = Field(None, ge=0)
    result: ProgressResult
    memo: str | None = None


class InboxCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class InboxProcess(BaseModel):
    linked_task_id: int | None = None
    linked_routine_id: int | None = None
    linked_project_id: int | None = None


class CapacityUpdate(BaseModel):
    available_minutes: int = Field(ge=0)
    note: str | None = None


class ReviewItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    routine_id: int | None = None
    project_id: int | None = None
    first_learned_on: date
    last_reviewed_on: date | None = None
    review_interval_days: int = Field(gt=0)
    next_review_on: date
    expected_minutes: int = Field(30, gt=0)
    active: bool = True


class ResourceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=40)
    url: str | None = None
    location_note: str | None = None
    routine_id: int | None = None
    project_id: int | None = None
    review_item_id: int | None = None

    @model_validator(mode="after")
    def validate_owner(self):
        owners = [self.routine_id, self.project_id, self.review_item_id]
        if sum(owner is not None for owner in owners) != 1:
            raise ValueError("resource must belong to exactly one item")
        return self


class SettingsUpdate(BaseModel):
    vision_text: str | None = Field(None, max_length=300)
    capacity_ratio: float | None = Field(None, gt=0, le=1)
    default_available_minutes: int | None = Field(None, ge=0)
