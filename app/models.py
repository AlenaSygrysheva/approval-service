import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Enum, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceType(str, PyEnum):
    publication = "publication"
    scenario = "scenario"
    edit = "edit"
    external = "external"


class RequestStatus(str, PyEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class DecisionAction(str, PyEnum):
    approve = "approve"
    reject = "reject"
    cancel = "cancel"


FINAL_STATUSES: frozenset[RequestStatus] = frozenset(
    {RequestStatus.approved, RequestStatus.rejected, RequestStatus.cancelled}
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_workspace_idempotency"),
        Index("ix_approval_requests_workspace_id", "workspace_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, native_enum=False), nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_user_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, native_enum=False), nullable=False, default=RequestStatus.pending
    )
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        "ApprovalDecision",
        back_populates="request",
        order_by="ApprovalDecision.created_at",
        lazy="select",
    )


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(
        String, ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    action: Mapped[DecisionAction] = mapped_column(Enum(DecisionAction, native_enum=False), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    request: Mapped["ApprovalRequest"] = relationship("ApprovalRequest", back_populates="decisions")
