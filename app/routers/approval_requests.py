from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.dependencies import AuthContext, get_auth, get_db

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/approval-requests",
    tags=["approval-requests"],
)


def _decision_out(request: models.ApprovalRequest) -> Optional[schemas.DecisionOut]:
    if not request.decisions:
        return None
    last = request.decisions[-1]
    return schemas.DecisionOut(
        action=last.action,
        actorUserId=last.actor_user_id,
        comment=last.comment,
        reason=last.reason,
        decidedAt=last.created_at,
    )


def _to_out(request: models.ApprovalRequest) -> schemas.ApprovalRequestOut:
    return schemas.ApprovalRequestOut(
        id=request.id,
        workspaceId=request.workspace_id,
        sourceType=request.source_type,
        sourceId=request.source_id,
        title=request.title,
        description=request.description,
        reviewerUserIds=request.reviewer_user_ids,
        status=request.status,
        createdBy=request.created_by,
        createdAt=request.created_at,
        updatedAt=request.updated_at,
        decision=_decision_out(request),
    )


def _get_or_404(db: Session, workspace_id: str, request_id: str) -> models.ApprovalRequest:
    req = crud.get_approval_request(db, workspace_id, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    return req


def _assert_not_final(req: models.ApprovalRequest) -> None:
    if req.status in models.FINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request is already in a final state: {req.status.value}",
        )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.ApprovalRequestOut)
def create_request(
    workspace_id: str,
    body: schemas.ApprovalRequestCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    auth.require("approval:create")
    req, created = crud.create_approval_request(
        db=db,
        workspace_id=workspace_id,
        data=body,
        created_by=auth.user_id,
        idempotency_key=idempotency_key,
    )
    out = _to_out(req)
    if not created:
        return JSONResponse(content=out.model_dump(mode="json"), status_code=status.HTTP_200_OK)
    return out


@router.get("", response_model=list[schemas.ApprovalRequestOut])
def list_requests(
    workspace_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
):
    auth.require("approval:read")
    return [_to_out(r) for r in crud.list_approval_requests(db, workspace_id)]


@router.get("/{request_id}", response_model=schemas.ApprovalRequestOut)
def get_request(
    workspace_id: str,
    request_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
):
    auth.require("approval:read")
    return _to_out(_get_or_404(db, workspace_id, request_id))


@router.post("/{request_id}/approve", response_model=schemas.ApprovalRequestOut)
def approve_request(
    workspace_id: str,
    request_id: str,
    body: schemas.ApproveBody,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
):
    auth.require("approval:decide")
    req = _get_or_404(db, workspace_id, request_id)
    _assert_not_final(req)
    return _to_out(
        crud.record_decision(db, req, models.DecisionAction.approve, auth.user_id, body.comment, None)
    )


@router.post("/{request_id}/reject", response_model=schemas.ApprovalRequestOut)
def reject_request(
    workspace_id: str,
    request_id: str,
    body: schemas.RejectBody,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
):
    auth.require("approval:decide")
    req = _get_or_404(db, workspace_id, request_id)
    _assert_not_final(req)
    return _to_out(
        crud.record_decision(db, req, models.DecisionAction.reject, auth.user_id, None, body.reason)
    )


@router.post("/{request_id}/cancel", response_model=schemas.ApprovalRequestOut)
def cancel_request(
    workspace_id: str,
    request_id: str,
    body: schemas.CancelBody,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
):
    auth.require("approval:cancel")
    req = _get_or_404(db, workspace_id, request_id)
    _assert_not_final(req)
    return _to_out(
        crud.record_decision(db, req, models.DecisionAction.cancel, auth.user_id, None, body.reason)
    )
