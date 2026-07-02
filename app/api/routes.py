from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_auth_context, get_idempotency_payload, require_action
from app.db.session import get_db
from app.schemas.approval_requests import (
    ApprovalDecisionApprove,
    ApprovalDecisionCancel,
    ApprovalDecisionReject,
    ApprovalRequestCreate,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
)
from app.schemas.auth import AuthContext
from app.services.approval_requests import ApprovalRequestService
from app.services.idempotency import IdempotencyService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/approval-requests", tags=["approval-requests"])


def _reuse_idempotency_response(record, response: Response):
    response.status_code = record.response_status_code
    return record.response_body


@router.post("", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_approval_request(
    workspace_id: str,
    payload: ApprovalRequestCreate,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
    idem_data: tuple[Optional[str], str] = Depends(get_idempotency_payload),
):
    require_action(auth, "approval:create")
    idem_key, request_hash = idem_data
    operation = "create_approval_request"
    idem_service = IdempotencyService(db)
    if idem_key:
        existing = idem_service.get_existing(workspace_id, operation, idem_key)
        if existing:
            idem_service.ensure_reusable(existing, request_hash)
            return _reuse_idempotency_response(existing, response)

    service = ApprovalRequestService(db)
    approval_request = service.create_request(workspace_id, auth, payload)
    body = ApprovalRequestResponse.model_validate(approval_request).model_dump(mode="json", by_alias=True)
    if idem_key:
        idem_service.save(workspace_id, operation, idem_key, request_hash, status.HTTP_201_CREATED, body)
    db.commit()
    db.refresh(approval_request)
    response.status_code = status.HTTP_201_CREATED
    return body


@router.get("", response_model=ApprovalRequestListResponse)
def list_approval_requests(
    workspace_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_action(auth, "approval:read")
    service = ApprovalRequestService(db)
    items = service.list_requests(workspace_id)
    return ApprovalRequestListResponse(
        items=[ApprovalRequestResponse.model_validate(item) for item in items],
    )


@router.get("/{request_id}", response_model=ApprovalRequestResponse)
def get_approval_request(
    workspace_id: str,
    request_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    require_action(auth, "approval:read")
    service = ApprovalRequestService(db)
    item = service.get_request(workspace_id, request_id)
    return ApprovalRequestResponse.model_validate(item)


async def _decide(
    workspace_id: str,
    request_id: str,
    auth: AuthContext,
    db: Session,
    idem_data: tuple[Optional[str], str],
    operation: str,
    perform: Callable[[ApprovalRequestService], object],
    success_status: int = status.HTTP_200_OK,
):
    idem_key, request_hash = idem_data
    idem_service = IdempotencyService(db)
    if idem_key:
        existing = idem_service.get_existing(workspace_id, operation, idem_key)
        if existing:
            idem_service.ensure_reusable(existing, request_hash)
            return existing.response_body

    service = ApprovalRequestService(db)
    approval_request = perform(service)
    body = ApprovalRequestResponse.model_validate(approval_request).model_dump(mode="json", by_alias=True)
    if idem_key:
        idem_service.save(workspace_id, operation, idem_key, request_hash, success_status, body)
    db.commit()
    db.refresh(approval_request)
    return body


@router.post("/{request_id}/approve", response_model=ApprovalRequestResponse)
async def approve_approval_request(
    workspace_id: str,
    request_id: str,
    payload: ApprovalDecisionApprove,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
    idem_data: tuple[Optional[str], str] = Depends(get_idempotency_payload),
):
    require_action(auth, "approval:decide")
    return await _decide(
        workspace_id,
        request_id,
        auth,
        db,
        idem_data,
        "approve_approval_request",
        lambda service: service.approve(workspace_id, request_id, auth, payload.comment),
    )


@router.post("/{request_id}/reject", response_model=ApprovalRequestResponse)
async def reject_approval_request(
    workspace_id: str,
    request_id: str,
    payload: ApprovalDecisionReject,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
    idem_data: tuple[Optional[str], str] = Depends(get_idempotency_payload),
):
    require_action(auth, "approval:decide")
    return await _decide(
        workspace_id,
        request_id,
        auth,
        db,
        idem_data,
        "reject_approval_request",
        lambda service: service.reject(workspace_id, request_id, auth, payload.reason),
    )


@router.post("/{request_id}/cancel", response_model=ApprovalRequestResponse)
async def cancel_approval_request(
    workspace_id: str,
    request_id: str,
    payload: ApprovalDecisionCancel,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
    idem_data: tuple[Optional[str], str] = Depends(get_idempotency_payload),
):
    require_action(auth, "approval:cancel")
    return await _decide(
        workspace_id,
        request_id,
        auth,
        db,
        idem_data,
        "cancel_approval_request",
        lambda service: service.cancel(workspace_id, request_id, auth, payload.reason),
    )
