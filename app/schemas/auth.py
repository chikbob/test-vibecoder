from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    workspace_id: str
    user_id: str
    actions: set[str]
