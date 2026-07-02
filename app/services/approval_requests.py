from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import sanitize_payload
from app.models.approval_request import ApprovalRequest, ApprovalRequestEvent, ApprovalStatus, OutboxEvent
from app.repositories.approval_requests import ApprovalRequestRepository
from app.schemas.approval_requests import ApprovalRequestCreate
from app.schemas.auth import AuthContext


FINAL_STATUSES = {
    ApprovalStatus.APPROVED.value,
    ApprovalStatus.REJECTED.value,
    ApprovalStatus.CANCELED.value,
}


class ApprovalRequestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ApprovalRequestRepository(db)

    def create_request(self, workspace_id: str, auth: AuthContext, data: ApprovalRequestCreate) -> ApprovalRequest:
        request = ApprovalRequest(
            workspace_id=workspace_id,
            source_type=data.source_type.value,
            source_id=data.source_id,
            title=data.title,
            description=data.description,
            reviewer_user_ids=data.reviewer_user_ids,
            status=ApprovalStatus.PENDING.value,
            created_by_user_id=auth.user_id,
        )
        self.repository.create(request)
        self._add_event(
            request=request,
            event_type="approval_request.created",
            actor_user_id=auth.user_id,
            payload={
                "sourceType": data.source_type.value,
                "sourceId": data.source_id,
                "title": data.title,
                "reviewerUserIds": data.reviewer_user_ids,
            },
        )
        return request

    def list_requests(self, workspace_id: str) -> list[ApprovalRequest]:
        return self.repository.list_by_workspace(workspace_id)

    def get_request(self, workspace_id: str, request_id: str) -> ApprovalRequest:
        request = self.repository.get_by_workspace(workspace_id, request_id)
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
        return request

    def approve(self, workspace_id: str, request_id: str, auth: AuthContext, comment: Optional[str]) -> ApprovalRequest:
        request = self.get_request(workspace_id, request_id)
        self._ensure_pending(request)
        request.status = ApprovalStatus.APPROVED.value
        request.decision_by_user_id = auth.user_id
        request.decision_comment = comment
        request.decision_reason = None
        self.db.flush()
        self._add_event(
            request=request,
            event_type="approval_request.approved",
            actor_user_id=auth.user_id,
            payload={"comment": comment},
        )
        return request

    def reject(self, workspace_id: str, request_id: str, auth: AuthContext, reason: str) -> ApprovalRequest:
        request = self.get_request(workspace_id, request_id)
        self._ensure_pending(request)
        request.status = ApprovalStatus.REJECTED.value
        request.decision_by_user_id = auth.user_id
        request.decision_reason = reason
        request.decision_comment = None
        self.db.flush()
        self._add_event(
            request=request,
            event_type="approval_request.rejected",
            actor_user_id=auth.user_id,
            payload={"reason": reason},
        )
        return request

    def cancel(self, workspace_id: str, request_id: str, auth: AuthContext, reason: str) -> ApprovalRequest:
        request = self.get_request(workspace_id, request_id)
        self._ensure_pending(request)
        request.status = ApprovalStatus.CANCELED.value
        request.decision_by_user_id = auth.user_id
        request.decision_reason = reason
        request.decision_comment = None
        self.db.flush()
        self._add_event(
            request=request,
            event_type="approval_request.canceled",
            actor_user_id=auth.user_id,
            payload={"reason": reason},
        )
        return request

    def _ensure_pending(self, request: ApprovalRequest) -> None:
        if request.status in FINAL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval request is already in final status: {request.status}",
            )

    def _add_event(self, request: ApprovalRequest, event_type: str, actor_user_id: str, payload: dict) -> None:
        safe_payload = sanitize_payload(payload)
        self.db.add(
            ApprovalRequestEvent(
                approval_request_id=request.id,
                workspace_id=request.workspace_id,
                event_type=event_type,
                actor_user_id=actor_user_id,
                payload=safe_payload,
            )
        )
        self.db.add(
            OutboxEvent(
                topic="approval-requests",
                aggregate_type="approval_request",
                aggregate_id=request.id,
                workspace_id=request.workspace_id,
                payload={
                    "eventType": event_type,
                    "requestId": request.id,
                    "workspaceId": request.workspace_id,
                    "actorUserId": actor_user_id,
                    "payload": safe_payload,
                },
            )
        )
        self.db.flush()
