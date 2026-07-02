from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.approval_request import IdempotencyRecord


class IdempotencyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_existing(self, workspace_id: str, operation: str, key: str) -> Optional[IdempotencyRecord]:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.workspace_id == workspace_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == key,
        )
        return self.db.scalar(stmt)

    def ensure_reusable(self, record: IdempotencyRecord, request_hash: str) -> None:
        if record.request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used with a different payload",
            )

    def save(self, workspace_id: str, operation: str, key: str, request_hash: str, status_code: int, response_body: dict) -> None:
        record = IdempotencyRecord(
            workspace_id=workspace_id,
            operation=operation,
            idempotency_key=key,
            request_hash=request_hash,
            response_status_code=status_code,
            response_body=response_body,
        )
        self.db.add(record)
        try:
            self.db.flush()
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate idempotency record") from exc
