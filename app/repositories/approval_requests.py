from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval_request import ApprovalRequest


class ApprovalRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, approval_request: ApprovalRequest) -> ApprovalRequest:
        self.db.add(approval_request)
        self.db.flush()
        return approval_request

    def list_by_workspace(self, workspace_id: str) -> list[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.workspace_id == workspace_id)
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def get_by_workspace(self, workspace_id: str, request_id: str) -> Optional[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.workspace_id == workspace_id,
            ApprovalRequest.id == request_id,
        )
        return self.db.scalar(stmt)
