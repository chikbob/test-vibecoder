from __future__ import annotations

import hashlib
import json
from typing import Optional

from fastapi import Body, Header, HTTPException, Request, status

from app.schemas.auth import AuthContext


def get_auth_context(
    workspace_id: str,
    x_auth_workspace_id: Optional[str] = Header(default=None),
    x_auth_user_id: Optional[str] = Header(default=None),
    x_auth_actions: Optional[str] = Header(default=None),
) -> AuthContext:
    if not x_auth_workspace_id or not x_auth_user_id or not x_auth_actions:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth headers")

    if x_auth_workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace mismatch")

    actions = {item.strip() for item in x_auth_actions.split(",") if item.strip()}
    return AuthContext(workspace_id=workspace_id, user_id=x_auth_user_id, actions=actions)


def require_action(auth: AuthContext, action: str) -> None:
    if action not in auth.actions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing action: {action}")


async def get_idempotency_payload(request: Request) -> tuple[Optional[str], str]:
    key = request.headers.get("Idempotency-Key")
    body = await request.body()
    request_hash = hashlib.sha256(body or b"{}").hexdigest()
    return key, request_hash


def sanitize_payload(payload: dict) -> dict:
    # Public contract for this task intentionally excludes secrets and provider data.
    return json.loads(json.dumps(payload))
