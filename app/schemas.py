from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import DecisionAction, RequestStatus, SourceType


class ApprovalRequestCreate(BaseModel):
    sourceType: SourceType
    sourceId: str
    title: str
    description: Optional[str] = None
    reviewerUserIds: list[str] = Field(min_length=1)


class DecisionOut(BaseModel):
    action: DecisionAction
    actorUserId: str
    comment: Optional[str] = None
    reason: Optional[str] = None
    decidedAt: datetime


class ApprovalRequestOut(BaseModel):
    id: str
    workspaceId: str
    sourceType: SourceType
    sourceId: str
    title: str
    description: Optional[str] = None
    reviewerUserIds: list[str]
    status: RequestStatus
    createdBy: str
    createdAt: datetime
    updatedAt: datetime
    decision: Optional[DecisionOut] = None


class ApproveBody(BaseModel):
    comment: Optional[str] = None


class RejectBody(BaseModel):
    reason: str


class CancelBody(BaseModel):
    reason: str
