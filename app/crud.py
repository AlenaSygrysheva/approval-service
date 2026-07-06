from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.events import publish_event


def create_approval_request(
    db: Session,
    workspace_id: str,
    data: schemas.ApprovalRequestCreate,
    created_by: str,
    idempotency_key: str | None,
) -> tuple[models.ApprovalRequest, bool]:
    """Return (request, created). created=False means idempotent replay."""
    if idempotency_key:
        existing = (
            db.query(models.ApprovalRequest)
            .filter_by(workspace_id=workspace_id, idempotency_key=idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    request = models.ApprovalRequest(
        workspace_id=workspace_id,
        source_type=models.SourceType(data.sourceType),
        source_id=data.sourceId,
        title=data.title,
        description=data.description,
        reviewer_user_ids=data.reviewerUserIds,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    db.add(request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(models.ApprovalRequest)
            .filter_by(workspace_id=workspace_id, idempotency_key=idempotency_key)
            .first()
        )
        return existing, False

    db.refresh(request)
    publish_event(
        "approval_request.created",
        {
            "requestId": request.id,
            "workspaceId": workspace_id,
            "sourceType": request.source_type.value,
            "sourceId": request.source_id,
            "createdBy": created_by,
        },
    )
    return request, True


def list_approval_requests(db: Session, workspace_id: str) -> list[models.ApprovalRequest]:
    return (
        db.query(models.ApprovalRequest)
        .filter_by(workspace_id=workspace_id)
        .order_by(models.ApprovalRequest.created_at.desc())
        .all()
    )


def get_approval_request(
    db: Session, workspace_id: str, request_id: str
) -> models.ApprovalRequest | None:
    return (
        db.query(models.ApprovalRequest)
        .filter_by(workspace_id=workspace_id, id=request_id)
        .first()
    )


def record_decision(
    db: Session,
    request: models.ApprovalRequest,
    action: models.DecisionAction,
    actor_user_id: str,
    comment: str | None,
    reason: str | None,
) -> models.ApprovalRequest:
    _STATUS_MAP = {
        models.DecisionAction.approve: models.RequestStatus.approved,
        models.DecisionAction.reject: models.RequestStatus.rejected,
        models.DecisionAction.cancel: models.RequestStatus.cancelled,
    }
    request.status = _STATUS_MAP[action]

    decision = models.ApprovalDecision(
        request_id=request.id,
        action=action,
        actor_user_id=actor_user_id,
        comment=comment,
        reason=reason,
    )
    db.add(decision)
    db.commit()
    db.refresh(request)

    publish_event(
        f"approval_request.{action.value}d",
        {
            "requestId": request.id,
            "workspaceId": request.workspace_id,
            "actorUserId": actor_user_id,
        },
    )
    return request
