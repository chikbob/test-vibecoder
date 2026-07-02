from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    PUBLICATION = "publication"
    SCENARIO = "scenario"
    EDIT = "edit"
    EXTERNAL = "external"


class ApprovalRequestCreate(BaseModel):
    source_type: SourceType = Field(alias="sourceType")
    source_id: str = Field(alias="sourceId", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    reviewer_user_ids: list[str] = Field(alias="reviewerUserIds", min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class ApprovalDecisionApprove(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=5000)


class ApprovalDecisionReject(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)


class ApprovalDecisionCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)


class ApprovalRequestResponse(BaseModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    source_type: str = Field(alias="sourceType")
    source_id: str = Field(alias="sourceId")
    title: str
    description: Optional[str]
    reviewer_user_ids: list[str] = Field(alias="reviewerUserIds")
    status: str
    created_by_user_id: str = Field(alias="createdByUserId")
    decision_by_user_id: Optional[str] = Field(alias="decisionByUserId")
    decision_comment: Optional[str] = Field(alias="decisionComment")
    decision_reason: Optional[str] = Field(alias="decisionReason")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ApprovalRequestListResponse(BaseModel):
    items: list[ApprovalRequestResponse]
